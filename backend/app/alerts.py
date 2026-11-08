"""Regras de alerta sobre o recorte atual.

Cada alerta traz o que está errado, o número que prova e uma ação operacional
(quem fala com quem, onde e em que horário), além de um drill-down que o
frontend aplica como filtro.
"""

from __future__ import annotations

from datetime import timedelta

from app import fmt
from app.filters import Filters
from app.repository import Repository
from app.schemas import Alert, DrillDown

SLA_HIGH = 0.80
SLA_WARN = 0.85
CANCEL_HIGH = 0.09
CANCEL_WARN = 0.06
STUCK_WARN = 0.03
STUCK_HUB_MAX = 0.30
SUBSIDY_WARN = 3.0
HUB_MIN = 300
STORE_MIN = 150

STAGES = {
    "production_p50": "preparo na loja",
    "collected_p50": "coleta",
    "expedition_p50": "expedição",
    "transit_p50": "trânsito",
}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _gap(row: dict, base: dict, key: str) -> float:
    a, b = row.get(key), base.get(key)
    return (a - b) if a is not None and b is not None else 0.0


def _worst_stage(row: dict, base: dict) -> tuple[str, float]:
    key = max(STAGES, key=lambda k: _gap(row, base, k))
    return key, _gap(row, base, key)


def _peak_hours(repo: Repository, f: Filters) -> list[int]:
    hours = repo.breakdown(f, "hour", sort="orders", limit=24)
    return sorted(int(h["key"]) for h in hours[:4])


def _hours_label(hours: list[int]) -> str:
    if not hours:
        return "no pico"
    return "entre " + f"{min(hours):02d}h e {max(hours) + 1:02d}h"


def _stage_action(stage: str, hub: dict, repo: Repository, f: Filters, peak: list[int]) -> str:
    hub_filter = f.model_copy(update={"hub": [int(hub["key"])]})
    if stage == "production_p50":
        slow = repo.breakdown(hub_filter, "store", sort="orders", limit=40, min_orders=50)
        slow = sorted((s for s in slow if s["production_p50"]), key=lambda s: -s["production_p50"])[:3]
        names = ", ".join(f"{s['label']} ({fmt.minutes(s['production_p50'])})" for s in slow)
        return (
            f"Ligar para as lojas com preparo mais lento no {hub['label']}: {names}. "
            "Revisar o tempo de preparo informado e a pausa de cardápio no pico."
        )
    if stage in ("collected_p50", "expedition_p50"):
        return (
            f"Gargalo dentro do {hub['label']}: revisar fila de coleta e posicionamento de entregadores "
            f"no hub {_hours_label(peak)}. Meta: expedição abaixo da mediana do recorte."
        )
    return (
        f"Trânsito longo no {hub['label']} (distância mediana {fmt.km(hub['distance_p50_km'])}): "
        f"reforçar motos {_hours_label(peak)} ou reduzir o raio de entrega no pico."
    )


def detect_alerts(repo: Repository, f: Filters) -> list[Alert]:
    return repo._cached("alerts:" + f.cache_key(), lambda: _detect(repo, f))


def _detect(repo: Repository, f: Filters) -> list[Alert]:
    base = repo.metrics(f)
    if base["orders"] == 0:
        return []

    alerts: list[Alert] = []
    peak = _peak_hours(repo, f)
    hubs = repo.breakdown(f, "hub", sort="orders", limit=100, min_orders=HUB_MIN)

    # 1. SLA do recorte e hub mais lento -------------------------------------
    sla = base["sla_rate"]
    if sla is not None and sla < SLA_WARN:
        alerts.append(Alert(
            id="sla-recorte",
            severity="high" if sla < SLA_HIGH else "medium",
            category="sla",
            title="Entregas fora do prazo",
            detail=(
                f"{fmt.pct(sla)} dos pedidos entregues dentro do SLA (food ≤ {repo.sla_food_min} min, "
                f"goods ≤ {repo.sla_good_min} min). Ciclo mediano {fmt.minutes(base['cycle_p50'])}, "
                f"p90 {fmt.minutes(base['cycle_p90'])}."
            ),
            action="Atacar primeiro o hub com pior SLA (alerta abaixo) em vez da média do recorte.",
        ))

    # Hub com muito pedido preso é problema de dado (alerta 5), não de operação.
    slow_hubs = [
        h for h in hubs
        if h["sla_rate"] is not None and sla is not None and h["sla_rate"] <= sla - 0.05
        and (h["stuck_rate"] or 0) < STUCK_HUB_MAX
    ]
    if slow_hubs and len(hubs) > 1:
        hub = min(slow_hubs, key=lambda h: h["sla_rate"])
        stage, gap = _worst_stage(hub, base)
        alerts.append(Alert(
            id=f"sla-hub-{hub['key']}",
            severity="high" if hub["sla_rate"] < SLA_HIGH else "medium",
            category="sla",
            title=f"Hub lento: {hub['label']}",
            detail=(
                f"SLA de {fmt.pct(hub['sla_rate'])} contra {fmt.pct(sla)} do recorte em "
                f"{fmt.integer(hub['delivered'])} entregas. Maior desvio na etapa de {STAGES[stage]} "
                f"(+{fmt.minutes(max(gap, 0))} sobre a mediana)."
            ),
            action=_stage_action(stage, hub, repo, f, peak),
            drilldown=DrillDown(label=f"Ver só {hub['label']}", filters={"hub": [int(hub["key"])]}),
        ))

    # 2. Cancelamento -------------------------------------------------------
    cancel = base["cancel_rate"] or 0.0
    if cancel >= CANCEL_WARN:
        segments = repo.breakdown(f, "segment", sort="cancel_rate", limit=5)
        worst = segments[0] if segments else None
        where = f" Concentrado em {worst['label']} ({fmt.pct(worst['cancel_rate'])})." if worst else ""
        alerts.append(Alert(
            id="cancel-recorte",
            severity="high" if cancel >= CANCEL_HIGH else "medium",
            category="cancelamento",
            title="Cancelamento acima do teto",
            detail=f"{fmt.pct(cancel)} dos pedidos cancelados (teto interno {fmt.pct(CANCEL_WARN, 0)}).{where}",
            action="Separar cancelamento por loja e por canal antes de agir: o mix muda quem precisa ser acionado.",
        ))

    if len(hubs) > 1 and cancel > 0:
        hot = [h for h in hubs if h["cancel_rate"] >= max(1.6 * cancel, CANCEL_WARN)]
        if hot:
            hub = max(hot, key=lambda h: h["canceled"])
            alerts.append(Alert(
                id=f"cancel-hub-{hub['key']}",
                severity="medium",
                category="cancelamento",
                title=f"Cancelamento fora da curva: {hub['label']}",
                detail=(
                    f"{fmt.pct(hub['cancel_rate'])} de cancelamento ({hub['cancel_rate'] / cancel:.1f}× o recorte) "
                    f"em {fmt.integer(hub['orders'])} pedidos, {fmt.integer(hub['canceled'])} cancelados."
                ),
                action=f"Abrir as lojas do {hub['label']} por cancelamento e ligar para as duas primeiras hoje.",
                drilldown=DrillDown(label=f"Ver só {hub['label']}", filters={"hub": [int(hub["key"])]}),
            ))

    # 3. Loja crítica -------------------------------------------------------
    stores = repo.breakdown(f, "store", sort="orders", limit=300, min_orders=STORE_MIN)
    if len(stores) > 1:
        critical = [s for s in stores if s["cancel_rate"] >= max(2.5 * cancel, 0.10)]
        critical.sort(key=lambda s: -s["canceled"])
        for store in critical[:2]:
            broken = store["cancel_rate"] >= 0.9
            alerts.append(Alert(
                id=f"cancel-store-{store['key']}",
                severity="high" if store["cancel_rate"] >= 0.15 else "medium",
                category="loja",
                title=f"{'Loja sem entregas' if broken else 'Loja crítica'}: {store['label']}",
                detail=(
                    f"{fmt.integer(store['canceled'])} cancelamentos em {fmt.integer(store['orders'])} pedidos "
                    f"({fmt.pct(store['cancel_rate'])}) no {store['parent']}."
                ),
                action=(
                    f"Tirar {store['label']} do ar hoje: com quase todo pedido cancelado, o problema é cadastro, "
                    "integração ou loja fechada recebendo pedido. Reativar só depois de um pedido de teste."
                    if broken else
                    f"Ligar para {store['label']}: checar ruptura de itens e loja fechada com cardápio aberto. "
                    "Se a taxa não cair em 7 dias, pausar o destaque da loja no app."
                ),
                drilldown=DrillDown(label=f"Ver só {store['label']}", filters={"store": [int(store["key"])]}),
            ))

    # 4. Pico ---------------------------------------------------------------
    hours = repo.breakdown(f, "hour", sort="orders", limit=24)
    if peak and sla is not None:
        in_peak = [h for h in hours if int(h["key"]) in peak and h["sla_rate"] is not None]
        off_peak = [h for h in hours if int(h["key"]) not in peak and h["sla_rate"] is not None]
        if in_peak and off_peak:
            def weighted(rows: list[dict]) -> float:
                total = sum(r["delivered"] for r in rows) or 1
                return sum(r["sla_rate"] * r["delivered"] for r in rows) / total

            peak_sla, off_sla = weighted(in_peak), weighted(off_peak)
            if peak_sla <= off_sla - 0.03:
                alerts.append(Alert(
                    id="sla-pico",
                    severity="medium",
                    category="frota",
                    title="SLA cai no horário de pico",
                    detail=(
                        f"{fmt.pct(peak_sla)} no prazo {_hours_label(peak)} contra {fmt.pct(off_sla)} fora do pico "
                        f"({fmt.pp(peak_sla - off_sla)})."
                    ),
                    action=(
                        f"Antecipar a escala de entregadores em 30 min antes das {min(peak):02d}h "
                        "nos hubs com pior SLA e segurar promoções nesse intervalo."
                    ),
                ))

    # 5. Pedidos presos no fluxo -------------------------------------------
    stuck = base["stuck_rate"]
    if stuck is not None and stuck >= STUCK_WARN:
        all_hubs = repo.breakdown(f, "hub", sort="stuck_rate", limit=1, min_orders=100)
        hub = all_hubs[0] if all_hubs else None
        stuck_n = round(stuck * base["delivered"])
        alerts.append(Alert(
            id="dados-presos",
            severity="medium",
            category="dados",
            title="Pedidos presos no fluxo",
            detail=(
                f"{fmt.integer(stuck_n)} entregas ({fmt.pct(stuck)}) com ciclo acima de 4h"
                + (f"; pior hub: {hub['label']} com {fmt.pct(hub['stuck_rate'])}." if hub else ".")
                + " Ficam fora das medianas de tempo."
            ),
            action=(
                "Conferir a rotina de finalização desses pedidos (baixa manual, agendamento ou goods "
                "com retirada posterior) antes de cobrar SLA do hub."
            ),
            drilldown=(
                DrillDown(label=f"Ver só {hub['label']}", filters={"hub": [int(hub["key"])]}) if hub else None
            ),
        ))

    # 6. Volume: últimos 7 dias contra os 7 anteriores -----------------------
    start, end = repo.period(f)
    if (end - start).days >= 13:
        last = repo.metrics(f.with_period(end - timedelta(days=6), end))
        prev = repo.metrics(f.with_period(end - timedelta(days=13), end - timedelta(days=7)))
        if prev["orders"] >= 100:
            change = last["orders"] / prev["orders"] - 1
            if change <= -0.15:
                alerts.append(Alert(
                    id="volume-queda",
                    severity="medium",
                    category="volume",
                    title="Queda de volume na última semana",
                    detail=(
                        f"{fmt.integer(last['orders'])} pedidos nos últimos 7 dias contra "
                        f"{fmt.integer(prev['orders'])} na semana anterior ({fmt.pct(change)})."
                    ),
                    action="Cruzar a queda por hub e canal: se for um canal só, falar com o parceiro do canal.",
                ))

    # 7. Subsídio de frete --------------------------------------------------
    subsidy = base["subsidy"]
    if subsidy is not None and subsidy >= SUBSIDY_WARN:
        alerts.append(Alert(
            id="custo-frete",
            severity="low",
            category="custo",
            title="Custo logístico acima do frete cobrado",
            detail=(
                f"Cada entrega custa {fmt.brl(base['cost_avg'])} e cobra {fmt.brl(base['fee_avg'])} de frete: "
                f"{fmt.brl(subsidy)} de subsídio por pedido."
            ),
            action="Revisar frete mínimo nas lojas com ticket baixo e distância alta.",
        ))

    alerts.sort(key=lambda a: _SEVERITY_ORDER[a.severity])
    return alerts
