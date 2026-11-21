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


def _tool_call(name: str = "get_kpis", arguments: str = "{}", call_id: str = "c1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _has_tool_result(kwargs: dict) -> bool:
    return any(m.get("role") == "tool" for m in kwargs.get("messages", ()))


def test_local_engine_does_not_burn_the_llm_quota(client, monkeypatch):
    calls: list[int] = []

    class Completions:
        def create(self, *args, **kwargs):
            if not _has_tool_result(kwargs):
                calls.append(1)
            if kwargs.get("tools") and not _has_tool_result(kwargs):
                msg = SimpleNamespace(content=None, tool_calls=[_tool_call()])
            else:
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
        if kwargs.get("tools") and not _has_tool_result(kwargs):
            msg = SimpleNamespace(content=None, tool_calls=[_tool_call()])
        else:
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
        assert "```leitura" not in body["answer"]
        assert '"drilldowns"' not in body["answer"]
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


def test_llm_severity_is_translated_to_pt_br(client, monkeypatch):
    payload = (
        "Os 2 alertas high mostram queda no SLA (high) e atraso medium.\n\n"
        "**Ação:** Líder do hub deve revisar os alertas high hoje.\n\n"
        "```leitura\n"
        '{"title":"Alertas high no hub","diagnosis":"Dois alertas high e um alerta medium ativos.",'
        '"action":"Líder deve tratar os alertas high agora.","drilldowns":[]}\n'
        "```"
    )
    _install(monkeypatch, payload)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "quais os alertas?"}).json()
        assert body["source"] == "llm"
        assert "alertas críticos" in body["answer"]
        assert "(crítico)" in body["answer"]
        assert body["title"] == "Alertas críticos no hub"
        assert "alertas críticos" in body["diagnosis"]
        assert "alerta em atenção" in body["diagnosis"]
        assert "alertas críticos" in body["action"]
        assert "```leitura" not in body["answer"]
        assert '"drilldowns"' not in body["answer"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_llm_truncated_leitura_fence_keeps_answer_and_action(client, monkeypatch):
    payload = (
        "SLA em 80,0%.\n\n"
        "**Ação:** Líder do hub deve revisar o SLA hoje.\n\n"
        '```leitura\n{"title":"Corte no meio'
    )
    _install(monkeypatch, payload)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["mode"] == "llm-tools"
        assert body["source"] == "llm"
        assert "revisar o SLA hoje" in body["action"]
        assert body["title"]
        assert body["diagnosis"]
        assert "```leitura" not in body["answer"]
        assert "Corte no meio" not in body["answer"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_internal_keys_from_tools_are_translated_in_llm_text():
    from app.agent.reading import _pt_severity

    text = "Hub 8 com `sla_below` e low_sample; volume_low_sample na loja. sla_rate 80% e cycle_p50 alto."
    out = _pt_severity(text)
    for raw in ("sla_below", "low_sample", "volume_low_sample", "sla_rate", "cycle_p50", "`"):
        assert raw not in out
    assert "SLA abaixo do recorte" in out
    assert "volume pequeno" in out
    assert "amostra pequena" in out


def test_copied_tool_arguments_are_removed_from_llm_text():
    from app.agent.reading import _pt_severity

    text = "Acionar as 10 lojas com maior preparo no jantar (window=jantar, sort=production_p50, min_measured=100) hoje."
    out = _pt_severity(text)
    assert "window=" not in out and "sort=" not in out
    assert out == "Acionar as 10 lojas com maior preparo no jantar hoje."
    # Parêntese comum continua.
    assert _pt_severity("SLA de 80,0% (sobre 1.200 entregas).") == "SLA de 80,0% (sobre 1.200 entregas)."


@pytest.mark.parametrize(
    "line",
    ["Ação: líder do hub revisa hoje.", "**Ação**: líder do hub revisa hoje.", "__Ação:__ líder do hub revisa hoje.",
     "  acao: líder do hub revisa hoje.", "**Ação:** líder do hub revisa hoje."],
)
def test_action_marker_variants_are_normalized(line):
    from app.agent.reading import normalize_action

    out = normalize_action(f"SLA em 80,0%.\n\n{line}")
    assert "**Ação:** líder do hub revisa hoje." in out
    assert out.count("**Ação:**") == 1


def test_action_taken_from_leitura_block_when_line_is_missing():
    from app.agent.reading import normalize_action

    text = 'SLA em 80,0%.\n\n```leitura\n{"title":"t","diagnosis":"d","action":"Líder do hub revisa hoje.","drilldowns":[]}\n```'
    out = normalize_action(text)
    assert "**Ação:** Líder do hub revisa hoje." in out
    assert out.index("**Ação:**") < out.index("```leitura")


def test_llm_answer_without_bold_action_is_accepted(client, monkeypatch):
    _install(monkeypatch, "SLA em 80,0%.\n\nAção: líder do hub revisa o SLA hoje.")
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["source"] == "llm"
        assert "revisa o SLA hoje" in body["action"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_bare_tool_call_in_prose_is_removed():
    from app.agent.reading import _pt_severity

    text = (
        'Analista investiga query_metrics group_by=["store"], metrics=["Cancelamento"], min_orders=150, '
        'sort="Cancelamento", order="worst" para achar lojas acima de 6%.'
    )
    out = _pt_severity(text)
    assert "query_metrics" not in out and "group_by" not in out and "=" not in out
    assert out == "Analista investiga uma consulta para achar lojas acima de 6%."


# A-01: marca de ação fora do lugar não derruba a resposta do modelo para a leitura local.
@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("O SLA do hub caiu para 80,0%.\nCorpo. **Ação:** Líder do hub revisa hoje.", "Líder do hub revisa hoje."),
        ("O SLA caiu.\n\n**Ação:** Líder do hub:\n- revisa a escala hoje.", "Líder do hub: revisa a escala hoje."),
        ("O SLA caiu.\n\n- **Ação:** Líder do hub revisa hoje.", "Líder do hub revisa hoje."),
        ("O SLA caiu.\n\n### Ação: Líder do hub revisa hoje.", "Líder do hub revisa hoje."),
        (
            "O SLA caiu.\n\n**Ação:** Líder do hub revisa hoje.\n\nObservação: base pequena.",
            "Líder do hub revisa hoje.",
        ),
    ],
    ids=["inline", "multiline", "bulleted", "heading", "trailing-note"],
)
def test_llm_action_outside_last_line_is_accepted(client, monkeypatch, content, expected):
    _install(monkeypatch, content)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["source"] == "llm"
        assert body["mode"].startswith("llm-")
        assert body["fallback_reason"] is None
        assert body["action"] == expected
        assert "**Ação:**" not in body["diagnosis"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_trailing_note_after_action_stays_in_the_body():
    from app.agent.reading import split_markdown

    body, action = split_markdown("O SLA caiu.\n\n**Ação:** Líder do hub revisa hoje.\n\nObservação: base pequena.")
    assert action == "Líder do hub revisa hoje."
    assert body == "O SLA caiu.\n\nObservação: base pequena."


def test_llm_with_empty_action_falls_back_with_a_reason(client, monkeypatch):
    _install(monkeypatch, "O SLA caiu.\n\n**Ação:** ")
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["source"] == "local"
        assert body["mode"] == "local"
        assert body["fallback_reason"] == "error"
        assert body["action"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_acceptable_matches_what_the_comanda_can_extract():
    from app.agent.reading import has_extractable_action

    assert has_extractable_action("Texto.\n\n**Ação:** Líder revisa hoje.")
    assert has_extractable_action('```leitura\n{"title":"t","diagnosis":"d","action":"Líder revisa hoje."}\n```')
    assert not has_extractable_action("Texto.\n\n**Ação:** ")
    assert not has_extractable_action("Texto sem ação.")
    assert not has_extractable_action(None)


# A-02: o bloco `leitura` não fica em `answer` (volta como histórico na próxima pergunta).
def test_leitura_fence_is_not_kept_in_the_answer(client, monkeypatch):
    payload = (
        "SLA do recorte em 70%.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.\n\n"
        "```leitura\n"
        '{"title":"SLA high","diagnosis":"SLA em 70% no recorte.","action":"Líder do hub deve revisar o SLA hoje.",'
        '"drilldowns":[{"label":"Ver hub real","filters":{"hub":[2]}}]}\n'
        "```"
    )
    _install(monkeypatch, payload)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["source"] == "llm"
        assert body["title"] == "SLA high"
        assert "```leitura" not in body["answer"]
        assert '"drilldowns"' not in body["answer"]
        assert body["answer"].startswith("SLA do recorte em 70%.")
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


def test_leitura_only_answer_gets_a_readable_answer(client, monkeypatch):
    _install(
        monkeypatch,
        '```leitura\n{"title":"SLA baixo","diagnosis":"SLA em 70%.","action":"Líder do hub revisa hoje.",'
        '"drilldowns":[]}\n```',
    )
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_rate_limit_enabled=False
    )
    try:
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        assert body["source"] == "llm"
        assert "```" not in body["answer"]
        assert "SLA em 70%." in body["answer"] and "Líder do hub revisa hoje." in body["answer"]
    finally:
        client.app.dependency_overrides.pop(get_settings, None)


# A-03: só argumento real de tool sai da prosa; amostra e números do modelo ficam.
@pytest.mark.parametrize(
    "text",
    [
        "SLA de 80,0% (n=42 pedidos).",
        "Amostra pequena com n=42 pedidos.",
        "Hub com taxa=80% e ciclo=45.",
        "Hub com SLA de 80% (base=42).",
    ],
)
def test_prose_with_equals_sign_is_kept(text):
    from app.agent.reading import _pt_severity

    assert _pt_severity(text) == text


# A-18: número en-US na prosa do modelo vira pt-BR; data, hora, Nº e código ficam.
def test_en_us_numbers_are_normalized_to_pt_br():
    from app.agent.reading import _pt_severity

    text = "SLA 82.4%, ciclo 38.5 min, queda de 1.2 p.p., GMV R$ 1,234.56 e frete R$ 9.90"
    assert _pt_severity(text) == "SLA 82,4%, ciclo 38,5 min, queda de 1,2 p.p., GMV R$ 1.234,56 e frete R$ 9,90"
    assert _pt_severity("R$ 1,234,567 no mês") == "R$ 1.234.567 no mês"


@pytest.mark.parametrize(
    "text",
    [
        "GMV de R$ 1.234,56 em 1.200 pedidos, SLA 82,4%.",
        "Pico em 05.01.2021 às 19.30, hub 8 e loja 1234.",
        "Versão 1.2 do relatório; jantar 19h-21h.",
        "Campo `sla_pct = 0.82%` no código.",
    ],
)
def test_pt_br_numbers_dates_and_code_are_untouched(text):
    from app.agent.reading import _pt_numbers

    assert _pt_numbers(text) == text


# A-16: sem vaga para o LLM, a pergunta sai na hora com a leitura local.
def test_llm_slots_full_answers_local_busy_fast(client, monkeypatch):
    import threading
    import time

    from app.agent import service

    entered = threading.Semaphore(0)
    release = threading.Event()

    def create(*_args, **_kwargs):
        entered.release()
        release.wait(10)
        msg = SimpleNamespace(content="SLA em 80,0%.\n\n**Ação:** Líder revisa hoje.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    settings = Settings(openrouter_api_key="test-key", chat_rate_limit_enabled=False, investigation_enabled=False)
    client.app.dependency_overrides[get_settings] = lambda: settings
    repo = client.app.state.repo
    results: list = []

    def ask() -> None:
        results.append(service.chat(service.ChatRequest(question="como esta o sla?"), repo, settings))

    workers = [threading.Thread(target=ask) for _ in range(service.LLM_MAX_CONCURRENT)]
    try:
        for worker in workers:
            worker.start()
        for _ in workers:
            assert entered.acquire(timeout=10), "chamada lenta não chegou ao modelo"
        started = time.monotonic()
        body = client.post("/api/agent/chat", json={"question": "como esta o sla?"}).json()
        # A meta é < 0,5 s de espera pela vaga; a folga cobre a leitura local num CI lento.
        assert time.monotonic() - started < 2.0
        assert body["mode"] == "local"
        assert body["fallback_reason"] == "busy"
        assert client.get("/api/health").status_code == 200
    finally:
        release.set()
        for worker in workers:
            worker.join(15)
        client.app.dependency_overrides.pop(get_settings, None)
    assert len(results) == service.LLM_MAX_CONCURRENT
    assert all(r.source == "llm" for r in results)
    # As vagas voltam: a próxima pergunta chega ao modelo.
    assert service.chat(service.ChatRequest(question="como esta o sla?"), repo, settings).source == "llm"


def test_llm_slot_size_comes_from_settings():
    from app.agent import service

    slots = service._llm_slots(Settings(llm_max_concurrent=2))
    assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)
    slots.release()
    slots.release()
    default = service._llm_slots(Settings())
    assert default is service._llm_slots(Settings(llm_max_concurrent=service.LLM_MAX_CONCURRENT))


# A-22: o motivo da queda é o que de fato aconteceu.
class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


def test_slow_api_error_keeps_error_reason(repo, monkeypatch):
    import httpx
    import openai

    from app.agent import service

    clock = _Clock()
    monkeypatch.setattr(service, "time", clock)

    def tools(*_args, deadline, **_kwargs):
        clock.now = deadline + 1.0  # o erro chega quando já não há reserva para o contexto
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://llm.invalid"))

    def context(*_args, **_kwargs):
        raise AssertionError("modo contexto não deveria rodar sem reserva")

    monkeypatch.setattr(service.llm, "answer_with_tools", tools)
    monkeypatch.setattr(service.llm, "answer_with_context", context)
    settings = Settings(openrouter_api_key="test-key", investigation_enabled=False)
    out = service.chat(service.ChatRequest(question="como esta o sla?"), repo, settings)
    assert out.source == "local"
    assert out.fallback_reason == "error"


def test_synthesis_skipped_near_deadline_is_timeout(repo, monkeypatch):
    from app.agent import service

    clock = _Clock()
    monkeypatch.setattr(service, "time", clock)
    monkeypatch.setattr(service.investigate, "should_investigate", lambda *_a, **_k: True)

    def investigate(*_args, deadline, **_kwargs) -> None:
        clock.now = deadline - 0.3  # `synthesize` pula com <= 0,5 s e devolve None

    monkeypatch.setattr(service.investigate, "investigate", investigate)
    monkeypatch.setattr(service.llm, "answer_with_context", lambda *_a, **_k: None)
    settings = Settings(openrouter_api_key="test-key", investigation_enabled=True)
    out = service.chat(service.ChatRequest(question="por que o sla mudou?"), repo, settings)
    assert out.source == "local"
    assert out.fallback_reason == "timeout"


def test_validate_drilldowns_matches_city_case_insensitively_and_returns_canonical_casing(repo):
    canonical = str(repo.meta()["cities"][0]["value"])
    drills = validate_drilldowns(
        repo,
        Filters(),
        [
            DrillDown(
                label="Cidade",
                filters={"city": [canonical.lower(), f"  {canonical.upper()}  ", "Cidade Inventada"]},
            ),
        ],
    )
    assert len(drills) == 1
    assert drills[0].filters == {"city": [canonical]}
