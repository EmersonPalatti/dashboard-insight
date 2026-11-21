"""API da Central de Operações. Rodar: `uvicorn app.main:app --reload` dentro de backend/."""

from __future__ import annotations

import hmac
import json
import math
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Iterator
from contextlib import ExitStack, asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent import service as agent
from app.agent.local import briefing as briefing_text
from app.alerts import detect_alerts, empty_reason, hero_readings
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
    OrderSort,
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

        body, status = await _read_body(receive, self.max_bytes)
        if status == "disconnected":
            return
        if status == "too_big":
            await _send_json(send, 413, _BODY_TOO_BIG)
            return

        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return await receive()
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
    if len(raws) != 1 or not (raw.isascii() and raw.isdigit()):
        return "bad"
    # Mais de 8 dígitos já passa de 64 KB. Evita int() num header enorme.
    if len(raw) > 8:
        return MAX_BODY_BYTES + 1
    return int(raw)


async def _read_body(receive, max_bytes: int) -> tuple[bytes, str]:
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b"", "disconnected"
        if message["type"] != "http.request":
            continue
        piece = message.get("body", b"") or b""
        total += len(piece)
        if total > max_bytes:
            return b"", "too_big"
        if piece:
            chunks.append(piece)
        if not message.get("more_body", False):
            break
    return b"".join(chunks), "ok"


_PUBLIC_CACHE_PATHS = frozenset({
    "/api/meta",
    "/api/kpis",
    "/api/timeseries",
    "/api/heatmap",
    "/api/breakdown",
    "/api/alerts",
    "/api/orders",
})
_PRIVATE_NO_STORE_PATHS = frozenset({
    "/api/briefing",
    "/api/alerts/routing",
})


class CacheControlMiddleware:
    """Middleware ASGI puro para Cache-Control (sem BaseHTTPMiddleware, compatível com streaming)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "GET":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _PUBLIC_CACHE_PATHS:
            header_value = b"public, max-age=600"
            only_200 = True
        elif path in _PRIVATE_NO_STORE_PATHS:
            header_value = b"private, no-store"
            only_200 = False
        elif path == "/api/health":
            header_value = b"no-store"
            only_200 = False
        else:
            await self.app(scope, receive, send)
            return

        async def send_with_cache(message):
            if message["type"] == "http.response.start" and (not only_200 or message["status"] == 200):
                headers = list(message.get("headers", []))
                if not any(k.lower() == b"cache-control" for k, _ in headers):
                    headers.append((b"cache-control", header_value))
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repo = Repository(settings.data_path, settings.sla_food_min, settings.sla_good_min)
    app.state.repo = repo
    try:
        yield
    finally:
        repo.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Central de Operações — API",
        version="2.0.0",
        description="KPIs, quebras, alertas e agente sobre o recorte filtrado do Delivery Center.",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(CacheControlMiddleware)
    # Dentro do CORS, para o 413/400 sair com o header de origem.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    register_routes(app)
    return app


class SlidingWindowLimiter:
    """Rate limiter em memória por cliente com janela deslizante (thread-safe e memória limitada)."""

    def __init__(self, window_s: float = 60.0, max_clients: int = 10_000):
        self.window_s = window_s
        self.max_clients = max_clients
        self._lock = threading.Lock()
        self._clients: OrderedDict[str, deque[float]] = OrderedDict()

    def reset(self) -> None:
        with self._lock:
            self._clients.clear()

    def _check_unlocked(self, key: str, limit: int, now: float) -> tuple[bool, int]:
        cutoff = now - self.window_s
        dq = self._clients.get(key)
        if dq is not None:
            self._clients.move_to_end(key)
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= limit:
                wait_s = max(1, math.ceil(dq[0] + self.window_s - now)) if dq else 1
                return False, int(wait_s)
        elif limit <= 0:
            return False, 1
        return True, 0

    def _record_unlocked(self, key: str, now: float) -> None:
        cutoff = now - self.window_s
        dq = self._clients.get(key)
        if dq is None:
            if len(self._clients) >= self.max_clients:
                self._prune_expired(cutoff)
                while self._clients and len(self._clients) >= self.max_clients:
                    self._clients.popitem(last=False)
            dq = deque()
            self._clients[key] = dq
        else:
            self._clients.move_to_end(key)
        dq.append(now)

    def check(self, key: str, limit: int) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            allowed, wait_s = self._check_unlocked(key, limit, now)
            if not allowed:
                return False, wait_s
            self._record_unlocked(key, now)
            return True, 0

    @staticmethod
    def check_all(checks: list[tuple[SlidingWindowLimiter, str, int]]) -> bool:
        """Verifica todos os limitadores atomicamente; só registra hit se todos aprovarem."""
        if not checks:
            return True
        now = time.monotonic()
        unique = sorted({id(lim): lim for lim, _, _ in checks}.values(), key=id)
        with ExitStack() as stack:
            for lim in unique:
                stack.enter_context(lim._lock)
            for lim, key, limit in checks:
                if not lim._check_unlocked(key, limit, now)[0]:
                    return False
            for lim, key, _ in checks:
                lim._record_unlocked(key, now)
            return True

    def _prune_expired(self, cutoff: float) -> None:
        empty = [k for k, dq in self._clients.items() if not dq or dq[-1] <= cutoff]
        for k in empty:
            self._clients.pop(k, None)


chat_limiter = SlidingWindowLimiter()
chat_global_limiter = SlidingWindowLimiter()
export_limiter = SlidingWindowLimiter()
_csv_export_sem = threading.BoundedSemaphore(2)
_MAX_IP_LEN = 64


class _GuardedStreamingResponse(StreamingResponse):
    """StreamingResponse que libera semáforo e fecha o cursor mesmo se o cliente desconectar."""

    def __init__(self, raw: Iterator[str], sem: threading.BoundedSemaphore, **kwargs):
        self._raw = raw
        self._sem = sem
        self._lock = threading.Lock()
        # Só passa a ser dono do semáforo depois do __init__: se ele falhar, quem libera é a rota.
        self._released = True
        self._aborted = False
        super().__init__(self._iter(), **kwargs)
        self._released = False

    def _release(self) -> None:
        with self._lock:
            if not self._released:
                self._released = True
                self._sem.release()

    def _close_raw(self) -> bool:
        """Fecha o gerador; retorna False se ele estiver em execução em outra thread."""
        close = getattr(self._raw, "close", None)
        if not callable(close):
            return True
        try:
            close()
        except ValueError:
            return False
        return True

    def _iter(self) -> Iterator[str]:
        try:
            for chunk in self._raw:
                if self._aborted:
                    break
                yield chunk
        finally:
            try:
                self._close_raw()
            finally:
                self._release()

    async def __call__(self, scope, receive, send) -> None:
        # Cliente que cai antes dos headers, no meio do corpo ou com o gerador nem iniciado: o finally
        # fecha o cursor e devolve a vaga. Se um next() ainda roda no threadpool, o finally do _iter
        # faz isso quando ele voltar.
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._aborted = True
            in_flight = False
            try:
                in_flight = not self._close_raw()
            finally:
                if not in_flight:
                    self._release()

    def __del__(self) -> None:
        if getattr(self, "_released", True):
            return
        self._aborted = True
        in_flight = False
        try:
            in_flight = not self._close_raw()
        except Exception:  # noqa: BLE001, S110 — destrutor nunca deve propagar erro
            pass
        finally:
            if not in_flight:
                self._release()


def get_client_ip(request: Request, settings: Settings | None = None) -> str:
    """IP do cliente para a cota.

    Com `client_ip_header` (ex.: `cf-connecting-ip` na borda Cloudflare do Render), esse header vale
    quando vem preenchido; `x-forwarded-for` é ignorado aqui para manter a leitura pelo último hop.
    Sem ele, vale o último hop de X-Forwarded-For (o que o proxy acrescenta; os anteriores podem ser forjados).
    """
    settings = settings or get_settings()
    trusted = (settings.client_ip_header or "").strip()
    if trusted and trusted.lower() != "x-forwarded-for":
        raw = request.headers.get(trusted)
        if raw:
            first = raw.split(",")[0].strip()
            if first:
                return first[:_MAX_IP_LEN]
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[-1].strip()
        if ip:
            return ip[:_MAX_IP_LEN]
    if request.client and request.client.host:
        return request.client.host[:_MAX_IP_LEN]
    return "127.0.0.1"


def llm_allowed(request: Request, settings: Settings) -> bool:
    """Cota de chamadas ao LLM. Estourou (por IP ou no teto global): a pergunta vai para o agente local."""
    if not settings.llm_enabled:
        return False
    if not settings.chat_rate_limit_enabled:
        return True
    ip_limit = settings.chat_rate_limit_per_minute
    global_limit = settings.chat_global_rate_limit_per_minute
    checks: list[tuple[SlidingWindowLimiter, str, int]] = []
    if ip_limit > 0:
        checks.append((chat_limiter, get_client_ip(request, settings), ip_limit))
    if global_limit > 0:
        checks.append((chat_global_limiter, "global", global_limit))
    return SlidingWindowLimiter.check_all(checks)


def _header_bytes(value: str | None) -> bytes:
    if not value:
        return b""
    try:
        return value.encode("latin-1")
    except UnicodeEncodeError:
        return value.encode("utf-8")


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
    # Compara bytes: str com acento no compare_digest levanta TypeError (500). O Starlette decodifica
    # o header em latin-1, então encode("latin-1") devolve os bytes que vieram na rede (UTF-8 do cliente).
    if not hmac.compare_digest(_header_bytes(x_automation_token), expected.encode("utf-8")):
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
        orders = repo.metrics(f)["orders"]
        return {
            "alerts": detect_alerts(repo, f),
            "orders": orders,
            "empty_reason": empty_reason(repo, f, orders=orders),
        }

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
        sort: Annotated[
            OrderSort,
            Query(description="Coluna de ordenação dos pedidos."),
        ] = "created_at",
        desc: bool = True,
    ):
        return repo.orders_page(f, offset, limit, sort, desc)

    @app.get("/api/orders.csv", tags=["pedidos"], response_class=StreamingResponse)
    def export_orders(
        repo: Repo,
        f: F,
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
        if not _csv_export_sem.acquire(blocking=False):
            return JSONResponse(
                status_code=429,
                content={"detail": "Muitas exportações simultâneas. Tente novamente em instantes."},
            )
        raw: Iterator[str] | None = None
        try:
            raw = repo.iter_orders_csv(f)
            return _GuardedStreamingResponse(
                raw,
                _csv_export_sem,
                media_type="text/csv",
                headers={
                    "Content-Disposition": 'attachment; filename="pedidos-recorte.csv"',
                    "Cache-Control": "no-store",
                },
            )
        except BaseException:
            if raw is not None:
                close = getattr(raw, "close", None)
                if callable(close):
                    close()
            _csv_export_sem.release()
            raise

    @app.post("/api/agent/chat", response_model=ChatResponse, tags=["insights"])
    def chat(
        req: ChatRequest,
        repo: Repo,
        settings: Annotated[Settings, Depends(get_settings)],
        request: Request,
    ):
        # engine=local, recorte vazio ou disjuntor de cota aberto não gastam o limitador.
        has_orders = repo.metrics(req.filters)["orders"] > 0
        use_llm = (
            req.engine != "local"
            and has_orders
            and (agent.quota_breaker.is_open() or llm_allowed(request, settings))
        )
        return agent.chat(req, repo, settings, use_llm=use_llm)


app = create_app()
