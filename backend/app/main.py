"""API da Central de Operações. Rodar: `uvicorn app.main:app --reload` dentro de backend/."""

from __future__ import annotations

import math
import os
import tempfile
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.agent import service as agent
from app.agent.local import briefing as briefing_text
from app.alerts import detect_alerts
from app.config import Settings, get_settings
from app.filters import Filters
from app.repository import Repository
from app.routing import route_alerts
from app.schemas import (
    AlertRoute,
    AlertsResponse,
    BreakdownResponse,
    BriefingResponse,
    ChatRequest,
    ChatResponse,
    Dimension,
    Grain,
    Health,
    HeatCell,
    KpiResponse,
    Meta,
    OrdersPage,
    SortKey,
    TimePoint,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.repo = Repository(settings.data_path, settings.sla_food_min, settings.sla_good_min)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Central de Operações — API",
        version="2.0.0",
        description="KPIs, quebras, alertas e agente sobre o recorte filtrado do Delivery Center.",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > 64 * 1024:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": "Corpo da requisição excede o limite de 64 KB."},
                        )
                except ValueError:
                    pass
        return await call_next(request)

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):
        response = await call_next(request)
        # Dados estáticos: GETs analíticos podem ficar 10 min no cache do navegador/CDN.
        if request.method == "GET" and response.status_code == 200 and request.url.path not in ("/api/health",):
            response.headers.setdefault("Cache-Control", "public, max-age=600")
        return response

    register_routes(app)
    return app


class SlidingWindowLimiter:
    """Rate limiter em memória por cliente com janela deslizante (thread-safe e memória limitada)."""

    def __init__(self, window_s: float = 60.0, max_clients: int = 10_000):
        self.window_s = window_s
        self.max_clients = max_clients
        self._lock = threading.Lock()
        self._clients: dict[str, deque[float]] = {}

    def reset(self) -> None:
        with self._lock:
            self._clients.clear()

    def check(self, key: str, limit: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_s
        with self._lock:
            if len(self._clients) > self.max_clients:
                self._prune_expired(cutoff)
                if len(self._clients) > self.max_clients:
                    to_remove = list(self._clients.keys())[:len(self._clients) - self.max_clients]
                    for k in to_remove:
                        self._clients.pop(k, None)

            dq = self._clients.setdefault(key, deque())
            while dq and dq[0] <= cutoff:
                dq.popleft()

            if len(dq) >= limit:
                wait_s = max(1, math.ceil(dq[0] + self.window_s - now))
                return False, int(wait_s)

            dq.append(now)
            return True, 0

    def _prune_expired(self, cutoff: float) -> None:
        empty = [k for k, dq in self._clients.items() if not dq or dq[-1] <= cutoff]
        for k in empty:
            self._clients.pop(k, None)


chat_limiter = SlidingWindowLimiter()


def get_client_ip(request: Request) -> str:
    # O último IP é o que o proxy do Render acrescentou; os anteriores vêm do cliente e podem ser forjados.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[-1].strip()
        if ip:
            return ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def llm_allowed(request: Request, settings: Settings) -> bool:
    """Cota de chamadas ao LLM por cliente. Estourou: a pergunta vai para o agente local, sem erro."""
    if not settings.llm_enabled:
        return False
    if not settings.chat_rate_limit_enabled or settings.chat_rate_limit_per_minute <= 0:
        return True
    allowed, _ = chat_limiter.check(get_client_ip(request), settings.chat_rate_limit_per_minute)
    return allowed


def repo_dep(request: Request) -> Repository:
    return request.app.state.repo


Repo = Annotated[Repository, Depends(repo_dep)]
F = Annotated[Filters, Query()]


def register_routes(app: FastAPI) -> None:
    @app.get("/api/health", response_model=Health, tags=["infra"])
    def health(repo: Repo):
        return {"status": "ok", "orders": repo.total_orders}

    @app.get("/api/meta", response_model=Meta, tags=["recorte"])
    def meta(repo: Repo, settings: Annotated[Settings, Depends(get_settings)]):
        return {**repo.meta(), "llm_enabled": settings.llm_enabled,
                "llm_model": settings.openrouter_model if settings.llm_enabled else None}

    @app.get("/api/kpis", response_model=KpiResponse, tags=["analytics"])
    def kpis(repo: Repo, f: F):
        start, end = repo.period(f)
        prev = repo.previous_period(f)
        return {
            "period": {"start": start, "end": end},
            "current": repo.metrics(f),
            "previous_period": {"start": prev[0], "end": prev[1]} if prev else None,
            "previous": repo.metrics(f.with_period(*prev)) if prev else None,
        }

    @app.get("/api/timeseries", response_model=list[TimePoint], tags=["analytics"])
    def timeseries(repo: Repo, f: F, grain: Grain = "day"):
        return repo.timeseries(f, grain)

    @app.get("/api/heatmap", response_model=list[HeatCell], tags=["analytics"])
    def heatmap(repo: Repo, f: F):
        return repo.heatmap(f)

    @app.get("/api/breakdown", response_model=BreakdownResponse, tags=["analytics"])
    def breakdown(
        repo: Repo,
        f: F,
        by: Dimension = "hub",
        sort: SortKey = "orders",
        desc: bool = True,
        limit: Annotated[int, Query(ge=1, le=1000)] = 50,
        min_orders: Annotated[int, Query(ge=0)] = 0,
    ):
        return {"by": by, "rows": repo.breakdown(f, by, sort, desc, limit, min_orders)}

    @app.get("/api/alerts", response_model=AlertsResponse, tags=["insights"])
    def alerts(repo: Repo, f: F):
        return {"alerts": detect_alerts(repo, f), "orders": repo.metrics(f)["orders"]}

    @app.get("/api/briefing", response_model=BriefingResponse, tags=["automacao"])
    def briefing(repo: Repo, f: F):
        alerts_now = detect_alerts(repo, f)
        start, end = repo.covered_period(f)
        return {
            "markdown": briefing_text(repo, f),
            "start": start,
            "end": end,
            "alert_count": len(alerts_now),
        }

    @app.get("/api/alerts/routing", response_model=list[AlertRoute], tags=["automacao"])
    def alert_routing(repo: Repo, f: F):
        meta = repo.meta()
        hub_names = {int(h["value"]): h["label"] for h in meta["hubs"]}
        store_names = {int(s["value"]): s["label"] for s in meta["stores"]}
        return route_alerts(detect_alerts(repo, f), hub_names, store_names)

    @app.get("/api/orders", response_model=OrdersPage, tags=["pedidos"])
    def orders(
        repo: Repo,
        f: F,
        offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        sort: str = "created_at",
        desc: bool = True,
    ):
        return repo.orders_page(f, offset, limit, sort, desc)

    @app.get("/api/orders.csv", tags=["pedidos"], response_class=FileResponse)
    def export_orders(repo: Repo, f: F, background: BackgroundTasks):
        fd, tmp = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        path = Path(tmp)
        repo.export_csv(f, path)
        background.add_task(path.unlink, missing_ok=True)
        return FileResponse(path, media_type="text/csv", filename="pedidos-recorte.csv",
                            headers={"Cache-Control": "no-store"})

    @app.post("/api/agent/chat", response_model=ChatResponse, tags=["insights"])
    def chat(
        req: ChatRequest,
        repo: Repo,
        settings: Annotated[Settings, Depends(get_settings)],
        request: Request,
    ):
        return agent.chat(req, repo, settings, use_llm=llm_allowed(request, settings))


app = create_app()
