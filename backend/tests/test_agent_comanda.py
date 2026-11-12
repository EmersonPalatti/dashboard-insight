"""Comanda do agente: estrutura completa, filtro validado e queda limpa do modelo."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent import local
from app.agent.reading import parse_leitura, validate_drilldowns
from app.config import Settings, get_settings
from app.filters import Filters
from app.main import chat_global_limiter, chat_limiter
from app.schemas import DrillDown

QUESTIONS = [
    "quais os alertas e problemas no recorte?",
    "onde esta o gargalo das etapas de entrega?",
    "quais lojas cancelam mais pedidos?",
    "quanto estamos gastando de frete e subsidio?",
    "como esta o pico do jantar?",
    "como esta o sla de entrega no prazo?",
    "qual o volume por canal marketplace ou proprio?",
    "qual o tempo de transito por modal moto e bike?",
    "quais as lojas do recorte?",
    "quais os hubs com maior volume na praca?",
    "qual o gmv e faturamento da operacao?",
    "me de um briefing com a visao geral",
]


@pytest.fixture(autouse=True)
def _reset_limiter():
    chat_limiter.reset()
    chat_global_limiter.reset()
    yield
    chat_limiter.reset()
    chat_global_limiter.reset()


def _ids(repo, dimension: str) -> set:
    found = set()
    for row in repo.breakdown(Filters(), dimension, limit=1000):
        if row.get("key") is None:
            continue
        found.add(int(row["key"]) if dimension in {"hub", "store"} else str(row["key"]))
    return found


@pytest.mark.parametrize("question", QUESTIONS)
def test_local_reading_is_a_complete_comanda(repo, question):
    reading = local.build_reading(question, repo, Filters())
    assert reading.title.strip()
    assert reading.diagnosis.strip()
    assert reading.action.strip()
    assert "**Ação:**" not in reading.action
    assert reading.answer.strip()
    assert reading.n > 0
    assert reading.measured >= 0
    assert reading.tools
    hubs = _ids(repo, "hub")
    stores = _ids(repo, "store")
    for drill in reading.drilldowns:
        for hub in drill.filters.get("hub", []):
            assert hub in hubs
        for store in drill.filters.get("store", []):
            assert store in stores
        assert drill.label.strip()


def test_invented_entity_is_dropped_and_real_one_stays(repo):
    drills = validate_drilldowns(
        repo,
        Filters(),
        [
            DrillDown(label="Hub que não existe", filters={"hub": [999_999]}),
            DrillDown(label="Ver hub real", filters={"hub": [2, 999_999], "city": ["Cidade Inventada"]}),
            DrillDown(label="Sem filtro", filters={"hub": ["nao-numerico"]}),
        ],
    )
    assert len(drills) == 1
    assert drills[0].filters == {"hub": [2]}
    assert "Cidade Inventada" not in str(drills[0].filters)
    assert 999_999 not in drills[0].filters["hub"]


def test_broken_leitura_json_is_not_a_reading():
    assert parse_leitura("Texto.\n\n**Ação:** Alguém faz hoje.\n\n```leitura\n{nao e json}\n```") is None
    parsed = parse_leitura(
        "```leitura\n"
        '{"title":"SLA baixo","diagnosis":"SLA em 70%.","action":"Líder do hub revisa hoje.",'
        '"drilldowns":[{"label":"Ver","filters":{"hub":[2]}}]}\n'
        "```"
    )
    assert parsed is not None
    assert parsed.sent_drilldowns is True
    assert parsed.drilldowns[0].filters == {"hub": [2]}


def test_chat_local_engine_returns_the_comanda(client):
    response = client.post("/api/agent/chat", json={"question": "como esta o sla?", "engine": "local"})
    body = response.json()
    assert response.status_code == 200
    assert body["mode"] == "local"
    assert body["source"] == "local"
    assert body["model"] is None
    assert body["title"]
    assert body["diagnosis"]
    assert body["action"]
    assert body["base"]["n"] > 0
    assert "low_sample" in body["base"]
    assert body["tool_labels"]
    assert all("get_" not in label for label in body["tool_labels"])
    assert "SLA do recorte" in body["answer"]


def test_local_engine_does_not_burn_the_llm_quota(client, monkeypatch):
    calls: list[int] = []

    class Completions:
        def create(self, *args, **kwargs):
            calls.append(1)
            msg = SimpleNamespace(
                content="Resposta do modelo.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
                tool_calls=None,
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_per_minute=1
    )
    headers = {"X-Forwarded-For": "198.51.100.40"}
    try:
        for index in range(3):
            body = client.post(
                "/api/agent/chat",
                json={"question": f"regras {index}", "engine": "local"},
                headers=headers,
            ).json()
            assert body["mode"] == "local"
        assert calls == []
        llm = client.post(
            "/api/agent/chat",
            json={"question": "agora o modelo", "engine": "auto"},
            headers=headers,
        ).json()
        assert llm["mode"] == "llm-tools"
        assert llm["source"] == "llm"
        assert len(calls) == 1
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def _install(monkeypatch, content: str):
    def create(*_args, **kwargs):
        msg = SimpleNamespace(content=content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )


def test_llm_without_leitura_falls_back_to_a_complete_comanda(client, monkeypatch):
    _install(monkeypatch, "Número do recorte.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.\n\n```leitura\n{quebrado}\n```")
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["mode"] == "llm-tools"
        assert body["source"] == "llm"
        assert body["answer"].startswith("Número do recorte.")
        assert body["title"]
        assert body["diagnosis"]
        assert "revisar o SLA hoje" in body["action"]
        assert body["base"]["n"] > 0
        assert "quebrado" not in body["title"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_llm_invented_drilldown_is_dropped(client, monkeypatch):
    payload = (
        "SLA do recorte em 70%.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.\n\n"
        "```leitura\n"
        '{"title":"SLA baixo","diagnosis":"SLA em 70% no recorte.","action":"Líder do hub deve revisar o SLA hoje.",'
        '"drilldowns":[{"label":"Ver hub inventado","filters":{"hub":[999999]}},'
        '{"label":"Ver hub real","filters":{"hub":[2]}}]}\n'
        "```"
    )
    _install(monkeypatch, payload)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["mode"] == "llm-tools"
        assert body["title"] == "SLA baixo"
        assert body["drilldowns"] == [{"label": "Ver hub real", "filters": {"hub": [2]}}]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_llm_only_invented_drilldown_leaves_the_list_empty(client, monkeypatch):
    payload = (
        "Texto.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.\n\n"
        "```leitura\n"
        '{"title":"Fora do recorte","diagnosis":"Nada aqui.","action":"Líder do hub deve revisar o SLA hoje.",'
        '"drilldowns":[{"label":"Ver loja inventada","filters":{"store":[999999]}}]}\n'
        "```"
    )
    _install(monkeypatch, payload)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["drilldowns"] == []
        assert body["source"] == "llm"
        assert body["title"] == "Fora do recorte"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_local_engine_keeps_the_body_limits(client):
    response = client.post(
        "/api/agent/chat",
        json={
            "question": "olá",
            "engine": "local",
            "history": [{"role": "user", "content": "a" * 2001}],
        },
    )
    assert response.status_code == 422
