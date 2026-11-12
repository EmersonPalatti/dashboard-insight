from __future__ import annotations

import anyio

from app.config import Settings, get_settings
from app.filters import Filters
from app.main import export_limiter


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


def test_orders_page_and_sort_whitelist(client):
    page = client.get("/api/orders", params={"limit": 5, "sort": "amount", "desc": "true"}).json()
    amounts = [r["amount"] for r in page["rows"]]
    assert amounts == sorted(amounts, reverse=True)
    assert page["total"] == 12000
    # coluna fora da lista cai para created_at em vez de virar SQL
    fallback = client.get("/api/orders", params={"sort": "amount; drop table orders", "limit": 5}).json()
    created = client.get("/api/orders", params={"sort": "created_at", "limit": 5}).json()
    assert [row["order_id"] for row in fallback["rows"]] == [row["order_id"] for row in created["rows"]]


def test_csv_export_respects_filter(client):
    r = client.get("/api/orders.csv", params={"city": "Curitiba"})
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("order_id,created_at")
    assert all(",Curitiba," in line for line in lines[1:50])


def test_timeseries_and_heatmap(client):
    ts = client.get("/api/timeseries", params={"grain": "week"}).json()
    assert len(ts) >= 8  # fixture cobre ~58 dias
    heat = client.get("/api/heatmap").json()
    assert all(0 <= c["weekday"] <= 6 and 0 <= c["hour"] <= 23 for c in heat)


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


def _asgi_post(app, headers: list[tuple[bytes, bytes]], parts: list[bytes]) -> tuple[int, bytes]:
    status: dict[str, int] = {}
    payload = bytearray()
    index = 0

    async def receive():
        nonlocal index
        if index >= len(parts):
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = parts[index]
        index += 1
        return {"type": "http.request", "body": chunk, "more_body": index < len(parts)}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            payload.extend(message.get("body") or b"")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/agent/chat",
        "raw_path": b"/api/agent/chat",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
    }
    anyio.run(app, scope, receive, send)
    return status["code"], bytes(payload)


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
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
        export_limiter.reset()


def test_alerts_response_serializes(client):
    response = client.get("/api/alerts", params={"store": 16})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["orders"], int) and body["orders"] > 0
    assert body["alerts"]
    for alert in body["alerts"]:
        assert alert["severity"] in {"high", "medium", "low"}
        assert alert["id"] and alert["title"] and alert["detail"] and alert["action"]
        assert alert["category"]
