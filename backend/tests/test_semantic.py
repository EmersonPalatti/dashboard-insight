"""Camada semântica: casa com o SQL, resolve o vocabulário do operador e recusa TOML inconsistente."""

from __future__ import annotations

import copy
import re
import tomllib
from collections.abc import Callable
from typing import Any, get_args

import pytest

from app import fmt, repository, semantic
from app.alerts import CANCEL_HIGH, CANCEL_WARN, SLA_HIGH, SLA_WARN, STUCK_WARN, SUBSIDY_WARN
from app.config import Settings, get_settings
from app.filters import ChannelType, Modal, Segment
from scripts.build_parquet import AMOUNT_OUTLIER, STUCK_CYCLE_MIN

FLAGS = {"low_sample", "volume_low_sample"}


@pytest.fixture(scope="module")
def layer() -> semantic.SemanticLayer:
    return semantic.load()


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    return tomllib.loads(semantic.SOURCE.read_text(encoding="utf-8"))


def _columns(repo, sql: str) -> set[str]:
    return {d[0] for d in repo._con.execute(f"select {sql} from orders limit 0").description}


def _keys(matches: list[semantic.Match]) -> list[tuple[str, str]]:
    return [(m.kind, m.key) for m in matches]


# ------------------------------------------------------------------ contrato com o SQL


def test_metrics_match_metrics_sql(layer, repo):
    columns = _columns(repo, repository.METRICS_SQL)
    assert set(layer.metric_keys(include_extra=False)) == columns - FLAGS
    assert not {m.key for m in layer.metrics.values() if not m.extra} & FLAGS


def test_extra_metrics_match_extra_sql(layer, repo):
    extra = {m.key for m in layer.metrics.values() if m.extra}
    assert extra == {"chargeback_rate", "multi_attempt_rate", "walking_p50"}
    extra_sql = getattr(repository, "EXTRA_METRICS_SQL", None)
    if extra_sql is not None:
        assert _columns(repo, extra_sql) == extra
    query_metrics = getattr(repository, "QUERY_METRICS", None)
    if query_metrics is not None:
        assert set(query_metrics) == set(layer.metrics)


def test_dimensions_match_repository(layer):
    assert set(layer.dimensions) == set(repository.DIMENSIONS)
    with_id = {k for k, (column, _label, _parent) in repository.DIMENSIONS.items() if column.endswith("_id")}
    assert {k for k, d in layer.dimensions.items() if d.has_id} == with_id


def test_enum_values_match_filters(layer):
    for key, literal in (("segment", Segment), ("channel_type", ChannelType), ("modal", Modal)):
        assert set(layer.dimensions[key].values) == set(get_args(literal))
    assert set(layer.dimensions["weekday"].values) == {str(d) for d in range(7)}
    # Rótulo de exibição igual ao do painel quando o painel tem um.
    for key in ("segment", "channel_type", "modal"):
        for code, label in layer.dimensions[key].values.items():
            assert label == repository.VALUE_LABELS[code]


def test_rate_numerator_is_count_column(layer):
    assert layer.metrics["cancel_rate"].numerator == "canceled"
    for m in layer.metrics.values():
        assert (m.kind == "rate") == (m.unit == "pct")


def test_causal_links_point_to_known_keys(layer):
    assert {"sla_rate", "cycle_p50", "cancel_rate", "subsidy", "orders"} <= set(layer.causal)
    for link in layer.causal.values():
        assert link.effect in layer.metrics
        assert all(d in layer.metrics and d != link.effect for d in link.drivers)
        assert link.dimensions and all(d in layer.dimensions for d in link.dimensions)
    assert layer.causal["sla_rate"].drivers[0] == "stuck_rate"
    assert "modal" not in layer.causal["cancel_rate"].dimensions
    assert layer.causal["cancel_rate"].dimensions[:2] == ("store", "hub")


def test_business_numbers_follow_the_code(layer):
    """Se uma régua mudar no código, o texto do agente tem que mudar junto (regra 7)."""
    settings = Settings()
    sla = layer.metrics["sla_rate"].definition
    assert f"{settings.sla_food_min} min" in sla and f"{settings.sla_good_min} min" in sla
    segment = layer.dimensions["segment"].definition
    assert f"{settings.sla_food_min} min" in segment and f"{settings.sla_good_min} min" in segment
    block = layer.prompt_block()
    assert "{sla_food_min}" not in block and "{sla_good_min}" not in block
    assert f"{STUCK_CYCLE_MIN // 60}h" in layer.concepts["pedido_preso"].definition
    assert f"R$ {AMOUNT_OUTLIER // 1000} mil" in layer.metrics["gmv"].definition
    assert str(repository.MIN_MEASURED) in layer.concepts["amostra_pequena"].definition
    reguas = layer.concepts["reguas"].definition
    for value in (SLA_HIGH, SLA_WARN, CANCEL_HIGH, CANCEL_WARN, STUCK_WARN):
        assert fmt.pct(value, 0) in reguas
    assert f"presos ≥ {fmt.pct(STUCK_WARN, 0)}" in reguas
    assert f"R$ {SUBSIDY_WARN:g}" in reguas
    desvio = layer.concepts["desvio"].definition
    assert f"{repository.SLA_BELOW_GAP * 100:g} p.p." in desvio
    assert fmt.decimal(repository.CANCEL_ABOVE_RATIO, 1) + "×" in desvio
    assert fmt.pct(repository.CANCEL_ABOVE_FLOOR, 0) in desvio


def test_parse_substitutes_sla_placeholders():
    parsed = semantic.parse(semantic.SOURCE.read_text(encoding="utf-8"), sla_food_min=45, sla_good_min=90)
    sla = parsed.metrics["sla_rate"].definition
    segment = parsed.dimensions["segment"].definition
    assert "45 min" in sla and "90 min" in sla
    assert "45 min" in segment and "90 min" in segment
    assert "60 min" not in sla and "120 min" not in sla
    assert "60 min" not in segment and "120 min" not in segment


def test_load_uses_sla_minutes_from_settings(monkeypatch):
    try:
        with monkeypatch.context() as mp:
            mp.setenv("SLA_FOOD_MIN", "45")
            mp.setenv("SLA_GOOD_MIN", "90")
            get_settings.cache_clear()
            semantic.load.cache_clear()
            loaded = semantic.load()
            assert "45 min" in loaded.metrics["sla_rate"].definition
            assert "90 min" in loaded.metrics["sla_rate"].definition
            assert "45 min" in loaded.dimensions["segment"].definition
            assert "90 min" in loaded.dimensions["segment"].definition
    finally:
        get_settings.cache_clear()
        semantic.load.cache_clear()


def test_examples_cover_the_core_questions(layer):
    assert 8 <= len(layer.examples) <= 12
    plans = " ".join(e.plan for e in layer.examples)
    for tool in ("explain_change", "drill_cause", "query_metrics", "get_alerts", "get_kpis", "get_timeseries"):
        assert tool in plans
    # Janela e comparação com o resto são o jeito novo de recortar almoço, jantar e fim de semana.
    assert "window:" in plans and "compare=rest" in plans


def test_example_plans_only_name_tools_the_llm_has(layer):
    from app.agent.llm import TOOLS

    names = {t["function"]["name"] for t in TOOLS}
    for ex in layer.examples:
        named = set(re.findall(r"\b([a-z]+(?:_[a-z0-9]+)+)\(", ex.plan))
        named |= set(re.findall(r"\b((?:get|compare|query|explain|drill)_[a-z_]+)\b", ex.plan))
        assert named, f"plano sem nenhuma ferramenta: {ex.question}"
        assert named <= names, (ex.question, sorted(named - names))


# ------------------------------------------------------------------ resolve


def test_resolve_delay_at_dinner(layer):
    matches = layer.resolve("por que o atraso subiu no jantar?")
    keys = _keys(matches)
    assert ("metric", "sla_rate") in keys
    assert ("concept", "jantar") in keys
    assert keys.index(("metric", "sla_rate")) < keys.index(("concept", "jantar"))
    assert layer.concepts["jantar"].hours == (18, 19, 20, 21)


def test_resolve_ignores_accents_and_case(layer):
    assert _keys(layer.resolve("CANCELAMENTO por Loja")) == [("metric", "cancel_rate"), ("dimension", "store")]
    assert _keys(layer.resolve("cancelámento POR lója")) == [("metric", "cancel_rate"), ("dimension", "store")]


def test_resolve_folds_simple_plurals(layer):
    assert _keys(layer.resolve("lojas")) == [("dimension", "store")]
    assert ("dimension", "channel") in _keys(layer.resolve("quais canais vendem mais"))
    assert ("dimension", "city") in _keys(layer.resolve("comparar regiões"))


def test_resolve_whole_words_only(layer):
    assert ("dimension", "modal") in _keys(layer.resolve("a bike atrasou"))
    assert not layer.resolve("bikeiro")
    assert not layer.resolve("fdsa motoboyzinho")
    # Número solto não vira dia da semana nem hora.
    assert _keys(layer.resolve("hub 4")) == [("dimension", "hub")]


def test_resolve_longest_phrase_wins(layer):
    assert _keys(layer.resolve("taxa de entrega")) == [("metric", "fee_avg")]
    assert _keys(layer.resolve("quantidade de cancelamentos")) == [("metric", "canceled")]
    assert _keys(layer.resolve("tempo de trânsito por modal")) == [
        ("metric", "transit_p50"),
        ("dimension", "modal"),
    ]


def test_resolve_has_no_duplicates(layer):
    matches = layer.resolve("atraso, atrasado e fora do prazo: SLA")
    assert _keys(matches) == [("metric", "sla_rate")]
    assert matches[0].term == "atraso"


def test_resolve_dimension_value_and_window(layer):
    keys = _keys(layer.resolve("jantar de sexta"))
    assert keys == [("concept", "jantar"), ("dimension", "weekday")]
    assert layer.value_code("weekday", "sexta") == "4"
    assert layer.value_code("channel_type", "canal próprio") == "own"
    assert layer.value_code("weekday", "feriado") is None
    assert _keys(layer.resolve("fim de semana vs dias úteis")) == [
        ("concept", "fim_de_semana"),
        ("concept", "dias_uteis"),
    ]
    assert layer.concepts["fim_de_semana"].weekdays == (5, 6)


def test_resolve_same_term_in_two_kinds(layer):
    keys = _keys(layer.resolve("quanto custa o frete subsidiado?"))
    assert ("metric", "subsidy") in keys and ("concept", "subsidio_frete") in keys
    assert ("metric", "chargeback_rate") in _keys(layer.resolve("chargeback por forma de pagamento"))
    assert ("dimension", "payment_method") in _keys(layer.resolve("chargeback por forma de pagamento"))


# ------------------------------------------------------------------ prompt e describe


def test_prompt_block_is_small_and_complete(layer):
    block = layer.prompt_block()
    assert len(block) <= semantic.PROMPT_LIMIT
    for key in layer.metrics:
        assert f"`{key}`" in block
    for key in layer.dimensions:
        assert key in block
    for key in layer.causal:
        assert f"`{key}` ←" in block
    assert "jantar 18h–22h" in block and "fim de semana sáb/dom" in block


def test_describe_every_key(layer):
    for key in (*layer.metrics, *layer.dimensions, *layer.concepts):
        text = layer.describe(key)
        assert text and "\n" not in text
    assert "base: entregues sem preso e com ciclo registrado" in layer.describe("sla_rate")
    assert layer.describe("nao_existe") is None


def test_metric_keys_filters(layer):
    medians = layer.metric_keys(kind="median")
    assert "production_p50" in medians and "walking_p50" in medians
    assert "walking_p50" not in layer.metric_keys(kind="median", include_extra=False)
    assert layer.metric_keys(kind="quantile") == ["cycle_p90"]


# ------------------------------------------------------------------ validação


def _set(path: str, value: Any) -> Callable[[dict], None]:
    def mutate(data: dict) -> None:
        *parents, last = path.split(".")
        node = data
        for part in parents:
            node = node[part]
        node[last] = value
    return mutate


def _too_long(data: dict) -> None:
    data["metrics"]["orders"]["definition"] = "x" * semantic.PROMPT_LIMIT


INVALID: list[tuple[str, Callable[[dict], None], str]] = [
    ("unit", _set("metrics.orders.unit", "reais"), "unit"),
    ("kind", _set("metrics.orders.kind", "mode"), "kind"),
    ("better", _set("metrics.orders.better", "higher"), "better"),
    ("base", _set("metrics.orders.base", "everything"), "base"),
    ("rate sem pct", _set("metrics.cancel_rate.unit", "count"), "rate"),
    ("numerator", _set("metrics.cancel_rate.numerator", "gmv"), "numerator"),
    ("campo", _set("metrics.orders.formula", "count(*)"), "campo desconhecido"),
    ("maiúscula", _set("metrics.orders.synonyms", ["Volume"]), "minúsculas"),
    ("sinônimo duplo", _set("metrics.gmv.synonyms", ["volume"]), "dois metrics"),
    ("plural duplo", _set("dimensions.hub.synonyms", ["restaurantes"]), "dois dimensions"),
    ("driver", _set("causal.sla_rate.drivers", ["mood"]), "drivers"),
    ("efeito", _set("causal.mood", {"drivers": [], "dimensions": ["hub"], "note": "x"}), "efeito"),
    ("dimensão causal", _set("causal.sla_rate.dimensions", ["planet"]), "dimensions"),
    ("related", _set("concepts.pico.related", ["nada"]), "related"),
    ("hora", _set("concepts.jantar.hours", [25]), "hours"),
    ("base faltando", _set("bases", {"orders": "todos"}), "bases"),
    ("seção", _set("glossary", {}), "seção"),
    ("chave em dois tipos", _set("concepts.hub", {"label": "Hub", "definition": "x", "synonyms": []}), "repetida"),
    ("tamanho", _too_long, "prompt_block"),
]


@pytest.mark.parametrize(("case", "mutate", "message"), INVALID, ids=[c[0] for c in INVALID])
def test_invalid_content_raises(raw, case, mutate, message):
    data = copy.deepcopy(raw)
    mutate(data)
    with pytest.raises(ValueError, match=message):
        semantic._build(data)


def test_invalid_toml_syntax_raises():
    with pytest.raises(ValueError):
        semantic.parse("[metrics.orders\nlabel = ")


def test_source_builds_without_mutation(raw):
    assert semantic._build(copy.deepcopy(raw)).metrics.keys() == semantic.load().metrics.keys()


def test_window_text_formats_hours_and_weekdays():
    assert semantic.window_text((18, 19, 20, 21)) == "18h–22h"
    assert semantic.window_text((0, 1, 2, 3, 4, 5)) == "0h–6h"
    assert semantic.window_text(weekdays=(5, 6)) == "sáb/dom"
    assert semantic.window_text(weekdays=(0, 1, 2, 3, 4)) == "seg–sex"
    assert semantic.window_text(weekdays=(4, 0, 2)) == "seg/qua/sex"
    assert semantic.window_text((18, 19, 20, 21), (4,)) == "18h–22h sex"
