"""Constrói `data/orders.parquet` a partir dos CSVs do Delivery Center (Kaggle).

Uso:
    python scripts/build_parquet.py               # lê data/raw/*.csv
    python scripts/build_parquet.py --raw outra/pasta --out data/orders.parquet

Decisões de limpeza (documentadas no README):
- Os timestamps do dataset estão em UTC (picos às 15h e 22h). Convertemos para
  horário de Brasília (UTC-3, sem horário de verão desde 2019) e descartamos os
  pedidos que caem em 31/12/2020 no horário local.
- Métricas de tempo negativas viram nulo.
- Ciclo > 240 min é marcado como `cycle_outlier` (pedido "preso" no fluxo);
  as medianas de tempo usam só os ciclos válidos.
- Valor > R$ 5.000 é marcado como `amount_outlier` (pedido de teste) e fica fora
  de GMV e ticket.
- Distância > 50 km ou negativa vira nulo.
- `deliveries` e `payments` têm várias linhas por pedido: ficamos com a última
  entrega concluída (entregador + distância) e o meio de pagamento de maior valor.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_OUT = ROOT / "data" / "orders.parquet"
TABLES = ["orders", "deliveries", "payments", "stores", "hubs", "drivers", "channels"]

SQL = """
create or replace table fact as
with del as (
    select
        delivery_order_id,
        count(*) as delivery_attempts,
        arg_max(
            {'driver_id': driver_id, 'distance': delivery_distance_meters},
            (delivery_status = 'DELIVERED')::bigint * 10000000000 + delivery_id
        ) as pick
    from deliveries
    group by 1
),
pay as (
    select
        payment_order_id,
        arg_max(payment_method, payment_amount) as payment_method,
        count(*) as payment_count,
        bool_or(payment_status = 'CHARGEBACK') as has_chargeback
    from payments
    group by 1
),
base as (
    select
        o.order_id,
        o.order_moment_created - interval 3 hour as created_at,
        case o.order_status when 'FINISHED' then 'delivered' else 'canceled' end as status,
        o.order_amount as amount,
        o.order_delivery_fee as delivery_fee,
        o.order_delivery_cost as delivery_cost,
        o.store_id,
        trim(s.store_name) as store_name,
        lower(s.store_segment) as segment,
        h.hub_id,
        trim(h.hub_name) as hub_name,
        trim(h.hub_city) as city,
        h.hub_state as state,
        trim(ch.channel_name) as channel,
        case ch.channel_type when 'MARKETPLACE' then 'marketplace' else 'own' end as channel_type,
        lower(pay.payment_method) as payment_method,
        coalesce(pay.has_chargeback, false) as has_chargeback,
        case dr.driver_modal when 'MOTOBOY' then 'moto' when 'BIKER' then 'bike' end as modal,
        case dr.driver_type when 'FREELANCE' then 'freelance' when 'LOGISTIC OPERATOR' then 'operator' end
            as driver_type,
        case when del.pick.distance between 0 and 50000 then del.pick.distance end as distance_m,
        coalesce(del.delivery_attempts, 0) as delivery_attempts,
        case when o.order_metric_production_time >= 0 then o.order_metric_production_time end as production_min,
        case when o.order_metric_collected_time >= 0 then o.order_metric_collected_time end as collected_min,
        case when o.order_metric_walking_time >= 0 then o.order_metric_walking_time end as walking_min,
        case when o.order_metric_expediton_speed_time >= 0 then o.order_metric_expediton_speed_time end
            as expedition_min,
        case when o.order_metric_transit_time >= 0 then o.order_metric_transit_time end as transit_min,
        case when o.order_metric_cycle_time >= 0 then o.order_metric_cycle_time end as cycle_min
    from orders o
    join stores s using (store_id)
    join hubs h using (hub_id)
    join channels ch using (channel_id)
    left join pay on pay.payment_order_id = o.payment_order_id
    left join del on del.delivery_order_id = o.delivery_order_id
    left join drivers dr on dr.driver_id = del.pick.driver_id
)
select
    order_id,
    created_at,
    cast(created_at as date) as created_date,
    hour(created_at)::tinyint as hour,
    (isodow(created_at) - 1)::tinyint as weekday,
    status,
    round(amount, 2) as amount,
    round(delivery_fee, 2) as delivery_fee,
    round(delivery_cost, 2) as delivery_cost,
    store_id, store_name, segment, hub_id, hub_name, city, state,
    channel, channel_type, payment_method, has_chargeback,
    modal, driver_type, distance_m, delivery_attempts,
    round(production_min, 2) as production_min,
    round(collected_min, 2) as collected_min,
    round(walking_min, 2) as walking_min,
    round(expedition_min, 2) as expedition_min,
    round(transit_min, 2) as transit_min,
    round(cycle_min, 2) as cycle_min,
    coalesce(cycle_min > 240, false) as cycle_outlier,
    amount > 5000 as amount_outlier
from base
where cast(created_at as date) >= date '2021-01-01'
order by created_at
"""


def _pretty(name: str) -> str:
    """'SÃO PAULO' -> 'São Paulo', 'PIMGUCIS DA VIVA' -> 'Pimgucis da Viva'."""
    small = {"da", "de", "do", "das", "dos", "e"}
    words = name.strip().lower().split()
    return " ".join(w if (i and w in small) else w.capitalize() for i, w in enumerate(words))


def _prettify_column(con: duckdb.DuckDBPyConnection, column: str) -> None:
    values = [r[0] for r in con.execute(f"select distinct {column} from fact where {column} is not null").fetchall()]
    con.execute("create or replace temp table name_map (k varchar, v varchar)")
    con.executemany("insert into name_map values (?, ?)", [(v, _pretty(v)) for v in values])
    con.execute(f"update fact set {column} = name_map.v from name_map where fact.{column} = name_map.k")


def build(raw: Path, out: Path) -> None:
    missing = [t for t in TABLES if not (raw / f"{t}.csv").exists()]
    if missing:
        sys.exit(f"CSVs ausentes em {raw}: {', '.join(missing)}")

    con = duckdb.connect()
    for table in TABLES:
        path = (raw / f"{table}.csv").as_posix()
        con.execute(f"create table {table} as select * from read_csv('{path}', header = true, encoding = 'latin-1')")

    con.execute(SQL)
    for column in ("store_name", "hub_name", "city", "channel"):
        _prettify_column(con, column)

    out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"copy (select * from fact order by created_at) to '{out.as_posix()}' "
        "(format parquet, compression zstd, row_group_size 100000)"
    )
    rows, start, end = con.execute(
        "select count(*), min(created_date), max(created_date) from fact"
    ).fetchone()
    print(f"{out} · {rows} pedidos · {start} a {end} · {out.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.raw, args.out)


if __name__ == "__main__":
    main()
