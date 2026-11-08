"""Fixtures: parquet sintético com o mesmo schema do ETL, sem depender do Kaggle.

Cenário plantado para os testes de alerta:
- hub 2 ("Hub Lento") tem trânsito +40 min → SLA ruim;
- loja 30 ("Loja Quebrada") cancela tudo;
- hub 3 ("Hub Preso") tem metade dos pedidos com ciclo > 4h.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

SQL = """
select setseed(0.42);
create table fact as
with base as (
    select
        i as order_id,
        timestamp '2021-01-01 11:00:00' + to_minutes((i * 7) % (120 * 24 * 60)) as created_at,
        (i % 4) + 1 as hub_id,
        ((i % 4) + 1) * 10 + (i % 3) as store_id,
        random() as r1, random() as r2, random() as r3
    from range(1, 12001) t(i)
)
select
    order_id,
    created_at,
    cast(created_at as date) as created_date,
    hour(created_at)::tinyint as hour,
    (isodow(created_at) - 1)::tinyint as weekday,
    case when store_id = 30 or r1 < 0.03 then 'canceled' else 'delivered' end as status,
    round(30 + r2 * 120, 2) as amount,
    round(case when r3 < 0.5 then 0 else 9.9 end, 2) as delivery_fee,
    round(6 + r3 * 4, 2) as delivery_cost,
    store_id,
    case store_id when 30 then 'Loja Quebrada' else 'Loja ' || store_id end as store_name,
    case when hub_id = 4 then 'good' else 'food' end as segment,
    hub_id,
    case hub_id when 1 then 'Hub Centro' when 2 then 'Hub Lento' when 3 then 'Hub Preso' else 'Hub Goods' end as hub_name,
    case when hub_id <= 2 then 'São Paulo' else 'Curitiba' end as city,
    case when hub_id <= 2 then 'SP' else 'PR' end as state,
    case when r2 < 0.8 then 'Food Place' else 'Own Place' end as channel,
    case when r2 < 0.8 then 'marketplace' else 'own' end as channel_type,
    'online' as payment_method,
    false as has_chargeback,
    case when r3 < 0.6 then 'moto' else 'bike' end as modal,
    'freelance' as driver_type,
    (1000 + r3 * 4000)::bigint as distance_m,
    1 as delivery_attempts,
    round(10 + r1 * 15, 2) as production_min,
    round(1 + r2 * 2, 2) as collected_min,
    round(2 + r2 * 3, 2) as walking_min,
    round(4 + r3 * 4, 2) as expedition_min,
    round(case when hub_id = 2 then 50 else 10 end + r3 * 12, 2) as transit_min,
    round(case
        when hub_id = 3 and r1 > 0.5 then 600
        else 15 + r1 * 15 + 5 + r3 * 4 + case when hub_id = 2 then 50 else 10 end + r3 * 12
    end, 2) as cycle_min
from base;
alter table fact add column cycle_outlier boolean;
alter table fact add column amount_outlier boolean;
update fact set cycle_outlier = cycle_min > 240, amount_outlier = amount > 5000;
"""


@pytest.fixture(scope="session")
def parquet_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "orders.parquet"
    con = duckdb.connect()
    con.execute(SQL)
    con.execute(f"copy fact to '{path.as_posix()}' (format parquet)")
    return path


@pytest.fixture(scope="session")
def client(parquet_path: Path):
    import os

    os.environ["DATA_PATH"] = str(parquet_path)
    os.environ["OPENROUTER_API_KEY"] = ""
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="session")
def repo(client):
    return client.app.state.repo
