from __future__ import annotations

from app.agent import local
from app.alerts import detect_alerts
from app.filters import Filters


def _ids(alerts):
    return {a.id for a in alerts}


def test_planted_problems_raise_alerts(repo):
    alerts = detect_alerts(repo, Filters(segment=["food"]))
    ids = _ids(alerts)
    assert "sla-hub-2" in ids, ids  # trânsito plantado no Hub Lento
    assert "cancel-store-30" in ids  # loja que cancela tudo
    assert "dados-presos" in ids  # Hub Preso
    slow = next(a for a in alerts if a.id == "sla-hub-2")
    assert "trânsito" in slow.detail
    assert slow.drilldown.filters == {"hub": [2]}


def test_stuck_hub_is_not_called_slow(repo):
    ids = _ids(detect_alerts(repo, Filters(segment=["food"])))
    assert "sla-hub-3" not in ids


def test_broken_store_gets_take_down_action(repo):
    alert = next(a for a in detect_alerts(repo, Filters()) if a.id == "cancel-store-30")
    assert alert.title.startswith("Loja sem entregas")
    assert "Tirar" in alert.action


def test_alerts_follow_the_filter(repo):
    ids = _ids(detect_alerts(repo, Filters(hub=[1])))
    assert "sla-hub-2" not in ids
    assert "cancel-store-30" not in ids


def test_empty_recorte(repo):
    f = Filters(city=["Nenhuma"])
    assert detect_alerts(repo, f) == []
    assert "Nenhum pedido" in local.answer("resumo", repo, f)


def test_local_agent_routes_by_intent(repo):
    f = Filters()
    assert "Mediana por etapa" in local.answer("onde está o gargalo?", repo, f)
    assert "Cancelamento no recorte" in local.answer("quais lojas cancelam mais?", repo, f)
    assert "subsídio" in local.answer("quanto custa o frete?", repo, f)
    assert "Briefing" in local.answer("bom dia", repo, f)


def test_chat_endpoint_without_key_is_local_and_scoped(client):
    r = client.post("/api/agent/chat", json={"question": "resumo", "filters": {"city": ["Curitiba"]}})
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "local"
    assert "Curitiba" in body["answer"]
    assert "São Paulo" not in body["answer"]


def test_llm_tools_stay_in_recorte_and_return_full_hours(repo):
    from app.agent.llm import ToolRunner

    runner = ToolRunner(repo, Filters(city=["Curitiba"]))
    hours = runner.run("get_breakdown", {"by": "hour", "limit": 3, "sort": "cancel_rate"})
    keys = [h["key"] for h in hours]
    assert keys == sorted(keys) and len(keys) > 3  # ignora limit/sort em hora
    hubs = runner.run("get_breakdown", {"by": "hub", "limit": 50})
    assert {h["parent"] for h in hubs} == {"Curitiba"}  # filtro forçado no servidor
    assert runner.run("get_breakdown", {"by": "drop table"}) == {"erro": "dimensão inválida: drop table"}
    assert runner.used[0] == "get_breakdown(hour)"
