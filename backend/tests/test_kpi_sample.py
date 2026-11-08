"""Base medida dos KPIs de operação: quantos pedidos sustentam SLA e ciclo mediano."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from app.filters import Filters
from app.repository import MIN_MEASURED


def test_measured_is_delivered_not_stuck_with_cycle(repo, parquet_path: Path):
    expected = duckdb.execute(
        f"select count(*) from read_parquet('{parquet_path.as_posix()}') "
        "where status = 'delivered' and not cycle_outlier and cycle_min is not null"
    ).fetchone()[0]
    current = repo.metrics(Filters())
    assert current["measured"] == expected
    assert current["low_sample"] is False
    assert current["sla_rate"] is not None


def test_store_with_no_measured_orders_is_low_sample(client):
    # Loja 30 do cenário plantado cancela tudo: nenhum pedido entra no SLA ou na mediana.
    current = client.get("/api/kpis", params={"store": 30}).json()["current"]
    assert current["orders"] > 0
    assert current["measured"] == 0
    assert current["low_sample"] is True
    assert current["sla_rate"] is None and current["cycle_p50"] is None


def test_low_sample_flag_matches_threshold_day_by_day(repo):
    # A cada dia a mais no recorte, a base só cresce; o flag tem que virar exatamente em MIN_MEASURED.
    start = date(2021, 1, 1)
    flags = []
    for n in range(120):
        m = repo.metrics(Filters(start=start, end=start + timedelta(days=n)))
        assert m["low_sample"] == (m["measured"] < MIN_MEASURED)
        flags.append(m["low_sample"])
    assert flags[0] is True  # um dia só não sustenta a medição
    assert flags[-1] is False  # quatro meses sustentam
    assert flags.index(False) > 0


def test_previous_period_carries_measured_and_flag(client):
    # Mesma loja nos dois períodos: fevereiro (atual) e janeiro (anterior), ambos sem base medida.
    body = client.get("/api/kpis", params={"store": 30, "start": "2021-02-01", "end": "2021-02-28"}).json()
    assert body["previous"] is not None
    assert body["previous"]["measured"] == 0
    assert body["previous"]["low_sample"] is True
    assert body["current"]["low_sample"] is True


def test_full_period_is_not_low_sample_on_both_sides(client):
    # Fevereiro tem período anterior (janeiro) dentro dos dados e base medida de sobra nos dois lados.
    # O fixture cobre só ~58 dias, por isso março ficaria vazio.
    body = client.get("/api/kpis", params={"start": "2021-02-01", "end": "2021-02-28"}).json()
    assert body["previous"] is not None
    assert body["current"]["low_sample"] is False
    assert body["previous"]["low_sample"] is False
    assert body["previous"]["measured"] >= MIN_MEASURED


def test_breakdown_rows_carry_the_same_base(client):
    rows = client.get("/api/breakdown", params={"by": "store", "min_orders": 30}).json()["rows"]
    by_label = {r["label"]: r for r in rows}
    assert by_label["Loja Quebrada"]["measured"] == 0
    assert by_label["Loja Quebrada"]["low_sample"] is True
    hub_rows = client.get("/api/breakdown", params={"by": "hub"}).json()["rows"]
    assert all(r["low_sample"] is False and r["measured"] >= MIN_MEASURED for r in hub_rows)
