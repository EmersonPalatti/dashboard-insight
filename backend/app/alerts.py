"""Regras de alerta sobre o recorte atual.

Cada alerta traz o que está errado, o número que prova e uma ação operacional
(quem fala com quem, onde e em que horário), além de um drill-down que o
frontend aplica como filtro.

Amostra pequena: SLA e ciclo sustentam-se na base medida (`low_sample`, entregues sem
preso). Cancelamento se sustenta no total de pedidos. Abaixo de MIN_MEASURED, o alerta de
recorte cai para severidade "low" e a ação manda ampliar o período antes de cobrar alguém.
"""

from __future__ import annotations

from datetime import timedelta

from app import fmt
from app.filters import Filters
from app.repository import MIN_MEASURED, VALUE_LABELS, Repository
from app.schemas import Alert, DrillDown, Evidence

SLA_HIGH = 0.80
SLA_WARN = 0.85
CANCEL_HIGH = 0.09
CANCEL_WARN = 0.06
STUCK_WARN = 0.03
STUCK_HUB_MAX = 0.30
SUBSIDY_WARN = 3.0
HUB_MIN = 300
STORE_MIN = 150
DROP_MIN_ORDERS = 30  # linha com menos pedidos que isso no período anterior não entra na comparação de queda

STAGES = {
    "production_p50": "preparo na loja",
    "collected_p50": "coleta",
    "expedition_p50": "expedição",
    "transit_p50": "trânsito",
}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

THIN_SLA_ACTION = (
    f"Não ligar para o líder com esta base: ampliar o período até {MIN_MEASURED} pedidos medidos "
    "e só então cobrar o SLA."
)
THIN_CANCEL_ACTION = (
    f"Não ligar para as lojas com esta base: ampliar o período até {MIN_MEASURED} pedidos "
    "e só então cobrar o cancelamento."
)


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
    """Faixas contínuas de horas: [12, 13, 19, 20] vira '12h–14h e 19h–21h'."""
    if not hours:
        return "sem pico definido"
    runs: list[tuple[int, int]] = []
    for hour in sorted(hours):
        if runs and hour == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], hour)
        else:
            runs.append((hour, hour))
    return " e ".join(f"{first:02d}h–{last + 1:02d}h" for first, last in runs)


def _slowest_stage(row: dict) -> str | None:
    """Etapa de maior mediana dentro da própria linha (usada quando não há hub para comparar)."""
    known = {k: row[k] for k in STAGES if row.get(k) is not None}
    return max(known, key=known.get) if known else None


def _peak_clause(stage: str | None, peak: list[int]) -> str:
    """Fecho da ação do SLA: a alavanca do pico depende da etapa que atrasa (frota só ajuda fora do preparo)."""
    if not peak:
        return ""
    start = f"{min(peak):02d}h"
    if stage == "production_p50":
        return f" Antes das {start}, início da faixa de pico, revisar com as lojas o tempo de preparo informado."
    return f" Reforçar a frota antes das {start}, início da faixa de pico."


def _weighted_sla(rows: list[dict]) -> float:
    """SLA médio de linhas por hora: cada linha pesa pela base medida, que é o denominador da taxa."""
    total = sum(r["measured"] for r in rows) or 1
    return sum(r["sla_rate"] * r["measured"] for r in rows) / total


def _sla_action(base: dict, hubs: list[dict], peak: list[int]) -> str:
    # Hub com base medida pequena não serve para apontar líder: a taxa seria de poucas entregas.
    ranked = [h for h in hubs if h["sla_rate"] is not None and not h["low_sample"]]
    if not ranked:
        stage = _slowest_stage(base)
        etapa = f", com {STAGES[stage]} como a etapa mais lenta" if stage else ""
        hour = _peak_clause(stage, peak)
        return (
            f"Ligar hoje para o líder da operação do recorte: {fmt.pct(base['sla_rate'])} no prazo{etapa}.{hour}"
        )
    if len(ranked) == 1:
        hub = ranked[0]
        stage = _slowest_stage(hub)
        etapa = f", com {STAGES[stage]} como a etapa mais lenta" if stage else ""
        hour = _peak_clause(stage, peak)
        return (
            f"Ligar hoje para o líder do hub {hub['label']}: {fmt.pct(hub['sla_rate'])} no prazo "
            f"neste recorte{etapa}.{hour}"
        )
    hub = min(ranked, key=lambda h: h["sla_rate"])
    stage, gap = _worst_stage(hub, base)
    etapa = f", com {STAGES[stage]} como a etapa mais lenta" if gap > 0 else ""
    hour = _peak_clause(stage if gap > 0 else None, peak)
    return (
        f"Ligar hoje para o líder do hub {hub['label']}: {fmt.pct(hub['sla_rate'])} no prazo "
        f"contra {fmt.pct(base['sla_rate'])} do recorte{etapa}.{hour}"
    )


def _stage_action(stage: str, gap: float, hub: dict, repo: Repository, f: Filters, peak: list[int]) -> str:
    label = hub["label"]
    if gap <= 0:
        # Nenhuma etapa passa da mediana do recorte: não há gargalo para apontar.
        return (
            f"Ligar hoje para o líder do hub {label}: nenhuma etapa passa da mediana do recorte. "
            f"Revisar a escala de entregadores e o tempo de preparo informado nos horários {_hours_label(peak)}."
        )
    if stage == "production_p50":
        hub_filter = f.model_copy(update={"hub": [int(hub["key"])]})
        slow = repo.breakdown(hub_filter, "store", sort="orders", limit=40, min_orders=50)
        slow = sorted((s for s in slow if s["production_p50"]), key=lambda s: -s["production_p50"])[:3]
        names = ", ".join(f"{s['label']} ({fmt.minutes(s['production_p50'])})" for s in slow)
        return (
            f"Ligar para as lojas com preparo mais lento no hub {label}: {names}. "
            "Revisar o tempo de preparo informado e a pausa de cardápio no pico."
        )
    if stage in ("collected_p50", "expedition_p50"):
        return (
            f"Gargalo dentro do hub {label}: revisar fila de coleta e posicionamento de entregadores "
            f"nos horários {_hours_label(peak)}. Meta: expedição abaixo da mediana do recorte."
        )
    return (
        f"Trânsito longo no hub {label} (distância mediana {fmt.km(hub['distance_p50_km'])}): "
        f"reforçar motos nos horários {_hours_label(peak)} ou reduzir o raio de entrega no pico."
    )


def _cancel_action(repo: Repository, f: Filters, cancel: float, peak: list[int]) -> str:
    """Loja de maior cancelamento entre as que têm base (STORE_MIN), com o hub dela para o líder."""
    stores = repo.breakdown(f, "store", sort="cancel_rate", limit=1, min_orders=STORE_MIN)
    if stores:
        store = stores[0]
        return (
            f"Ligar hoje para o líder do hub {store['parent']}: a loja {store['label']} cancela "
            f"{fmt.pct(store['cancel_rate'])} dos pedidos, a maior taxa entre as lojas com {STORE_MIN}+ pedidos. "
            f"Checar ruptura de itens e loja fechada com cardápio aberto antes do pico ({_hours_label(peak)})."
        )
    return (
        "Ligar hoje para o líder da operação do recorte: confirmar antes do pico "
        f"({_hours_label(peak)}) se ruptura de itens ou loja fechada explica os {fmt.pct(cancel)} de cancelamento."
    )


def _biggest_drop(repo: Repository, last_f: Filters, prev_f: Filters, by: str) -> tuple[float, str] | None:
    """Maior queda de pedidos entre o período anterior e o último, por hub ou canal: (variação, rótulo)."""
    now = {r["key"]: r["orders"] for r in repo.breakdown(last_f, by, limit=100)}
    worst: tuple[float, str] | None = None
    for row in repo.breakdown(prev_f, by, limit=100):
        if row["orders"] < DROP_MIN_ORDERS:
            continue
        change = now.get(row["key"], 0) / row["orders"] - 1
        if worst is None or change < worst[0]:
            worst = (change, row["label"])
    return worst


def _volume_action(repo: Repository, last_f: Filters, prev_f: Filters) -> str:
    hub = _biggest_drop(repo, last_f, prev_f, "hub")
    channel = _biggest_drop(repo, last_f, prev_f, "channel")
    if hub and channel:
        return (
            f"Falar hoje com o parceiro do canal {channel[1]} ({fmt.pct(channel[0])} na semana), a maior queda "
            f"entre os canais, e ligar para o líder do hub {hub[1]} ({fmt.pct(hub[0])}) nesta semana."
        )
    if hub:
        return f"Ligar hoje para o líder do hub {hub[1]}: {fmt.pct(hub[0])} na semana, a maior queda entre os hubs."
    if channel:
        return (
            f"Falar hoje com o parceiro do canal {channel[1]} ({fmt.pct(channel[0])} na semana), "
            "a maior queda entre os canais."
        )
    return "Ligar hoje para o líder da operação do recorte: a queda não se concentra em hub nem em canal."


def _freight_action(repo: Repository, f: Filters, base: dict) -> str:
    """Loja de maior subsídio entre as que têm base (STORE_MIN): o responsável comercial sobe o frete mínimo dela."""
    stores = repo.breakdown(f, "store", sort="subsidy", limit=1, min_orders=STORE_MIN)
    if stores:
        store = stores[0]
        return (
            f"Ligar esta semana para o responsável comercial da loja {store['label']} (hub {store['parent']}) "
            f"e subir o frete mínimo: a entrega custa {fmt.brl(store['cost_avg'])} e cobra {fmt.brl(store['fee_avg'])}."
        )
    return (
        "Ligar esta semana para o responsável comercial do recorte e subir o frete mínimo: "
        f"a entrega custa {fmt.brl(base['cost_avg'])} e cobra {fmt.brl(base['fee_avg'])}."
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
    thin_sla = base["low_sample"]  # SLA: base medida (entregues sem preso)
    thin_cancel = base["orders"] < MIN_MEASURED  # cancelamento: total de pedidos, não a base medida

    # 1. SLA do recorte e hub mais lento -------------------------------------
    sla = base["sla_rate"]
    if sla is not None and sla < SLA_WARN:
        detail = (
            f"{fmt.pct(sla)} dos pedidos entregues dentro do SLA (food ≤ {repo.sla_food_min} min, "
            f"goods ≤ {repo.sla_good_min} min). Ciclo mediano {fmt.minutes(base['cycle_p50'])}, "
            f"p90 {fmt.minutes(base['cycle_p90'])}."
        )
        alerts.append(Alert(
            id="sla-recorte",
            severity="low" if thin_sla else ("high" if sla < SLA_HIGH else "medium"),
            category="sla",
            title="Entregas fora do prazo",
            detail=detail + (f" Recorte com amostra pequena ({base['measured']} pedidos medidos)." if thin_sla else ""),
            action=THIN_SLA_ACTION if thin_sla else _sla_action(base, hubs, peak),
            evidence=Evidence(view="kpi", kpi="sla_rate"),
        ))

    # Hub com muito pedido preso é problema de dado (alerta 5), não de operação.
    # Hub com base medida pequena também fica de fora: SLA sobre algumas dezenas de entregas não cobra ninguém.
    slow_hubs = [
        h for h in hubs
        if h["sla_rate"] is not None and sla is not None and h["sla_rate"] <= sla - 0.05
        and (h["stuck_rate"] or 0) < STUCK_HUB_MAX and not h["low_sample"]
    ]
    if slow_hubs and len(hubs) > 1:
        hub = min(slow_hubs, key=lambda h: h["sla_rate"])
        stage, gap = _worst_stage(hub, base)
        if gap > 0:
            stage_text = (
                f"Maior desvio na etapa de {STAGES[stage]} (+{fmt.minutes(gap)} sobre a mediana do recorte)."
            )
        else:
            stage_text = "Nenhuma etapa passa da mediana do recorte: o atraso está no ciclo como um todo."
        alerts.append(Alert(
            id=f"sla-hub-{hub['key']}",
            severity="high" if hub["sla_rate"] < SLA_HIGH else "medium",
            category="sla",
            title=f"Hub lento: {hub['label']}",
            detail=(
                f"SLA de {fmt.pct(hub['sla_rate'])} contra {fmt.pct(sla)} do recorte em "
                f"{fmt.integer(hub['delivered'])} entregas. {stage_text}"
            ),
            action=_stage_action(stage, gap, hub, repo, f, peak),
            drilldown=DrillDown(label=f"Ver só {hub['label']}", filters={"hub": [int(hub["key"])]}),
            evidence=Evidence(view="stages", hubs=[int(hub["key"])]),
        ))

    # 2. Cancelamento -------------------------------------------------------
    cancel = base["cancel_rate"] or 0.0
    if cancel >= CANCEL_WARN:
        segments = repo.breakdown(f, "segment", sort="cancel_rate", limit=5)
        worst = segments[0] if segments else None
        where = (
            f" Concentrado no segmento {VALUE_LABELS.get(worst['label'], worst['label'])} "
            f"({fmt.pct(worst['cancel_rate'])})."
        ) if worst else ""
        alerts.append(Alert(
            id="cancel-recorte",
            severity="low" if thin_cancel else ("high" if cancel >= CANCEL_HIGH else "medium"),
            category="cancelamento",
            title="Cancelamento acima do teto",
            detail=(
                f"{fmt.pct(cancel)} dos pedidos cancelados (teto interno {fmt.pct(CANCEL_WARN, 0)}).{where}"
                + (f" Recorte com amostra pequena ({base['orders']} pedidos no total)." if thin_cancel else "")
            ),
            action=THIN_CANCEL_ACTION if thin_cancel else _cancel_action(repo, f, cancel, peak),
            evidence=Evidence(view="kpi", kpi="cancel_rate"),
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
                action=f"Abrir as lojas do hub {hub['label']} por cancelamento e ligar para as duas primeiras hoje.",
                drilldown=DrillDown(label=f"Ver só {hub['label']}", filters={"hub": [int(hub["key"])]}),
                evidence=Evidence(view="scatter", metric="cancel_rate", hub_label=hub["label"]),
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
                    f"({fmt.pct(store['cancel_rate'])}) no hub {store['parent']}."
                ),
                action=(
                    f"Tirar {store['label']} do ar hoje: com quase todo pedido cancelado, o problema é cadastro, "
                    "integração ou loja fechada recebendo pedido. Reativar só depois de um pedido de teste."
                    if broken else
                    f"Ligar para {store['label']}: checar ruptura de itens e loja fechada com cardápio aberto. "
                    "Se a taxa não cair em 7 dias, pausar o destaque da loja no app."
                ),
                drilldown=DrillDown(label=f"Ver só {store['label']}", filters={"store": [int(store["key"])]}),
                evidence=Evidence(view="scatter", metric="cancel_rate", stores=[int(store["key"])]),
            ))

    # 4. Pico ---------------------------------------------------------------
    hours = repo.breakdown(f, "hour", sort="orders", limit=24)
    if peak and sla is not None:
        in_peak = [h for h in hours if int(h["key"]) in peak and h["sla_rate"] is not None]
        off_peak = [h for h in hours if int(h["key"]) not in peak and h["sla_rate"] is not None]
        if in_peak and off_peak:
            peak_sla, off_sla = _weighted_sla(in_peak), _weighted_sla(off_peak)
            if peak_sla <= off_sla - 0.03:
                alerts.append(Alert(
                    id="sla-pico",
                    severity="low" if thin_sla else "medium",
                    category="frota",
                    title="SLA cai no horário de pico",
                    detail=(
                        f"No pico ({_hours_label(peak)}), {fmt.pct(peak_sla)} dos pedidos no prazo contra "
                        f"{fmt.pct(off_sla)} fora dele ({fmt.pp(peak_sla - off_sla)})."
                        + (f" Recorte com amostra pequena ({base['measured']} pedidos medidos)." if thin_sla else "")
                    ),
                    action=THIN_SLA_ACTION if thin_sla else (
                        f"Antecipar a escala de entregadores em 30 min antes das {min(peak):02d}h "
                        "nos hubs com pior SLA e segurar promoções nesse intervalo."
                    ),
                    evidence=Evidence(view="heatmap", metric="sla_rate", hours=peak),
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
            evidence=Evidence(view="kpi", kpi="sla_rate"),
        ))

    # 6. Volume: últimos 7 dias contra os 7 anteriores -----------------------
    start, end = repo.period(f)
    if (end - start).days >= 13:
        last_f = f.with_period(end - timedelta(days=6), end)
        prev_f = f.with_period(end - timedelta(days=13), end - timedelta(days=7))
        last = repo.metrics(last_f)
        prev = repo.metrics(prev_f)
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
                    action=_volume_action(repo, last_f, prev_f),
                    evidence=Evidence(view="kpi", kpi="orders"),
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
            action=_freight_action(repo, f, base),
            evidence=Evidence(view="kpi", kpi="ticket"),
        ))

    alerts.sort(key=lambda a: _SEVERITY_ORDER[a.severity])
    return alerts
