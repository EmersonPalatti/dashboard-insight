"""API da Central de Operações. Rodar: `uvicorn app.main:app --reload` dentro de backend/."""

from __future__ import annotations

import hmac
import json
import math
import os
import tempfile
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.agent import service as agent
from app.agent.local import briefing as briefing_text
from app.alerts import detect_alerts, hero_readings
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

MAX_BODY_BYTES = 64 * 1024
_BODY_TOO_BIG = "Corpo da requisição excede o limite de 64 KB."
_BODY_BAD_LENGTH = "Content-Length inválido."
_MIN_ORDERS_MAX = 100_000


async def _send_json(send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}, ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class BodySizeLimitMiddleware:
    """Recusa POST acima de 64 KB contando os bytes do receive.

    Content-Length ausente, quebrado ou menor que o corpo não libera o pedido.
    """

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        declared = _declared_length(scope)
        if declared == "bad":
            await _send_json(send, 400, _BODY_BAD_LENGTH)
            return
        if isinstance(declared, int) and declared > self.max_bytes:
            await _send_json(send, 413, _BODY_TOO_BIG)
            return

        body, too_big = await _read_body(receive, self.max_bytes)
        if too_big:
            await _send_json(send, 413, _BODY_TOO_BIG)
            return

        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def _declared_length(scope) -> int | None | str:
    """Inteiro do Content-Length, None se o header não veio, ou 'bad' se estiver quebrado."""
    raws = [
        value.decode("latin-1").strip()
        for key, value in scope.get("headers", [])
        if key.lower() == b"content-length"
    ]
    if not raws:
        return None
    raw = raws[0]
    if len(raws) != 1 or not raw.isdigit():
        return "bad"
    # Mais de 8 dígitos já passa de 64 KB. Evita int() num header enorme.
    if len(raw) > 8:
        return MAX_BODY_BYTES + 1
    return int(raw)


async def _read_body(receive, max_bytes: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        piece = message.get("body", b"") or b""
        total += len(piece)
        if total > max_bytes:
            return b"", True
        if piece:
            chunks.append(piece)
        if not message.get("more_body", False):
            break
    return b"".join(chunks), False


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
    # Dentro do CORS, para o 413/400 sair com o header de origem.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

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
chat_global_limiter = SlidingWindowLimiter()
export_limiter = SlidingWindowLimiter()


def get_client_ip(request: Request, settings: Settings | None = None) -> str:
    """IP do cliente para a cota.

    Com `client_ip_header` (ex.: true-client-ip), esse header vale quando vem preenchido.
    Sem ele, o último hop de X-Forwarded-For: é o que o proxy acrescenta. Os anteriores podem ser forjados.
    """
    settings = settings or get_settings()
    trusted = (settings.client_ip_header or "").strip()
    if trusted:
        raw = request.headers.get(trusted)
        if raw and raw.split(",")[0].strip():
            return raw.split(",")[0].strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[-1].strip()
        if ip:
            return ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def llm_allowed(request: Request, settings: Settings) -> bool:
    """Cota de chamadas ao LLM. Estourou (por IP ou no teto global): a pergunta vai para o agente local."""
    if not settings.llm_enabled:
        return False
    if not settings.chat_rate_limit_enabled:
        return True
    ip_limit = settings.chat_rate_limit_per_minute
    global_limit = settings.chat_global_rate_limit_per_minute
    if ip_limit <= 0 and global_limit <= 0:
        return True
    if ip_limit > 0 and not chat_limiter.check(get_client_ip(request, settings), ip_limit)[0]:
        return False
    if global_limit <= 0:
        return True
    allowed, _ = chat_global_limiter.check("global", global_limit)
    return allowed


def require_automation(
    settings: Annotated[Settings, Depends(get_settings)],
    x_automation_token: Annotated[
        str | None,
        Header(description="Obrigatório só se AUTOMATION_TOKEN estiver definido no servidor."),
    ] = None,
) -> None:
    """Sem AUTOMATION_TOKEN o endpoint segue aberto. Com o token, o header tem que bater."""
    expected = settings.automation_token or ""
    if not expected:
        return
    provided = x_automation_token or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Token de automação inválido.")


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
                "llm_model": settings.openrouter_model if settings.llm_enabled else None,
                "csv_max_rows": settings.csv_export_max_rows}

    @app.get("/api/kpis", response_model=KpiResponse, tags=["analytics"])
    def kpis(repo: Repo, f: F):
        start, end = repo.period(f)
        prev = repo.previous_period(f)
        return {
            "period": {"start": start, "end": end},
            "current": repo.metrics(f),
            "previous_period": {"start": prev[0], "end": prev[1]} if prev else None,
            "previous": repo.metrics(f.with_period(*prev)) if prev else None,
            "heroes": hero_readings(repo, f),
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
        min_orders: Annotated[int, Query(ge=0, le=_MIN_ORDERS_MAX)] = 0,
    ):
        return {"by": by, "rows": repo.breakdown(f, by, sort, desc, limit, min_orders)}

    @app.get("/api/alerts", response_model=AlertsResponse, tags=["insights"])
    def alerts(repo: Repo, f: F):
        return {"alerts": detect_alerts(repo, f), "orders": repo.metrics(f)["orders"]}

    @app.get("/api/briefing", response_model=BriefingResponse, tags=["automacao"])
    def briefing(repo: Repo, f: F, _: Annotated[None, Depends(require_automation)]):
        alerts_now = detect_alerts(repo, f)
        start, end = repo.covered_period(f)
        return {
            "markdown": briefing_text(repo, f),
            "start": start,
            "end": end,
            "alert_count": len(alerts_now),
        }

    @app.get("/api/alerts/routing", response_model=list[AlertRoute], tags=["automacao"])
    def alert_routing(repo: Repo, f: F, _: Annotated[None, Depends(require_automation)]):
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
    def export_orders(
        repo: Repo,
        f: F,
        background: BackgroundTasks,
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ):
        per_minute = settings.csv_export_per_minute
        if per_minute > 0:
            allowed, wait_s = export_limiter.check(get_client_ip(request, settings), per_minute)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Muitas exportações em seguida. Espere um pouco e tente de novo."},
                    headers={"Retry-After": str(wait_s)},
                )
        orders = repo.metrics(f)["orders"]
        if orders > settings.csv_export_max_rows:
            cap = f"{settings.csv_export_max_rows:,}".replace(",", ".")
            found = f"{orders:,}".replace(",", ".")
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"O recorte tem {found} pedidos, acima do limite de {cap}. "
                        "Afine o filtro para exportar."
                    )
                },
            )
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
        # engine=local não passa no limitador: a cota é só da chamada ao modelo.
        use_llm = req.engine != "local" and llm_allowed(request, settings)
        return agent.chat(req, repo, settings, use_llm=use_llm)


app = create_app()
