"""Regras do repositório: filtro de status, marcas do ranking, mediana de distância, pedido preso e CSV."""

from __future__ import annotations

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.alerts import hero_readings
from app.config import get_settings
from app.filters import Filters
from app.main import create_app
from app.repository import HEATMAP_MIN_SAMPLE, MIN_MEASURED, Repository, _csv_cell, _flag_outliers


# ----------------------------------------------------------------- filtro de status
def test_status_filter_splits_orders_by_status(repo, parquet_path: Path):
    expected_canceled = duckdb.execute(
        f"select count(*) from read_parquet('{parquet_path.as_posix()}') where status = 'canceled'"
    ).fetchone()[0]
    total = repo.metrics(Filters())
    canceled = repo.metrics(Filters(status=["canceled"]))
    delivered = repo.metrics(Filters(status=["delivered"]))
    assert canceled["orders"] == expected_canceled == total["canceled"] > 0
    assert canceled["delivered"] == 0
    assert delivered["orders"] == total["delivered"] > 0
    assert delivered["canceled"] == 0
    assert canceled["orders"] + delivered["orders"] == total["orders"]
    both = repo.metrics(Filters(status=["delivered", "canceled"]))
    assert both["orders"] == total["orders"]


def test_status_filter_changes_kpis_through_the_api(client):
    total = client.get("/api/kpis").json()["current"]
    canceled = client.get("/api/kpis", params={"status": "canceled"}).json()["current"]
    assert canceled["orders"] == total["canceled"] > 0
    assert canceled["delivered"] == 0


def test_unknown_status_is_422(client):
    assert client.get("/api/kpis", params={"status": "foo"}).status_code == 422


def test_describe_names_the_status_filter(repo):
    assert "status cancelado" in repo.describe(Filters(status=["canceled"]))
    assert "status concluído" in repo.describe(Filters(status=["delivered"]))
    assert "status" not in repo.describe(Filters())


# ------------------------------------------------- marcas do ranking (amostra pequena)
def test_small_sample_rows_are_never_flagged():
    base = {"sla_rate": 0.8, "cancel_rate": 0.05}
    small_sla = {"low_sample": True, "orders": 4470, "sla_rate": 0.10, "cancel_rate": 0.02}
    small_orders = {"low_sample": True, "orders": 40, "sla_rate": 0.10, "cancel_rate": 0.60}
    solid = {"low_sample": False, "orders": 900, "sla_rate": 0.10, "cancel_rate": 0.60}
    rows = _flag_outliers([small_sla, small_orders, solid], base)
    # Poucas entregas medidas: SLA não marca, mesmo com 4 mil pedidos no total.
    assert rows[0]["sla_below"] is False and rows[0]["cancel_above"] is False
    # Poucos pedidos no total: cancelamento não marca (denominador é o total de pedidos).
    assert rows[1]["sla_below"] is False and rows[1]["cancel_above"] is False
    # Linha com base suficiente continua marcada.
    assert rows[2]["sla_below"] is True and rows[2]["cancel_above"] is True


def test_breakdown_on_a_short_range_flags_no_small_sample(repo):
    # Três dias do fixture: quase todas as lojas ficam abaixo de MIN_MEASURED.
    f = Filters(start=repo.min_date, end=repo.min_date + timedelta(days=2))
    rows = repo.breakdown(f, "store", min_orders=0)
    assert any(r["low_sample"] for r in rows)
    for r in rows:
        if r["low_sample"]:
            assert r["sla_below"] is False
        if r["orders"] < MIN_MEASURED:
            assert r["cancel_above"] is False


# --------------------------------------------------------- mediana de distância
def test_distance_median_excludes_stuck_orders(repo, parquet_path: Path):
    path = parquet_path.as_posix()
    # Mesma base das outras medianas: entregues, sem pedido preso.
    expected = duckdb.execute(
        f"select median(distance_m) / 1000.0 from read_parquet('{path}') "
        "where status = 'delivered' and not cycle_outlier and hub_id = 3"
    ).fetchone()[0]
    with_stuck = duckdb.execute(
        f"select median(distance_m) / 1000.0 from read_parquet('{path}') "
        "where status = 'delivered' and hub_id = 3"
    ).fetchone()[0]
    # Sem essa diferença, o teste não distinguiria a base certa da errada.
    assert with_stuck != pytest.approx(expected)
    assert repo.metrics(Filters(hub=[3]))["distance_p50_km"] == pytest.approx(expected)


# ------------------------------------------------------------- pedido preso no CSV/API
def test_stuck_orders_have_no_on_time(client):
    stuck_rows = client.get(
        "/api/orders", params={"hub": 3, "sort": "cycle_min", "desc": "true", "limit": 50}
    ).json()["rows"]
    stuck = [r for r in stuck_rows if r["status"] == "delivered" and r["cycle_min"] > 240]
    assert stuck, "o cenário plantado precisa ter pedidos presos no hub 3"
    assert all(r["on_time"] is None for r in stuck)

    measured_rows = client.get(
        "/api/orders", params={"hub": 3, "sort": "cycle_min", "desc": "false", "limit": 50}
    ).json()["rows"]
    measured = [r for r in measured_rows if r["status"] == "delivered" and r["cycle_min"] is not None]
    assert measured and all(isinstance(r["on_time"], bool) for r in measured)


def _repo_with_gaps(tmp_path: Path):
    """Parquet mínimo com modal/pagamento nulos e frete sem custo (e o inverso)."""
    path = tmp_path / "gaps.parquet"
    con = duckdb.connect()
    con.execute(
        """
        create table fact as
        select * from (values
            (1, timestamp '2021-01-06 12:00:00', date '2021-01-06', 12::tinyint, 2::tinyint,
             'delivered', 40.0, 1.0, 9.0, 11, 'Loja 11', 'food', 1, 'Hub Centro', 'São Paulo', 'SP',
             'Food Place', 'marketplace', 'online', false, 'moto', 'freelance', 1000::bigint, 1,
             10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false),
            (2, timestamp '2021-01-06 13:00:00', date '2021-01-06', 13::tinyint, 2::tinyint,
             'delivered', 50.0, 5.0, cast(null as double), 11, 'Loja 11', 'food', 1, 'Hub Centro',
             'São Paulo', 'SP', 'Food Place', 'marketplace', cast(null as varchar), false,
             cast(null as varchar), cast(null as varchar), 1000::bigint, 1,
             10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false),
            (3, timestamp '2021-01-06 14:00:00', date '2021-01-06', 14::tinyint, 2::tinyint,
             'delivered', 60.0, 2.0, 10.0, 11, 'Loja 11', 'food', 1, 'Hub Centro', 'São Paulo', 'SP',
             'Food Place', 'marketplace', cast(null as varchar), false, cast(null as varchar),
             'operator', 1000::bigint, 1,
             10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false),
            (4, timestamp '2021-01-06 15:00:00', date '2021-01-06', 15::tinyint, 2::tinyint,
             'delivered', 55.0, cast(null as double), 8.0, 11, 'Loja 11', 'food', 1, 'Hub Centro',
             'São Paulo', 'SP', 'Food Place', 'marketplace', 'cash', false, 'bike', 'freelance',
             1000::bigint, 1,
             10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false),
            (5, timestamp '2021-01-07 10:00:00', date '2021-01-07', 10::tinyint, 3::tinyint,
             'canceled', 70.0, 0.0, 0.0, 12, 'Loja 12', 'food', 1, 'Hub Centro', 'São Paulo', 'SP',
             'Own Place', 'own', 'cash', false, 'bike', 'freelance', 1000::bigint, 1,
             10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false)
        ) t(order_id, created_at, created_date, hour, weekday, status, amount, delivery_fee,
            delivery_cost, store_id, store_name, segment, hub_id, hub_name, city, state, channel,
            channel_type, payment_method, has_chargeback, modal, driver_type, distance_m,
            delivery_attempts, production_min, collected_min, walking_min, expedition_min,
            transit_min, cycle_min, cycle_outlier, amount_outlier)
        """
    )
    con.execute(f"copy fact to '{path.as_posix()}' (format parquet)")
    return Repository(path, 60, 120)


def test_subsidy_uses_rows_where_fee_and_cost_are_both_present(tmp_path: Path):
    repo = _repo_with_gaps(tmp_path)
    metrics = repo.metrics(Filters())
    # Só os pedidos 1 (1 e 9) e 3 (2 e 10). O 2 não tem custo, o 4 não tem frete, o 5 é cancelado.
    assert metrics["fee_avg"] == pytest.approx(1.5)
    assert metrics["cost_avg"] == pytest.approx(9.5)
    assert metrics["subsidy"] == pytest.approx(8.0)
    assert metrics["cost_avg"] - metrics["fee_avg"] == pytest.approx(metrics["subsidy"])


def test_breakdown_keeps_null_keys_with_a_label(tmp_path: Path):
    repo = _repo_with_gaps(tmp_path)
    total = repo.metrics(Filters())["orders"]
    modal = repo.breakdown(Filters(), "modal", limit=20)
    payment = repo.breakdown(Filters(), "payment_method", limit=20)
    driver = repo.breakdown(Filters(), "driver_type", limit=20)
    assert sum(row["orders"] for row in modal) == total
    assert sum(row["orders"] for row in payment) == total
    missing_modal = next(row for row in modal if row["key"] is None)
    missing_payment = next(row for row in payment if row["key"] is None)
    missing_driver = next(row for row in driver if row["key"] is None)
    assert missing_modal["label"] == "Sem entregador"
    assert missing_modal["orders"] == 2
    assert missing_payment["label"] == "Sem pagamento"
    assert missing_driver["label"] == "Não informado"


def test_null_breakdown_key_serializes_as_json_null(tmp_path: Path, monkeypatch):
    path = tmp_path / "gaps.parquet"
    _repo_with_gaps(tmp_path)
    monkeypatch.setenv("DATA_PATH", str(path))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            rows = client.get("/api/breakdown", params={"by": "modal", "limit": 20}).json()["rows"]
        assert any(row["key"] is None and row["label"] == "Sem entregador" for row in rows)
    finally:
        get_settings.cache_clear()


def test_csv_endpoint_works_when_temp_dir_has_single_quote(client, tmp_path: Path, monkeypatch):
    quoted = tmp_path / "O'Neil"
    quoted.mkdir()
    # tempfile.mkstemp usa tempfile.tempdir quando definido.
    monkeypatch.setattr(tempfile, "tempdir", str(quoted))
    r = client.get("/api/orders.csv", params={"city": "Curitiba"})
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("order_id,")


def test_filters_cache_key_is_canonical_for_list_order_and_duplicates():
    assert Filters(hub=[1, 2]).cache_key() == Filters(hub=[2, 1, 1]).cache_key()
    assert Filters(city=["Curitiba", "São Paulo"]).cache_key() == Filters(city=["São Paulo", "Curitiba"]).cache_key()


def test_weekly_timeseries_clamps_first_bucket_to_dataset_start(repo):
    ts = repo.timeseries(Filters(), "week")
    assert ts
    assert ts[0]["t"] >= datetime(2021, 1, 1)


def test_breakdown_sorts_by_stages_and_filters_min_measured(repo):
    by_transit = repo.breakdown(Filters(), "hub", sort="transit_p50", desc=True, limit=10)
    transits = [r["transit_p50"] for r in by_transit if r["transit_p50"] is not None]
    assert transits == sorted(transits, reverse=True)
    assert by_transit[0]["label"] == "Hub Lento"

    by_prod = repo.breakdown(Filters(), "hub", sort="production_p50", desc=True, limit=10)
    prods = [r["production_p50"] for r in by_prod if r["production_p50"] is not None]
    assert prods == sorted(prods, reverse=True)

    reliable_stores = repo.breakdown(Filters(), "store", sort="orders", limit=100, min_measured=MIN_MEASURED)
    assert reliable_stores
    assert all(r["measured"] >= MIN_MEASURED and r["low_sample"] is False for r in reliable_stores)
    assert all(r["label"] != "Loja Quebrada" for r in reliable_stores)


def test_subslice_metrics_and_complement_sum_to_base(repo):
    base = repo.metrics(Filters())
    peak = repo.subslice_metrics(Filters(), hours=[12, 13, 19, 20])
    off_peak = repo.subslice_metrics(Filters(), hours=[12, 13, 19, 20], complement=True)
    assert peak["orders"] > 0 and off_peak["orders"] > 0
    assert peak["orders"] + off_peak["orders"] == base["orders"]
    assert peak["delivered"] + off_peak["delivered"] == base["delivered"]


def test_subslice_complement_includes_null_dimension_rows(tmp_path: Path):
    gap_repo = _repo_with_gaps(tmp_path)
    try:
        total = gap_repo.metrics(Filters())
        moto = gap_repo.subslice_metrics(Filters(), dimension="modal", values=["moto"])
        rest = gap_repo.subslice_metrics(Filters(), dimension="modal", values=["moto"], complement=True)
        assert moto["orders"] == 1
        assert rest["orders"] == 4
        assert moto["orders"] + rest["orders"] == total["orders"]
    finally:
        gap_repo.close()


def test_subslice_metrics_matches_null_labels_like_query_metrics(tmp_path: Path):
    gap_repo = _repo_with_gaps(tmp_path)
    try:
        total = gap_repo.metrics(Filters())["orders"]
        sub_modal = gap_repo.subslice_metrics(Filters(), dimension="modal", values=["sem entregador"])
        qm_modal = gap_repo.query_metrics(Filters(), metrics=["orders"], where={"modal": ["sem entregador"]})["total"]
        rest_modal = gap_repo.subslice_metrics(Filters(), dimension="modal", values=["sem entregador"], complement=True)
        assert sub_modal["orders"] == qm_modal["orders"] == 2
        assert rest_modal["orders"] == 3
        assert sub_modal["orders"] + rest_modal["orders"] == total

        sub_driver = gap_repo.subslice_metrics(Filters(), dimension="driver_type", values=["não informado"])
        qm_driver = gap_repo.query_metrics(
            Filters(), metrics=["orders"], where={"driver_type": ["não informado"]}
        )["total"]
        assert sub_driver["orders"] == qm_driver["orders"] == 1
    finally:
        gap_repo.close()


@pytest.mark.parametrize(
    "f",
    [
        Filters(start=date(2021, 5, 1)),
        Filters(city=["Curitiba"], start=date(2021, 5, 1)),
        Filters(city=["Curitiba"], end=date(2020, 12, 31)),
        Filters(end=date(2020, 12, 20)),
    ],
)
def test_one_sided_out_of_range_dates_do_not_invert_period_or_crash_heroes(repo, f: Filters):
    start, end = repo.period(f)
    assert start <= end
    assert repo.previous_period(f) is None
    assert repo.describe(f).startswith(f"{start:%d/%m/%Y} a {end:%d/%m/%Y}")
    assert len(hero_readings(repo, f)) == 3


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2021-05-01"},
        {"city": "Curitiba", "start": "2021-05-01"},
        {"city": "Curitiba", "end": "2020-12-31"},
        {"end": "2020-12-20"},
    ],
)
def test_kpis_http_one_sided_out_of_range_dates_return_200(client, params: dict):
    r = client.get("/api/kpis", params=params)
    assert r.status_code == 200
    body = r.json()
    assert body["period"]["start"] <= body["period"]["end"]
    assert body["previous_period"] is None
    assert body["previous"] is None
    assert body["current"]["orders"] == 0


def test_csv_cell_neutralizes_formulas_without_touching_numbers():
    assert _csv_cell('=HYPERLINK("http://x","y")') == '\'=HYPERLINK("http://x","y")'
    assert _csv_cell("+1+1") == "'+1+1"
    assert _csv_cell("-1+1") == "'-1+1"
    assert _csv_cell("@SUM(A1)") == "'@SUM(A1)"
    assert _csv_cell("\t=1") == "'\t=1"
    assert _csv_cell("\r=1") == "'\r=1"
    assert _csv_cell(-12.5) == -12.5
    assert _csv_cell(-3) == -3
    assert _csv_cell(0) == 0
    assert _csv_cell("") == ""
    assert _csv_cell("Loja 11") == "Loja 11"
    assert _csv_cell(True) == "true"
    assert _csv_cell(False) == "false"
    assert _csv_cell(None) == ""
    assert _csv_cell(datetime(2021, 1, 2, 3, 4, 5)) == "2021-01-02 03:04:05"


def test_describe_falls_back_to_ids_when_unknown(repo):
    assert repo.describe(Filters(hub=[999999])).endswith("hub 999999")
    assert repo.describe(Filters(store=[999999])).endswith("loja 999999")
    many = repo.describe(Filters(store=[999991, 999992, 999993, 999994, 999995]))
    assert many.endswith("loja 5 lojas")


def test_breakdown_tie_breaker_is_deterministic_and_preserves_winners(tmp_path: Path):
    path = tmp_path / "ties.parquet"
    con = duckdb.connect()
    row_sql = []
    oid = 1
    for store_id, store_name, modal, count in (
        (5, "Loja 5", "van", 3),
        (20, "Loja 20", "moto", 2),
        (10, "Loja 10", "bike", 2),
        (30, "Loja 30", None, 2),
    ):
        for _ in range(count):
            modal_sql = "cast(null as varchar)" if modal is None else f"'{modal}'"
            row_sql.append(
                f"({oid}, timestamp '2021-01-06 12:00:00', date '2021-01-06', 12::tinyint, 2::tinyint, "
                f"'delivered', 40.0, 5.0, 7.0, {store_id}, '{store_name}', 'food', 1, 'Hub Centro', "
                f"'São Paulo', 'SP', 'Food Place', 'marketplace', 'online', false, {modal_sql}, 'freelance', "
                f"1000::bigint, 1, 10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false)"
            )
            oid += 1
    con.execute(
        f"""
        create table fact as
        select * from (values {", ".join(row_sql)})
        t(order_id, created_at, created_date, hour, weekday, status, amount, delivery_fee,
          delivery_cost, store_id, store_name, segment, hub_id, hub_name, city, state, channel,
          channel_type, payment_method, has_chargeback, modal, driver_type, distance_m,
          delivery_attempts, production_min, collected_min, walking_min, expedition_min,
          transit_min, cycle_min, cycle_outlier, amount_outlier)
        """
    )
    con.execute(f"copy fact to '{path.as_posix()}' (format parquet)")
    con.close()

    tie_repo = Repository(path, 60, 120)
    try:
        for _ in range(5):
            tie_repo._cache.clear()
            stores = tie_repo.breakdown(Filters(), "store", sort="orders", limit=10)
            assert [r["key"] for r in stores] == [5, 10, 20, 30]
            modals = tie_repo.breakdown(Filters(), "modal", sort="orders", limit=10)
            assert [r["key"] for r in modals] == ["van", "bike", "moto", None]
    finally:
        tie_repo.close()


def test_orders_page_reuses_metrics_and_skips_query_past_total(repo, monkeypatch):
    f = Filters(city=["Curitiba"])
    total = repo.metrics(f)["orders"]
    assert total > 0

    calls: list[str] = []
    orig_rows = repo._rows

    def spy_rows(sql: str, params: list | None = None):
        calls.append(sql)
        return orig_rows(sql, params)

    monkeypatch.setattr(repo, "_rows", spy_rows)

    at_end = repo.orders_page(f, total, 50, "created_at", True)
    past_end = repo.orders_page(f, total + 500, 50, "created_at", True)
    assert at_end == {"total": total, "offset": total, "limit": 50, "rows": []}
    assert past_end == {"total": total, "offset": total + 500, "limit": 50, "rows": []}
    assert len(calls) == 0

    first_page = repo.orders_page(f, 0, 50, "created_at", True)
    assert first_page["total"] == total
    assert len(first_page["rows"]) == min(50, total)
    assert len(calls) == 1
    assert "select count(*)" not in calls[0].lower()


def test_orders_page_exposes_exact_ids_and_amount_outlier(tmp_path: Path):
    path = tmp_path / "homonyms.parquet"
    con = duckdb.connect()
    con.execute(
        """
        create table fact as
        select * from (values
            (1, timestamp '2021-01-06 12:00:00', date '2021-01-06', 12::tinyint, 2::tinyint,
             'delivered', 5000.00, 5.0, 7.0, 101, 'Loja Homonima', 'food', 10, 'Hub A',
             'São Paulo', 'SP', 'Food Place', 'marketplace', 'online', false, 'moto', 'freelance',
             1000::bigint, 1, 10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false),
            (2, timestamp '2021-01-06 13:00:00', date '2021-01-06', 13::tinyint, 2::tinyint,
             'delivered', 5000.01, 5.0, 7.0, 202, 'Loja Homonima', 'food', 20, 'Hub B',
             'São Paulo', 'SP', 'Food Place', 'marketplace', 'online', false, 'moto', 'freelance',
             1000::bigint, 1, 10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, true)
        ) t(order_id, created_at, created_date, hour, weekday, status, amount, delivery_fee,
            delivery_cost, store_id, store_name, segment, hub_id, hub_name, city, state, channel,
            channel_type, payment_method, has_chargeback, modal, driver_type, distance_m,
            delivery_attempts, production_min, collected_min, walking_min, expedition_min,
            transit_min, cycle_min, cycle_outlier, amount_outlier)
        """
    )
    con.execute(f"copy fact to '{path.as_posix()}' (format parquet)")
    con.close()

    r = Repository(path, 60, 120)
    try:
        rows = r.orders_page(Filters(), 0, 10, "order_id", False)["rows"]
        # Mesma loja em hubs diferentes: a API entrega ids próprios e o flag de outlier do ETL.
        assert [(row["order_id"], row["hub_id"], row["store_id"], row["amount_outlier"]) for row in rows] == [
            (1, 10, 101, False),
            (2, 20, 202, True),
        ]
    finally:
        r.close()


def test_heatmap_flags_measured_below_threshold_independently_of_orders(tmp_path: Path):
    path = tmp_path / "heat_sample.parquet"
    con = duckdb.connect()
    rows_sql = []
    # Célula (segunda 12h): 20 pedidos, sendo 19 cancelados e só 1 entregue medido (orders >= 20, measured = 1).
    for oid in range(1, HEATMAP_MIN_SAMPLE + 1):
        status = "'delivered'" if oid == 1 else "'canceled'"
        rows_sql.append(
            f"({oid}, timestamp '2021-01-04 12:00:00', date '2021-01-04', 12::tinyint, 0::tinyint, "
            f"{status}, 40.0, 5.0, 7.0, 11, 'Loja 11', 'food', 1, 'Hub Centro', 'São Paulo', 'SP', "
            f"'Food Place', 'marketplace', 'online', false, 'moto', 'freelance', 1000::bigint, 1, "
            f"10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false)"
        )
    # Célula (terça 12h): 20 entregas medidas (orders >= 20, measured == 20).
    for offset in range(1, HEATMAP_MIN_SAMPLE + 1):
        oid = HEATMAP_MIN_SAMPLE + offset
        rows_sql.append(
            f"({oid}, timestamp '2021-01-05 12:00:00', date '2021-01-05', 12::tinyint, 1::tinyint, "
            f"'delivered', 40.0, 5.0, 7.0, 11, 'Loja 11', 'food', 1, 'Hub Centro', 'São Paulo', 'SP', "
            f"'Food Place', 'marketplace', 'online', false, 'moto', 'freelance', 1000::bigint, 1, "
            f"10.0, 1.0, 2.0, 4.0, 12.0, 30.0, false, false)"
        )
    con.execute(
        f"""
        create table fact as
        select * from (values {", ".join(rows_sql)})
        t(order_id, created_at, created_date, hour, weekday, status, amount, delivery_fee,
          delivery_cost, store_id, store_name, segment, hub_id, hub_name, city, state, channel,
          channel_type, payment_method, has_chargeback, modal, driver_type, distance_m,
          delivery_attempts, production_min, collected_min, walking_min, expedition_min,
          transit_min, cycle_min, cycle_outlier, amount_outlier)
        """
    )
    con.execute(f"copy fact to '{path.as_posix()}' (format parquet)")
    con.close()

    r = Repository(path, 60, 120)
    try:
        cells = {c["weekday"]: c for c in r.heatmap(Filters())}
        assert cells[0]["orders"] == HEATMAP_MIN_SAMPLE
        assert cells[0]["measured"] == 1
        assert cells[0]["volume_low_sample"] is False
        assert cells[0]["low_sample"] is True

        assert cells[1]["orders"] == HEATMAP_MIN_SAMPLE
        assert cells[1]["measured"] == HEATMAP_MIN_SAMPLE
        assert cells[1]["volume_low_sample"] is False
        assert cells[1]["low_sample"] is False
    finally:
        r.close()


def test_eval_run_main_closes_repository(parquet_path: Path, monkeypatch):
    from evals import run as eval_run

    opened: list[Repository] = []
    real_repo_cls = eval_run.Repository

    def tracking_repo(*args, **kwargs):
        instance = real_repo_cls(*args, **kwargs)
        opened.append(instance)
        return instance

    monkeypatch.setattr(eval_run, "Repository", tracking_repo)
    eval_run.main(["--engine", "local", "--data", str(parquet_path), "--cases", "ov-geral", "--quiet"])
    with pytest.raises(SystemExit):
        eval_run.main(["--engine", "local", "--data", str(parquet_path), "--cases", "nao-existe", "--quiet"])

    assert len(opened) == 2
    for instance in opened:
        with pytest.raises(duckdb.ConnectionException):
            instance.metrics(Filters(store=[999999]))
