from __future__ import annotations

from app.filters import Filters


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["orders"] == 12000


def test_meta_lists_dynamic_options(client):
    meta = client.get("/api/meta").json()
    assert {c["value"] for c in meta["cities"]} == {"São Paulo", "Curitiba"}
    assert len(meta["hubs"]) == 4
    assert meta["llm_enabled"] is False


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
    assert client.get("/api/orders", params={"sort": "amount; drop table orders"}).status_code == 200


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
