"""Regras do repositório: filtro de status, marcas do ranking, mediana de distância, pedido preso e CSV."""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import duckdb
import pytest

from app.filters import Filters
from app.repository import MIN_MEASURED, _flag_outliers


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


# ------------------------------------------------------------------- exportação CSV
def test_csv_export_works_when_target_dir_has_single_quote(repo, tmp_path: Path):
    target_dir = tmp_path / "O'Neil"
    target_dir.mkdir()
    target = target_dir / "pedidos.csv"
    f = Filters(city=["Curitiba"])
    repo.export_csv(f, target)
    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("order_id,created_at,status,city")
    assert len(lines) - 1 == repo.metrics(f)["orders"] > 0


def test_csv_endpoint_works_when_temp_dir_has_single_quote(client, tmp_path: Path, monkeypatch):
    quoted = tmp_path / "O'Neil"
    quoted.mkdir()
    # tempfile.mkstemp usa tempfile.tempdir quando definido.
    monkeypatch.setattr(tempfile, "tempdir", str(quoted))
    r = client.get("/api/orders.csv", params={"city": "Curitiba"})
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("order_id,")
