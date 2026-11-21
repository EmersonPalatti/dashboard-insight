from __future__ import annotations

import contextlib
import gc
import inspect
import re
import threading
from typing import get_args

import anyio
import duckdb
import pytest

from app import main as main_mod
from app.config import Settings, get_settings
from app.filters import Filters
from app.main import BodySizeLimitMiddleware, create_app, export_limiter
from app.repository import HEATMAP_MIN_SAMPLE, MIN_MEASURED, ORDER_SORTS
from app.schemas import OrderSort


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["orders"] == 12000


def test_meta_lists_dynamic_options(client):
    meta = client.get("/api/meta").json()
    assert {c["value"] for c in meta["cities"]} == {"São Paulo", "Curitiba"}
    assert len(meta["hubs"]) == 4
    assert meta["llm_enabled"] is False
    assert meta["csv_max_rows"] == 50_000
    assert meta["heatmap_min_sample"] == HEATMAP_MIN_SAMPLE


def test_filters_change_every_kpi(client):
    full = client.get("/api/kpis").json()["current"]
    sp = client.get("/api/kpis", params={"city": "São Paulo"}).json()["current"]
    assert 0 < sp["orders"] < full["orders"]
    one_hub = client.get("/api/kpis", params=[("hub", 1)]).json()["current"]
    two_hubs = client.get("/api/kpis", params=[("hub", 1), ("hub", 2)]).json()["current"]
    assert one_hub["orders"] < two_hubs["orders"]


def test_previous_period_only_when_inside_data(client):
    r = client.get("/api/kpis", params={"start": "2021-03-01", "end": "2021-03-31"}).json()
    assert r["previous_period"] == {"start": "2021-01-29", "end": "2021-02-28"}
    assert r["previous"]["orders"] > 0
    r = client.get("/api/kpis").json()
    assert r["previous"] is None


def test_invalid_range_is_422(client):
    r = client.get("/api/kpis", params={"start": "2021-04-01", "end": "2021-03-01"})
    assert r.status_code == 422


def test_unknown_enum_is_422(client):
    assert client.get("/api/kpis", params={"segment": "pharma"}).status_code == 422


def test_sql_injection_is_just_a_value(client):
    r = client.get("/api/kpis", params={"city": "x') or 1=1 --"})
    assert r.status_code == 200
    assert r.json()["current"]["orders"] == 0


def test_stuck_orders_stay_out_of_medians(repo):
    stuck = repo.metrics(Filters(hub=[3]))
    assert stuck["stuck_rate"] > 0.4
    assert stuck["cycle_p50"] < 240


def test_breakdown_sort_and_min_orders(client):
    rows = client.get("/api/breakdown", params={"by": "hub", "sort": "sla_rate", "desc": "false"}).json()["rows"]
    assert rows[0]["label"] == "Hub Lento"
    rows = client.get("/api/breakdown", params={"by": "store", "min_orders": 100000}).json()["rows"]
    assert rows == []


def test_breakdown_flags_outliers_against_recorte(client):
    rows = client.get("/api/breakdown", params={"by": "hub"}).json()["rows"]
    assert all(isinstance(r["sla_below"], bool) and isinstance(r["cancel_above"], bool) for r in rows)
    # Hub Lento (trânsito plantado) fica abaixo do SLA do recorte; os demais, não.
    by_label = {r["label"]: r for r in rows}
    assert by_label["Hub Lento"]["sla_below"] is True
    assert by_label["Hub Centro"]["sla_below"] is False
    # Hub Preso concentra a loja que cancela tudo, então o cancelamento sobe acima do recorte.
    assert by_label["Hub Preso"]["cancel_above"] is True


def test_breakdown_store_cancel_outlier(client):
    rows = client.get("/api/breakdown", params={"by": "store", "min_orders": 30}).json()["rows"]
    by_label = {r["label"]: r for r in rows}
    assert by_label["Loja Quebrada"]["cancel_above"] is True
    assert client.get("/api/breakdown", params={"by": "hub", "city": "Nenhuma"}).json()["rows"] == []


def test_flag_outliers_treats_null_rates_as_not_flagged():
    from app.repository import _flag_outliers

    base = {"sla_rate": None, "cancel_rate": None}
    rows = _flag_outliers([{"sla_rate": 0.0, "cancel_rate": 1.0}], base)
    assert rows[0]["sla_below"] is False
    assert rows[0]["cancel_above"] is True  # sem base, o piso de 6% ainda vale
    rows = _flag_outliers([{"sla_rate": None, "cancel_rate": None}], {"sla_rate": 0.9, "cancel_rate": 0.02})
    assert rows[0]["sla_below"] is False and rows[0]["cancel_above"] is False


_NAIVE_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def test_orders_page_and_sort_whitelist(client, repo):
    assert set(get_args(OrderSort)) == ORDER_SORTS
    page = client.get("/api/orders", params={"limit": 5, "sort": "amount", "desc": "true"}).json()
    amounts = [r["amount"] for r in page["rows"]]
    assert amounts == sorted(amounts, reverse=True)
    assert page["total"] == 12000
    for row in page["rows"]:
        assert isinstance(row["hub_id"], int)
        assert isinstance(row["store_id"], int)
        assert isinstance(row["amount_outlier"], bool)
        assert row["amount_outlier"] is (row["amount"] > 5000)
        assert _NAIVE_DATETIME_RE.match(row["created_at"])

    # Contrato HTTP rejeita sort inválido com 422; a proteção defensiva no repositório continua.
    invalid = client.get("/api/orders", params={"sort": "amount; drop table orders", "limit": 5})
    assert invalid.status_code == 422
    fallback = repo.orders_page(Filters(), 0, 5, "amount; drop table orders", True)
    created = client.get("/api/orders", params={"sort": "created_at", "limit": 5}).json()
    assert [row["order_id"] for row in fallback["rows"]] == [row["order_id"] for row in created["rows"]]


def test_csv_export_respects_filter(client):
    r = client.get("/api/orders.csv", params={"city": "Curitiba"})
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("order_id,created_at")
    assert all(",Curitiba," in line for line in lines[1:50])


def test_timeseries_and_heatmap(client):
    ts = client.get("/api/timeseries", params={"grain": "week"}).json()
    assert len(ts) >= 8  # fixture cobre jan–mar (~90 dias)
    assert all(
        _NAIVE_DATETIME_RE.match(p["t"])
        and isinstance(p["measured"], int)
        and p["measured"] >= 0
        and p["low_sample"] == (p["measured"] < MIN_MEASURED)
        and p["volume_low_sample"] == (p["orders"] < MIN_MEASURED)
        for p in ts
    )
    heat = client.get("/api/heatmap").json()
    assert all(
        0 <= c["weekday"] <= 6
        and 0 <= c["hour"] <= 23
        and isinstance(c["measured"], int)
        and c["measured"] >= 0
        and c["low_sample"] == (c["measured"] < HEATMAP_MIN_SAMPLE)
        and c["volume_low_sample"] == (c["orders"] < HEATMAP_MIN_SAMPLE)
        for c in heat
    )

    thin_ts = client.get(
        "/api/timeseries",
        params={"grain": "day", "start": "2021-03-02", "end": "2021-03-02", "store": 15},
    ).json()
    assert len(thin_ts) == 1
    assert thin_ts[0]["low_sample"] is True
    assert thin_ts[0]["volume_low_sample"] is True

    thin_heat = client.get(
        "/api/heatmap",
        params={"start": "2021-03-02", "end": "2021-03-02", "store": 15},
    ).json()
    assert thin_heat and all(c["low_sample"] is True and c["volume_low_sample"] is True for c in thin_heat)


def test_week_bucket_starts_at_the_filter_not_the_previous_monday(client):
    # 2021-01-06 é quarta. date_trunc('week') cairia em 2021-01-04.
    start = "2021-01-06"
    rows = client.get("/api/timeseries", params={"grain": "week", "start": start, "end": "2021-01-20"}).json()
    assert rows[0]["t"].startswith("2021-01-06")
    assert all(row["t"][:10] >= start for row in rows)
    assert rows[1]["t"].startswith("2021-01-11")  # segunda seguinte, já dentro do recorte


def test_day_and_hour_grains_stay_inside_the_filter(client):
    day = client.get("/api/timeseries", params={"grain": "day", "start": "2021-01-06", "end": "2021-01-08"}).json()
    assert [row["t"][:10] for row in day] == ["2021-01-06", "2021-01-07", "2021-01-08"]
    hour = client.get("/api/timeseries", params={"grain": "hour", "start": "2021-01-06", "end": "2021-01-06"}).json()
    assert hour
    assert all(row["t"].startswith("2021-01-06T") for row in hour)


def test_filter_bounds_reject_oversized_values(client):
    assert client.get("/api/kpis", params={"start": "1999-12-31"}).status_code == 422
    assert client.get("/api/kpis", params={"end": "2101-01-01"}).status_code == 422
    assert client.get("/api/kpis", params={"start": "2000-01-01", "end": "2000-01-02"}).status_code == 200
    assert client.get("/api/kpis", params={"city": "a" * 81}).status_code == 422
    assert client.get("/api/kpis", params={"city": "a" * 80}).status_code == 200
    too_many = [("hub", i) for i in range(1, 52)]
    assert client.get("/api/kpis", params=too_many).status_code == 422
    assert client.get("/api/breakdown", params={"by": "store", "min_orders": 100001}).status_code == 422
    assert client.get("/api/breakdown", params={"by": "store", "min_orders": 100000}).status_code == 200


def _scope(method: str, path: str, headers: list[tuple[bytes, bytes]], query: bytes = b"", spec: str = "2.3"):
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": spec},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
    }


def _asgi_request(
    app,
    headers: list[tuple[bytes, bytes]],
    parts: list[bytes],
    disconnect_after: int | None = None,
) -> tuple[int | None, dict[str, str], bytes]:
    """POST no chat pelo ASGI cru. `disconnect_after=n`: o cliente cai depois de n pedaços do corpo."""
    sent: dict = {"status": None, "headers": {}}
    payload = bytearray()
    index = 0

    async def receive():
        nonlocal index
        if disconnect_after is not None and index >= disconnect_after:
            return {"type": "http.disconnect"}
        if index >= len(parts):
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = parts[index]
        index += 1
        return {"type": "http.request", "body": chunk, "more_body": index < len(parts)}

    async def send(message):
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]
            sent["headers"] = {k.decode().lower(): v.decode("latin-1") for k, v in message.get("headers", [])}
        elif message["type"] == "http.response.body":
            payload.extend(message.get("body") or b"")

    anyio.run(app, _scope("POST", "/api/agent/chat", headers), receive, send)
    return sent["status"], sent["headers"], bytes(payload)


def _asgi_post(app, headers: list[tuple[bytes, bytes]], parts: list[bytes]) -> tuple[int, bytes]:
    status, _, body = _asgi_request(app, headers, parts)
    assert status is not None
    return status, body


def test_post_without_content_length_over_64kb_is_413(client):
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json")],
        [b"x" * (40 * 1024), b"y" * (30 * 1024)],
    )
    assert code == 413
    assert "64 KB" in body.decode()


def test_post_with_bad_content_length_is_400(client):
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json"), (b"content-length", b"nope")],
        [b'{"question":"oi"}'],
    )
    assert code == 400
    assert "Content-Length" in body.decode()


def test_post_without_content_length_under_the_cap_reaches_the_route(client):
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json")],
        [b'{"question":"ola"}'],
    )
    assert code == 200
    assert b"local" in body


def test_csv_export_rejects_recorte_over_the_row_cap(client):
    export_limiter.reset()
    client.app.dependency_overrides[get_settings] = lambda: Settings(csv_export_max_rows=10, csv_export_per_minute=0)
    try:
        response = client.get("/api/orders.csv", params={"city": "Curitiba"})
        assert response.status_code == 413
        assert "Afine o filtro" in response.json()["detail"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
        export_limiter.reset()


def test_csv_export_rate_limit_per_ip(client):
    export_limiter.reset()
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        csv_export_max_rows=100_000, csv_export_per_minute=1
    )
    try:
        headers = {"X-Forwarded-For": "203.0.113.8"}
        assert client.get("/api/orders.csv", params={"city": "Curitiba"}, headers=headers).status_code == 200
        blocked = client.get("/api/orders.csv", params={"city": "Curitiba"}, headers=headers)
        assert blocked.status_code == 429
        assert "export" in blocked.json()["detail"].lower()
        assert 1 <= int(blocked.headers["retry-after"]) <= 60
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
        export_limiter.reset()


def test_alerts_response_serializes(client):
    response = client.get("/api/alerts", params={"store": 16})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["orders"], int) and body["orders"] > 0
    assert body["empty_reason"] is None
    assert body["alerts"]
    for alert in body["alerts"]:
        assert alert["severity"] in {"high", "medium", "low"}
        assert alert["id"] and alert["title"] and alert["detail"] and alert["action"]
        assert alert["category"]


def test_alerts_empty_reason_over_http(client):
    bad_place = client.get("/api/alerts", params={"city": "Curitiba", "hub": 1}).json()
    assert bad_place == {
        "alerts": [],
        "orders": 0,
        "empty_reason": "O hub Hub Centro fica em São Paulo, fora de Curitiba. Tire um dos filtros.",
    }

    bad_period = client.get("/api/alerts", params={"start": "2021-05-01"}).json()
    assert bad_period["orders"] == 0
    assert bad_period["alerts"] == []
    assert "fora dela" in bad_period["empty_reason"]


def test_lifespan_closes_repository_on_shutdown(parquet_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DATA_PATH", str(parquet_path))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as local_client:
            app_repo = local_client.app.state.repo
            assert app_repo.metrics(Filters())["orders"] > 0
        with pytest.raises(duckdb.ConnectionException):
            app_repo.metrics(Filters(city=["Curitiba"]))
    finally:
        get_settings.cache_clear()


# ------------------------------------------------------------ corpo do POST (BodySizeLimitMiddleware)
def test_content_length_with_non_ascii_digit_is_400(client):
    # "²" (0xB2 em latin-1) passa em str.isdigit(), mas int() quebrava com 500.
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json"), (b"content-length", bytes([0xB2]))],
        [b'{"question":"oi"}'],
    )
    assert code == 400
    assert "Content-Length" in body.decode()


def test_duplicate_content_length_is_400(client):
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json"), (b"content-length", b"17"), (b"content-length", b"17")],
        [b'{"question":"oi"}'],
    )
    assert code == 400
    assert "Content-Length" in body.decode()


def test_content_length_with_more_than_eight_digits_is_413(client):
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json"), (b"content-length", b"123456789")],
        [b'{"question":"oi"}'],
    )
    assert code == 413
    assert "64 KB" in body.decode()


def test_small_declared_length_does_not_let_a_big_body_through(client):
    code, body = _asgi_post(
        client.app,
        [(b"content-type", b"application/json"), (b"content-length", b"10")],
        [b"x" * (40 * 1024), b"y" * (30 * 1024)],
    )
    assert code == 413
    assert "64 KB" in body.decode()


def test_early_rejections_keep_the_cors_header(client):
    origins = get_settings().cors_origin_list
    if not origins:
        pytest.skip("sem origem CORS configurada")
    origin = origins[0].encode()
    for headers, parts, expected in (
        ([(b"content-length", b"nope")], [b"{}"], 400),
        ([], [b"x" * (65 * 1024)], 413),
    ):
        code, sent, _ = _asgi_request(client.app, [(b"origin", origin), *headers], parts)
        assert code == expected
        assert sent["access-control-allow-origin"] == origin.decode()


def test_client_disconnect_mid_body_never_reaches_the_route(client, monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(main_mod.agent, "chat", lambda *args, **kwargs: calls.append(args))
    code, _, body = _asgi_request(
        client.app,
        [(b"content-type", b"application/json")],
        [b'{"question":', b'"oi"}'],
        disconnect_after=1,
    )
    # Antes, o corpo truncado seguia como completo e a rota respondia 422.
    assert code is None
    assert body == b""
    assert calls == []


def test_body_limit_replays_the_body_once_then_hands_receive_back():
    seen: list[dict] = []

    async def inner(scope, receive, send):
        seen.append(await receive())
        seen.append(await receive())

    messages = [{"type": "http.request", "body": b"oi", "more_body": False}, {"type": "http.disconnect"}]

    async def receive():
        return messages.pop(0)

    anyio.run(BodySizeLimitMiddleware(inner), {"type": "http", "method": "POST", "headers": []}, receive, None)
    assert seen == [{"type": "http.request", "body": b"oi", "more_body": False}, {"type": "http.disconnect"}]


# ------------------------------------------------------------ Cache-Control
@pytest.mark.parametrize(
    "path",
    ["/api/meta", "/api/kpis", "/api/timeseries", "/api/heatmap", "/api/breakdown", "/api/alerts", "/api/orders"],
)
def test_analytic_gets_are_publicly_cacheable(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=600"


def test_health_and_errors_are_not_publicly_cached(client):
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    invalid = client.get("/api/kpis", params={"start": "2021-04-01", "end": "2021-03-01"})
    assert invalid.status_code == 422
    assert "cache-control" not in invalid.headers
    assert "public" not in client.get("/openapi.json").headers.get("cache-control", "")


# ------------------------------------------------------------ exportação CSV
@pytest.fixture
def csv_slots():
    export_limiter.reset()
    assert main_mod._csv_export_sem._value == 2
    yield main_mod._csv_export_sem
    export_limiter.reset()


@pytest.fixture
def tracked_csv(repo, monkeypatch, csv_slots):
    """Guarda cada gerador do CSV (lotes pequenos, vários pedaços) para checar que ele foi fechado."""
    gens = []
    original = repo.iter_orders_csv

    def tracked(f, batch_size=5000):
        gen = original(f, batch_size=50)
        gens.append(gen)
        return gen

    monkeypatch.setattr(repo, "iter_orders_csv", tracked)
    return gens


def test_csv_export_headers_and_empty_recorte(client, csv_slots):
    response = client.get("/api/orders.csv", params={"city": "Nenhuma"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == 'attachment; filename="pedidos-recorte.csv"'
    lines = response.text.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("order_id,created_at")
    assert csv_slots._value == 2


def test_csv_export_is_429_when_both_slots_are_busy(client, csv_slots):
    assert csv_slots.acquire(blocking=False)
    assert csv_slots.acquire(blocking=False)
    try:
        response = client.get("/api/orders.csv", params={"city": "Curitiba"})
        assert response.status_code == 429
        assert "simultâneas" in response.json()["detail"]
    finally:
        csv_slots.release()
        csv_slots.release()
    assert client.get("/api/orders.csv", params={"city": "Curitiba"}).status_code == 200


@pytest.mark.parametrize("spec", ["2.3", "2.4"])
@pytest.mark.parametrize("fails_on", ["http.response.start", "http.response.body"])
def test_csv_export_releases_slot_when_the_socket_write_fails(client, tracked_csv, csv_slots, spec, fails_on):
    """Cliente caiu antes dos headers (gerador nem começou) ou no meio do corpo (send levanta OSError)."""

    async def scenario():
        async def receive():
            await anyio.sleep(5)
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == fails_on:
                raise OSError("cliente caiu")

        with contextlib.suppress(Exception):
            await client.app(_scope("GET", "/api/orders.csv", [], b"city=Curitiba", spec=spec), receive, send)

    anyio.run(scenario)
    # Sem gc.collect(): a vaga volta na hora e o gerador fica fechado (antes, o corpo deixava 1 de 2).
    assert csv_slots._value == 2
    assert len(tracked_csv) == 1
    assert inspect.getgeneratorstate(tracked_csv[0]) == inspect.GEN_CLOSED


def test_csv_export_releases_slot_and_cursor_when_client_drops_mid_body(client, tracked_csv, csv_slots):
    chunks: list[bytes] = []

    async def scenario():
        got_body = anyio.Event()

        async def receive():
            await got_body.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body" and message.get("body"):
                chunks.append(message["body"])
                got_body.set()

        await client.app(_scope("GET", "/api/orders.csv", [], b"city=Curitiba", spec="2.3"), receive, send)

    anyio.run(scenario)
    assert chunks
    assert csv_slots._value == 2
    # Gerador fechado = o finally do iter_orders_csv rodou e fechou o cursor do DuckDB.
    assert inspect.getgeneratorstate(tracked_csv[0]) == inspect.GEN_CLOSED
    for _ in range(3):
        assert client.get("/api/orders.csv", params={"city": "Curitiba"}).status_code == 200
    assert csv_slots._value == 2


def _fails_on_call(f, batch_size=5000):
    raise RuntimeError("consulta falhou")


def _fails_on_first_chunk(f, batch_size=5000):
    raise RuntimeError("consulta falhou")
    yield ""  # pragma: no cover


@pytest.mark.parametrize("broken", [_fails_on_call, _fails_on_first_chunk])
def test_csv_export_releases_slot_when_the_query_fails(client, repo, monkeypatch, csv_slots, broken):
    monkeypatch.setattr(repo, "iter_orders_csv", broken)
    with pytest.raises(RuntimeError, match="consulta falhou"):
        client.get("/api/orders.csv", params={"city": "Curitiba"})
    assert csv_slots._value == 2


def test_guarded_response_never_sent_releases_on_collect():
    sem = threading.BoundedSemaphore(1)
    assert sem.acquire(blocking=False)

    def gen():
        yield "x"

    raw = gen()
    response = main_mod._GuardedStreamingResponse(raw, sem, media_type="text/csv")
    del response
    gc.collect()
    assert sem.acquire(blocking=False)
    assert inspect.getgeneratorstate(raw) == inspect.GEN_CLOSED


def test_guarded_response_waits_for_a_chunk_still_in_the_threadpool():
    """Cliente caiu com um next() rodando no threadpool: quem fecha e libera é o próprio _iter."""
    sem = threading.BoundedSemaphore(1)
    assert sem.acquire(blocking=False)
    entered = threading.Event()
    release = threading.Event()

    def gen():
        yield "a"
        entered.set()
        release.wait(5)
        yield "b"
        yield "c"

    raw = gen()
    response = main_mod._GuardedStreamingResponse(raw, sem, media_type="text/csv")

    async def scenario():
        stream = response.body_iterator
        assert await stream.__anext__() == "a"

        async def pull():
            with contextlib.suppress(StopAsyncIteration):
                await stream.__anext__()

        async with anyio.create_task_group() as tg:
            tg.start_soon(pull)
            await anyio.to_thread.run_sync(entered.wait, 5)
            response._aborted = True
            assert response._close_raw() is False  # gerador ocupado em outra thread
            assert not sem.acquire(blocking=False)  # a vaga ainda é dele
            release.set()

    try:
        anyio.run(scenario)
    finally:
        release.set()
    assert inspect.getgeneratorstate(raw) == inspect.GEN_CLOSED
    assert sem.acquire(blocking=False)


# ------------------------------------------------------------ validação das rotas
@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/orders", {"limit": 0}),
        ("/api/orders", {"limit": 501}),
        ("/api/orders", {"offset": -1}),
        ("/api/breakdown", {"by": "planeta"}),
        ("/api/breakdown", {"sort": "nada"}),
        ("/api/breakdown", {"limit": 0}),
        ("/api/breakdown", {"limit": 1001}),
        ("/api/breakdown", {"min_orders": -1}),
        ("/api/timeseries", {"grain": "year"}),
        ("/api/kpis", {"modal": "aviao"}),
        ("/api/kpis", {"channel_type": "fax"}),
        ("/api/kpis", [("store", i) for i in range(1, 52)]),
    ],
)
def test_invalid_query_params_are_422(client, path, params):
    assert client.get(path, params=params).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [{"question": ""}, {"question": "a" * 801}, {"question": "oi", "engine": "turbo"}],
)
def test_invalid_chat_payload_is_422(client, payload):
    assert client.post("/api/agent/chat", json=payload).status_code == 422
