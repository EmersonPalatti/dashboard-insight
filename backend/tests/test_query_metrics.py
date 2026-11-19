"""Consulta estruturada (Repository.query_metrics): mesmos números do breakdown, subfatias,
comparações e validação. Cenários do parquet sintético descritos em conftest.py."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from app.filters import Filters
from app.repository import QUERY_METRICS, Repository

MARCH_WEEK = Filters(start=date(2021, 3, 8), end=date(2021, 3, 14))


def _by_key(rows: list[dict], dim: str) -> dict:
    return {r["keys"][dim]["key"]: r for r in rows}


@pytest.fixture(scope="module")
def odd_parquet(parquet_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Cópia do parquet com modal nulo, chargeback, mais de uma tentativa e caminhada variada."""
    dest = tmp_path_factory.mktemp("odd") / "orders.parquet"
    src = parquet_path.as_posix().replace("'", "''")
    out = dest.as_posix().replace("'", "''")
    con = duckdb.connect()
    con.execute(
        f"""copy (select * replace (
                case when order_id % 7 = 0 then null else modal end as modal,
                order_id % 11 = 0 as has_chargeback,
                case when order_id % 5 = 0 then 2 else delivery_attempts end as delivery_attempts,
                walking_min + order_id % 13 as walking_min
            ) from read_parquet('{src}')) to '{out}' (format parquet)"""
    )
    con.close()
    return dest


@pytest.fixture(scope="module")
def odd_repo(odd_parquet: Path) -> Repository:
    return Repository(odd_parquet, sla_food_min=60, sla_good_min=120)


def test_query_metrics_keys_cover_metrics_sql_and_extras():
    assert "low_sample" not in QUERY_METRICS and "volume_low_sample" not in QUERY_METRICS
    for key in ("orders", "measured", "cancel_rate", "sla_rate", "cycle_p50", "subsidy"):
        assert key in QUERY_METRICS
    assert QUERY_METRICS[-3:] == ("chargeback_rate", "multi_attempt_rate", "walking_p50")
    assert len(set(QUERY_METRICS)) == len(QUERY_METRICS)


@pytest.mark.parametrize("f", [Filters(), MARCH_WEEK])
def test_single_dimension_matches_breakdown(repo, f):
    metrics = ["orders", "cancel_rate", "sla_rate", "cycle_p50", "gmv"]
    result = repo.query_metrics(f, metrics=metrics, group_by=["hub"], limit=50)
    expected = {r["key"]: r for r in repo.breakdown(f, "hub", limit=50)}
    rows = _by_key(result["rows"], "hub")
    assert rows.keys() == expected.keys()
    for key, row in rows.items():
        assert row["keys"]["hub"]["label"] == expected[key]["label"]
        for m in (*metrics, "measured", "low_sample"):
            assert row[m] == pytest.approx(expected[key][m]), (key, m)
    total = repo.metrics(f)
    for m in metrics:
        assert result["total"][m] == pytest.approx(total[m])
    # sem sort: maior volume primeiro, como o breakdown
    assert [r["orders"] for r in result["rows"]] == sorted((r["orders"] for r in result["rows"]), reverse=True)


def test_sample_floors_match_breakdown(repo):
    result = repo.query_metrics(MARCH_WEEK, metrics=["sla_rate"], group_by=["store"], min_measured=100, limit=50)
    expected = repo.breakdown(MARCH_WEEK, "store", min_measured=100, limit=50)
    assert {r["keys"]["store"]["key"] for r in result["rows"]} == {r["key"] for r in expected}
    assert all(r["measured"] >= 100 for r in result["rows"])


def test_two_dimensions_cells_sum_to_total(repo):
    day = Filters(start=date(2021, 3, 3), end=date(2021, 3, 3))
    result = repo.query_metrics(day, metrics=["orders", "canceled"], group_by=["weekday", "hour"], limit=50)
    assert not result["truncated"]
    assert sum(r["orders"] for r in result["rows"]) == result["total"]["orders"] == repo.metrics(day)["orders"]
    assert sum(r["canceled"] for r in result["rows"]) == repo.metrics(day)["canceled"]
    keys = [(r["keys"]["weekday"]["key"], r["keys"]["hour"]["key"]) for r in result["rows"]]
    assert keys == sorted(keys)  # sem sort e com dimensão de tempo: ordem cronológica


def test_two_dimensions_respect_limit_and_flag_truncation(repo):
    result = repo.query_metrics(Filters(), metrics=["orders"], group_by=["weekday", "hour"], limit=50)
    assert len(result["rows"]) == 50
    assert result["truncated"] and result["n_groups"] > 50
    assert result["note"]


def test_hour_series_is_chronological_and_not_cut_by_default_limit(repo):
    result = repo.query_metrics(Filters(), metrics=["orders"], group_by=["hour"])  # limit padrão 10
    hours = [r["keys"]["hour"]["key"] for r in result["rows"]]
    assert hours == sorted(hours) and len(hours) == result["n_groups"]
    assert not result["truncated"]
    by_hour: dict[int, int] = {}
    for cell in repo.heatmap(Filters()):
        by_hour[cell["hour"]] = by_hour.get(cell["hour"], 0) + cell["orders"]
    assert {r["keys"]["hour"]["key"]: r["orders"] for r in result["rows"]} == by_hour


def test_where_dimension_by_label_or_id_case_insensitive(repo):
    expected = repo.metrics(Filters(hub=[1]))
    for values in (["hub centro"], ["HUB CENTRO"], [1], ["1"], [" Hub Centro ", "hub centro"]):
        total = repo.query_metrics(Filters(), metrics=["orders", "sla_rate"], where={"hub": values})["total"]
        assert total["orders"] == expected["orders"], values
        assert total["sla_rate"] == pytest.approx(expected["sla_rate"])


def test_where_hour_and_weekday(repo):
    heat = repo.heatmap(Filters())
    result = repo.query_metrics(Filters(), metrics=["orders"], where={"hour": [19, "20"], "weekday": [0]})
    assert result["where"] == {"hour": [19, 20], "weekday": [0]}
    expected = sum(c["orders"] for c in heat if c["hour"] in (19, 20) and c["weekday"] == 0)
    assert result["total"]["orders"] == expected


def test_compare_rest_partitions_recorte(repo):
    f = MARCH_WEEK
    result = repo.query_metrics(f, metrics=["orders", "canceled", "cancel_rate"], where={"store": [25]}, compare="rest")
    whole = repo.metrics(f)
    total, rest = result["total"], result["total_compare"]
    assert total["orders"] == 200
    assert total["orders"] + rest["orders"] == whole["orders"]
    assert total["canceled"] + rest["canceled"] == whole["canceled"]
    assert total["cancel_rate"] == pytest.approx(0.45)
    assert result["total_delta"]["cancel_rate"] == pytest.approx(0.45 - rest["cancel_rate"])
    assert result["compare_period"] == result["period"]


def test_compare_rest_grouped_rows_partition_per_group(repo):
    result = repo.query_metrics(
        MARCH_WEEK, metrics=["orders"], group_by=["hub"], where={"store": [25]}, compare="rest", limit=50
    )
    expected = {r["key"]: r["orders"] for r in repo.breakdown(MARCH_WEEK, "hub", limit=50)}
    for row in result["rows"]:
        assert row["orders"] + row["compare"]["orders"] == expected[row["keys"]["hub"]["key"]]


def test_compare_previous_matches_breakdown_of_previous_period(repo):
    f = MARCH_WEEK
    prev = repo.previous_period(f)
    result = repo.query_metrics(f, metrics=["orders", "sla_rate", "cancel_rate"], group_by=["hub"], compare="previous")
    assert result["compare"] == "previous"
    assert result["compare_period"] == {"start": prev[0], "end": prev[1]}
    expected = {r["key"]: r for r in repo.breakdown(f.with_period(*prev), "hub", limit=50)}
    for row in result["rows"]:
        old = expected[row["keys"]["hub"]["key"]]
        for m in ("orders", "sla_rate", "cancel_rate"):
            assert row["compare"][m] == pytest.approx(old[m])
            assert row["delta"][m] == pytest.approx(row[m] - old[m])
    assert result["total_compare"]["orders"] == repo.metrics(f.with_period(*prev))["orders"]


def test_compare_previous_unavailable_is_a_note_not_an_error(repo):
    f = Filters(start=date(2021, 1, 1), end=date(2021, 1, 7))
    result = repo.query_metrics(f, metrics=["orders"], group_by=["hub"], compare="previous", sort="delta:orders")
    assert result["compare"] is None and result["compare_period"] is None and result["total_compare"] is None
    assert all(r["compare"] is None for r in result["rows"])
    assert "anterior" in result["note"]


def test_sort_by_delta(repo):
    result = repo.query_metrics(
        MARCH_WEEK, metrics=["sla_rate"], group_by=["store"], compare="previous", sort="delta:sla_rate", limit=50
    )
    deltas = [r["delta"]["sla_rate"] for r in result["rows"]]
    present = [d for d in deltas if d is not None]
    assert present == sorted(present, reverse=True)
    assert deltas[: len(present)] == present  # loja nova (sem par) fica no fim
    assert None in deltas  # loja 25 e 17 só existem na semana atual
    asc = repo.query_metrics(
        MARCH_WEEK, metrics=["sla_rate"], group_by=["store"], compare="previous", sort="delta:sla_rate",
        desc=False, limit=50,
    )
    asc_present = [r["delta"]["sla_rate"] for r in asc["rows"] if r["delta"]["sla_rate"] is not None]
    assert asc_present == sorted(present)


def test_sort_by_metric_adds_it_to_output(repo):
    result = repo.query_metrics(MARCH_WEEK, metrics=["orders"], group_by=["store"], sort="cancel_rate")
    assert result["metrics"] == ["orders", "cancel_rate"]
    assert result["rows"][0]["keys"]["store"]["key"] == 25


def test_null_dimension_gets_label_and_is_filterable(odd_repo):
    f = Filters()
    result = odd_repo.query_metrics(f, metrics=["orders"], group_by=["modal"])
    rows = _by_key(result["rows"], "modal")
    assert rows[None]["keys"]["modal"]["label"] == "Sem entregador"
    assert sum(r["orders"] for r in result["rows"]) == odd_repo.total_orders
    only_null = odd_repo.query_metrics(f, metrics=["orders"], where={"modal": ["sem entregador"]})
    assert only_null["total"]["orders"] == rows[None]["orders"] > 0


def test_extra_metrics_match_direct_duckdb(odd_repo, odd_parquet):
    f = MARCH_WEEK
    result = odd_repo.query_metrics(
        f, metrics=["chargeback_rate", "multi_attempt_rate", "walking_p50"], group_by=["hub"], limit=50
    )
    con = duckdb.connect()
    path = odd_parquet.as_posix().replace("'", "''")
    expected = con.execute(
        f"""select hub_id,
                avg(has_chargeback::int),
                avg((delivery_attempts > 1)::int) filter (where status = 'delivered'),
                median(walking_min) filter (where status = 'delivered' and not cycle_outlier)
            from read_parquet('{path}') where created_date between ? and ? group by 1""",
        [f.start, f.end],
    ).fetchall()
    con.close()
    rows = _by_key(result["rows"], "hub")
    assert rows.keys() == {e[0] for e in expected}
    for hub, chargeback, multi, walking in expected:
        assert rows[hub]["chargeback_rate"] == pytest.approx(chargeback)
        assert rows[hub]["multi_attempt_rate"] == pytest.approx(multi)
        assert rows[hub]["walking_p50"] == pytest.approx(walking)
    assert 0 < result["total"]["chargeback_rate"] < 1
    assert 0 < result["total"]["multi_attempt_rate"] < 1


def test_injection_like_values_are_plain_parameters(repo):
    for value in ("x' or 1=1 --", "1); drop table orders; --", "%"):
        result = repo.query_metrics(Filters(), metrics=["orders"], group_by=["hub"], where={"store": [value]})
        assert result["total"]["orders"] == 0
        assert result["rows"] == []
    assert repo.metrics(Filters())["orders"] == repo.total_orders


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"metrics": ["nope"]}, "Métrica desconhecida"),
        ({"metrics": []}, "ao menos uma"),
        ({"metrics": list(QUERY_METRICS[:9])}, "No máximo 8"),
        ({"metrics": ["orders"], "group_by": ["hub", "hour", "weekday"]}, "No máximo 2"),
        ({"metrics": ["orders"], "group_by": ["hub", "hub"]}, "repetir"),
        ({"metrics": ["orders"], "group_by": ["state"]}, "Dimensão desconhecida"),
        ({"metrics": ["orders"], "compare": "rest"}, "informe where"),
        ({"metrics": ["orders"], "compare": "yoy"}, "compare aceita"),
        ({"metrics": ["orders"], "where": {"hour": [24]}}, "hour aceita"),
        ({"metrics": ["orders"], "where": {"weekday": ["seg"]}}, "weekday aceita"),
        ({"metrics": ["orders"], "where": {"hour": [1.5]}}, "hour aceita"),
        ({"metrics": ["orders"], "where": {"order_id": [1]}}, "Dimensão desconhecida"),
        ({"metrics": ["orders"], "sort": "delta:orders"}, "delta"),
        ({"metrics": ["orders"], "sort": "random()"}, "Ordenação desconhecida"),
    ],
)
def test_validation_errors(repo, kwargs, message):
    with pytest.raises(ValueError, match=message):
        repo.query_metrics(Filters(), **kwargs)


def test_limit_is_clamped(repo):
    result = repo.query_metrics(Filters(), metrics=["orders"], group_by=["store"], limit=500)
    assert len(result["rows"]) <= 50
    assert len(repo.query_metrics(Filters(), metrics=["orders"], group_by=["store"], limit=0)["rows"]) == 1
