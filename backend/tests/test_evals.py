"""Benchmark do agente (`evals/`): corretor, casos derivados dos dados e piso do agente local.

Sem rede e sem API key. O piso do agente local fica um pouco abaixo do medido no parquet
sintético: se cair, alguma regra do agente regrediu (ou um caso ficou mais exigente de propósito).
"""

from __future__ import annotations

import pytest

from app.filters import Filters
from app.schemas import ChatResponse, DrillDown, ReadingBase
from evals import grader
from evals.cases import CASES, Case, select
from evals.grader import (
    CaseNotApplicable,
    Entity,
    Expectations,
    NumberFact,
    extract_numbers,
    grade,
    parse_token,
)
from evals.run import main, render_markdown, run_suite

# Medido em 2026-11-18 no parquet sintético: aprovação 1,000 (45/45, com cmp-fds e cmp-jantar agora nas
# duas engines), nota média 1,000 (antes: 0,605 e 0,939). O piso tolera um caso a menos (44/45 = 0,978). Subiu com uma melhoria do agente? Suba o piso junto, para a melhoria não regredir calada.
LOCAL_PASS_FLOOR = 0.97
LOCAL_SCORE_FLOOR = 0.98


def _resp(answer: str, *, action: str = "", drills: list[DrillDown] | None = None, n: int = 0) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        mode="local",
        model=None,
        tools_used=[],
        title="t",
        diagnosis="",
        action=action,
        drilldowns=drills or [],
        base=ReadingBase(n=n, measured=n, low_sample=False),
        source="local",
    )


# ----------------------------------------------------------------- números pt-BR
@pytest.mark.parametrize(
    ("token", "value", "decimals"),
    [
        ("82,4", 82.4, 1),
        ("1.234,56", 1234.56, 2),
        ("1.234", 1234.0, 0),
        ("368.990", 368990.0, 0),
        ("34.728.612,77", 34728612.77, 2),
        ("82.4", 82.4, 1),  # en-US também é lido, o aviso de formato é outra verificação
        ("1,234.5", 1234.5, 1),
        ("38", 38.0, 0),
    ],
)
def test_parse_token(token, value, decimals):
    assert parse_token(token) == pytest.approx((value, decimals))


def test_extract_numbers_units():
    text = "SLA 82,4% · GMV R$ 1.234,56 · ciclo 38 min · −1,6 p.p. vs anterior · 1.234 pedidos · 369 mil entregas"
    found = {(n.unit, round(n.value, 2)) for n in extract_numbers(text)}
    assert ("pct", 82.4) in found
    assert ("brl", 1234.56) in found
    assert ("min", 38.0) in found
    assert ("pp", -1.6) in found
    assert ("count", 1234.0) in found
    assert ("count", 369000.0) in found


def test_extract_numbers_ignores_dates_and_hours():
    numbers = extract_numbers("Recorte de 01/03/2021 a 31/03/2021, pico às 19h")
    assert all(n.unit != "count" for n in numbers)
    assert any(n.unit == "h" and n.value == 19 for n in numbers)


@pytest.mark.parametrize(
    ("text", "fact", "ok"),
    [
        ("SLA de 82,4%", NumberFact("sla", 82.43, "pct"), True),
        ("SLA de 82%", NumberFact("sla", 82.43, "pct"), True),  # menos casas, meia unidade de folga
        ("SLA de 81,9%", NumberFact("sla", 82.43, "pct"), False),
        ("caiu 1,6 p.p.", NumberFact("delta", -1.6, "pp"), True),  # sinal em palavra
        ("variação de −1,6 pontos percentuais", NumberFact("delta", -1.6, "pp"), True),
        ("subsídio de R$ 1,31", NumberFact("sub", 1.312, "brl"), True),
        ("GMV de R$ 34,7 milhões", NumberFact("gmv", 34_728_612.77, "brl"), True),
        ("ciclo mediano 41,2 min", NumberFact("ciclo", 41.18, "min"), True),
        ("41,2 min", NumberFact("ciclo", 41.18, "pct"), False),  # unidade errada não casa
        ("368.990 pedidos", NumberFact("n", 368_990, "count"), True),
        ("R$ 368.990", NumberFact("n", 368_990, "count"), False),
    ],
)
def test_number_matching(text, fact, ok):
    assert grader.number_found(fact, extract_numbers(text), text) is ok


def test_number_near_entity():
    text = "Rede com 80,0% no prazo.\n- Hub Alfa: 91,0% · 300 pedidos\n- Hub Beta: 80,0% · 200 pedidos"
    assert grader.number_found(NumberFact("a", 80.0, "pct", near="Hub Beta"), extract_numbers(text), text)
    assert not grader.number_found(NumberFact("a", 80.0, "pct", near="Hub Alfa"), extract_numbers(text), text)


def test_en_us_format_warns():
    assert grader.en_us_hits("SLA de 82.4% e R$ 1,234.56")
    assert grader.en_us_hits("ciclo de 38.5 min")
    assert not grader.en_us_hits("SLA de 82,4%, R$ 1.234,56, 1.234 pedidos, 38,5 min")


# ----------------------------------------------------------------- entidades e termos
def test_entity_matching_accent_and_case_insensitive():
    resp = _resp("O pior hub é o SAO PAULO CENTRO, com loja 25 atrás.")
    text = grader.norm(grader.visible_text(resp))
    assert grader.entity_found(Entity("hub", 1, "São Paulo Centro"), text, resp)
    assert grader.entity_found(Entity("store", 25, "Loja 25"), text, resp)
    assert not grader.entity_found(Entity("store", 2, "Loja 2"), text, resp)  # "Loja 25" não prova a "Loja 2"


def test_entity_found_in_drilldown():
    resp = _resp("Sem nome no texto.", drills=[DrillDown(label="Ver só", filters={"hub": [8]})])
    text = grader.norm(resp.answer)
    assert grader.entity_found(Entity("hub", 8, "Hub Oito"), text, resp)
    assert not grader.entity_found(Entity("hub", 9, "Hub Nove"), text, resp)


def test_hour_entity():
    text = grader.norm("Pior faixa: 19h–21h. Às 9h tudo bem.")
    assert grader.entity_in_text(Entity("hour", 19, "19h"), text)
    assert grader.entity_in_text(Entity("hour", 21, "21h"), text)
    assert grader.entity_in_text(Entity("hour", 9, "09h"), text)
    assert not grader.entity_in_text(Entity("hour", 1, "01h"), grader.norm("às 19h e 21h"))


def test_forbidden_terms():
    hits = grader.forbidden_hits("Alerta high no hub; usei get_breakdown. Fluxo ok.", list(grader.DEFAULT_FORBID))
    assert "'high'" in hits and "'get_breakdown'" in hits
    assert not grader.forbidden_hits("Fluxo baixo, loja Highway", ["low", "high"])  # só palavra inteira
    assert grader.forbidden_hits("nota média de 4,5", ["re:nota (media )?(de )?\\d"])
    # termo que é parte de um nome do dado fica de fora
    assert not grader.forbidden_hits("Loja Low Cost cancelou", ["low"], skip_words=frozenset({"low"}))


@pytest.mark.parametrize(
    "token",
    ["drill_cause", "explain_change", "get_timeseries", "get_kpis", "get_alerts", "query_metrics",
     "volume_low_sample", "low_sample", "sla_below", "cancel_above"],
)
def test_default_forbid_catches_raw_tool_and_flag_names(token):
    assert f"'{token}'" in grader.forbidden_hits(f"Hub 8 marcado com {token}, olhe.", grader.DEFAULT_FORBID)


def test_default_forbid_spares_natural_ptbr():
    # O que esses tokens viram em prosa: nenhum deles casa como termo inteiro.
    text = (
        "Amostra pequena no hub 8, trate como indício. SLA abaixo da média e cancelamento acima "
        "do recorte; a série diária mostra a queda. Explicação da mudança: a etapa de expedição "
        "puxa o ciclo. Alertas e KPIs do recorte conferem."
    )
    assert grader.forbidden_hits(text, grader.DEFAULT_FORBID) == []
    # `low_sample` dentro de `volume_low_sample` acusa só o termo inteiro, sem dupla contagem.
    assert grader.forbidden_hits("flag volume_low_sample", ["low_sample", "volume_low_sample"]) == ["'volume_low_sample'"]


def test_raw_json_outside_fence_is_forbidden(repo):
    fenced = _resp('Texto.\n\n**Ação:** x.\n\n```leitura\n{"title":"a","diagnosis":"b","action":"c"}\n```', action="x")
    raw = _resp('Texto {"title": "a"}\n\n**Ação:** x.', action="x")
    exp = Expectations(require_action=False)
    assert grader.check_forbidden(fenced, exp, grader.visible_text(fenced), repo).passed
    assert not grader.check_forbidden(raw, exp, grader.visible_text(raw), repo).passed


# ----------------------------------------------------------------- ação, atalhos, escopo, nota
def test_action_check(repo):
    hub = repo.meta()["hubs"][0]["label"]
    exp = Expectations()
    good = _resp(f"Diag.\n\n**Ação:** Líder do hub {hub} deve reforçar a frota às 19h.", action=f"Líder do hub {hub} deve reforçar a frota às 19h.")
    generic = _resp("Diag.\n\n**Ação:** Time deve acompanhar hoje.", action="Time deve acompanhar hoje.")
    missing = _resp("Só diagnóstico.", action="")
    assert grader.check_action(good, exp, repo).passed
    c = grader.check_action(generic, exp, repo)
    assert not c.passed and c.score == pytest.approx(2 / 3) and "genérica" in c.reason
    assert grader.check_action(missing, exp, repo).score == 0
    assert grader.check_action(generic, Expectations(specific_action=False), repo).passed


def test_drilldown_validation(repo):
    hub = int(repo.meta()["hubs"][0]["value"])
    ok = _resp("x", drills=[DrillDown(label="a", filters={"hub": [hub], "segment": ["food"]})])
    bad = _resp("x", drills=[
        DrillDown(label="a", filters={"hub": [999_999]}),
        DrillDown(label="b", filters={"start": ["2021-01-01"]}),
        DrillDown(label="c", filters={"modal": ["carro"]}),
    ])
    assert grader.check_drilldowns(ok, repo).passed
    problems = grader.drilldown_problems(bad, repo)
    assert len(problems) == 3


def test_scope_check(repo):
    total = repo.metrics(Filters())["orders"]
    assert grader.check_scope(_resp("x", n=total), repo, Filters()).passed
    assert not grader.check_scope(_resp("x", n=total - 1), repo, Filters()).passed


def test_scoring_math(repo):
    g = grader.Grade([
        grader.Check("a", 1.0, 2.0),
        grader.Check("b", 0.5, 2.0),
        grader.Check("c", 0.0, 1.0, level="warn"),
    ])
    assert g.score == pytest.approx((2 + 1 + 0) / 5)
    assert not g.passed  # "b" é erro e ficou abaixo de 1
    warn_only = grader.Grade([grader.Check("a", 1.0, 2.0), grader.Check("c", 0.0, 1.0, level="warn")])
    assert warn_only.passed and warn_only.score == pytest.approx(2 / 3)


def test_grade_end_to_end(repo):
    m = repo.metrics(Filters())
    hub = repo.meta()["hubs"][0]
    answer = (
        f"SLA {m['sla_rate'] * 100:.1f}% no recorte.".replace(".", ",", 1)
        + f"\n\n**Ação:** Líder do hub {hub['label']} deve revisar a expedição às 12h."
    )
    resp = _resp(answer, action=f"Líder do hub {hub['label']} deve revisar a expedição às 12h.", n=m["orders"])
    exp = Expectations(
        entities=[Entity("hub", hub["value"], hub["label"])],
        numbers=[NumberFact("sla", m["sla_rate"] * 100, "pct")],
        must_mention=[("sla",)],
    )
    g = grade(resp, exp, repo, Filters(), latency_s=0.1, default_max_latency_s=5)
    assert g.passed, [c.reason for c in g.failures]
    assert g.score == pytest.approx(1.0)


# ----------------------------------------------------------------- casos
def test_suite_shape():
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))
    assert 30 <= len(CASES) <= 45
    assert all(set(c.engines) <= {"local", "llm"} and c.engines for c in CASES)
    assert {c.category for c in CASES} >= {
        "overview", "sla", "cancelamento", "etapas", "frete", "volume", "pagamento",
        "comparacao", "por-que", "drill", "fora-escopo", "injecao", "vazio",
    }
    assert select(CASES, "why-*") and all(c.id.startswith("why-") for c in select(CASES, "why-*"))
    assert all("local" in c.engines for c in select(CASES, None, engine_tag="local"))


def test_cases_have_no_fixed_entity_names():
    """Perguntas e regras dos casos não podem citar hub, loja ou cidade do dado."""
    import inspect

    from evals import cases

    source = inspect.getsource(cases)
    for name in ("Hub Centro", "Hub Lento", "Hub Preso", "Hub Goods", "Loja Quebrada", "São Paulo", "Curitiba",
                 "Golden Shopping", "Rio de Janeiro", "Porto Alegre"):
        assert name not in source


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case_builds_on_synthetic(case: Case, repo):
    try:
        f, question, exp = case.build(repo)
    except CaseNotApplicable as exc:  # pragma: no cover - o sintético foi montado para cobrir todos
        pytest.fail(f"{case.id} não se aplica ao parquet sintético: {exc}")
    assert question.strip()
    assert isinstance(f, Filters)
    meta = repo.meta()
    known = {
        "hub": {int(h["value"]) for h in meta["hubs"]},
        "store": {int(s["value"]) for s in meta["stores"]},
        "city": {str(c["value"]) for c in meta["cities"]},
    }
    for req in exp.entities:
        for e in (req if isinstance(req, tuple) else (req,)):
            assert e.label
            if e.dimension in known:
                assert (int(e.key) if e.dimension != "city" else str(e.key)) in known[e.dimension], e
    for req in exp.numbers:
        for n in (req if isinstance(req, tuple) else (req,)):
            assert n.value == n.value  # não é NaN


def test_planted_scenarios_drive_expectations(repo):
    """A verdade dos casos acompanha os cenários plantados do conftest."""
    by_id = {c.id: c for c in CASES}
    _, _, broken = by_id["cancel-quebrada"].build(repo)
    labels = {e.label for e in broken.entities[0]}
    assert "Loja Quebrada" in labels  # loja 30 cancela tudo
    _, _, worst = by_id["sla-pior-hub"].build(repo)
    assert "Hub Lento" in {e.label for e in worst.entities[0]} or "Hub Preso" in {e.label for e in worst.entities[0]}


# ----------------------------------------------------------------- piso do agente local
def test_local_baseline_floor(repo, capsys):
    from app.config import get_settings

    cases = select(CASES, None, engine_tag="local")
    suite = run_suite(repo, get_settings(), cases, engine="local", max_latency_s=5.0)
    s = suite.summary()
    with capsys.disabled():
        # ASCII: fora da captura do pytest o console do Windows não é UTF-8.
        print(f"\n[evals] local baseline (synthetic): pass_rate={s['pass_rate']:.3f} mean_score={s['mean_score']:.3f} "
              f"cases={s['cases']} failed_checks={s['failed_checks']}")
    assert not suite.skipped, suite.skipped
    assert not [r for r in suite.results if r.error], [r.error for r in suite.results if r.error]
    # Toda resposta do agente local fecha com ação e respeita o recorte.
    for r in suite.results:
        names = {c["name"]: c for c in r.checks}
        assert names["scope"]["score"] == 1, (r.case_id, names["scope"]["reason"])
        assert names["forbidden"]["score"] == 1, (r.case_id, names["forbidden"]["reason"])
        assert names["drilldowns"]["score"] == 1, (r.case_id, names["drilldowns"]["reason"])
    assert s["pass_rate"] >= LOCAL_PASS_FLOOR
    assert s["mean_score"] >= LOCAL_SCORE_FLOOR
    assert "## Resumo" in render_markdown(suite)


def test_runner_writes_markdown(parquet_path, tmp_path):
    out = tmp_path / "placar.md"
    js = tmp_path / "placar.json"
    suite = main(["--engine", "local", "--data", str(parquet_path), "--cases", "overview,vazio",
                  "--out", str(out), "--json", str(js), "--quiet"])
    text = out.read_text(encoding="utf-8")
    assert "# Placar do agente de insights" in text
    assert "| Taxa de aprovação |" in text
    assert "ov-geral" in text and "empty-periodo" in text
    assert js.exists() and '"pass_rate"' in js.read_text(encoding="utf-8")
    assert {r.category for r in suite.results} == {"overview", "vazio"}
