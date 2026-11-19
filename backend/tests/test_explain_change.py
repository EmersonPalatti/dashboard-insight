"""Decomposição "por que mudou" (app.analytics.explain_change) sobre o parquet sintético.

Semana 08–14/03 contra 01–07/03: a loja 25 (45% de cancelamento) só existe na semana atual e as
lojas de 03/03 (33, 38… muito cancelamento) só na anterior. Há movimento real nos dois sentidos.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.analytics import OTHERS_LABEL, drill_cause, explain_change
from app.filters import Filters

MARCH_WEEK = Filters(start=date(2021, 3, 8), end=date(2021, 3, 14))


def _contrib_sum(result: dict) -> float:
    return sum(d["contribution"] for d in result["drivers"])


@pytest.mark.parametrize("metric", ["cancel_rate", "sla_rate", "stuck_rate"])
@pytest.mark.parametrize("by", ["hub", "store"])
def test_shift_share_sums_exactly_to_total_delta(repo, metric, by):
    result = explain_change(repo, MARCH_WEEK, metric=metric, by=by, limit=50, min_orders=0)
    assert result["method"] == "shift_share"
    prev = repo.previous_period(MARCH_WEEK)
    assert result["previous_period"] == {"start": prev[0], "end": prev[1]}
    total = result["total"]
    assert total["current"] == pytest.approx(repo.metrics(MARCH_WEEK)[metric], abs=1e-12)
    assert total["previous"] == pytest.approx(repo.metrics(MARCH_WEEK.with_period(*prev))[metric], abs=1e-12)
    assert abs(total["delta"]) > 0.01  # há movimento de verdade para decompor
    drivers = result["drivers"]
    assert all(d["label"] != OTHERS_LABEL for d in drivers)
    assert abs(sum(d["rate_effect"] + d["mix_effect"] for d in drivers) - total["delta"]) < 1e-9
    assert abs(_contrib_sum(result) - total["delta"]) < 1e-9
    assert sum(d["share_of_change"] for d in drivers) == pytest.approx(1.0)
    assert sum(d["weight_current"] for d in drivers) == pytest.approx(1.0)
    assert sum(d["weight_previous"] for d in drivers) == pytest.approx(1.0)


def test_group_only_in_one_period_is_pure_mix(repo):
    result = explain_change(repo, MARCH_WEEK, metric="cancel_rate", by="store", limit=50, min_orders=0)
    for d in result["drivers"]:
        if d["presence"] in ("current_only", "previous_only"):
            assert d["rate_effect"] == 0
            assert d["weight_current" if d["presence"] == "previous_only" else "weight_previous"] == 0


def test_planted_store_is_top_cancel_driver(repo):
    result = explain_change(repo, MARCH_WEEK, metric="cancel_rate", by="store")
    top = result["drivers"][0]
    assert top["key"] == 25 and top["label"] == "Loja 25"
    assert top["presence"] == "current_only"
    assert top["current"] == pytest.approx(0.45)
    assert top["orders_current"] == 200 and top["orders_previous"] == 0
    # a loja nova puxa o cancelamento para cima mesmo com a semana caindo no total
    assert top["contribution"] > 0 > result["total"]["delta"]
    assert 0 < result["concentration"]["top1"] <= result["concentration"]["top3"] <= 1


def test_vanished_bad_store_counts_in_favor(repo):
    """Loja 28 (03/03, 100 medidos e todos atrasados) sai da conta: isso sobe o SLA."""
    result = explain_change(repo, MARCH_WEEK, metric="sla_rate", by="store", limit=50, min_orders=0)
    store_28 = next(d for d in result["drivers"] if d["key"] == 28)
    assert store_28["presence"] == "previous_only" and store_28["previous"] == 0
    assert store_28["contribution"] > 0


def test_additive_orders_by_store_is_exact(repo):
    prev = repo.previous_period(MARCH_WEEK)
    result = explain_change(repo, MARCH_WEEK, metric="orders", by="store", limit=50, min_orders=0)
    assert result["method"] == "additive"
    expected = repo.metrics(MARCH_WEEK)["orders"] - repo.metrics(MARCH_WEEK.with_period(*prev))["orders"]
    assert result["total"]["delta"] == expected
    assert _contrib_sum(result) == expected
    assert all(d["rate_effect"] is None and d["mix_effect"] is None for d in result["drivers"])


@pytest.mark.parametrize("metric", ["orders", "cancel_rate", "sla_rate"])
def test_others_bucket_keeps_sums_exact(repo, metric):
    full = explain_change(repo, MARCH_WEEK, metric=metric, by="store", limit=50, min_orders=0)
    result = explain_change(repo, MARCH_WEEK, metric=metric, by="store", limit=2, min_orders=0)
    drivers = result["drivers"]
    assert len(drivers) == 3 and drivers[-1]["label"] == OTHERS_LABEL
    assert drivers[-1]["groups"] == result["n_groups"] - 2
    assert [d["key"] for d in drivers[:2]] == [d["key"] for d in full["drivers"][:2]]
    assert abs(_contrib_sum(result) - result["total"]["delta"]) < 1e-9
    assert sum(d["orders_current"] for d in drivers) == repo.metrics(MARCH_WEEK)["orders"]


def test_small_groups_fold_into_others(repo):
    result = explain_change(repo, MARCH_WEEK, metric="cancel_rate", by="store", limit=50, min_orders=150)
    named = [d for d in result["drivers"] if d["label"] != OTHERS_LABEL]
    assert named and all(max(d["orders_current"], d["orders_previous"]) >= 150 for d in named)
    others = result["drivers"][-1]
    assert others["label"] == OTHERS_LABEL and others["groups"] == result["n_groups"] - len(named)
    assert abs(_contrib_sum(result) - result["total"]["delta"]) < 1e-9
    everything = explain_change(repo, MARCH_WEEK, metric="cancel_rate", by="store", min_orders=10_000)
    assert [d["label"] for d in everything["drivers"]] == [OTHERS_LABEL]
    assert abs(everything["drivers"][0]["contribution"] - everything["total"]["delta"]) < 1e-9
    assert everything["drivers"][0]["current"] == pytest.approx(everything["total"]["current"])


def test_median_is_approx_with_note(repo):
    result = explain_change(repo, MARCH_WEEK, metric="cycle_p50", by="hub")
    assert result["method"] == "approx"
    assert "não se decompõe" in result["note"]
    prev = repo.previous_period(MARCH_WEEK)
    assert result["total"]["current"] == pytest.approx(repo.metrics(MARCH_WEEK)["cycle_p50"])
    assert result["total"]["previous"] == pytest.approx(repo.metrics(MARCH_WEEK.with_period(*prev))["cycle_p50"])
    for d in result["drivers"]:
        assert d["share_of_change"] is None and d["rate_effect"] is None
        if d["delta"] is not None:
            assert d["contribution"] == pytest.approx(d["delta"] * d["weight_current"])


def test_previous_period_unavailable_returns_error_dict(repo):
    for f in (Filters(start=date(2021, 1, 1), end=date(2021, 1, 7)), Filters()):
        result = explain_change(repo, f, metric="cancel_rate", by="hub")
        assert result["previous_period"] is None
        assert "anterior" in result["error"]
        assert "drivers" not in result


def test_period_without_base_returns_error_dict(repo):
    # Hub 3 não tem pedido em 08–14/03: sem base no período atual.
    result = explain_change(repo, MARCH_WEEK.model_copy(update={"hub": [3]}), metric="sla_rate", by="store")
    assert "error" in result and "drivers" not in result


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"metric": "nope", "by": "hub"}, "Métrica desconhecida"), ({"metric": "orders", "by": "state"}, "Dimensão")],
)
def test_validation_errors(repo, kwargs, message):
    with pytest.raises(ValueError, match=message):
        explain_change(repo, MARCH_WEEK, **kwargs)


def test_drill_cause_finds_slow_transit_in_slow_hub(repo):
    """Hub 2 ("Hub Lento") tem trânsito +40 min na base de jan–fev."""
    f = Filters(start=date(2021, 1, 22), end=date(2021, 2, 10))
    result = drill_cause(repo, f, metric="sla_rate", group={"hub": ["hub lento"]})
    assert result["group"] == {"hub": ["hub lento"]}
    assert result["top_stage_vs_rest"] == "transit_p50"
    transit = next(s for s in result["stages"] if s["metric"] == "transit_p50")
    assert transit["vs_rest"] > 30
    assert result["headline"]["vs_rest"] < 0  # SLA do hub abaixo do resto
    assert result["previous_period"] is not None and result["sample"]["previous"]["orders"] > 0


def test_drill_cause_without_slower_stage(repo):
    """Loja 46 atrasa com etapas curtas: nenhuma etapa explica (cenário sla-hub sem etapa)."""
    f = Filters(start=date(2021, 3, 26), end=date(2021, 3, 31))
    result = drill_cause(repo, f, metric="sla_rate", group={"store": [46]})
    assert result["headline"]["current"] == 0
    assert result["top_stage_vs_rest"] is None
    assert all(s["vs_rest"] < 0 for s in result["stages"])


def test_drill_cause_whole_recorte_and_validation(repo):
    result = drill_cause(repo, Filters(start=date(2021, 1, 1), end=date(2021, 1, 7)), metric="cycle_p50")
    assert result["sample"]["rest"] is None and result["previous_period"] is None
    assert all(s["vs_rest"] is None and s["vs_previous"] is None for s in result["stages"])
    assert "anterior" in result["note"]
    with pytest.raises(ValueError, match="drill_cause"):
        drill_cause(repo, MARCH_WEEK, metric="orders")
