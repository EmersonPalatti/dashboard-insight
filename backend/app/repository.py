"""Consultas analíticas em DuckDB sobre o parquet carregado em memória.

Todo SQL recebe valores do usuário só como parâmetros (`?`). Nomes de coluna e
ordenação vêm de listas fixas (DIMENSIONS, SORTS, ORDER_SORTS).
"""

from __future__ import annotations

import tempfile
import threading
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import duckdb

from app.filters import Filters
from app.schemas import Dimension, Grain, SortKey

# Colunas de ciclo/etapa só valem para entregues e sem pedido "preso" (> 4h).
_VALID = "status = 'delivered' and not cycle_outlier"
_SALE = "status = 'delivered' and not amount_outlier"

METRICS_SQL = f"""
    count(*)::int as orders,
    count(*) filter (where status = 'delivered')::int as delivered,
    count(*) filter (where status = 'canceled')::int as canceled,
    coalesce(sum(amount) filter (where {_SALE}), 0)::double as gmv,
    avg(amount) filter (where {_SALE}) as ticket,
    avg((status = 'canceled')::int) as cancel_rate,
    median(cycle_min) filter (where {_VALID}) as cycle_p50,
    quantile_cont(cycle_min, 0.9) filter (where {_VALID}) as cycle_p90,
    avg(on_time(segment, cycle_min)::int) filter (where {_VALID} and cycle_min is not null) as sla_rate,
    avg(cycle_outlier::int) filter (where status = 'delivered') as stuck_rate,
    median(production_min) filter (where {_VALID}) as production_p50,
    median(collected_min) filter (where {_VALID}) as collected_p50,
    median(expedition_min) filter (where {_VALID}) as expedition_p50,
    median(transit_min) filter (where {_VALID}) as transit_p50,
    median(distance_m) filter (where status = 'delivered') / 1000.0 as distance_p50_km,
    avg(delivery_fee) filter (where status = 'delivered') as fee_avg,
    avg(delivery_cost) filter (where status = 'delivered') as cost_avg,
    avg(delivery_cost - delivery_fee) filter (where status = 'delivered') as subsidy
"""

# dimensão -> (chave, rótulo, pai)
DIMENSIONS: dict[str, tuple[str, str, str]] = {
    "city": ("city", "city", "state"),
    "hub": ("hub_id", "hub_name", "city"),
    "store": ("store_id", "store_name", "hub_name"),
    "channel": ("channel", "channel", "channel_type"),
    "channel_type": ("channel_type", "channel_type", "null"),
    "segment": ("segment", "segment", "null"),
    "modal": ("modal", "modal", "null"),
    "driver_type": ("driver_type", "driver_type", "null"),
    "payment_method": ("payment_method", "payment_method", "null"),
    "hour": ("hour", "hour::varchar", "null"),
    "weekday": ("weekday", "weekday::varchar", "null"),
}
SORTS: dict[str, str] = {
    "orders": "orders", "gmv": "gmv", "ticket": "ticket", "cancel_rate": "cancel_rate",
    "cycle_p50": "cycle_p50", "sla_rate": "sla_rate", "stuck_rate": "stuck_rate", "subsidy": "subsidy",
}
ORDER_COLUMNS = (
    "order_id, created_at, status, city, hub_name, store_name, segment, channel, modal, payment_method, "
    "amount, delivery_fee, cycle_min, production_min, transit_min, distance_m::int as distance_m, "
    "case when status = 'delivered' and cycle_min is not null then on_time(segment, cycle_min) end as on_time"
)
ORDER_SORTS = {
    "created_at", "amount", "delivery_fee", "cycle_min", "production_min", "transit_min",
    "distance_m", "store_name", "hub_name", "city", "status",
}
GRAINS = {"hour": "hour", "day": "day", "week": "week"}


class Repository:
    def __init__(self, data_path: Path, sla_food_min: int, sla_good_min: int, cache_size: int = 512):
        if not data_path.exists():
            raise FileNotFoundError(
                f"{data_path} não existe. Rode `python scripts/build_parquet.py` com os CSVs em data/raw/."
            )
        self._con = duckdb.connect(":memory:")
        self._con.execute("set memory_limit = '400MB'")
        # Spill de memória vai para o temp do sistema, nunca para a pasta do projeto.
        spill = (Path(tempfile.gettempdir()) / "central-operacoes-duckdb").as_posix().replace("'", "''")
        self._con.execute(f"set temp_directory = '{spill}'")
        path = data_path.as_posix().replace("'", "''")
        self._con.execute(f"create table orders as select * from read_parquet('{path}')")
        self._con.execute(
            "create macro on_time(seg, cyc) as "
            f"cyc <= case seg when 'good' then {int(sla_good_min)} else {int(sla_food_min)} end"
        )
        self.sla_food_min = sla_food_min
        self.sla_good_min = sla_good_min
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()
        self.min_date, self.max_date, self.total_orders = self._con.execute(
            "select min(created_date), max(created_date), count(*)::int from orders"
        ).fetchone()

    # ------------------------------------------------------------------ infra
    def _rows(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        cur = self._con.cursor()  # um cursor por chamada: seguro entre threads
        try:
            result = cur.execute(sql, params or [])
            columns = [d[0] for d in result.description]
            return [dict(zip(columns, row)) for row in result.fetchall()]
        finally:
            cur.close()

    def _cached(self, key: str, compute: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        value = compute()
        with self._lock:
            self._cache[key] = value
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return value

    # ------------------------------------------------------------------ meta
    def options(self, key: str, label: str, parent: str = "null", where: str = "true") -> list[dict]:
        return self._rows(
            f"select {key} as value, {label} as label, {parent} as parent, count(*)::int as orders "
            f"from orders where {key} is not null and {where} group by all order by orders desc"
        )

    def meta(self) -> dict:
        def build() -> dict:
            return {
                "min_date": self.min_date,
                "max_date": self.max_date,
                "total_orders": self.total_orders,
                "sla_food_min": self.sla_food_min,
                "sla_good_min": self.sla_good_min,
                "cities": self.options("city", "city", "state"),
                "hubs": self.options("hub_id", "hub_name", "city"),
                "stores": self.options("store_id", "store_name", "hub_id"),
                "segments": self.options("segment", "segment"),
                "channel_types": self.options("channel_type", "channel_type"),
                "modals": self.options("modal", "modal"),
            }

        return self._cached("meta", build)

    def names(self, dimension: str, ids: list[int]) -> list[str]:
        if not ids:
            return []
        key, label, _ = DIMENSIONS[dimension]
        rows = self._rows(f"select distinct {label} as label from orders where list_contains(?, {key})", [ids])
        return sorted(r["label"] for r in rows)

    def describe(self, f: Filters) -> str:
        """Descrição legível do recorte, usada pelo agente e pela exportação."""
        start = f.start or self.min_date
        end = f.end or self.max_date
        parts = [f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"]
        if f.city:
            parts.append("cidade " + ", ".join(f.city))
        if f.hub:
            parts.append("hub " + ", ".join(self.names("hub", f.hub)))
        if f.store:
            names = self.names("store", f.store)
            parts.append("loja " + (", ".join(names) if len(names) <= 4 else f"{len(names)} lojas"))
        labels = {"food": "food", "good": "goods", "marketplace": "marketplace", "own": "canal próprio",
                  "moto": "moto", "bike": "bike"}
        for title, values in (("segmento", f.segment), ("canal", f.channel_type), ("modal", f.modal)):
            if values:
                parts.append(f"{title} " + ", ".join(labels.get(v, v) for v in values))
        return " · ".join(parts)

    # ------------------------------------------------------------- analytics
    def metrics(self, f: Filters) -> dict:
        def build() -> dict:
            where, params = f.where()
            return self._rows(f"select {METRICS_SQL} from orders where {where}", params)[0]

        return self._cached("metrics:" + f.cache_key(), build)

    def period(self, f: Filters) -> tuple[date, date]:
        return (f.start or self.min_date, f.end or self.max_date)

    def previous_period(self, f: Filters) -> tuple[date, date] | None:
        start, end = self.period(f)
        length = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
        if prev_start < self.min_date:
            return None
        return prev_start, prev_end

    def timeseries(self, f: Filters, grain: Grain) -> list[dict]:
        trunc = GRAINS[grain]

        def build() -> list[dict]:
            where, params = f.where()
            return self._rows(
                f"""select date_trunc('{trunc}', created_at) as t,
                       count(*)::int as orders,
                       count(*) filter (where status = 'delivered')::int as delivered,
                       coalesce(sum(amount) filter (where {_SALE}), 0)::double as gmv,
                       avg((status = 'canceled')::int) as cancel_rate,
                       median(cycle_min) filter (where {_VALID}) as cycle_p50,
                       avg(on_time(segment, cycle_min)::int)
                           filter (where {_VALID} and cycle_min is not null) as sla_rate
                    from orders where {where} group by 1 order by 1""",
                params,
            )

        return self._cached(f"ts:{grain}:" + f.cache_key(), build)

    def heatmap(self, f: Filters) -> list[dict]:
        def build() -> list[dict]:
            where, params = f.where()
            return self._rows(
                f"""select weekday::int as weekday, hour::int as hour, count(*)::int as orders,
                       avg((status = 'canceled')::int) as cancel_rate,
                       median(cycle_min) filter (where {_VALID}) as cycle_p50,
                       avg(on_time(segment, cycle_min)::int)
                           filter (where {_VALID} and cycle_min is not null) as sla_rate
                    from orders where {where} group by all order by 1, 2""",
                params,
            )

        return self._cached("heat:" + f.cache_key(), build)

    def breakdown(
        self,
        f: Filters,
        by: Dimension,
        sort: SortKey = "orders",
        desc: bool = True,
        limit: int = 50,
        min_orders: int = 0,
    ) -> list[dict]:
        key, label, parent = DIMENSIONS[by]
        order = SORTS[sort]
        direction = "desc" if desc else "asc"

        def build() -> list[dict]:
            where, params = f.where()
            return self._rows(
                f"""select {key} as key, {label} as label, {parent}::varchar as parent, {METRICS_SQL}
                    from orders where {where} and {key} is not null
                    group by all having count(*) >= ?
                    order by {order} {direction} nulls last, orders desc limit ?""",
                [*params, int(min_orders), int(limit)],
            )

        return self._cached(f"bd:{by}:{sort}:{desc}:{limit}:{min_orders}:" + f.cache_key(), build)

    def orders_page(self, f: Filters, offset: int, limit: int, sort: str, desc: bool) -> dict:
        if sort not in ORDER_SORTS:
            sort = "created_at"
        direction = "desc" if desc else "asc"
        where, params = f.where()
        total = self._rows(f"select count(*)::int as n from orders where {where}", params)[0]["n"]
        rows = self._rows(
            f"select {ORDER_COLUMNS} from orders where {where} "
            f"order by {sort} {direction} nulls last, order_id limit ? offset ?",
            [*params, int(limit), int(offset)],
        )
        return {"total": total, "offset": offset, "limit": limit, "rows": rows}

    def export_csv(self, f: Filters, target: Path) -> None:
        where, params = f.where()
        cur = self._con.cursor()
        try:
            cur.execute(
                f"copy (select {ORDER_COLUMNS} from orders where {where} order by created_at) "
                f"to '{target.as_posix()}' (header, delimiter ',')",
                params,
            )
        finally:
            cur.close()
