from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import Settings, get_settings
from app.main import chat_global_limiter, chat_limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    chat_limiter.reset()
    chat_global_limiter.reset()
    yield
    chat_limiter.reset()
    chat_global_limiter.reset()


def test_orders_offset_bounds(client):
    # offset dentro do limite: 200
    r_ok = client.get("/api/orders?offset=1000")
    assert r_ok.status_code == 200

    # offset no limite máximo: 200
    r_max = client.get("/api/orders?offset=1000000")
    assert r_max.status_code == 200

    # offset acima do limite máximo (1_000_000): 422
    r_bad = client.get("/api/orders?offset=1000001")
    assert r_bad.status_code == 422

    # offset astronômico (10**20): 422, sem estourar 500
    r_huge = client.get("/api/orders?offset=100000000000000000000")
    assert r_huge.status_code == 422


def test_post_body_size_guard(client):
    oversized_bytes = b"x" * (65 * 1024)  # 65 KB > 64 KB
    r = client.post(
        "/api/agent/chat",
        content=oversized_bytes,
        headers={"Content-Type": "application/json", "Content-Length": str(len(oversized_bytes))},
    )
    assert r.status_code == 413
    assert "64 KB" in r.text or "excede" in r.text


def test_chat_payload_validation_limits(client):
    # content > 2000 em ChatTurn -> 422
    r_content = client.post(
        "/api/agent/chat",
        json={
            "question": "olá",
            "history": [{"role": "user", "content": "a" * 2001}],
        },
    )
    assert r_content.status_code == 422

    # history > 8 turnos -> 422
    r_history = client.post(
        "/api/agent/chat",
        json={
            "question": "olá",
            "history": [{"role": "user", "content": f"msg {i}"} for i in range(9)],
        },
    )
    assert r_history.status_code == 422


def _fast_llm(monkeypatch, calls: list[int]):
    """LLM falso que responde na hora e conta as chamadas."""

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


def test_chat_over_quota_falls_back_to_local_without_error(client, monkeypatch):
    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_per_minute=3
    )
    headers = {"X-Forwarded-For": "198.51.100.1"}
    try:
        modes = [
            client.post("/api/agent/chat", json={"question": f"teste {i}"}, headers=headers).json()["mode"]
            for i in range(5)
        ]
        # 3 dentro da cota vão ao LLM; o resto responde com regras locais, nunca 429.
        assert modes == ["llm-tools"] * 3 + ["local"] * 2
        assert len(calls) == 3

        other = client.post("/api/agent/chat", json={"question": "outro"}, headers={"X-Forwarded-For": "198.51.100.2"})
        assert other.json()["mode"] == "llm-tools"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_chat_quota_keys_on_proxy_appended_ip(client, monkeypatch):
    """Forjar o início do X-Forwarded-For não renova a cota: vale o IP que o proxy acrescentou."""
    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_per_minute=2
    )
    try:
        modes = [
            client.post(
                "/api/agent/chat",
                json={"question": f"teste {i}"},
                headers={"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.9"},
            ).json()["mode"]
            for i in range(4)
        ]
        assert modes == ["llm-tools", "llm-tools", "local", "local"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_chat_quota_uses_configured_client_ip_header(client, monkeypatch):
    """Com CLIENT_IP_HEADER, a cota segue esse header e não o último hop do X-Forwarded-For."""
    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key",
        chat_rate_limit_per_minute=2,
        client_ip_header="true-client-ip",
    )
    try:
        modes = [
            client.post(
                "/api/agent/chat",
                json={"question": f"teste {i}"},
                headers={"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.9", "True-Client-IP": "192.0.2.10"},
            ).json()["mode"]
            for i in range(4)
        ]
        assert modes == ["llm-tools", "llm-tools", "local", "local"]
        other = client.post(
            "/api/agent/chat",
            json={"question": "outro ip"},
            headers={"X-Forwarded-For": "203.0.113.50, 198.51.100.9", "True-Client-IP": "192.0.2.11"},
        )
        assert other.json()["mode"] == "llm-tools"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_chat_global_cap_falls_back_to_local(client, monkeypatch):
    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key",
        chat_rate_limit_per_minute=10,
        chat_global_rate_limit_per_minute=3,
    )
    try:
        modes = [
            client.post(
                "/api/agent/chat",
                json={"question": f"teste {i}"},
                headers={"X-Forwarded-For": f"198.51.100.{i}"},
            ).json()["mode"]
            for i in range(5)
        ]
        assert modes == ["llm-tools"] * 3 + ["local"] * 2
        assert len(calls) == 3
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_chat_slow_llm_returns_within_budget_with_local_mode(client, monkeypatch):
    test_settings = Settings(
        openrouter_api_key="test-key",
        chat_budget_s=0.3,
        llm_timeout_s=0.3,
    )
    client.app.dependency_overrides[get_settings] = lambda: test_settings

    # Simula cliente OpenAI lento que estoura o budget
    class SlowCompletions:
        def create(self, *args, **kwargs):
            time.sleep(0.4)

    class SlowOpenAI:
        chat = SimpleNamespace(completions=SlowCompletions())

    monkeypatch.setattr("app.agent.llm._client", lambda settings, timeout=None: SlowOpenAI())

    try:
        t0 = time.monotonic()
        res = client.post(
            "/api/agent/chat",
            json={"question": "onde está o gargalo?"},
            headers={"X-Forwarded-For": "10.10.10.10"},
        )
        elapsed = time.monotonic() - t0
        assert res.status_code == 200
        body = res.json()
        assert body["mode"] == "local"
        assert body["model"] is None
        assert elapsed < 1.0
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_chat_tool_call_id_none_and_malformed_json_handled(client, monkeypatch):
    test_settings = Settings(
        openrouter_api_key="test-key",
        chat_budget_s=5.0,
        llm_timeout_s=5.0,
    )
    client.app.dependency_overrides[get_settings] = lambda: test_settings

    # Simula chamada com call.id = None e arguments com JSON malformado
    call_mock = SimpleNamespace(
        id=None,
        function=SimpleNamespace(name="get_kpis", arguments="{invalid_json"),
    )
    round1_msg = SimpleNamespace(content=None, tool_calls=[call_mock])
    round1_choice = SimpleNamespace(message=round1_msg)
    round1_response = SimpleNamespace(choices=[round1_choice])

    round2_msg = SimpleNamespace(
        content="Resposta final estruturada.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
        tool_calls=None,
    )
    round2_choice = SimpleNamespace(message=round2_msg)
    round2_response = SimpleNamespace(choices=[round2_choice])

    mock_create = MagicMock(side_effect=[round1_response, round2_response])
    mock_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))

    monkeypatch.setattr("app.agent.llm._client", lambda settings, timeout=None: mock_client)

    try:
        res = client.post(
            "/api/agent/chat",
            json={"question": "resumo geral"},
            headers={"X-Forwarded-For": "10.10.10.20"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["mode"] == "llm-tools"
        assert body["answer"] == "Resposta final estruturada.\n\n**Ação:** Líder do hub deve revisar o SLA hoje."
        # Verifica que o mock_create foi chamado 2 vezes (round 0 e round 1)
        assert mock_create.call_count == 2
        # Verifica que na 2ª chamada o message da tool tinha tool_call_id gerado (ex: "call_0_0")
        call2_messages = mock_create.call_args_list[1].kwargs["messages"]
        tool_msg = next(m for m in call2_messages if m.get("role") == "tool")
        assert tool_msg["tool_call_id"] == "call_0_0"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def _llm_settings(**overrides) -> Settings:
    base = {
        "openrouter_api_key": "test-key",
        "chat_budget_s": 20,
        "llm_timeout_s": 45,
        "chat_rate_limit_enabled": False,
    }
    base.update(overrides)
    return Settings(**base)


def _install_llm(monkeypatch, create):
    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )


def test_tools_none_with_budget_left_runs_context(client, monkeypatch):
    """Texto vazio nas tools não pula o contexto enquanto ainda há prazo."""
    calls: list[dict] = []

    def create(*_args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("tools"):
            msg = SimpleNamespace(content="", tool_calls=None)
        else:
            msg = SimpleNamespace(
                content="Pelo contexto.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
                tool_calls=None,
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "llm-context"
        assert body["answer"].startswith("Pelo contexto.")
        assert len(calls) == 2
        assert "tools" in calls[0]
        assert "tools" not in calls[1]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_tools_exception_falls_through_to_context(client, monkeypatch):
    def create(*_args, **kwargs):
        if kwargs.get("tools"):
            raise RuntimeError("tools down")
        msg = SimpleNamespace(
            content="Contexto depois da falha.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
            tool_calls=None,
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "llm-context"
        assert "Contexto depois da falha." in body["answer"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_context_failure_falls_back_to_local(client, monkeypatch):
    def create(*_args, **kwargs):
        if kwargs.get("tools"):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=None))])
        raise RuntimeError("context down")

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "local"
        assert body["model"] is None
        assert "**Ação:**" in body["answer"]
        assert "SLA do recorte" in body["answer"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_answer_without_action_falls_through_the_chain(client, monkeypatch):
    calls: list[dict] = []

    def create(*_args, **kwargs):
        calls.append(kwargs)
        msg = SimpleNamespace(content="Número solto, sem fechamento.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "local"
        assert "**Ação:**" in body["answer"]
        assert len(calls) == 2  # tools e contexto, os dois sem ação
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_timeout_is_passed_to_the_client_and_capped_for_tools(client, monkeypatch):
    client_timeouts: list[float | None] = []
    create_timeouts: list[float] = []

    def create(*_args, **kwargs):
        create_timeouts.append(kwargs["timeout"])
        if kwargs.get("tools"):
            msg = SimpleNamespace(content="", tool_calls=None)
        else:
            msg = SimpleNamespace(
                content="No prazo.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
                tool_calls=None,
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def factory(_settings, timeout=None):
        client_timeouts.append(timeout)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr("app.agent.llm._client", factory)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "llm-context"
        assert client_timeouts[0] == create_timeouts[0]
        # 25% do orçamento de 20s fica para o contexto: a chamada de tools não leva os 20 nem os 45.
        assert 12 < client_timeouts[0] < 16
        assert client_timeouts[1] == create_timeouts[1]
        assert create_timeouts[1] > 0
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_last_tool_round_answers_without_tools(client, monkeypatch):
    calls: list[dict] = []

    def create(*_args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("tools"):
            call = SimpleNamespace(
                id=f"c{len(calls)}", function=SimpleNamespace(name="get_kpis", arguments="{}")
            )
            msg = SimpleNamespace(content=None, tool_calls=[call])
        else:
            msg = SimpleNamespace(
                content="Fechei com os números das tools.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
                tool_calls=None,
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "llm-tools"
        assert "Fechei com os números" in body["answer"]
        assert len(calls) == 3
        assert "tools" in calls[0] and "tools" in calls[1]
        assert "tools" not in calls[2]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_tool_calls_are_capped_at_six_per_round(client, monkeypatch):
    captured: list[dict] = []

    def create(*_args, **kwargs):
        captured.append(kwargs)
        if len(captured) == 1:
            tool_calls = [
                SimpleNamespace(id=f"id{i}", function=SimpleNamespace(name="get_kpis", arguments="{}"))
                for i in range(10)
            ]
            msg = SimpleNamespace(content=None, tool_calls=tool_calls)
        else:
            msg = SimpleNamespace(
                content="Seis bastam.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
                tool_calls=None,
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "resumo"}).json()
        assert body["mode"] == "llm-tools"
        assistant = next(m for m in captured[1]["messages"] if m.get("role") == "assistant")
        tool_msgs = [m for m in captured[1]["messages"] if m.get("role") == "tool"]
        assert len(assistant["tool_calls"]) == 6
        assert len(tool_msgs) == 6
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
