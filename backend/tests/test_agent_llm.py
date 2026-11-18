"""Testes das ferramentas, matemática, economia de tokens e loop do agente LLM."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agent.llm import (
    MAX_ROUNDS,
    SYSTEM_PROMPT,
    ToolRunner,
    answer_with_context,
    answer_with_tools,
)
from app.agent.reading import labels_for
from app.config import Settings, get_settings
from app.filters import Filters
from app.main import chat_global_limiter, chat_limiter
from app.schemas import ChatTurn


@pytest.fixture(autouse=True)
def _reset_limiter():
    chat_limiter.reset()
    chat_global_limiter.reset()
    yield
    chat_limiter.reset()
    chat_global_limiter.reset()


def _col_map(res: dict) -> list[dict]:
    cols = res["columns"]
    return [dict(zip(cols, row)) for row in res["rows"]]


# ------------------------------------------------------------------ get_kpis
def test_get_kpis_units_periods_and_exact_deltas(repo):
    f = Filters(start=date(2021, 2, 1), end=date(2021, 2, 28))
    res = ToolRunner(repo, f).run("get_kpis", {})

    curr_raw = repo.metrics(f)
    prev_p = repo.previous_period(f)
    assert prev_p is not None
    prev_raw = repo.metrics(f.with_period(*prev_p))

    assert res["periodo"] == {"inicio": "2021-02-01", "fim": "2021-02-28"}
    assert res["periodo_anterior"] == {"inicio": prev_p[0].isoformat(), "fim": prev_p[1].isoformat()}
    assert res["atual"]["sla_pct"] == round(curr_raw["sla_rate"] * 100.0, 1)
    assert res["atual"]["cancel_pct"] == round(curr_raw["cancel_rate"] * 100.0, 1)
    assert res["atual"]["ticket"] == round(curr_raw["ticket"], 2)
    assert res["atual"]["fee_avg"] == round(curr_raw["fee_avg"], 2)
    assert res["atual"]["cost_avg"] == round(curr_raw["cost_avg"], 2)
    assert res["atual"]["subsidy"] == round(curr_raw["subsidy"], 2)

    deltas = res["variacao_vs_anterior"]
    assert deltas["sla_comparavel"] is True
    assert deltas["sla_pp"] == round((curr_raw["sla_rate"] - prev_raw["sla_rate"]) * 100.0, 1)
    assert deltas["cancel_pp"] == round((curr_raw["cancel_rate"] - prev_raw["cancel_rate"]) * 100.0, 1)
    assert deltas["orders_pct"] == round((curr_raw["orders"] / prev_raw["orders"] - 1.0) * 100.0, 1)


def test_get_kpis_blocks_sla_comparison_on_low_sample(repo):
    f = Filters(start=date(2021, 2, 1), end=date(2021, 2, 28), store=[30])
    res = ToolRunner(repo, f).run("get_kpis", {})
    deltas = res["variacao_vs_anterior"]
    assert deltas["sla_comparavel"] is False
    assert deltas["sla_pp"] is None
    assert deltas["cycle_p50_min"] is None
    assert deltas["cycle_p50_pct"] is None
    assert "amostra pequena" in deltas["nota"]


# ------------------------------------------------------------------ get_breakdown
def test_get_breakdown_rejects_invalid_sort_and_focus_instead_of_silent_fallback(repo):
    runner = ToolRunner(repo, Filters())
    bad_sort = runner.run("get_breakdown", {"by": "store", "sort": "metrica_inexistente"})
    assert "erro" in bad_sort and "ordenação inválida" in bad_sort["erro"]

    bad_focus = runner.run("get_breakdown", {"by": "hub", "focus": "invalido"})
    assert "erro" in bad_focus and "focus inválido" in bad_focus["erro"]


def test_get_breakdown_coerces_string_bool_none_stage_sorts_and_ids(repo):
    runner = ToolRunner(repo, Filters())
    res = runner.run(
        "get_breakdown",
        {"by": "hub", "sort": "transit_p50", "ascending": "false", "limit": None, "min_orders": None},
    )
    assert res["order"] == "desc"
    assert res["focus"] == "stages"  # auto-focus para etapas
    assert res["columns"][0] == "id"
    rows = _col_map(res)
    assert rows[0]["label"] == "Hub Lento"
    assert isinstance(rows[0]["id"], int)
    assert [r["transit_p50"] for r in rows] == sorted([r["transit_p50"] for r in rows], reverse=True)

    asc = runner.run("get_breakdown", {"by": "hub", "sort": "production_p50", "ascending": "true"})
    assert asc["order"] == "asc"
    asc_rows = _col_map(asc)
    assert [r["production_p50"] for r in asc_rows] == sorted([r["production_p50"] for r in asc_rows])

    cities = runner.run("get_breakdown", {"by": "city"})
    assert cities["columns"][:2] == ["label", "parent"]
    hours = runner.run("get_breakdown", {"by": "hour"})
    assert hours["columns"][0] == "label"


def test_get_breakdown_weekday_nominal_and_flags(repo):
    runner = ToolRunner(repo, Filters())
    wd = runner.run("get_breakdown", {"by": "weekday"})
    wd_rows = _col_map(wd)
    assert [r["label"] for r in wd_rows] == ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

    hubs = _col_map(runner.run("get_breakdown", {"by": "hub", "focus": "overview"}))
    by_label = {r["label"]: r for r in hubs}
    assert "sla_below" in by_label["Hub Lento"]["flags"]
    assert "cancel_above" in by_label["Hub Preso"]["flags"]


def test_get_breakdown_only_reliable_excludes_low_sample_and_falls_back(repo):
    runner = ToolRunner(repo, Filters())
    reliable = _col_map(
        runner.run("get_breakdown", {"by": "store", "sort": "sla_rate", "ascending": True, "limit": 15}),
    )
    assert all(r["measured"] >= 100 for r in reliable)
    assert all(r["label"] != "Loja Quebrada" for r in reliable)

    # Recorte de 1 dia: nenhuma loja tem 100 entregas medidas -> fallback com nota explícita
    thin_f = Filters(start=date(2021, 3, 2), end=date(2021, 3, 2), store=[15])
    thin = ToolRunner(repo, thin_f).run("get_breakdown", {"by": "store", "sort": "sla_rate", "ascending": True})
    assert len(thin["rows"]) == 1
    assert "amostra pequena" in thin["nota"]
    assert "low_sample" in _col_map(thin)[0]["flags"]


# ------------------------------------------------------------------ get_alerts & get_timeseries
def test_get_alerts_excludes_evidence_and_internal_fields(repo):
    alerts = ToolRunner(repo, Filters()).run("get_alerts", {})
    assert len(alerts) > 0
    for alert in alerts:
        assert "evidence" not in alert
        assert "drilldown" not in alert
        assert "id" not in alert
        assert {"severity", "category", "title", "detail", "action"} <= set(alert.keys())


def test_get_timeseries_truncation_and_validation(repo):
    runner = ToolRunner(repo, Filters())
    bad = runner.run("get_timeseries", {"grain": "month"})
    assert "erro" in bad

    daily = runner.run("get_timeseries", {"grain": "day"})
    assert daily["truncated"] is True
    assert daily["total_points"] > 60
    assert daily["shown"] == 60
    assert len(daily["rows"]) == 60
    assert len(daily["range_shown"]) == 2
    assert "Série cortada" in daily["nota"]

    weekly = runner.run("get_timeseries", {"grain": "week"})
    assert weekly["truncated"] is False
    assert "nota" not in weekly


# ------------------------------------------------------------------ get_heatmap
def test_get_heatmap_finds_peak_and_supports_filters_and_fallback(repo):
    # Loja 17 tem atrasos plantados às 12h, 13h, 19h e 20h
    runner = ToolRunner(repo, Filters(store=[17]))
    hm = runner.run("get_heatmap", {"metric": "sla_rate", "worst": True, "min_orders": 5, "limit": 10})
    rows = _col_map(hm)
    assert rows
    assert all(r["hour"] in {"12h", "13h", "19h", "20h"} for r in rows[:4])

    filtered = runner.run(
        "get_heatmap",
        {"weekday": "segunda", "hours": [12, 13], "min_orders": 10000, "limit": 5},
    )
    f_rows = _col_map(filtered)
    assert f_rows
    assert all(r["weekday"] == "seg" and r["hour"] in {"12h", "13h"} for r in f_rows)
    assert "nota" in filtered

    assert "erro" in runner.run("get_heatmap", {"metric": "invalid"})
    assert "erro" in runner.run("get_heatmap", {"hours": [25]})


# ------------------------------------------------------------------ compare_slices
def test_compare_slices_sums_to_recorte_and_respects_server_filter(repo):
    f = Filters()
    runner = ToolRunner(repo, f)
    base = repo.metrics(f)
    res = runner.run("compare_slices", {"groups": [{"name": "Jantar", "hours": [19, 20]}]})

    g0, g1 = res["grupos"]
    assert g0["name"] == "Jantar"
    assert g1["name"] == "Restante do recorte"
    assert g0["orders"] + g1["orders"] == base["orders"]
    assert g0["orders_share_pct"] == round(g0["orders"] / base["orders"] * 100.0, 1)
    assert "diferenca_primeiro_vs_segundo" in res

    # Aceita rótulos humanos ("goods" -> "good")
    seg_res = runner.run(
        "compare_slices",
        {
            "groups": [
                {"name": "Goods", "dimension": "segment", "values": ["goods"]},
                {"name": "Food", "dimension": "segment", "values": ["food"]},
            ],
        },
    )
    assert seg_res["grupos"][0]["orders"] > 0
    assert seg_res["grupos"][1]["orders"] > 0
    assert seg_res["grupos"][0]["orders"] + seg_res["grupos"][1]["orders"] == base["orders"]

    # Recorte de Curitiba não vaza São Paulo mesmo se pedido explicitamente
    cwb = ToolRunner(repo, Filters(city=["Curitiba"])).run(
        "compare_slices",
        {"groups": [{"name": "SP", "dimension": "city", "values": ["São Paulo"]}], "vs_rest": False},
    )
    assert cwb["grupos"][0]["orders"] == 0
    assert "aviso" in cwb["grupos"][0]

    assert "erro" in runner.run("compare_slices", {"groups": []})
    assert "erro" in runner.run("compare_slices", {"groups": [{"name": "X", "hours": [25]}]})


# ------------------------------------------------------------------ reading labels & token savings
def test_reading_labels_include_new_tools_without_internal_names():
    labels = labels_for(["get_kpis", "get_heatmap", "compare_slices"])
    assert labels == ["KPIs do recorte", "Mapa de calor (dia × hora)", "Comparação de subfatias"]
    assert all("get_" not in lbl and "compare_" not in lbl for lbl in labels)


def test_token_savings_against_legacy_payload_sizes(repo):
    runner = ToolRunner(repo, Filters())
    hour_json = json.dumps(runner.run("get_breakdown", {"by": "hour"}), ensure_ascii=False, separators=(",", ":"))
    alerts_json = json.dumps(runner.run("get_alerts", {}), ensure_ascii=False, separators=(",", ":"))
    # Antes: breakdown(hour) passava de 10.400 chars e alerts incluía 'evidence' (~2.850 chars)
    assert len(hour_json) < 2000
    assert "evidence" not in alerts_json


# ------------------------------------------------------------------ loop answer_with_tools & fallback
def _resp(content=None, tool_calls=None, finish_reason="stop", prompt_tokens=120, completion_tokens=30):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def test_answer_with_tools_required_dedup_and_forced_synthesis(repo, monkeypatch):
    seen_calls: list[dict] = []
    call_kpis = SimpleNamespace(id="c1", function=SimpleNamespace(name="get_kpis", arguments="{}"))
    call_dup = SimpleNamespace(id="c2", function=SimpleNamespace(name="get_kpis", arguments="{}"))
    call_bad_json = SimpleNamespace(id="c3", function=SimpleNamespace(name="get_alerts", arguments="{bad"))

    responses = [
        _resp(content=None, tool_calls=[call_kpis], finish_reason="tool_calls"),
        _resp(content=None, tool_calls=[call_dup, call_bad_json], finish_reason="tool_calls"),
        _resp(
            content="Síntese final na última rodada.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
            tool_calls=None,
            finish_reason="stop",
        ),
    ]

    class FakeCompletions:
        def create(self, **kwargs):
            seen_calls.append({**kwargs, "messages": list(kwargs["messages"])})
            return responses[len(seen_calls) - 1]

    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())),
    )

    settings = Settings(openrouter_api_key="k", chat_budget_s=10.0, llm_timeout_s=5.0)
    out = answer_with_tools("Como está o SLA?", [], repo, Filters(), settings)
    assert out is not None
    text, used = out
    assert "Síntese final na última rodada." in text
    assert used == ["get_kpis"]  # duplicada e JSON inválido não rodam ToolRunner

    assert len(seen_calls) == MAX_ROUNDS
    # Rodada 0 sem histórico: tool_choice="required", system estático sem recorte dinâmico, reasoning low
    assert seen_calls[0]["tool_choice"] == "required"
    assert seen_calls[0]["messages"][0]["content"] == SYSTEM_PROMPT
    assert "<dados_recorte>" in seen_calls[0]["messages"][1]["content"]
    assert seen_calls[0]["max_tokens"] == settings.llm_max_tokens
    assert seen_calls[0]["extra_body"] == {"reasoning": {"effort": "low", "exclude": True}}

    # Rodada 1: deduplicação e JSON inválido entregues ao modelo
    r2_tools = [m for m in seen_calls[2]["messages"] if m.get("role") == "tool"]
    assert "reutilize os dados já retornados" in r2_tools[1]["content"]
    assert "JSON inválido" in r2_tools[2]["content"]

    # Rodada 2 (última): omite tools para forçar síntese sem descartar as rodadas anteriores
    assert seen_calls[1]["tool_choice"] == "auto"
    assert "tools" not in seen_calls[2]
    assert "tool_choice" not in seen_calls[2]


def test_answer_with_tools_with_history_uses_auto_and_retries_bad_request(repo, monkeypatch):
    seen_calls: list[dict] = []
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    bad_req = openai.BadRequestError("unsupported extra_body", response=httpx.Response(400, request=req), body=None)

    class RetryCompletions:
        def create(self, **kwargs):
            seen_calls.append({**kwargs, "messages": list(kwargs["messages"])})
            if len(seen_calls) == 1:
                raise bad_req
            return _resp(content="Resposta após retry.\n\n**Ação:** Líder do hub deve revisar hoje.", tool_calls=None)

    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=RetryCompletions())),
    )

    settings = Settings(openrouter_api_key="k", chat_budget_s=10.0, llm_timeout_s=5.0)
    history = [ChatTurn(role="user", content="Oi"), ChatTurn(role="assistant", content="Olá")]
    out = answer_with_tools("E os hubs?", history, repo, Filters(), settings)
    assert out == ("Resposta após retry.\n\n**Ação:** Líder do hub deve revisar hoje.", [])
    assert seen_calls[0]["tool_choice"] == "auto"
    assert "extra_body" in seen_calls[0]
    assert "extra_body" not in seen_calls[1]


def test_empty_choices_falls_back_to_context_and_context_is_compact(client, repo, monkeypatch):
    captured_context_msgs: list[list[dict]] = []

    class MixedCompletions:
        def create(self, **kwargs):
            if "tools" in kwargs:
                return SimpleNamespace(choices=[], usage=None)
            captured_context_msgs.append(kwargs["messages"])
            return _resp(
                content="Resposta via contexto.\n\n**Ação:** Líder do hub deve revisar o SLA hoje.",
                tool_calls=None,
            )

    monkeypatch.setattr(
        "app.agent.llm._client",
        lambda settings, timeout=None: SimpleNamespace(chat=SimpleNamespace(completions=MixedCompletions())),
    )
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        openrouter_api_key="test-key", chat_budget_s=10.0, llm_timeout_s=5.0, chat_rate_limit_enabled=False
    )
    try:
        res = client.post(
            "/api/agent/chat",
            json={"question": "resumo do recorte"},
            headers={"X-Forwarded-For": "10.10.10.30"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["mode"] == "llm-context"
        assert "Resposta via contexto." in body["answer"]
        assert body["source"] == "llm"
        assert captured_context_msgs
        user_ctx = captured_context_msgs[0][-1]["content"]
        assert "<contexto_recorte>" in user_ctx
        assert "evidence" not in user_ctx
        assert len(user_ctx) < 7000  # antes era > 22.000 chars

        # Chamada direta a answer_with_context com choices=[] não levanta IndexError
        monkeypatch.setattr(
            "app.agent.llm._client",
            lambda settings, timeout=None: SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(choices=[])))
            ),
        )
        assert answer_with_context("resumo", [], repo, Filters(), get_settings()) is None
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
