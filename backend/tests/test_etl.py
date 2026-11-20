"""Testes de ponta a ponta do ETL (`scripts/build_parquet.py`) com CSVs sintéticos."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import duckdb
import pytest

from app.repository import Repository
from scripts.build_parquet import _pretty, build


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="latin-1", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)


def _base_tables() -> dict[str, tuple[list[str], list[list[object]]]]:
    return {
        "hubs": (
            ["hub_id", "hub_name", "hub_city", "hub_state"],
            [[1, "HUB DO CENTRO", "SÃO PAULO", "SP"]],
        ),
        "stores": (
            ["store_id", "hub_id", "store_name", "store_segment"],
            [[10, 1, "PIMGUCIS DA VIVA", "FOOD"]],
        ),
        "channels": (
            ["channel_id", "channel_name", "channel_type"],
            [[1, "FOOD PLACE", "MARKETPLACE"]],
        ),
        "drivers": (
            ["driver_id", "driver_modal", "driver_type"],
            [
                [1, "MOTOBOY", "FREELANCE"],
                [2, "BIKER", "LOGISTIC OPERATOR"],
                [3, "MOTOBOY", "FREELANCE"],
            ],
        ),
        "orders": (
            [
                "order_id",
                "store_id",
                "channel_id",
                "payment_order_id",
                "delivery_order_id",
                "order_status",
                "order_amount",
                "order_delivery_fee",
                "order_delivery_cost",
                "order_created_hour",
                "order_created_minute",
                "order_created_day",
                "order_created_month",
                "order_created_year",
                "order_moment_created",
                "order_metric_production_time",
                "order_metric_collected_time",
                "order_metric_walking_time",
                "order_metric_expediton_speed_time",
                "order_metric_transit_time",
                "order_metric_cycle_time",
            ],
            [
                # 1: 02:30 UTC -> 2020-12-31 23:30 Brasília (descartado).
                [
                    1, 10, 1, 101, 201, "FINISHED", 50.0, 5.0, 7.0,
                    2, 30, 1, 1, 2021, "2021-01-01 02:30:00",
                    10.0, 2.0, 1.0, 3.0, 12.0, 28.0,
                ],
                # 2: 03:00 UTC -> 2021-01-01 00:00 Brasília (sexta, weekday=4); várias entregas e pagamentos.
                [
                    2, 10, 1, 102, 202, "FINISHED", 5000.0, 0.0, 8.0,
                    3, 0, 1, 1, 2021, "2021-01-01 03:00:00",
                    0.0, 1.5, 2.0, 4.0, 10.0, 240.0,
                ],
                # 3: cancelado sem entrega DELIVERED (fallback para maior delivery_id > 10^10); distância=50000;
                # métricas negativas -> None; valor > 5000 -> amount_outlier.
                [
                    3, 10, 1, 103, 203, "CANCELED", 5000.01, 9.9, 12.0,
                    15, 0, 2, 1, 2021, "2021-01-02 15:00:00",
                    -5.0, -1.0, -0.5, -2.0, -3.0, -10.0,
                ],
                # 4: ciclo 240.01 -> cycle_outlier; distância negativa -> None.
                [
                    4, 10, 1, 104, 204, "FINISHED", 120.0, 4.5, 6.0,
                    16, 0, 2, 1, 2021, "2021-01-02 16:00:00",
                    12.0, 2.0, 1.0, 5.0, 220.01, 240.01,
                ],
                # 5: distância 50001 -> None.
                [
                    5, 10, 1, 105, 205, "FINISHED", 80.0, 4.5, 6.0,
                    17, 0, 2, 1, 2021, "2021-01-02 17:00:00",
                    10.0, 2.0, 1.0, 4.0, 15.0, 32.0,
                ],
            ],
        ),
        "deliveries": (
            [
                "delivery_id",
                "delivery_order_id",
                "driver_id",
                "delivery_distance_meters",
                "delivery_status",
            ],
            [
                # Pedido 2: DELIVERED id=10, CANCELLED com id > 10^10, DELIVERED id=20 -> vence id=20 (driver 2, 0 m).
                [10, 202, 1, 1500, "DELIVERED"],
                [20000000000, 202, 3, 9999, "CANCELLED"],
                [20, 202, 2, 0, "DELIVERED"],
                # Pedido 3: sem DELIVERED; CANCELLED (10^10 + 1) vs status NULL (2*10^10 + 5) -> vence maior id.
                [10000000001, 203, 1, 1200, "CANCELLED"],
                [20000000005, 203, 2, 50000, None],
                # Pedido 4: distância negativa (-1) -> None.
                [30, 204, 1, -1, "DELIVERED"],
                # Pedido 5: distância > 50 km (50001) -> None.
                [40, 205, 3, 50001, "DELIVERED"],
            ],
        ),
        "payments": (
            [
                "payment_id",
                "payment_order_id",
                "payment_amount",
                "payment_fee",
                "payment_method",
                "payment_status",
            ],
            [
                [1, 102, 20.0, 1.0, "VOUCHER", "PAID"],
                [2, 102, 80.0, 2.0, "CREDIT_CARD", "CHARGEBACK"],
                [3, 103, 5000.01, 1.0, "DEBIT", "PAID"],
                [4, 104, 120.0, 1.0, "PIX", "PAID"],
                [5, 105, 80.0, 1.0, "ONLINE", "PAID"],
            ],
        ),
    }


def _write_raw(raw_dir: Path, tables: dict[str, tuple[list[str], list[list[object]]]]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, (headers, rows) in tables.items():
        _write_csv(raw_dir / f"{name}.csv", headers, rows)


def test_etl_end_to_end_cleaning_and_aggregations(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    out_parquet = tmp_path / "out" / "orders.parquet"
    _write_raw(raw_dir, _base_tables())

    build(raw_dir, out_parquet)
    assert out_parquet.exists()

    with duckdb.connect() as con:
        rows = con.execute(
            f"""
            select
                order_id, created_date, hour, weekday, status,
                store_name, hub_name, city, channel, channel_type,
                payment_method, has_chargeback, modal, driver_type,
                distance_m, delivery_attempts, production_min, cycle_min,
                cycle_outlier, amount_outlier
            from read_parquet('{out_parquet.as_posix()}')
            order by order_id
            """
        ).fetchall()

    assert [r[0] for r in rows] == [2, 3, 4, 5]

    by_id = {r[0]: r for r in rows}

    # Pedido 2: 03:00 UTC -> 2021-01-01 00:00 Brasília, delivery_attempts=3, pick=id 20 (bike/operator, 0 m),
    # payment=credit_card + has_chargeback=True, amount=5000 (não outlier), cycle=240 (não outlier).
    r2 = by_id[2]
    assert r2[1] == date(2021, 1, 1)
    assert r2[2] == 0
    assert r2[3] == 4
    assert r2[4] == "delivered"
    assert r2[5] == "Pimgucis da Viva"
    assert r2[6] == "Hub do Centro"
    assert r2[7] == "São Paulo"
    assert r2[8] == "Food Place"
    assert r2[9] == "marketplace"
    assert r2[10] == "credit_card"
    assert r2[11] is True
    assert r2[12] == "bike"
    assert r2[13] == "operator"
    assert r2[14] == 0
    assert r2[15] == 3
    assert r2[16] == 0.0
    assert r2[17] == 240.0
    assert r2[18] is False
    assert r2[19] is False

    # Pedido 3: sem DELIVERED -> fallback para maior delivery_id (2*10^10+5, driver 2 -> bike, 50000 m),
    # métricas negativas -> None, amount=5000.01 -> amount_outlier=True.
    r3 = by_id[3]
    assert r3[4] == "canceled"
    assert r3[12] == "bike"
    assert r3[14] == 50000
    assert r3[15] == 2
    assert r3[16] is None
    assert r3[17] is None
    assert r3[18] is False
    assert r3[19] is True

    # Pedido 4: cycle=240.01 -> cycle_outlier=True, distância -1 -> None.
    r4 = by_id[4]
    assert r4[2] == 13  # 16:00 UTC -> 13h em Brasília
    assert r4[14] is None
    assert r4[18] is True

    # Pedido 5: distância 50001 -> None.
    assert by_id[5][14] is None

    # O parquet gerado sobe no Repository da aplicação (SLA food 60 / goods 120 min).
    repo = Repository(out_parquet, 60, 120)
    assert repo.total_orders == 4


def test_pretty_formats_portuguese_prepositions():
    assert _pretty("SÃO PAULO") == "São Paulo"
    assert _pretty("PIMGUCIS DA VIVA") == "Pimgucis da Viva"
    assert _pretty("RIO DE JANEIRO") == "Rio de Janeiro"
    assert _pretty("DA SILVA") == "Da Silva"


def test_etl_missing_csv_exits(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    _write_raw(raw_dir, _base_tables())
    (raw_dir / "channels.csv").unlink()

    with pytest.raises(SystemExit, match="channels"):
        build(raw_dir, tmp_path / "orders.parquet")


@pytest.mark.parametrize("bad_status", ["OPEN", "PENDING", None])
def test_etl_rejects_unknown_order_status(tmp_path: Path, bad_status: str | None):
    raw_dir = tmp_path / "raw"
    tables = _base_tables()
    headers, rows = tables["orders"]
    mutated = [list(row) for row in rows]
    mutated[0][5] = bad_status
    tables["orders"] = (headers, mutated)
    _write_raw(raw_dir, tables)

    with pytest.raises(ValueError, match="order_status"):
        build(raw_dir, tmp_path / "orders.parquet")


@pytest.mark.parametrize("bad_channel", ["PARTNER", None])
def test_etl_rejects_unknown_channel_type(tmp_path: Path, bad_channel: str | None):
    raw_dir = tmp_path / "raw"
    tables = _base_tables()
    headers, _ = tables["channels"]
    tables["channels"] = (headers, [[1, "FOOD PLACE", bad_channel]])
    _write_raw(raw_dir, tables)

    with pytest.raises(ValueError, match="channel_type"):
        build(raw_dir, tmp_path / "orders.parquet")


def test_etl_rejects_unknown_store_segment(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    tables = _base_tables()
    headers, _ = tables["stores"]
    tables["stores"] = (headers, [[10, 1, "PIMGUCIS DA VIVA", "ELECTRONICS"]])
    _write_raw(raw_dir, tables)

    with pytest.raises(ValueError, match="store_segment"):
        build(raw_dir, tmp_path / "orders.parquet")


@pytest.mark.parametrize(
    ("table", "col_idx"),
    [
        ("stores", 2),   # store_name
        ("orders", 6),   # order_amount
    ],
)
def test_etl_rejects_null_required_field(tmp_path: Path, table: str, col_idx: int):
    raw_dir = tmp_path / "raw"
    tables = _base_tables()
    headers, rows = tables[table]
    mutated = [list(row) for row in rows]
    mutated[0][col_idx] = None
    tables[table] = (headers, mutated)
    _write_raw(raw_dir, tables)

    with pytest.raises(ValueError, match="valores nulos"):
        build(raw_dir, tmp_path / "orders.parquet")
