"""Consultas analíticas em DuckDB sobre o parquet carregado em memória.

Todo SQL recebe valores do usuário só como parâmetros (`?`). Nomes de coluna e
ordenação vêm de listas fixas (DIMENSIONS, SORTS, ORDER_SORTS).
"""

from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from app.filters import Filters
from app.schemas import Dimension, Grain, SortKey

# Colunas de ciclo/etapa só valem para entregues e sem pedido "preso" (> 4h).
_VALID = "status = 'delivered' and not cycle_outlier"
_SALE = "status = 'delivered' and not amount_outlier"
# Frete, custo e subsídio na mesma base, senão a frase "custa X e cobra Y" não fecha.
_PRICED = "status = 'delivered' and delivery_fee is not null and delivery_cost is not null"
# Base da medição: entregues com ciclo e sem presos. É o denominador do SLA e o universo da mediana.
_MEASURED = f"{_VALID} and cycle_min is not null"
# Abaixo disso, SLA e ciclo mediano saem com aviso de amostra pequena. Com n = 100, a margem de erro
# de 95% de uma taxa perto de 80% é ±8 p.p. (1,96 · √(0,8 · 0,2 / 100)), mais que o desvio de 5 p.p.
# (SLA_BELOW_GAP) que o painel usa para marcar uma linha. Abaixo de 100, a figura oscila mais que a
# diferença que o painel quer apontar.
MIN_MEASURED = 100

# Desvio de uma linha do ranking em relação ao recorte (marcado pelo servidor).
SLA_BELOW_GAP = 0.05  # no prazo abaixo de SLA do recorte menos 5 pontos
CANCEL_ABOVE_RATIO = 1.6  # cancelamento acima de 1,6x o do recorte...
CANCEL_ABOVE_FLOOR = 0.06  # ...e de pelo menos 6%

METRICS_SQL = f"""
    count(*)::int as orders,
    count(*) filter (where status = 'delivered')::int as delivered,
    count(*) filter (where status = 'canceled')::int as canceled,
    coalesce(sum(amount) filter (where {_SALE}), 0)::double as gmv,
    avg(amount) filter (where {_SALE}) as ticket,
    avg((status = 'canceled')::int) as cancel_rate,
    count(*) filter (where {_MEASURED})::int as measured,
    count(*) filter (where {_MEASURED}) < {MIN_MEASURED} as low_sample,
    count(*) < {MIN_MEASURED} as volume_low_sample,
    median(cycle_min) filter (where {_VALID}) as cycle_p50,
    quantile_cont(cycle_min, 0.9) filter (where {_VALID}) as cycle_p90,
    avg(on_time(segment, cycle_min)::int) filter (where {_MEASURED}) as sla_rate,
    avg(cycle_outlier::int) filter (where status = 'delivered') as stuck_rate,
    median(production_min) filter (where {_VALID}) as production_p50,
    median(collected_min) filter (where {_VALID}) as collected_p50,
    median(expedition_min) filter (where {_VALID}) as expedition_p50,
    median(transit_min) filter (where {_VALID}) as transit_p50,
    median(distance_m) filter (where {_VALID}) / 1000.0 as distance_p50_km,
    avg(delivery_fee) filter (where {_PRICED}) as fee_avg,
    avg(delivery_cost) filter (where {_PRICED}) as cost_avg,
    avg(delivery_cost - delivery_fee) filter (where {_PRICED}) as subsidy
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
    "cycle_p50": "cycle_p50", "cycle_p90": "cycle_p90", "sla_rate": "sla_rate",
    "stuck_rate": "stuck_rate", "production_p50": "production_p50",
    "collected_p50": "collected_p50", "expedition_p50": "expedition_p50",
    "transit_p50": "transit_p50", "distance_p50_km": "distance_p50_km",
    "fee_avg": "fee_avg", "cost_avg": "cost_avg", "subsidy": "subsidy",
}
ORDER_COLUMNS = (
    "order_id, created_at, status, city, hub_name, store_name, segment, channel, modal, payment_method, "
    "amount, delivery_fee, cycle_min, production_min, transit_min, distance_m::int as distance_m, "
    f"case when {_MEASURED} then on_time(segment, cycle_min) end as on_time"
)
ORDER_SORTS = {
    "created_at", "amount", "delivery_fee", "cycle_min", "production_min", "transit_min",
    "distance_m", "store_name", "hub_name", "city", "status",
}
GRAINS = {"hour": "hour", "day": "day", "week": "week"}

# Rótulo da linha quando a dimensão vem nula. Sem isso a soma da quebra perde pedidos.
NULL_LABELS = {
    "modal": "Sem entregador",
    "payment_method": "Sem pagamento",
}
_NULL_LABEL = "Não informado"

# Métricas só da consulta estruturada (query_metrics). Ficam fora de METRICS_SQL para não mudar
# o contrato dos endpoints que já existem.
EXTRA_METRICS_SQL = f"""
    avg(has_chargeback::int) as chargeback_rate,
    avg((delivery_attempts > 1)::int) filter (where status = 'delivered') as multi_attempt_rate,
    median(walking_min) filter (where {_VALID}) as walking_p50
"""
# Numerador e denominador de cada taxa, com a mesma base do avg() correspondente (avg ignora nulo).
# A decomposição do "por que mudou" precisa dos dois por grupo para somar exato.
RATE_PARTS: dict[str, tuple[str, str]] = {
    "cancel_rate": ("status = 'canceled'", "status is not null"),
    "sla_rate": (f"{_MEASURED} and on_time(segment, cycle_min)", _MEASURED),
    "stuck_rate": ("status = 'delivered' and cycle_outlier", "status = 'delivered' and cycle_outlier is not null"),
    "chargeback_rate": ("has_chargeback", "has_chargeback is not null"),
    "multi_attempt_rate": (
        "status = 'delivered' and delivery_attempts > 1",
        "status = 'delivered' and delivery_attempts is not null",
    ),
}
RATE_PARTS_SQL = ",\n".join(
    f"count(*) filter (where {num})::int as {name}__num, count(*) filter (where {den})::int as {name}__den"
    for name, (num, den) in RATE_PARTS.items()
)


def _aliases(sql: str) -> list[str]:
    return re.findall(r"\bas (\w+),?\s*$", sql, re.MULTILINE)


# Chaves aceitas por query_metrics: tudo de METRICS_SQL menos os avisos de amostra, mais as extras.
QUERY_METRICS: tuple[str, ...] = tuple(
    [a for a in _aliases(METRICS_SQL) if a not in ("low_sample", "volume_low_sample")]
    + _aliases(EXTRA_METRICS_SQL)
)
TIME_DIMENSIONS = ("hour", "weekday")
QUERY_COMPARES = ("previous", "rest")
_TIME_RANGES = {"hour": range(24), "weekday": range(7)}
_MAX_QUERY_METRICS = 8
_MAX_GROUP_BY = 2
_MAX_QUERY_LIMIT = 50
_MAX_WHERE_VALUES = 50
# Soma por grupo: grupo sem pedido vale 0, não "sem dado".
ADDITIVE_METRICS = ("orders", "delivered", "canceled", "gmv", "measured")


def _normalize_metrics(metrics: list[str] | None) -> list[str]:
    wanted = list(dict.fromkeys(str(m).strip() for m in (metrics or [])))
    if not wanted:
        raise ValueError(f"Informe ao menos uma métrica. Válidas: {', '.join(QUERY_METRICS)}.")
    if len(wanted) > _MAX_QUERY_METRICS:
        raise ValueError(f"No máximo {_MAX_QUERY_METRICS} métricas por consulta (recebidas {len(wanted)}).")
    unknown = [m for m in wanted if m not in QUERY_METRICS]
    if unknown:
        raise ValueError(f"Métrica desconhecida: {', '.join(unknown)}. Válidas: {', '.join(QUERY_METRICS)}.")
    return wanted


def _normalize_group_by(group_by: list[str] | None) -> list[str]:
    dims = [str(d).strip() for d in (group_by or [])]
    if len(dims) > _MAX_GROUP_BY:
        raise ValueError(f"No máximo {_MAX_GROUP_BY} dimensões em group_by (recebidas {len(dims)}).")
    if len(set(dims)) != len(dims):
        raise ValueError("group_by não pode repetir dimensão.")
    unknown = [d for d in dims if d not in DIMENSIONS]
    if unknown:
        raise ValueError(f"Dimensão desconhecida: {', '.join(unknown)}. Válidas: {', '.join(DIMENSIONS)}.")
    return dims


def _time_value(dim: str, value: Any) -> int:
    valid = _TIME_RANGES[dim]
    try:
        number = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError, OverflowError):
        number = None
    if isinstance(value, bool) or number is None or number not in valid or (
        isinstance(value, float) and value != number
    ):
        raise ValueError(f"{dim} aceita só inteiros de {valid.start} a {valid.stop - 1} (recebido {value!r}).")
    return number


def _normalize_where(where: dict[str, Any] | None) -> dict[str, list]:
    """Valida a subfatia: dimensão de DIMENSIONS -> valores. Hora e dia da semana viram inteiros."""
    norm: dict[str, list] = {}
    for dim, raw in (where or {}).items():
        if dim not in DIMENSIONS:
            raise ValueError(f"Dimensão desconhecida em where: {dim!r}. Válidas: {', '.join(DIMENSIONS)}.")
        values = list(raw) if isinstance(raw, (list, tuple, set)) else [raw]
        if len(values) > _MAX_WHERE_VALUES:
            raise ValueError(f"No máximo {_MAX_WHERE_VALUES} valores por dimensão em where ({dim}).")
        if dim in _TIME_RANGES:
            clean: list = sorted({_time_value(dim, v) for v in values})
        else:
            # Sem diferenciar maiúsculas: "hub centro" e "Hub Centro" são o mesmo valor.
            by_lower: dict[str, str] = {}
            for v in values:
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                text = "" if v is None else str(v).strip()
                if text:
                    by_lower.setdefault(text.lower(), text)
            clean = [by_lower[k] for k in sorted(by_lower)]
        if clean:
            norm[dim] = clean
    return dict(sorted(norm.items()))


def _where_sql(norm: dict[str, list]) -> tuple[str, list]:
    """SQL da subfatia (só `?`). Valor casa com a chave ou o rótulo; o rótulo de nulo casa com nulo."""
    clauses: list[str] = []
    params: list = []
    for dim, values in norm.items():
        key, label, _ = DIMENSIONS[dim]
        if dim in _TIME_RANGES:
            clauses.append(f"list_contains(?, {key})")
            params.append(values)
            continue
        lowered = [v.lower() for v in values]
        clause = (
            f"list_contains(?, lower(cast({label} as varchar))) or list_contains(?, lower(cast({key} as varchar)))"
        )
        params.extend([lowered, lowered])
        if NULL_LABELS.get(dim, _NULL_LABEL).lower() in lowered:
            clause += f" or {key} is null"
        clauses.append(f"({clause})")
    return " and ".join(clauses), params


def _empty_compare(metrics: list[str]) -> dict:
    """Grupo sem par no outro lado: soma vale 0, taxa/mediana não existe."""
    return {
        **{m: (0 if m in ADDITIVE_METRICS else None) for m in metrics},
        "orders": 0,
        "measured": 0,
    }


def _delta(current: dict, other: dict | None, metrics: list[str]) -> dict | None:
    if other is None:
        return None
    return {
        m: (current[m] - other[m] if current.get(m) is not None and other.get(m) is not None else None)
        for m in metrics
    }


def _flag_outliers(rows: list[dict], base: dict) -> list[dict]:
    """Marca linhas do ranking que desviam do recorte (`base` = metrics do recorte inteiro).

    Taxa nula nunca é marcada: sem base para comparar, não há desvio.
    Amostra pequena nunca é marcada. SLA usa a base medida (`low_sample`, abaixo de MIN_MEASURED).
    Cancelamento usa todos os pedidos como denominador, então a mesma régua vale para `orders`.
    Chave ausente (linha montada à mão, sem METRICS_SQL) cai na regra antiga: não bloqueia a marca.
    """
    sla_floor = base["sla_rate"] - SLA_BELOW_GAP if base["sla_rate"] is not None else None
    base_cancel = base["cancel_rate"] or 0.0
    for row in rows:
        sla_ok = not row.get("low_sample", False)
        # "mais de 5 pontos": exatamente 5 pontos não marca.
        row["sla_below"] = (
            sla_ok and sla_floor is not None and row["sla_rate"] is not None and row["sla_rate"] < sla_floor
        )
        cancel_ok = row.get("orders", MIN_MEASURED) >= MIN_MEASURED
        rate = row["cancel_rate"]
        # "acima de 1,6×" é estrito; "pelo menos 6%" inclui o piso.
        row["cancel_above"] = (
            cancel_ok
            and rate is not None
            and rate >= CANCEL_ABOVE_FLOOR
            and rate > base_cancel * CANCEL_ABOVE_RATIO
        )
    return rows


# Rótulos de exibição dos valores crus do dataset (segmento, canal, modal, status).
VALUE_LABELS = {
    "food": "food",
    "good": "goods",
    "marketplace": "marketplace",
    "own": "canal próprio",
    "moto": "moto",
    "bike": "bike",
    "delivered": "concluído",
    "canceled": "cancelado",
}


class _Inflight:
    __slots__ = ("error", "event", "value")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.value: Any = None
        self.error: BaseException | None = None


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class Repository:
    def __init__(self, data_path: Path, sla_food_min: int, sla_good_min: int, cache_size: int = 512):
        if not data_path.exists():
            raise FileNotFoundError(
                f"{data_path} não existe. Rode `python scripts/build_parquet.py` com os CSVs em data/raw/."
            )
        self._con = duckdb.connect(":memory:")
        self._con.execute("set memory_limit = '256MB'")
        self._con.execute("set threads = 2")
        self._con.execute("set preserve_insertion_order = false")
        # Spill de memória vai para o temp do sistema, nunca para a pasta do projeto.
        spill = (Path(tempfile.gettempdir()) / "central-operacoes-duckdb").as_posix().replace("'", "''")
        self._con.execute(f"set temp_directory = '{spill}'")
        path = data_path.as_posix().replace("'", "''")
        self._con.execute(f"create table orders as select * from read_parquet('{path}')")
        # Lojas homônimas no mesmo shopping recebem o id para ficarem distinguíveis no filtro e no ranking.
        self._con.execute(
            """
            update orders set store_name = store_name || ' #' || store_id::varchar
            where store_id in (
                select unnest(ids) from (
                    select hub_id, store_name, list(distinct store_id) as ids
                    from orders
                    group by 1, 2
                    having count(distinct store_id) > 1
                )
            )
            """
        )
        self._con.execute(
            "create macro on_time(seg, cyc) as "
            f"cyc <= case seg when 'good' then {int(sla_good_min)} else {int(sla_food_min)} end"
        )
        self.sla_food_min = sla_food_min
        self.sla_good_min = sla_good_min
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()
        self._inflight: dict[str, _Inflight] = {}
        self._query_sem = threading.BoundedSemaphore(2)
        self.min_date, self.max_date, self.total_orders = self._con.execute(
            "select min(created_date), max(created_date), count(*)::int from orders"
        ).fetchone()

    # ------------------------------------------------------------------ infra
    def close(self) -> None:
        self._con.close()

    def _rows(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        with self._query_sem:
            cur = self._con.cursor()  # um cursor por chamada: seguro entre threads
            try:
                result = cur.execute(sql, params or [])
                columns = [d[0] for d in result.description]
                return [dict(zip(columns, row)) for row in result.fetchall()]
            finally:
                cur.close()

    def cached(self, key: str, compute: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            slot = self._inflight.get(key)
            if slot is None:
                slot = _Inflight()
                self._inflight[key] = slot
                owner = True
            else:
                owner = False

        if not owner:
            slot.event.wait()
            if slot.error is not None:
                raise slot.error
            return slot.value

        try:
            value = compute()
        except BaseException as exc:
            slot.error = exc
            with self._lock:
                self._inflight.pop(key, None)
            slot.event.set()
            raise

        slot.value = value
        with self._lock:
            self._cache[key] = value
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
            self._inflight.pop(key, None)
        slot.event.set()
        return value

    # ------------------------------------------------------------------ meta
    def options(self, key: str, label: str, parent: str = "null") -> list[dict]:
        return self._rows(
            f"select {key} as value, {label} as label, {parent} as parent, count(*)::int as orders "
            f"from orders where {key} is not null group by all order by orders desc"
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

        return self.cached("meta", build)

    def names(self, dimension: str, ids: list[int]) -> list[str]:
        if not ids:
            return []
        key, label, _ = DIMENSIONS[dimension]
        rows = self._rows(f"select distinct {label} as label from orders where list_contains(?, {key})", [ids])
        return sorted(r["label"] for r in rows)

    def describe(self, f: Filters) -> str:
        """Descrição legível do recorte, usada pelo agente e pela exportação."""
        start, end = self.period(f)
        parts = [f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"]
        if f.city:
            parts.append("cidade " + ", ".join(f.city))
        if f.hub:
            hub_labels = self.names("hub", f.hub) or [str(i) for i in dict.fromkeys(f.hub)]
            parts.append("hub " + ", ".join(hub_labels))
        if f.store:
            store_labels = self.names("store", f.store) or [str(i) for i in dict.fromkeys(f.store)]
            parts.append(
                "loja " + (", ".join(store_labels) if len(store_labels) <= 4 else f"{len(store_labels)} lojas")
            )
        for title, values in (
            ("segmento", f.segment),
            ("canal", f.channel_type),
            ("modal", f.modal),
            ("status", f.status),
        ):
            if values:
                parts.append(f"{title} " + ", ".join(VALUE_LABELS.get(v, v) for v in values))
        return " · ".join(parts)

    # ------------------------------------------------------------- analytics
    def metrics(self, f: Filters) -> dict:
        def build() -> dict:
            where, params = f.where()
            return self._rows(f"select {METRICS_SQL} from orders where {where}", params)[0]

        return self.cached("metrics:" + f.cache_key(), build)

    def period(self, f: Filters) -> tuple[date, date]:
        if f.start is not None and f.end is not None:
            return f.start, f.end
        if f.start is not None:
            return f.start, max(self.max_date, f.start)
        if f.end is not None:
            return min(self.min_date, f.end), f.end
        return self.min_date, self.max_date

    def covered_period(self, f: Filters) -> tuple[date | None, date | None]:
        """Período efetivo do recorte para automação.

        Datas pedidas no filtro valem como estão. Sem uma delas, entra o primeiro
        ou o último dia com pedido dentro do recorte. Recorte vazio sem essa data
        devolve None: não há intervalo coberto.
        """
        if f.start is not None and f.end is not None:
            return f.start, f.end

        def build() -> tuple[date | None, date | None]:
            where, params = f.where()
            row = self._rows(
                f"select min(created_date) as start, max(created_date) as end from orders where {where}",
                params,
            )[0]
            return f.start or row["start"], f.end or row["end"]

        return self.cached("covered:" + f.cache_key(), build)

    def previous_period(self, f: Filters) -> tuple[date, date] | None:
        start, end = self.period(f)
        if end < start or start > self.max_date or end < self.min_date:
            return None
        length = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
        if prev_start < self.min_date or prev_end > self.max_date:
            return None
        return prev_start, prev_end

    def timeseries(self, f: Filters, grain: Grain) -> list[dict]:
        trunc = GRAINS[grain]

        def build() -> list[dict]:
            where, params = f.where()
            # Semana truncada cai na segunda anterior ao início do período. O rótulo não pode sair do recorte.
            bucket_params: list = []
            if grain == "week":
                floor_date = max(f.start, self.min_date) if f.start else self.min_date
                bucket = "greatest(date_trunc('week', created_at), ?)"
                bucket_params = [datetime(floor_date.year, floor_date.month, floor_date.day)]
            else:
                bucket = f"date_trunc('{trunc}', created_at)"
            return self._rows(
                f"""select {bucket} as t,
                       count(*)::int as orders,
                       count(*) filter (where status = 'delivered')::int as delivered,
                       coalesce(sum(amount) filter (where {_SALE}), 0)::double as gmv,
                       avg((status = 'canceled')::int) as cancel_rate,
                       median(cycle_min) filter (where {_VALID}) as cycle_p50,
                       avg(on_time(segment, cycle_min)::int)
                           filter (where {_VALID} and cycle_min is not null) as sla_rate
                    from orders where {where} group by 1 order by 1""",
                [*bucket_params, *params],
            )

        return self.cached(f"ts:{grain}:" + f.cache_key(), build)

    def heatmap(self, f: Filters) -> list[dict]:
        def build() -> list[dict]:
            where, params = f.where()
            return self._rows(
                f"""select weekday::int as weekday, hour::int as hour, count(*)::int as orders,
                       count(*) filter (where {_MEASURED})::int as measured,
                       avg((status = 'canceled')::int) as cancel_rate,
                       median(cycle_min) filter (where {_VALID}) as cycle_p50,
                       avg(on_time(segment, cycle_min)::int)
                           filter (where {_VALID} and cycle_min is not null) as sla_rate
                    from orders where {where} group by all order by 1, 2""",
                params,
            )

        return self.cached("heat:" + f.cache_key(), build)

    def breakdown(
        self,
        f: Filters,
        by: Dimension,
        sort: SortKey = "orders",
        desc: bool = True,
        limit: int = 50,
        min_orders: int = 0,
        min_measured: int = 0,
    ) -> list[dict]:
        key, label, parent = DIMENSIONS[by]
        order = SORTS[sort]
        direction = "desc" if desc else "asc"

        def build() -> list[dict]:
            where, params = f.where()
            null_label = NULL_LABELS.get(by, _NULL_LABEL).replace("'", "''")
            shown = f"case when {key} is null then '{null_label}' else {label} end"
            rows = self._rows(
                f"""select {key} as key, {shown} as label, {parent}::varchar as parent, {METRICS_SQL}
                    from orders where {where}
                    group by all having count(*) >= ? and count(*) filter (where {_MEASURED}) >= ?
                    order by {order} {direction} nulls last, orders desc, key asc nulls last limit ?""",
                [*params, int(min_orders), int(min_measured), int(limit)],
            )
            return _flag_outliers(rows, self.metrics(f))

        return self.cached(
            f"bd:{by}:{sort}:{desc}:{limit}:{min_orders}:{min_measured}:" + f.cache_key(),
            build,
        )

    def subslice_metrics(
        self,
        f: Filters,
        *,
        hours: list[int] | None = None,
        weekdays: list[int] | None = None,
        dimension: Dimension | None = None,
        values: list[str] | None = None,
        complement: bool = False,
    ) -> dict:
        """Métricas agregadas de uma subfatia dentro do recorte `f` (ou de seu complemento)."""
        norm_hours = sorted({int(h) for h in hours}) if hours else []
        norm_weekdays = sorted({int(w) for w in weekdays}) if weekdays else []
        norm_vals = [str(v).strip().lower() for v in (values or []) if str(v).strip()]
        dim = dimension if (dimension and norm_vals) else None

        if not norm_hours and not norm_weekdays and not dim:
            return self.metrics(f)

        def build() -> dict:
            base_where, base_params = f.where()
            sub_clauses: list[str] = []
            sub_params: list = []
            if norm_hours:
                sub_clauses.append("list_contains(?, hour)")
                sub_params.append(norm_hours)
            if norm_weekdays:
                sub_clauses.append("list_contains(?, weekday)")
                sub_params.append(norm_weekdays)
            if dim:
                key, label, _ = DIMENSIONS[dim]
                clause = (
                    f"list_contains(?, lower(cast({label} as varchar))) "
                    f"or list_contains(?, lower(cast({key} as varchar)))"
                )
                sub_params.extend([norm_vals, norm_vals])
                if NULL_LABELS.get(dim, _NULL_LABEL).lower() in norm_vals:
                    clause += f" or {key} is null"
                sub_clauses.append(f"({clause})")

            sub_sql = " and ".join(sub_clauses)
            if complement:
                where = f"({base_where}) and not coalesce(({sub_sql}), false)"
            else:
                where = f"({base_where}) and ({sub_sql})"
            return self._rows(f"select {METRICS_SQL} from orders where {where}", [*base_params, *sub_params])[0]

        cache_id = (
            f"sub:{norm_hours}:{norm_weekdays}:{dim}:{sorted(set(norm_vals))}:{complement}:"
            + f.cache_key()
        )
        return self.cached(cache_id, build)

    # ------------------------------------------------------ consulta estruturada
    def _grouped_rows(
        self,
        f: Filters,
        group_by: list[str],
        sub_sql: str = "",
        sub_params: list | None = None,
        *,
        complement: bool = False,
        min_orders: int = 0,
        min_measured: int = 0,
    ) -> list[dict]:
        """Todas as métricas (+ partes das taxas) por grupo, sem limite. Sem group_by: uma linha, o total."""
        base_where, params = f.where()
        where = f"({base_where})"
        if sub_sql:
            where += f" and not coalesce(({sub_sql}), false)" if complement else f" and ({sub_sql})"
            params = [*params, *(sub_params or [])]
        columns: list[str] = []
        for i, dim in enumerate(group_by):
            key, label, _ = DIMENSIONS[dim]
            null_label = NULL_LABELS.get(dim, _NULL_LABEL).replace("'", "''")
            columns.append(
                f"{key} as g{i}_key, case when {key} is null then '{null_label}' else {label} end as g{i}_label"
            )
        select = ", ".join([*columns, METRICS_SQL, EXTRA_METRICS_SQL, RATE_PARTS_SQL])
        sql = f"select {select} from orders where {where}"
        if group_by:
            sql += f" group by all having count(*) >= ? and count(*) filter (where {_MEASURED}) >= ?"
            params = [*params, int(min_orders), int(min_measured)]
        return self._rows(sql, params)

    def grouped_metrics(self, f: Filters, by: str) -> list[dict]:
        """Todos os grupos de uma dimensão no recorte, sem limite, com `key`/`label`, todas as métricas
        de QUERY_METRICS e `<taxa>__num`/`<taxa>__den` (RATE_PARTS). Base do explain_change."""
        _normalize_group_by([by])

        def build() -> list[dict]:
            rows = self._grouped_rows(f, [by])
            for row in rows:
                row["key"] = row.pop("g0_key")
                row["label"] = row.pop("g0_label")
            return rows

        return self.cached(f"grp:{by}:" + f.cache_key(), build)

    def query_metrics(
        self,
        f: Filters,
        *,
        metrics: list[str],
        group_by: list[str] | None = None,
        where: dict[str, list] | None = None,
        compare: str | None = None,
        sort: str | None = None,
        desc: bool = True,
        limit: int = 10,
        min_orders: int = 0,
        min_measured: int = 0,
    ) -> dict:
        """Consulta estruturada dentro do recorte: métricas × até 2 dimensões, subfatia e comparação.

        Valores crus (taxas de 0 a 1). `compare="previous"` usa o período anterior de mesmo tamanho;
        `"rest"` usa o complemento de `where` dentro do recorte. Entrada inválida -> ValueError (pt-BR).
        """
        wanted = _normalize_metrics(metrics)
        dims = _normalize_group_by(group_by)
        norm_where = _normalize_where(where)
        if compare not in (None, *QUERY_COMPARES):
            raise ValueError(f"compare aceita {', '.join(QUERY_COMPARES)} ou nada (recebido {compare!r}).")
        if compare == "rest" and not norm_where:
            raise ValueError("compare='rest' compara a subfatia com o resto do recorte: informe where.")
        sort_metric: str | None = None
        sort_delta = False
        if sort:
            sort = str(sort).strip()
            sort_delta = sort.startswith("delta:")
            sort_metric = sort.removeprefix("delta:")
            if sort_metric not in QUERY_METRICS:
                raise ValueError(f"Ordenação desconhecida: {sort!r}. Use uma métrica ou 'delta:<métrica>'.")
            if sort_delta and compare is None:
                raise ValueError("Ordenar por 'delta:' pede compare='previous' ou compare='rest'.")
            if sort_metric not in wanted:
                wanted.append(sort_metric)  # a coluna da ordenação aparece na resposta
        limit = max(1, min(int(limit), _MAX_QUERY_LIMIT))
        min_orders = max(0, int(min_orders))
        min_measured = max(0, int(min_measured))
        args = {
            "m": wanted, "g": dims, "w": norm_where, "c": compare, "s": sort_metric, "sd": sort_delta,
            "desc": bool(desc), "l": limit, "mo": min_orders, "mm": min_measured,
        }
        cache_id = "qm:" + json.dumps(args, ensure_ascii=False, sort_keys=True) + ":" + f.cache_key()
        return self.cached(
            cache_id,
            lambda: self._query_metrics(
                f, wanted, dims, norm_where, compare, sort_metric, sort_delta, bool(desc), limit,
                min_orders, min_measured,
            ),
        )

    def _query_metrics(
        self,
        f: Filters,
        wanted: list[str],
        dims: list[str],
        norm_where: dict[str, list],
        compare: str | None,
        sort_metric: str | None,
        sort_delta: bool,
        desc: bool,
        limit: int,
        min_orders: int,
        min_measured: int,
    ) -> dict:
        sub_sql, sub_params = _where_sql(norm_where)
        notes: list[str] = []
        start, end = self.period(f)

        def shape(row: dict) -> dict:
            return {
                "orders": row["orders"], "measured": row["measured"], "low_sample": row["low_sample"],
                **{m: row[m] for m in wanted},
            }

        current = (
            self._grouped_rows(f, dims, sub_sql, sub_params, min_orders=min_orders, min_measured=min_measured)
            if dims else []
        )
        total = shape(self._grouped_rows(f, [], sub_sql, sub_params)[0])

        other_f: Filters | None = None
        complement = False
        compare_period = None
        if compare == "previous":
            prev = self.previous_period(f)
            if prev is None:
                notes.append(
                    f"Sem período anterior de mesmo tamanho na base ({self.min_date:%d/%m/%Y} a "
                    f"{self.max_date:%d/%m/%Y}); comparação omitida."
                )
                compare = None
            else:
                other_f = f.with_period(*prev)
                compare_period = {"start": prev[0], "end": prev[1]}
        elif compare == "rest":
            other_f, complement = f, True
            compare_period = {"start": start, "end": end}
            if set(dims) & set(norm_where):
                notes.append(
                    "O resto exclui os valores de where, então agrupar pela mesma dimensão deixa as linhas "
                    "sem par; compare pelos totais."
                )

        total_compare = None
        others: dict[tuple, dict] = {}
        if other_f is not None:
            total_compare = shape(self._grouped_rows(other_f, [], sub_sql, sub_params, complement=complement)[0])
            if dims:
                for row in self._grouped_rows(other_f, dims, sub_sql, sub_params, complement=complement):
                    others[tuple(row[f"g{i}_key"] for i in range(len(dims)))] = shape(row)

        rows: list[dict] = []
        for row in current:
            out = {
                "keys": {
                    dim: {"key": row[f"g{i}_key"], "label": row[f"g{i}_label"]} for i, dim in enumerate(dims)
                },
                **shape(row),
            }
            if compare is not None:
                cmp = others.get(tuple(row[f"g{i}_key"] for i in range(len(dims)))) or _empty_compare(wanted)
                out["compare"] = {m: cmp[m] for m in (*wanted, "orders", "measured")}
                out["delta"] = _delta(out, cmp, wanted)
            else:
                out["compare"] = None
            rows.append(out)

        if sort_delta and compare is None:
            notes.append(f"Sem comparação, a ordenação usa {sort_metric} em vez da variação.")
            sort_delta = False

        def key_tuple(r: dict) -> tuple:
            return tuple((v is None, v) for v in (r["keys"][d]["key"] for d in dims))

        if sort_metric is None and any(d in TIME_DIMENSIONS for d in dims):
            rows.sort(key=key_tuple)  # série no tempo sai em ordem cronológica
            if len(dims) == 1:
                limit = min(_MAX_QUERY_LIMIT, max(limit, len(_TIME_RANGES[dims[0]])))
        else:
            metric = sort_metric or "orders"

            def value(r: dict) -> Any:
                return (r["delta"] or {}).get(metric) if sort_delta else r.get(metric)

            rows.sort(key=lambda r: (-r["orders"], key_tuple(r)))  # desempate estável: volume
            present = [r for r in rows if value(r) is not None]
            present.sort(key=value, reverse=desc)
            rows = present + [r for r in rows if value(r) is None]  # sem valor sempre por último

        n_groups = len(rows)
        if n_groups > limit:
            notes.append(f"Mostrando {limit} de {n_groups} grupos.")
        return {
            "metrics": wanted,
            "group_by": dims,
            "where": norm_where,
            "compare": compare,
            "period": {"start": start, "end": end},
            "compare_period": compare_period if compare is not None else None,
            "total": total,
            "total_compare": total_compare,
            "total_delta": _delta(total, total_compare, wanted),
            "rows": rows[:limit],
            "truncated": n_groups > limit,
            "n_groups": n_groups,
            "note": " ".join(notes) or None,
        }

    def orders_page(self, f: Filters, offset: int, limit: int, sort: str, desc: bool) -> dict:
        if sort not in ORDER_SORTS:
            sort = "created_at"
        total = self.metrics(f)["orders"]
        if offset >= total:
            return {"total": total, "offset": offset, "limit": limit, "rows": []}
        direction = "desc" if desc else "asc"
        where, params = f.where()
        rows = self._rows(
            f"select {ORDER_COLUMNS} from orders where {where} "
            f"order by {sort} {direction} nulls last, order_id limit ? offset ?",
            [*params, int(limit), int(offset)],
        )
        return {"total": total, "offset": offset, "limit": limit, "rows": rows}

    def iter_orders_csv(self, f: Filters, batch_size: int = 5000) -> Iterator[str]:
        """Gera o CSV do recorte em lotes para não materializar dezenas de MB em disco."""
        where, params = f.where()
        cur = self._con.cursor()
        try:
            with self._query_sem:
                result = cur.execute(f"select {ORDER_COLUMNS} from orders where {where} order by created_at", params)
                header = [d[0] for d in result.description]
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator="\n")
            writer.writerow(header)
            yield buf.getvalue()

            while True:
                with self._query_sem:
                    batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                buf.seek(0)
                buf.truncate(0)
                for row in batch:
                    writer.writerow([_csv_cell(v) for v in row])
                yield buf.getvalue()
        finally:
            cur.close()
