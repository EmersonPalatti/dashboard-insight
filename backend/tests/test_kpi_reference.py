"""Referência e veredito dos KPIs de operação. A régua é a das comandas do recorte."""

from __future__ import annotations

from datetime import date

import pytest

from app.alerts import (
    CANCEL_HIGH,
    CANCEL_WARN,
    SLA_HIGH,
    SLA_WARN,
    STUCK_HUB_MAX,
    cancel_band,
    hero_readings,
    hub_spread,
    minute_reference,
    rate_reference,
    sla_band,
)
from app.filters import Filters
from app.repository import MIN_MEASURED


def _hero(readings: list[dict], key: str) -> dict:
    return next(item for item in readings if item["key"] == key)


def test_bands_are_the_comanda_thresholds():
    assert sla_band(SLA_HIGH - 0.001) == "critical"
    assert sla_band(SLA_HIGH) == "attention"
    assert sla_band(SLA_WARN - 0.001) == "attention"
    assert sla_band(SLA_WARN) == "within"
    assert cancel_band(CANCEL_HIGH) == "critical"
    assert cancel_band(CANCEL_HIGH - 0.001) == "attention"
    assert cancel_band(CANCEL_WARN) == "attention"
    assert cancel_band(CANCEL_WARN - 0.001) == "within"


def test_reference_phrases_use_pt_br():
    assert rate_reference(0.80, 0.824) == "2,4 p.p. abaixo da rede"
    assert rate_reference(0.855, 0.824) == "3,1 p.p. acima da rede"
    assert rate_reference(0.80, 0.80004) == "igual à rede"
    assert minute_reference(44.3, 41.2) == "3,1 min acima da rede"
    assert minute_reference(41.2, 44.3) == "3,1 min abaixo da rede"
    assert minute_reference(41.2, 41.24) == "igual à rede"
    assert hub_spread([0.8, 0.934], "rate") == "hubs de 80,0% a 93,4%"
    assert hub_spread([28.4, 61.2], "minutes") == "hubs de 28,4 a 61,2 min"
    assert hub_spread([0.8], "rate") is None


def test_narrow_recorte_compares_to_the_network_in_the_same_period(client, repo):
    f = Filters(city=["Curitiba"], start=date(2021, 2, 1), end=date(2021, 2, 28))
    start, end = repo.period(f)
    network = repo.metrics(Filters(start=start, end=end))
    current = repo.metrics(f)
    body = client.get("/api/kpis", params={"city": "Curitiba", "start": "2021-02-01", "end": "2021-02-28"}).json()
    assert body["previous"] is not None  # o vão da rede convive com o delta do período anterior
    sla = _hero(body["heroes"], "sla_rate")
    cycle = _hero(body["heroes"], "cycle_p50")
    cancel = _hero(body["heroes"], "cancel_rate")
    assert sla["reference"] == rate_reference(current["sla_rate"], network["sla_rate"])
    assert sla["reference"].endswith("da rede")
    assert sla["network_value"] == pytest.approx(network["sla_rate"])
    assert cycle["reference"] == minute_reference(current["cycle_p50"], network["cycle_p50"])
    assert cycle["verdict"] is None
    assert cycle["network_value"] == pytest.approx(network["cycle_p50"])
    assert cancel["reference"] == rate_reference(current["cancel_rate"], network["cancel_rate"])
    assert cancel["network_value"] == pytest.approx(network["cancel_rate"])
    assert "hubs de" not in sla["reference"]


def test_full_network_uses_the_hub_spread_and_no_outside_target(client, repo):
    f = Filters()
    rows = repo.breakdown(f, "hub", sort="orders", limit=500, min_orders=0)
    body = client.get("/api/kpis").json()
    sla_values = [
        row["sla_rate"] for row in rows
        if row["sla_rate"] is not None and not row["low_sample"] and (row["stuck_rate"] or 0) <= STUCK_HUB_MAX
    ]
    cycle_values = [row["cycle_p50"] for row in rows if row["cycle_p50"] is not None and not row["low_sample"]]
    cancel_values = [
        row["cancel_rate"] for row in rows
        if row["cancel_rate"] is not None and row["orders"] >= MIN_MEASURED
    ]
    sla = _hero(body["heroes"], "sla_rate")
    cycle = _hero(body["heroes"], "cycle_p50")
    cancel = _hero(body["heroes"], "cancel_rate")
    assert sla["reference"] == hub_spread(sla_values, "rate")
    assert cycle["reference"] == hub_spread(cycle_values, "minutes")
    assert cancel["reference"] == hub_spread(cancel_values, "rate")
    assert sla["network_value"] is None
    assert cycle["network_value"] is None
    assert cycle["verdict"] is None
    assert "da rede" not in (sla["reference"] or "")
    # Período sozinho continua sendo a rede: a referência não vira um alvo de fora.
    dated = client.get("/api/kpis", params={"start": "2021-02-01", "end": "2021-02-28"}).json()
    assert _hero(dated["heroes"], "sla_rate")["network_value"] is None
    assert _hero(dated["heroes"], "sla_rate")["reference"].startswith("hubs")


def test_verdict_matches_the_recorte_comanda(client):
    cases = (
        ({"store": 16}, "sla_rate", "sla-recorte", {"high": "critical"}),
        ({"store": 18}, "sla_rate", "sla-recorte", {}),
        ({"store": 25}, "cancel_rate", "cancel-recorte", {"high": "critical"}),
        ({"store": 18}, "cancel_rate", "cancel-recorte", {}),
    )
    for params, key, alert_id, expected in cases:
        kpis = client.get("/api/kpis", params=params).json()
        alerts = {a["id"]: a for a in client.get("/api/alerts", params=params).json()["alerts"]}
        verdict = _hero(kpis["heroes"], key)["verdict"]
        comanda = alerts.get(alert_id)
        if comanda is None:
            assert verdict in (None, "within")
        else:
            assert verdict == expected[comanda["severity"]]


def test_stuck_slice_does_not_call_sla_critical(client, repo):
    # Loja 28: SLA medido abaixo de 80%, mas a comanda manda não cobrar prazo.
    f = Filters(store=[28])
    metrics = repo.metrics(f)
    assert metrics["sla_rate"] < SLA_HIGH
    assert metrics["stuck_rate"] > STUCK_HUB_MAX
    assert metrics["low_sample"] is False
    body = client.get("/api/kpis", params={"store": 28}).json()
    alerts = {a["id"] for a in client.get("/api/alerts", params={"store": 28}).json()["alerts"]}
    sla = _hero(body["heroes"], "sla_rate")
    assert "sla-recorte" not in alerts
    assert sla["verdict"] is None
    assert sla["reference"] is not None
    assert sla["reference"].endswith("da rede")
    assert hero_readings(repo, f)[0]["verdict"] is None


def test_low_sample_hides_the_reference_gap(client):
    body = client.get("/api/kpis", params={"store": 15, "start": "2021-03-02", "end": "2021-03-02"}).json()
    assert body["current"]["low_sample"] is True
    assert body["current"]["volume_low_sample"] is True
    assert body["current"]["orders"] < MIN_MEASURED
    for hero in body["heroes"]:
        assert hero["verdict"] is None
        assert hero["reference"] is None
        assert hero["network_value"] is None


def test_extreme_thin_cancel_stays_critical_without_a_gap(client):
    # 89 cancelados: a comanda não rebaixa, mas o vão contra a rede não se sustenta.
    body = client.get("/api/kpis", params={"store": 35}).json()
    alerts = {a["id"]: a for a in client.get("/api/alerts", params={"store": 35}).json()["alerts"]}
    cancel = _hero(body["heroes"], "cancel_rate")
    assert body["current"]["orders"] < MIN_MEASURED
    assert body["current"]["volume_low_sample"] is True
    assert alerts["cancel-recorte"]["severity"] == "high"
    assert cancel["verdict"] == "critical"
    assert cancel["reference"] is None
    assert cancel["network_value"] is None


def test_thin_cancel_does_not_upgrade_the_low_comanda(client):
    body = client.get(
        "/api/kpis", params={"store": 36, "start": "2021-03-03", "end": "2021-03-03"}
    ).json()
    alerts = {a["id"]: a for a in client.get("/api/alerts", params={"store": 36, "start": "2021-03-03", "end": "2021-03-03"}).json()["alerts"]}
    assert alerts["cancel-recorte"]["severity"] == "low"
    assert alerts["sla-recorte"]["severity"] == "low"
    assert _hero(body["heroes"], "cancel_rate")["verdict"] is None
    assert _hero(body["heroes"], "sla_rate")["verdict"] is None
    assert _hero(body["heroes"], "cancel_rate")["reference"] is None


def test_volume_low_sample_follows_the_order_floor(client, repo):
    one_day = client.get("/api/kpis", params={"start": "2021-01-01", "end": "2021-01-01"}).json()
    assert one_day["current"]["orders"] < MIN_MEASURED
    assert one_day["current"]["volume_low_sample"] is True
    full = client.get("/api/kpis").json()
    assert full["current"]["volume_low_sample"] is False
    assert repo.metrics(Filters())["volume_low_sample"] is False
