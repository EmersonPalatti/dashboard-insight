"""API da Central de Operações. Rodar: `uvicorn app.main:app --reload` dentro de backend/."""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from app.agent import service as agent
from app.alerts import detect_alerts
from app.config import Settings, get_settings
from app.filters import Filters
from app.repository import Repository
from app.schemas import (
    AlertsResponse, BreakdownResponse, ChatRequest, ChatResponse, Dimension, Grain, HeatCell, Health,
    KpiResponse, Meta, OrdersPage, SortKey, TimePoint,
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
    async def cache_headers(request: Request, call_next):
        response = await call_next(request)
        # Dados estáticos: GETs analíticos podem ficar 10 min no cache do navegador/CDN.
        if request.method == "GET" and response.status_code == 200 and request.url.path not in ("/api/health",):
            response.headers.setdefault("Cache-Control", "public, max-age=600")
        return response

    register_routes(app)
    return app


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

    @app.get("/api/orders", response_model=OrdersPage, tags=["pedidos"])
    def orders(
        repo: Repo,
        f: F,
        offset: Annotated[int, Query(ge=0)] = 0,
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
    def chat(req: ChatRequest, repo: Repo, settings: Annotated[Settings, Depends(get_settings)]):
        return agent.chat(req, repo, settings)


app = create_app()
