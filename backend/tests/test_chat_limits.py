from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import Settings, get_settings
from app.main import chat_limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    chat_limiter.reset()
    yield
    chat_limiter.reset()


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
            msg = SimpleNamespace(content="Resposta do modelo.", tool_calls=None)
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

    round2_msg = SimpleNamespace(content="Resposta final estruturada.", tool_calls=None)
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
        assert body["answer"] == "Resposta final estruturada."
        # Verifica que o mock_create foi chamado 2 vezes (round 0 e round 1)
        assert mock_create.call_count == 2
        # Verifica que na 2ª chamada o message da tool tinha tool_call_id gerado (ex: "call_0_0")
        call2_messages = mock_create.call_args_list[1].kwargs["messages"]
        tool_msg = next(m for m in call2_messages if m.get("role") == "tool")
        assert tool_msg["tool_call_id"] == "call_0_0"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
