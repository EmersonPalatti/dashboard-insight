from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.agent.service import CONTEXT_MIN_S, context_reserve
from app.config import Settings, get_settings
from app.main import SlidingWindowLimiter, chat_global_limiter, chat_limiter, get_client_ip


class _FakeClock:
    """Relógio parado que o teste avança na mão; o resto do módulo time segue o real."""

    def __init__(self, now: float = 1000.0):
        self.now = now

    def monotonic(self) -> float:
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


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
    assert "64 KB" in r.text


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
    """O prazo de parede corta a chamada presa: LLMDeadlineExceeded vira leitura local com motivo."""
    monkeypatch.setattr("app.agent.llm._CALL_GRACE_S", 0.02)
    test_settings = Settings(
        openrouter_api_key="test-key",
        chat_budget_s=0.3,
        llm_timeout_s=0.3,
    )
    client.app.dependency_overrides[get_settings] = lambda: test_settings
    release = threading.Event()

    # Cliente OpenAI preso: só responde (com uma resposta válida) depois que o teste solta.
    class SlowCompletions:
        def create(self, *args, **kwargs):
            release.wait(timeout=5.0)
            msg = SimpleNamespace(content="Tarde demais.\n\n**Ação:** Líder do hub revisa hoje.", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

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
        assert body["fallback_reason"] == "timeout"
        assert elapsed < 3.0  # não esperou a chamada presa (que só voltaria em 5 s)
    finally:
        release.set()
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
        "chat_budget_s": 12,
        "llm_timeout_s": 10,
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
        # 3 s do orçamento de 12 s ficam para o contexto: a chamada de tools leva até 9 s, não os 10 do timeout.
        assert 8 < client_timeouts[0] <= 9
        assert client_timeouts[0] == pytest.approx(12 - CONTEXT_MIN_S, abs=0.5)
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


def test_empty_slice_does_not_spend_llm_quota(client, monkeypatch):
    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_per_minute=1
    )
    headers = {"X-Forwarded-For": "198.51.100.77"}
    try:
        empty = client.post(
            "/api/agent/chat",
            json={"question": "resumo", "filters": {"city": ["Nenhuma"]}},
            headers=headers,
        )
        assert empty.status_code == 200
        assert empty.json()["mode"] == "local"
        assert calls == []

        valid = client.post("/api/agent/chat", json={"question": "resumo"}, headers=headers)
        assert valid.status_code == 200
        assert valid.json()["mode"] == "llm-tools"
        assert len(calls) == 1
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_llm_strips_think_block_passes_max_tokens_and_handles_empty_choices(client, monkeypatch):
    captured: list[dict] = []

    def create_with_think(*_args, **kwargs):
        captured.append(kwargs)
        msg = SimpleNamespace(
            content="<think>raciocinio</think> Resposta final.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
            tool_calls=None,
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    _install_llm(monkeypatch, create_with_think)
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "resumo"}).json()
        assert body["mode"] == "llm-tools"
        assert body["answer"].startswith("Resposta final.")
        assert "<think>" not in body["answer"]
        assert captured[0]["max_tokens"] == 2000
    finally:
        client.app.dependency_overrides.pop(get_settings, None)

    _install_llm(monkeypatch, lambda *_args, **_kwargs: SimpleNamespace(choices=[]))
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings()
    try:
        body = client.post("/api/agent/chat", json={"question": "resumo"}).json()
        assert body["mode"] == "local"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_latency_defaults_fit_the_free_model_budget():
    """Padrões do modelo gratuito: resposta rápida e reserva coerente para o modo contexto."""
    fields = Settings.model_fields
    assert fields["chat_budget_s"].default == 20.0
    assert fields["llm_timeout_s"].default == 18.0
    assert fields["llm_max_tokens"].default == 2000
    budget = fields["chat_budget_s"].default
    assert context_reserve(budget) == CONTEXT_MIN_S == 3.0
    # Tools ficam com o resto do orçamento, abaixo do timeout de uma chamada.
    assert budget - context_reserve(budget) <= fields["llm_timeout_s"].default
    # Orçamento pequeno (testes) não é engolido pela reserva.
    assert context_reserve(0.4) == pytest.approx(0.1)


def test_context_is_skipped_when_less_than_the_reserve_remains(client, monkeypatch):
    """Tools gastaram o prazo delas: sobra menos que a reserva e o contexto não é tentado."""
    calls: list[dict] = []
    clock = _FakeClock()
    monkeypatch.setattr("app.agent.service.time", clock)
    monkeypatch.setattr("app.agent.llm.time", clock)

    def create(*_args, **kwargs):
        calls.append(kwargs)
        clock.now += 0.17
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=None))])

    _install_llm(monkeypatch, create)
    # Orçamento 0,2 s: reserva de 25% = 0,05 s. A chamada de tools "leva" 0,17 s no relógio falso e
    # deixa 0,03 s, sem depender de quanto o TestClient demora de verdade.
    client.app.dependency_overrides[get_settings] = lambda: _llm_settings(chat_budget_s=0.2, llm_timeout_s=0.2)
    try:
        body = client.post("/api/agent/chat", json={"question": "como está o sla?"}).json()
        assert body["mode"] == "local"
        assert len(calls) == 1
        assert "tools" in calls[0]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


# ------------------------------------------------------------ cota do modelo gratuito
def _rate_limit(message: str):
    import httpx
    import openai

    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.RateLimitError(message, response=httpx.Response(429, request=request), body=None)


def test_daily_quota_skips_context_and_opens_breaker(client, monkeypatch):
    """429 diário: nada de segunda chamada, leitura local com motivo, e as próximas nem chamam o LLM."""
    calls: list[dict] = []

    def create(*_args, **kwargs):
        calls.append(kwargs)
        raise _rate_limit("Rate limit exceeded: free-models-per-day")

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        first = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert first["mode"] == "local"
        assert first["fallback_reason"] == "quota"
        assert len(calls) == 1  # o modo contexto não gasta outra chamada que também voltaria 429

        second = client.post("/api/agent/chat", json={"question": "e o cancelamento?"}).json()
        assert second["fallback_reason"] == "quota"
        assert len(calls) == 1  # disjuntor aberto: nem chega no OpenRouter
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_provider_429_does_not_open_breaker(client, monkeypatch):
    """429 repassado do provedor (congestionamento) não é a cota da conta: a próxima pergunta tenta de novo."""
    calls: list[dict] = []

    def create(*_args, **kwargs):
        calls.append(kwargs)
        raise _rate_limit("Error code: 429 - Provider returned error")

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        first = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert first["fallback_reason"] == "busy"
        assert len(calls) == 2  # uma nova tentativa no mesmo modelo; o contexto não gasta outra
        client.post("/api/agent/chat", json={"question": "e o cancelamento?"})
        assert len(calls) == 4  # disjuntor fechado: a próxima pergunta tenta de novo
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_minute_quota_breaker_is_short():
    from app.agent.service import _QuotaBreaker

    breaker = _QuotaBreaker()
    before = time.monotonic()
    breaker.open_for(_rate_limit("Rate limit exceeded: free-models-per-min"))
    assert breaker.is_open()
    assert breaker._until - before <= _QuotaBreaker.MINUTE_COOLDOWN_S + 1


def test_llm_timeout_sets_fallback_reason(client, monkeypatch):
    from app.agent import llm as llm_mod

    def create(*_args, **kwargs):
        raise llm_mod.LLMDeadlineExceeded("lento")

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["mode"] == "local"
        assert body["fallback_reason"] == "timeout"
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_local_engine_has_no_fallback_reason(client):
    body = client.post("/api/agent/chat", json={"question": "como esta o sla?", "engine": "local"}).json()
    assert body["fallback_reason"] is None


def test_provider_429_is_retried_once_and_recovers(client, monkeypatch):
    """Congestionamento passageiro: a segunda tentativa no mesmo modelo responde."""
    from app.agent import llm as llm_mod

    monkeypatch.setattr(llm_mod, "BUSY_RETRY_DELAY_S", 0.01)
    calls: list[dict] = []

    def create(*_args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise _rate_limit("Error code: 429 - Provider returned error")
        msg = SimpleNamespace(content="SLA em 80,0%.\n\n**Ação:** Líder do hub revisa o SLA hoje.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")], usage=None)

    _install_llm(monkeypatch, create)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["source"] == "llm"
        assert body["fallback_reason"] is None
        assert len(calls) == 2
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_account_quota_is_not_retried():
    from app.agent import llm as llm_mod

    calls: list[dict] = []

    def create(**kwargs):
        calls.append(kwargs)
        raise _rate_limit("Rate limit exceeded: free-models-per-day")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    settings = Settings(openrouter_api_key="k", llm_reasoning_effort=None)
    import openai

    with pytest.raises(openai.RateLimitError):
        llm_mod._create_completion(client, settings=settings, messages=[], timeout=10.0, deadline=time.monotonic() + 15)
    assert len(calls) == 1


def test_fallback_models_go_to_openrouter_models_list():
    from app.agent import llm as llm_mod

    seen: dict = {}

    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(choices=[])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    settings = Settings(
        openrouter_api_key="k",
        openrouter_model="a/primary:free",
        openrouter_fallback_models=" b/backup:free, a/primary:free ,,b/backup:free",
        llm_reasoning_effort="low",
    )
    llm_mod._create_completion(client, settings=settings, messages=[], timeout=2.0)
    assert seen["extra_body"]["models"] == ["a/primary:free", "b/backup:free"]
    assert seen["extra_body"]["reasoning"]["effort"] == "low"


def test_no_fallback_models_by_default():
    assert Settings.model_fields["openrouter_fallback_models"].default == ""
    assert Settings(openrouter_api_key="k").fallback_models == []


# ------------------------------------------------------------ limites das settings
@pytest.mark.parametrize(
    "overrides",
    [
        {"investigation_max_probes": 10},
        {"investigation_max_probes": -1},
        {"chat_budget_s": 0},
        {"llm_timeout_s": -1},
        {"investigation_budget_s": 0},
        {"llm_max_tokens": 0},
        {"investigation_synth_max_tokens": 50},
    ],
)
def test_settings_reject_out_of_range_budgets(overrides):
    # max_probes 10 passaria e o LangGraph estouraria o limite de passos depois de gastar ~10 chamadas.
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_settings_accept_the_edges():
    s = Settings(investigation_max_probes=5, chat_budget_s=120, llm_max_tokens=100, investigation_budget_s=0.1)
    assert (s.investigation_max_probes, s.chat_budget_s, s.llm_max_tokens) == (5, 120, 100)


# ------------------------------------------------------------ SlidingWindowLimiter
def test_limiter_window_expires(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr("app.main.time", clock)
    limiter = SlidingWindowLimiter(window_s=60)
    assert limiter.check("a", 2) == (True, 0)
    clock.now += 10
    assert limiter.check("a", 2) == (True, 0)
    assert limiter.check("a", 2) == (False, 50)  # o primeiro hit sai da janela em 50 s
    clock.now += 50.5
    assert limiter.check("a", 2) == (True, 0)


def test_limiter_evicts_the_least_recently_seen_client():
    limiter = SlidingWindowLimiter(window_s=60, max_clients=2)
    assert limiter.check("a", 1)[0]
    assert limiter.check("b", 1)[0]
    assert not limiter.check("a", 1)[0]  # a bloqueado, e agora é o mais recente
    assert limiter.check("c", 1)[0]  # entra c: sai b, o menos recente, nunca o cliente ativo
    assert list(limiter._clients) == ["a", "c"]
    assert not limiter.check("a", 1)[0]  # a própria chamada não despeja a nem zera a janela
    assert limiter.check("b", 1)[0]  # b foi despejado e volta com a janela zerada
    assert len(limiter._clients) == 2


def test_limiter_zero_limit_blocks():
    assert SlidingWindowLimiter().check("a", 0)[0] is False


def test_check_all_records_nothing_when_any_limiter_refuses():
    per_ip = SlidingWindowLimiter()
    overall = SlidingWindowLimiter()
    assert overall.check("global", 1)[0]  # teto global cheio
    assert not SlidingWindowLimiter.check_all([(per_ip, "192.0.2.1", 1), (overall, "global", 1)])
    assert "192.0.2.1" not in per_ip._clients
    overall.reset()
    assert SlidingWindowLimiter.check_all([(per_ip, "192.0.2.1", 1), (overall, "global", 1)])
    assert not SlidingWindowLimiter.check_all([(per_ip, "192.0.2.1", 1), (overall, "global", 5)])
    assert len(overall._clients["global"]) == 1  # a recusa por IP não gastou o global


def test_global_cap_rejection_does_not_burn_the_ip_quota(client, monkeypatch):
    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_per_minute=2, chat_global_rate_limit_per_minute=1
    )

    def ask(ip: str) -> str:
        return client.post("/api/agent/chat", json={"question": "resumo"}, headers={"X-Forwarded-For": ip}).json()[
            "mode"
        ]

    try:
        assert ask("198.51.100.30") == "llm-tools"  # enche o teto global
        assert [ask("198.51.100.31"), ask("198.51.100.31")] == ["local", "local"]
        chat_global_limiter.reset()  # a vaga global volta
        assert ask("198.51.100.31") == "llm-tools"  # a cota do IP seguiu intacta
        assert len(calls) == 2
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_open_quota_breaker_does_not_spend_the_rate_limit(client, monkeypatch):
    from app.agent.service import quota_breaker

    calls: list[int] = []
    _fast_llm(monkeypatch, calls)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_per_minute=2
    )
    headers = {"X-Forwarded-For": "198.51.100.40"}
    try:
        quota_breaker.open_for(_rate_limit("Rate limit exceeded: free-models-per-min"))
        for i in range(3):
            body = client.post("/api/agent/chat", json={"question": f"teste {i}"}, headers=headers).json()
            assert body["mode"] == "local"
            assert body["fallback_reason"] == "quota"
        assert calls == []
        assert "198.51.100.40" not in chat_limiter._clients
        assert "global" not in chat_global_limiter._clients
        quota_breaker.reset()
        modes = [
            client.post("/api/agent/chat", json={"question": f"depois {i}"}, headers=headers).json()["mode"]
            for i in range(2)
        ]
        assert modes == ["llm-tools", "llm-tools"]  # cota cheia de novo depois do disjuntor
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


# ------------------------------------------------------------ get_client_ip
def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": ("10.0.0.1", 1234)})


def test_client_ip_header_set_to_x_forwarded_for_still_uses_the_last_hop():
    settings = Settings(client_ip_header="X-Forwarded-For")
    assert get_client_ip(_request({"X-Forwarded-For": "6.6.6.6, 198.51.100.9"}), settings) == "198.51.100.9"


def test_missing_or_blank_trusted_header_falls_back_to_the_proxy_hop():
    settings = Settings(client_ip_header="cf-connecting-ip")
    xff = {"X-Forwarded-For": "6.6.6.6, 198.51.100.9"}
    assert get_client_ip(_request(xff), settings) == "198.51.100.9"
    assert get_client_ip(_request({**xff, "CF-Connecting-IP": "  "}), settings) == "198.51.100.9"
    assert get_client_ip(_request({**xff, "CF-Connecting-IP": "192.0.2.7, 10.0.0.2"}), settings) == "192.0.2.7"
    assert get_client_ip(_request({}), settings) == "10.0.0.1"


def test_client_ip_is_capped_so_junk_headers_cannot_bloat_the_limiter():
    settings = Settings(client_ip_header="cf-connecting-ip")
    assert len(get_client_ip(_request({"X-Forwarded-For": "a" * 500}), settings)) == 64
    assert len(get_client_ip(_request({"CF-Connecting-IP": "b" * 500}), settings)) == 64
