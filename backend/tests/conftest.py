"""Fixtures: parquet sintético com o mesmo schema do ETL, sem depender do Kaggle.

Base (`BASE_SQL`): pedidos uniformes de 01/01 a ~14/02/2021 com o cenário antigo:
- hub 2 ("Hub Lento") tem trânsito +40 min → SLA ruim;
- loja 30 ("Loja Quebrada") cancela tudo;
- hub 3 ("Hub Preso") tem metade dos pedidos com ciclo > 4h.

Cenário plantado de março (`_planted_rows`): cada regra de alerta tem uma loja nova, dentro de
um hub existente, numa janela de datas só dela. Assim a fatia do teste é filtrável e a base de
jan–fev não muda de sentido. Os pedidos plantados contam no total de 12.000 (test_api fixa esse
número), então a base encolhe na mesma medida.

| Loja | Hub | Janela       | O que planta                                             | Regra que deve disparar    |
|------|-----|--------------|----------------------------------------------------------|----------------------------|
| 15   | 1   | 02/03        | 17 entregues atrasados + 10 cancelados (um dia)           | sla/cancel-recorte em baixa amostra |
| 16   | 1   | 05–11/03     | 200 entregues atrasados                                  | sla-recorte                |
| 17   | 1   | 12–18/03     | 4 horas de pico (12h, 13h, 19h, 20h) atrasadas            | sla-pico (rótulo "12h–14h e 19h–21h") |
| 18   | 1   | 01–31/03     | 15 pedidos por dia, no prazo, sem cancelamento            | fatia saudável            |
| 19   | 1   | 18–31/03     | queda de ~60% na última semana                           | volume-queda               |
| 25   | 2   | 08–14/03     | 45% de cancelamento em 200 pedidos                        | cancel-store (loja crítica) |
| 26   | 2   | 20–31/03     | 320 entregues no prazo                                   | contrapeso (hub 2 saudável) |
| 13   | 1   | 20–31/03     | 280 cancelados + 40 entregues atrasados                  | sla-hub com amostra pequena |
| 46   | 4   | 26–31/03     | 320 entregues atrasados, etapas curtas (goods)            | sla-hub sem etapa acima da mediana |
| 14   | 1   | 26–31/03     | 320 entregues no prazo, etapas longas                    | contrapeso do cenário acima |
| 45   | 4   | 01–31/03     | 160 entregas com frete R$ 2 e custo R$ 12                 | custo-frete                |
| 33   | 3   | 03/03        | 160 cancelados                                            | tirar do ar mesmo sozinha  |
| 34   | 3   | 03/03        | 80 cancelados + 80 presos (50%)                           | par da 33; não é 2,5×      |
| 27   | 2   | 03/03        | 130 atrasados + 20 cancelados                             | segmento food com base     |
| 47   | 4   | 03/03        | 2 cancelados                                              | goods 100% sem base        |
| 35   | 3   | 03/03        | 89 cancelados                                             | taxa extrema, amostra fina |
| 36   | 3   | 03/03        | 5 cancelados + 45 atrasados                               | amostra fina sem data      |
| 28   | 2   | 03/03        | 210 presos + 100 atrasados                                | SLA não pede frota         |
| 38   | 3   | 03/03        | 201 cancelados + 99 presos                                | razão com vírgula          |
| 43   | 4   | 03/03        | 30 cancelados + 270 no prazo                              | contrapeso da razão        |
| 24   | 2   | 03/03        | 225 no prazo + 75 atrasados (SLA 75%)                     | borda de 5 p.p.            |
| 44   | 4   | 03/03        | 255 no prazo + 45 atrasados (SLA 85%, goods)              | contrapeso dos 5 p.p.      |
| 37   | 3   | 03/03        | 36 cancelados + 264 presos (12%)                          | borda de 1,6×              |
| 49   | 4   | 03/03        | 9 cancelados + 291 no prazo (3%)                          | contrapeso do 1,6×         |
| 39   | 3   | 03/03        | 9 cancelados + 141 presos (6%)                            | piso de 6% inclusivo       |
| 48   | 4   | 03/03        | 150 no prazo                                              | contrapeso do piso de 6%   |

Os cenários novos ficam em 03/03 para não mexer na janela de volume (18–31/03) nem na data máxima.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from scripts.build_parquet import AMOUNT_OUTLIER, STUCK_CYCLE_MIN

TOTAL_ORDERS = 12_000  # test_api/test_health fixam este total
HUB_INFO = {
    1: ("Hub Centro", "São Paulo", "SP", "food"),
    2: ("Hub Lento", "São Paulo", "SP", "food"),
    3: ("Hub Preso", "Curitiba", "PR", "food"),
    4: ("Hub Goods", "Curitiba", "PR", "good"),
}
COLUMNS = (
    "order_id", "created_at", "created_date", "hour", "weekday", "status", "amount", "delivery_fee",
    "delivery_cost", "store_id", "store_name", "segment", "hub_id", "hub_name", "city", "state", "channel",
    "channel_type", "payment_method", "has_chargeback", "modal", "driver_type", "distance_m",
    "delivery_attempts", "production_min", "collected_min", "walking_min", "expedition_min", "transit_min",
    "cycle_min",
)
BASE_SQL = """
select setseed(0.42);
create table fact as
with base as (
    select
        i as order_id,
        -- 64.757 min é o fim da base original (9.251 linhas × 7 min). Menos linhas
        -- continuam espalhadas até ~15/02, senão fevereiro fica sem pedido medido.
        timestamp '2021-01-01 11:00:00'
            + to_minutes(cast(((i - 1) * 64757) / ({base_rows} - 1) as bigint)) as created_at,
        (i % 4) + 1 as hub_id,
        ((i % 4) + 1) * 10 + (i % 3) as store_id,
        random() as r1, random() as r2, random() as r3
    from range(1, {base_rows} + 1) t(i)
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
"""
FLAGS_SQL = f"""
alter table fact add column cycle_outlier boolean;
alter table fact add column amount_outlier boolean;
update fact set cycle_outlier = cycle_min > {STUCK_CYCLE_MIN}, amount_outlier = amount > {AMOUNT_OUTLIER};
"""
LATE = 90.0  # food passa de 60 min; goods (120 min) continua no prazo
GOODS_LATE = 150.0  # goods passa de 120 min
STUCK_CYCLE = 600.0  # acima de 4h: preso, fora do SLA
ON_TIME = 30.0
LONG_STAGES = (12.0, 2.0, 5.0, 15.0)  # mesma ordem de STAGES: preparo, coleta, expedição, trânsito
SHORT_STAGES = (3.0, 1.0, 2.0, 5.0)


def _order(
    store: int,
    at: datetime,
    *,
    status: str = "delivered",
    cycle: float = ON_TIME,
    stages: tuple[float, float, float, float] = LONG_STAGES,
    fee: float = 9.9,
    cost: float = 8.0,
) -> dict:
    hub = store // 10
    hub_name, city, state, segment = HUB_INFO[hub]
    production, collected, expedition, transit = stages
    return {
        "created_at": at,
        "created_date": at.date(),
        "hour": at.hour,
        "weekday": at.weekday(),
        "status": status,
        "amount": 80.0,
        "delivery_fee": fee,
        "delivery_cost": cost,
        "store_id": store,
        "store_name": f"Loja {store}",
        "segment": segment,
        "hub_id": hub,
        "hub_name": hub_name,
        "city": city,
        "state": state,
        "channel": "Food Place",
        "channel_type": "marketplace",
        "payment_method": "online",
        "has_chargeback": False,
        "modal": "moto",
        "driver_type": "freelance",
        "distance_m": 2000,
        "delivery_attempts": 1,
        "production_min": production,
        "collected_min": collected,
        "walking_min": 3.0,
        "expedition_min": expedition,
        "transit_min": transit,
        "cycle_min": cycle,
    }


def _planted_rows() -> list[dict]:
    rows: list[dict] = []
    add = rows.append

    def at(day: int, hour: int, minute: int = 0) -> datetime:
        return datetime(2021, 3, day, hour, minute)

    # 15: um dia, amostra pequena (17 entregues medidos, todos atrasados) e 10 cancelados.
    for k in range(17):
        add(_order(15, at(2, 9 + k % 12, (k * 7) % 60), cycle=LATE))
    for k in range(10):
        add(_order(15, at(2, 10 + k % 8, (k * 5) % 60), status="canceled"))

    # 16: SLA ruim com base grande (200 entregues atrasados).
    for k in range(200):
        add(_order(16, at(5 + k % 7, 10 + k % 12, (k * 3) % 60), cycle=LATE))

    # 17: pico nas 12h, 13h, 19h e 20h (40 atrasados por hora); outras 20 horas com 2 pedidos no prazo.
    peak_hours = (12, 13, 19, 20)
    for hour in peak_hours:
        for k in range(40):
            add(_order(17, at(12 + k % 7, hour, (k * 7) % 60), cycle=LATE))
    for hour in range(24):
        if hour in peak_hours:
            continue
        for k in range(2):
            add(_order(17, at(12 + k, hour, 30), cycle=ON_TIME))

    # 18: saudável, 15 pedidos por dia em março, sempre no prazo e sem cancelamento.
    for day in range(1, 32):
        for k in range(15):
            add(_order(18, at(day, 8 + k % 14, (k * 11) % 60)))

    # 19: queda de volume: 22 pedidos por dia em 18–24/03 e 9 por dia em 25–31/03.
    for day in range(18, 25):
        for k in range(22):
            add(_order(19, at(day, 9 + k % 12, (k * 2) % 60)))
    for day in range(25, 32):
        for k in range(9):
            add(_order(19, at(day, 9 + k % 12, (k * 3) % 60)))

    # 25: loja crítica, não quebrada. 200 pedidos, 9 de cada 20 cancelados (45%).
    for k in range(200):
        add(_order(25, at(8 + k % 7, 10 + k % 10, (k * 5) % 60), status="canceled" if k % 20 < 9 else "delivered"))

    # 26: hub 2 no prazo (320 pedidos), 13: hub 1 com quase tudo cancelado e 40 atrasados. Mesma janela.
    for k in range(320):
        add(_order(26, at(20 + k % 12, 9 + k % 13, (k * 3) % 60)))
    for k in range(280):
        add(_order(13, at(20 + k % 12, 9 + k % 13, (k * 2) % 60), status="canceled"))
    for k in range(40):
        add(_order(13, at(20 + k % 12, 9 + k % 13, (k * 4) % 60), cycle=LATE))

    # 46: hub 4 (goods) com 320 pedidos atrasados e etapas curtas. 14: hub 1 no prazo, etapas longas.
    for k in range(320):
        add(_order(46, at(26 + k % 6, 9 + k % 13, (k * 3) % 60), cycle=150.0, stages=SHORT_STAGES))
    for k in range(320):
        add(_order(14, at(26 + k % 6, 9 + k % 13, (k * 3) % 60)))

    # 45: 160 entregas no prazo com frete de R$ 2 e custo de R$ 12 (subsídio de R$ 10 por pedido).
    for k in range(160):
        add(_order(45, at(1 + k % 31, 9 + k % 12, (k * 5) % 60), fee=2.0, cost=12.0))

    # Cenários de 03/03. Lojas novas, fora da janela de volume (18–31/03).
    def on_day(index: int) -> datetime:
        return datetime(2021, 3, 3, 8 + (index // 60) % 14, index % 60)

    def add_n(store: int, n: int, *, status: str = "delivered", cycle: float = ON_TIME, start: int = 0) -> int:
        for k in range(n):
            add(_order(store, on_day(start + k), status=status, cycle=cycle))
        return start + n

    # 33: 100% cancelada, com base. 34: 50%, entregas presas para não diluir o hub 3.
    # Cancelado com ciclo curto iria ocupar a página dos menores ciclos do hub 3.
    add_n(33, 160, status="canceled", cycle=LATE)
    add_n(34, 80, status="canceled", cycle=LATE)
    add_n(34, 80, cycle=STUCK_CYCLE, start=80)
    # 27 + 47: food leva os cancelamentos; goods é 2/2 e não pode ser "concentrado".
    add_n(27, 130, cycle=LATE)
    add_n(27, 20, status="canceled", cycle=LATE, start=130)
    add_n(47, 2, status="canceled", cycle=LATE)
    # 35: 89/89 cancelados. 36: 10% de cancelamento e SLA ruim, abaixo de 100 pedidos.
    add_n(35, 89, status="canceled", cycle=LATE)
    add_n(36, 45, cycle=LATE)
    add_n(36, 5, status="canceled", cycle=LATE, start=45)
    # 28: 210/310 presos e os 100 medidos atrasados.
    add_n(28, 210, cycle=STUCK_CYCLE)
    add_n(28, 100, cycle=LATE, start=210)
    # 38 e 43: 67% contra 10% → fator com casa decimal.
    add_n(38, 201, status="canceled", cycle=LATE)
    add_n(38, 99, cycle=STUCK_CYCLE, start=201)
    add_n(43, 30, status="canceled", cycle=LATE)
    add_n(43, 270, start=30)
    # 24 e 44: SLA 75% e 85%, recorte 80%. O desvio é exatamente 5 pontos.
    add_n(24, 225)
    add_n(24, 75, cycle=LATE, start=225)
    add_n(44, 255)
    add_n(44, 45, cycle=GOODS_LATE, start=255)
    # 37 e 49: 12% e 3%. O hub quente é exatamente 1,6× o recorte (7,5%).
    add_n(37, 36, status="canceled", cycle=LATE)
    add_n(37, 264, cycle=STUCK_CYCLE, start=36)
    add_n(49, 9, status="canceled", cycle=LATE)
    add_n(49, 291, start=9)
    # 39 e 48: 6% contra 0%. O piso de 6% inclui a igualdade.
    add_n(39, 9, status="canceled", cycle=LATE)
    add_n(39, 141, cycle=STUCK_CYCLE, start=9)
    add_n(48, 150)

    return rows


PLANTED = _planted_rows()
BASE_ROWS = TOTAL_ORDERS - len(PLANTED)
assert BASE_ROWS > 0


def _build_parquet(path: Path) -> None:
    con = duckdb.connect()
    con.execute(BASE_SQL.format(base_rows=BASE_ROWS))
    for offset, row in enumerate(PLANTED, start=1):
        row["order_id"] = BASE_ROWS + offset
    placeholders = ", ".join(["?"] * len(COLUMNS))
    con.executemany(
        f"insert into fact ({', '.join(COLUMNS)}) values ({placeholders})",
        [tuple(row[c] for c in COLUMNS) for row in PLANTED],
    )
    con.execute(FLAGS_SQL)
    con.execute(f"copy fact to '{path.as_posix()}' (format parquet)")


@pytest.fixture(scope="session")
def parquet_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "orders.parquet"
    _build_parquet(path)
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
