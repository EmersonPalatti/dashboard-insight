"""Decomposição determinística de "por que a métrica mudou" entre o recorte e o período anterior.

O LLM escolhe métrica e dimensão; toda a conta fica aqui. Três métodos:

- `shift_share` (taxas): taxa total = Σ wᵢ·rᵢ, com wᵢ = fatia do grupo no denominador da taxa.
  Forma simétrica, que fecha exato com a variação total:
  efeito taxa ᵢ = ((w0ᵢ + w1ᵢ)/2)·(r1ᵢ − r0ᵢ)  ·  efeito mix ᵢ = (w1ᵢ − w0ᵢ)·((r0ᵢ + r1ᵢ)/2 − R̄),
  com R̄ = (R0 + R1)/2. Como Σ(w1ᵢ − w0ᵢ) = 0, subtrair R̄ não muda a soma, mas tira o viés da forma
  sem centro: nela um grupo com taxa estável "explica" a variação só porque o peso dele subiu, e um
  grupo ruim que sumiu contribui zero. Centrado, ganhar peso conta a favor só se a taxa do grupo
  está acima da média.
  Grupo que só existe (ou só tem denominador) num dos períodos usa a taxa do outro período no
  lugar da que falta: efeito taxa 0, tudo vira efeito mix (o grupo entrou ou saiu da conta).
- `additive` (contagens e GMV): contribuição = v1 − v0, soma exata.
- `approx` (medianas e médias): não há soma exata. Vai a variação do grupo e um "impacto"
  (variação × peso atual do grupo) só para ordenar.

Entrada inválida (métrica ou dimensão) levanta ValueError em pt-BR. Falta de dado (sem período
anterior na base, período sem base para a métrica) não é erro do chamador: volta um dict com
`error` em pt-BR e os campos de identificação, sem `drivers`.
"""

from __future__ import annotations

from typing import Any

from app.filters import Filters
from app.repository import ADDITIVE_METRICS, DIMENSIONS, QUERY_METRICS, RATE_PARTS, Repository

# Taxa -> base do peso (denominador). As contas usam `<taxa>__num`/`<taxa>__den` de RATE_PARTS,
# que são esses mesmos denominadores sem os nulos que o avg() ignora.
RATE_DENOMINATORS: dict[str, str] = {
    "cancel_rate": "orders",
    "sla_rate": "measured",
    "stuck_rate": "delivered",
    "chargeback_rate": "orders",
    "multi_attempt_rate": "delivered",
}
# Mediana/média -> volume que pesa o "impacto". Ciclo e etapas valem sobre a base medida.
APPROX_WEIGHTS: dict[str, str] = {
    "cycle_p50": "measured", "cycle_p90": "measured", "production_p50": "measured",
    "collected_p50": "measured", "expedition_p50": "measured", "transit_p50": "measured",
    "distance_p50_km": "measured", "walking_p50": "measured",
    "ticket": "delivered", "fee_avg": "delivered", "cost_avg": "delivered", "subsidy": "delivered",
}
OTHERS_LABEL = "Outros"
_MAX_LIMIT = 50
_EPS = 1e-12

assert set(RATE_DENOMINATORS) == set(RATE_PARTS)
assert set(QUERY_METRICS) == set(RATE_DENOMINATORS) | set(ADDITIVE_METRICS) | set(APPROX_WEIGHTS)


def method_for(metric: str) -> str:
    if metric in RATE_DENOMINATORS:
        return "shift_share"
    if metric in ADDITIVE_METRICS:
        return "additive"
    return "approx"


def _validate(metric: str, by: str) -> None:
    if metric not in QUERY_METRICS:
        raise ValueError(f"Métrica desconhecida: {metric!r}. Válidas: {', '.join(QUERY_METRICS)}.")
    if by not in DIMENSIONS:
        raise ValueError(f"Dimensão desconhecida: {by!r}. Válidas: {', '.join(DIMENSIONS)}.")


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def explain_change(
    repo: Repository, f: Filters, *, metric: str, by: str, limit: int = 5, min_orders: int = 30
) -> dict:
    """Explica a variação de `metric` entre o recorte e o período anterior, grupo a grupo de `by`.

    `drivers`: top `limit` grupos por |contribution| e, se sobrar, um balde "Outros" com o resto e os
    grupos com menos de `min_orders` pedidos nos dois períodos. A soma de `contribution` (incluindo
    "Outros") é exatamente `total.delta` em shift_share e additive.
    """
    _validate(metric, by)
    limit = max(1, min(int(limit), _MAX_LIMIT))
    min_orders = max(0, int(min_orders))
    method = method_for(metric)
    start, end = repo.period(f)
    head: dict[str, Any] = {"metric": metric, "by": by, "method": method, "period": {"start": start, "end": end}}

    prev = repo.previous_period(f)
    if prev is None:
        return {
            **head,
            "previous_period": None,
            "error": (
                f"Sem período anterior de mesmo tamanho na base ({repo.min_date:%d/%m/%Y} a "
                f"{repo.max_date:%d/%m/%Y}); não há com o que comparar."
            ),
        }
    head["previous_period"] = {"start": prev[0], "end": prev[1]}
    cache_id = f"explain:{metric}:{by}:{limit}:{min_orders}:" + f.cache_key()
    return repo.cached(cache_id, lambda: _explain(repo, f, f.with_period(*prev), head, limit, min_orders))


def _explain(repo: Repository, f: Filters, f_prev: Filters, head: dict, limit: int, min_orders: int) -> dict:
    metric, method = head["metric"], head["method"]
    current = {r["key"]: r for r in repo.grouped_metrics(f, head["by"])}
    previous = {r["key"]: r for r in repo.grouped_metrics(f_prev, head["by"])}
    keys = list(current) + [k for k in previous if k not in current]

    base = {"shift_share": RATE_DENOMINATORS, "additive": {}, "approx": APPROX_WEIGHTS}[method].get(metric, metric)

    def weight_of(row: dict) -> float:
        return row[f"{metric}__den"] if method == "shift_share" else (row[base] or 0)

    def value_of(row: dict) -> float | None:
        if method == "shift_share":
            return _ratio(row[f"{metric}__num"], row[f"{metric}__den"])
        return (row[metric] or 0) if method == "additive" else row[metric]

    W1 = sum(weight_of(r) for r in current.values())
    W0 = sum(weight_of(r) for r in previous.values())
    if method == "shift_share":
        total_cur = _ratio(sum(r[f"{metric}__num"] for r in current.values()), W1)
        total_prev = _ratio(sum(r[f"{metric}__num"] for r in previous.values()), W0)
    elif method == "additive":
        total_cur, total_prev = W1, W0
    else:
        total_cur = repo.query_metrics(f, metrics=[metric])["total"][metric]
        total_prev = repo.query_metrics(f_prev, metrics=[metric])["total"][metric]
    if total_cur is None or total_prev is None:
        which = "atual" if total_cur is None else "anterior"
        return {**head, "error": f"Sem base para {metric} no período {which} do recorte."}
    delta = total_cur - total_prev
    mean_rate = (total_cur + total_prev) / 2
    has_delta = abs(delta) > _EPS * max(1.0, abs(total_cur), abs(total_prev))

    units: list[dict] = []
    for k in keys:
        c, p = current.get(k), previous.get(k)
        w1 = weight_of(c) / W1 if c is not None and W1 else 0.0
        w0 = weight_of(p) / W0 if p is not None and W0 else 0.0
        v1 = value_of(c) if c is not None else (0 if method == "additive" else None)
        v0 = value_of(p) if p is not None else (0 if method == "additive" else None)
        unit = {
            "key": k,
            "label": (c or p)["label"],
            "current": v1,
            "previous": v0,
            "delta": v1 - v0 if v1 is not None and v0 is not None else None,
            "weight_current": w1,
            "weight_previous": w0,
            "rate_effect": None,
            "mix_effect": None,
            "contribution": None,
            "share_of_change": None,
            "orders_current": c["orders"] if c else 0,
            "orders_previous": p["orders"] if p else 0,
            "presence": "both" if c and p else ("current_only" if c else "previous_only"),
        }
        if method == "shift_share":
            if v1 is None and v0 is None:
                continue  # sem denominador nos dois lados: peso 0, não mexe na taxa
            r1 = v1 if v1 is not None else v0
            r0 = v0 if v0 is not None else v1
            unit["rate_effect"] = (w0 + w1) / 2 * (r1 - r0)
            unit["mix_effect"] = (w1 - w0) * ((r0 + r1) / 2 - mean_rate)
            unit["contribution"] = unit["rate_effect"] + unit["mix_effect"]
        elif method == "additive":
            unit["contribution"] = unit["delta"]
        else:
            unit["contribution"] = unit["delta"] * w1 if unit["delta"] is not None else None
        if method != "approx" and has_delta:
            unit["share_of_change"] = unit["contribution"] / delta
        units.append(unit)

    def size(u: dict) -> float:
        return abs(u["contribution"] or 0.0)

    small: list[dict] = []
    ranked: list[dict] = []
    for u in units:
        (small if u["orders_current"] < min_orders and u["orders_previous"] < min_orders else ranked).append(u)
    ranked.sort(key=size, reverse=True)
    drivers = ranked[:limit]
    rest = ranked[limit:] + small
    if rest:
        drivers.append(_others(rest, method, metric, current, previous, delta if has_delta else None))

    spread = sum(size(u) for u in units)
    notes = {
        "shift_share": (
            f"Efeito taxa = mudança de {metric} dentro do grupo; efeito mix = mudança do peso do grupo "
            f"na base ({base}), medida contra a média dos dois períodos. Grupo presente em só um período entra "
            "como efeito mix puro."
        ),
        "additive": None,
        "approx": (
            f"{metric} é mediana ou média e não se decompõe em soma exata. 'contribution' = variação do "
            f"grupo × peso atual do grupo ({base}), só para ordenar; não soma a variação total."
        ),
    }
    return {
        **head,
        "total": {"current": total_cur, "previous": total_prev, "delta": delta},
        "weight_base": base,
        "n_groups": len(units),
        "drivers": drivers,
        "concentration": {
            "top1": sum(size(u) for u in ranked[:1]) / spread if spread else None,
            "top3": sum(size(u) for u in ranked[:3]) / spread if spread else None,
        },
        "note": notes[method],
    }


def _others(
    rest: list[dict], method: str, metric: str, current: dict, previous: dict, delta: float | None
) -> dict:
    """Balde "Outros": soma efeitos e pesos; taxa e soma vêm do agregado dos membros."""

    def total(field: str) -> float | None:
        values = [u[field] for u in rest if u[field] is not None]
        return sum(values) if values else None

    cur, prev = None, None
    if method == "shift_share":
        num1 = sum(current[u["key"]][f"{metric}__num"] for u in rest if u["key"] in current)
        den1 = sum(current[u["key"]][f"{metric}__den"] for u in rest if u["key"] in current)
        num0 = sum(previous[u["key"]][f"{metric}__num"] for u in rest if u["key"] in previous)
        den0 = sum(previous[u["key"]][f"{metric}__den"] for u in rest if u["key"] in previous)
        cur, prev = _ratio(num1, den1), _ratio(num0, den0)
    elif method == "additive":
        cur, prev = total("current"), total("previous")
    contribution = total("contribution")
    return {
        "key": None,
        "label": OTHERS_LABEL,
        "current": cur,
        "previous": prev,
        "delta": cur - prev if cur is not None and prev is not None else None,
        "weight_current": sum(u["weight_current"] for u in rest),
        "weight_previous": sum(u["weight_previous"] for u in rest),
        "rate_effect": total("rate_effect"),
        "mix_effect": total("mix_effect"),
        "contribution": contribution,
        "share_of_change": contribution / delta if method != "approx" and delta and contribution is not None else None,
        "orders_current": sum(u["orders_current"] for u in rest),
        "orders_previous": sum(u["orders_previous"] for u in rest),
        "presence": None,
        "groups": len(rest),
    }


# Etapas do ciclo em minutos (mesma unidade, dá para dizer qual pesou mais) e contexto à parte.
STAGE_METRICS = ("production_p50", "collected_p50", "expedition_p50", "transit_p50")
CONTEXT_METRICS = ("distance_p50_km", "stuck_rate")
DRILL_METRICS = ("sla_rate", "cycle_p50")


def drill_cause(repo: Repository, f: Filters, *, metric: str = "sla_rate", group: dict[str, Any] | None = None) -> dict:
    """Qual etapa explica o SLA/ciclo de um grupo: compara medianas de etapa com o resto do recorte
    (só com `group`, no formato `where` de query_metrics) e com o período anterior (se houver).

    `vs_rest`/`vs_previous` = atual − referência; positivo = etapa mais lenta. `top_stage_*` é a etapa
    com maior aumento em minutos, ou None quando nenhuma ficou mais lenta.
    """
    if metric not in DRILL_METRICS:
        raise ValueError(f"drill_cause aceita {', '.join(DRILL_METRICS)} (recebido {metric!r}).")
    metrics = [*DRILL_METRICS, *STAGE_METRICS, *CONTEXT_METRICS]
    base = repo.query_metrics(f, metrics=metrics, where=group, compare="previous")
    rest = repo.query_metrics(f, metrics=metrics, where=group, compare="rest") if base["where"] else None
    previous = base["total_compare"]
    rest_total = rest["total_compare"] if rest else None

    def row(m: str) -> dict:
        cur = base["total"][m]
        ref_rest = rest_total[m] if rest_total else None
        ref_prev = previous[m] if previous else None
        return {
            "metric": m,
            "current": cur,
            "rest": ref_rest,
            "previous": ref_prev,
            "vs_rest": cur - ref_rest if cur is not None and ref_rest is not None else None,
            "vs_previous": cur - ref_prev if cur is not None and ref_prev is not None else None,
        }

    stages = [row(m) for m in STAGE_METRICS]

    def top(field: str) -> str | None:
        moved = [s for s in stages if s[field] is not None and s[field] > 0]
        return max(moved, key=lambda s: s[field])["metric"] if moved else None

    def sample(total: dict | None) -> dict | None:
        return {k: total[k] for k in ("orders", "measured", "low_sample")} if total else None

    notes = ["Medianas de etapa não somam a mediana do ciclo; compare etapa com etapa."]
    if base["note"]:
        notes.append(base["note"])
    return {
        "metric": metric,
        "group": base["where"],
        "period": base["period"],
        "previous_period": base["compare_period"],
        "sample": {"current": sample(base["total"]), "rest": sample(rest_total), "previous": sample(previous)},
        "headline": row(metric),
        "stages": stages,
        "context": [row(m) for m in CONTEXT_METRICS],
        "top_stage_vs_rest": top("vs_rest"),
        "top_stage_vs_previous": top("vs_previous"),
        "note": " ".join(notes),
    }
