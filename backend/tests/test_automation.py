"""Endpoints de automação: briefing em Markdown e roteamento de alertas por template."""

from __future__ import annotations

import pytest

from app.routing import message_for, recipient_for, route_alerts
from app.schemas import Alert, DrillDown, Evidence

OUTSIDE = {"start": "2020-01-01", "end": "2020-01-31"}


def _alert(**overrides) -> Alert:
    base = {
        "id": "sla-recorte",
        "severity": "medium",
        "category": "sla",
        "title": "Entregas fora do prazo",
        "detail": "80,0% dos pedidos entregues dentro do SLA.",
        "action": "Ligar hoje para o líder da operação do recorte.",
    }
    base.update(overrides)
    return Alert(**base)


def test_briefing_on_planted_slice_counts_alerts_and_covers_dates(client):
    # Loja 16: 200 entregas atrasadas em 05–11/03, sem data no filtro.
    body = client.get("/api/briefing", params={"store": 16}).json()
    assert body["alert_count"] >= 1
    assert "Briefing do recorte" in body["markdown"]
    assert "Entregas fora do prazo" in body["markdown"]
    assert body["start"] == "2021-03-05"
    assert body["end"] == "2021-03-11"
    assert client.get("/api/briefing", params={"store": 16}).headers["cache-control"] == "public, max-age=600"


def test_briefing_keeps_requested_dates(client):
    body = client.get(
        "/api/briefing",
        params={"store": 16, "start": "2021-03-01", "end": "2021-03-31"},
    ).json()
    assert body["start"] == "2021-03-01"
    assert body["end"] == "2021-03-31"
    assert body["alert_count"] >= 1


def test_briefing_empty_slice_is_valid_markdown(client):
    dated = client.get("/api/briefing", params=OUTSIDE)
    assert dated.status_code == 200
    body = dated.json()
    assert body["alert_count"] == 0
    assert body["start"] == "2020-01-01"
    assert body["end"] == "2020-01-31"
    assert "Nenhum pedido" in body["markdown"]
    assert "**Ação:**" in body["markdown"]

    undated = client.get("/api/briefing", params={"city": "Nenhuma"}).json()
    assert undated["alert_count"] == 0
    assert undated["start"] is None
    assert undated["end"] is None
    assert "Nenhum pedido" in undated["markdown"]


def test_routing_on_planted_store_is_deterministic(client):
    params = [("store", 25), ("store", 18)]
    first = client.get("/api/alerts/routing", params=params)
    second = client.get("/api/alerts/routing", params=params)
    assert first.status_code == 200
    assert first.headers["cache-control"] == "public, max-age=600"
    rows = first.json()
    assert rows == second.json()
    assert rows
    routed = next(row for row in rows if row["alert_id"] == "cancel-store-25")
    assert routed["recipient"] == "Loja 25"
    assert routed["severity"] == "high"
    assert "Ação:" in routed["message"]
    assert "%" in routed["message"]
    assert "," in routed["message"]
    assert all(row["recipient"] and row["message"] for row in rows)


def test_routing_hub_comes_from_drilldown(client):
    rows = client.get("/api/alerts/routing", params=[("store", 46), ("store", 14)]).json()
    hub = next(row for row in rows if row["alert_id"] == "sla-hub-4")
    assert hub["recipient"] == "Líder do hub 4"
    assert all(row["recipient"] for row in rows)


def test_routing_without_structured_target_uses_operations_team(client):
    rows = client.get("/api/alerts/routing", params={"store": 16}).json()
    sla = next(row for row in rows if row["alert_id"] == "sla-recorte")
    assert sla["recipient"] == "Time de operações da praça"
    assert sla["message"]


def test_routing_empty_slice(client):
    response = client.get("/api/alerts/routing", params=OUTSIDE)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("path", ["/api/briefing", "/api/alerts/routing"])
def test_invalid_dates_match_the_rest_of_the_api(client, path):
    assert client.get(path, params={"start": "2021-04-01", "end": "2021-03-01"}).status_code == 422
    assert client.get(path, params={"start": "not-a-date"}).status_code == 422


def test_recipient_templates_and_message_are_pure():
    store = _alert(
        id="cancel-store-25",
        severity="high",
        category="loja",
        title="Loja crítica: x",
        detail="90 cancelamentos em 200 pedidos (45,0%).",
        action="Ligar para a loja hoje.",
        drilldown=DrillDown(label="Ver só a loja", filters={"store": [25]}),
    )
    hub = _alert(
        id="sla-hub-8",
        drilldown=DrillDown(label="Ver só o hub", filters={"hub": [8]}),
        evidence=Evidence(view="stages", hubs=[8]),
    )
    from_evidence = _alert(
        id="cancel-store-extra",
        category="loja",
        evidence=Evidence(view="scatter", metric="cancel_rate", stores=[123]),
    )
    from_id = _alert(id="cancel-hub-3")
    plain = _alert()

    routes = route_alerts([store, hub, from_evidence, from_id, plain])
    assert [item.recipient for item in routes] == [
        "Loja 25",
        "Líder do hub 8",
        "Loja 123",
        "Líder do hub 3",
        "Time de operações da praça",
    ]
    assert routes[0].message == message_for(store)
    assert "45,0%" in routes[0].message
    assert "Ação: Ligar para a loja hoje." in routes[0].message
    assert route_alerts([store, hub, from_evidence, from_id, plain]) == routes
    assert recipient_for(plain) == "Time de operações da praça"
