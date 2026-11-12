"""Regras de alerta sobre o recorte atual.

Cada alerta traz o que está errado, o número que prova e uma ação operacional
(quem fala com quem, onde e em que horário), além de um drill-down que o
frontend aplica como filtro.

Amostra pequena: SLA e ciclo sustentam-se na base medida (`low_sample`, entregues sem
preso). Cancelamento se sustenta no total de pedidos. Abaixo de MIN_MEASURED, o alerta de
recorte cai para severidade "low" e a ação manda ampliar o período antes de cobrar alguém.
Taxa extrema (nenhuma entrega, ou cancelamento de 90% ou mais) não rebaixa. Sem dia do
dataset fora do filtro, a ação não pede para ampliar o período.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from app import fmt
from app.filters import Filters
from app.repository import (
    CANCEL_ABOVE_FLOOR,
    CANCEL_ABOVE_RATIO,
    MIN_MEASURED,
    SLA_BELOW_GAP,
    VALUE_LABELS,
    Repository,
)
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
BROKEN_CANCEL = 0.9  # loja sem entregas: regra absoluta, independente da taxa do recorte

# Abaixo disso o vão arredondado (1 casa) vira 0,0: a frase diz "igual à rede".
_FLAT_RATE = 0.0005
_FLAT_MIN = 0.05
Verdict = Literal["within", "attention", "critical"]


def sla_band(sla: float) -> Verdict:
    """Régua da comanda de SLA do recorte. Igual ao limiar conta como atenção, não crítico."""
    if sla < SLA_HIGH:
        return "critical"
    if sla < SLA_WARN:
        return "attention"
    return "within"


def cancel_band(cancel: float) -> Verdict:
    """Régua da comanda de cancelamento do recorte. O teto entra na faixa (>=)."""
    if cancel >= CANCEL_HIGH:
        return "critical"
    if cancel >= CANCEL_WARN:
        return "attention"
    return "within"


SEGMENT_MIN_ORDERS = MIN_MEASURED  # abaixo disso o segmento não sustenta "concentrado"
CONCENTRATION_GAP = 0.05  # participação nos cancelamentos acima da participação nos pedidos
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
THIN_SLA_ACTION_CLOSED = (
    f"Não ligar para o líder com esta base: o recorte já cobre todo o período dos dados "
    f"e não chega a {MIN_MEASURED} pedidos medidos."
)
THIN_CANCEL_ACTION_CLOSED = (
    f"Não ligar para as lojas com esta base: o recorte já cobre todo o período dos dados "
    f"e não chega a {MIN_MEASURED} pedidos."
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


def _times(value: float) -> str:
    """Fator com vírgula decimal (6,7×). fmt.pct já formata; o fator não é uma taxa."""
    return fmt.pct(value / 100, 1).removesuffix("%") + "×"


def _period_can_widen(repo: Repository, f: Filters) -> bool:
    """Há dia do dataset fora do filtro. Sem data, ou já no intervalo inteiro, não há o que ampliar."""
    if f.start is None and f.end is None:
        return False
    start, end = repo.period(f)
    return start > repo.min_date or end < repo.max_date


def _extreme_cancel(base: dict) -> bool:
    return base["delivered"] == 0 or (base["cancel_rate"] or 0) >= BROKEN_CANCEL


def _segment_clause(segments: list[dict]) -> str:
    """Só chama de concentrado quem tem base e leva bem mais cancelamentos do que pedidos.

    Um segmento sozinho no recorte não concentra nada: ele é o recorte.
    """
    if len(segments) < 2:
        return ""
    total_orders = sum(s["orders"] for s in segments)
    total_canceled = sum(s["canceled"] for s in segments)
    if total_orders == 0 or total_canceled == 0:
        return ""
    best: dict | None = None
    best_gap = 0.0
    for seg in segments:
        if seg["orders"] < SEGMENT_MIN_ORDERS:
            continue
        gap = seg["canceled"] / total_canceled - seg["orders"] / total_orders
        if best is None or gap > best_gap:
            best = seg
            best_gap = gap
    if best is None or best_gap < CONCENTRATION_GAP:
        return ""
    label = VALUE_LABELS.get(best["label"], best["label"])
    return f" Concentrado no segmento {label} ({fmt.pct(best['cancel_rate'])})."


def detect_alerts(repo: Repository, f: Filters) -> list[Alert]:
    return repo._cached("alerts:" + f.cache_key(), lambda: _detect(repo, f))


def _detect(repo: Repository, f: Filters) -> list[Alert]:
    base = repo.metrics(f)
    if base["orders"] == 0:
        return []

    alerts: list[Alert] = []
    peak = _peak_hours(repo, f)
    hubs = repo.breakdown(f, "hub", sort="orders", limit=100, min_orders=HUB_MIN)
    stuck = base["stuck_rate"]
    # Acima do mesmo teto da comparação entre hubs, o SLA medido não sustenta ação de frota.
    stuck_blocks_sla = stuck is not None and stuck > STUCK_HUB_MAX
    can_widen = _period_can_widen(repo, f)
    thin_sla_action = THIN_SLA_ACTION if can_widen else THIN_SLA_ACTION_CLOSED
    thin_cancel_action = THIN_CANCEL_ACTION if can_widen else THIN_CANCEL_ACTION_CLOSED
    # Nenhuma entrega, ou cancelamento de 90%+: a taxa já é o problema, não a amostra.
    thin_sla = base["low_sample"] and base["delivered"] != 0
    thin_cancel = base["orders"] < MIN_MEASURED and not _extreme_cancel(base)

    # 1. SLA do recorte e hub mais lento -------------------------------------
    sla = base["sla_rate"]
    sla_level = sla_band(sla) if sla is not None else "within"
    if sla_level != "within" and not stuck_blocks_sla:
        detail = (
            f"{fmt.pct(sla)} dos pedidos entregues dentro do SLA (food ≤ {repo.sla_food_min} min, "
            f"goods ≤ {repo.sla_good_min} min). Ciclo mediano {fmt.minutes(base['cycle_p50'])}, "
            f"p90 {fmt.minutes(base['cycle_p90'])}."
        )
        alerts.append(Alert(
            id="sla-recorte",
            severity="low" if thin_sla else ("high" if sla_level == "critical" else "medium"),
            category="sla",
            title="Entregas fora do prazo",
            detail=detail + (f" Recorte com amostra pequena ({base['measured']} pedidos medidos)." if thin_sla else ""),
            action=thin_sla_action if thin_sla else _sla_action(base, hubs, peak),
            evidence=Evidence(view="kpi", kpi="sla_rate"),
        ))

    # Hub com muito pedido preso é problema de dado (alerta 5), não de operação.
    # Hub com base medida pequena também fica de fora: SLA sobre algumas dezenas de entregas não cobra ninguém.
    slow_hubs = [
        h for h in hubs
        if h["sla_rate"] is not None and sla is not None and h["sla_rate"] < sla - SLA_BELOW_GAP
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
            severity="high" if sla_band(hub["sla_rate"]) == "critical" else "medium",
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
    stores = repo.breakdown(f, "store", sort="orders", limit=300, min_orders=STORE_MIN)
    broken_stores = [s for s in stores if (s["cancel_rate"] or 0) >= BROKEN_CANCEL]
    # Recorte feito só de lojas quebradas: o cancel-recorte mandaria checar ruptura
    # na mesma loja que tem de sair do ar.
    recorte_is_broken = bool(broken_stores) and len(broken_stores) == len(stores)
    cancel_level = cancel_band(cancel)
    if cancel_level != "within" and not recorte_is_broken:
        segments = repo.breakdown(f, "segment", sort="cancel_rate", limit=5)
        where = _segment_clause(segments)
        alerts.append(Alert(
            id="cancel-recorte",
            severity="low" if thin_cancel else ("high" if cancel_level == "critical" else "medium"),
            category="cancelamento",
            title="Cancelamento acima do teto",
            detail=(
                f"{fmt.pct(cancel)} dos pedidos cancelados (teto interno {fmt.pct(CANCEL_WARN, 0)}).{where}"
                + (f" Recorte com amostra pequena ({base['orders']} pedidos no total)." if thin_cancel else "")
            ),
            action=thin_cancel_action if thin_cancel else _cancel_action(repo, f, cancel, peak),
            evidence=Evidence(view="kpi", kpi="cancel_rate"),
        ))

    if len(hubs) > 1 and cancel > 0:
        # Mesma régua do ranking: acima de 1,6× o recorte e de pelo menos 6%.
        hot = [
            h for h in hubs
            if h["cancel_rate"] is not None
            and h["cancel_rate"] >= CANCEL_ABOVE_FLOOR
            and h["cancel_rate"] > cancel * CANCEL_ABOVE_RATIO
        ]
        if hot:
            hub = max(hot, key=lambda h: h["canceled"])
            alerts.append(Alert(
                id=f"cancel-hub-{hub['key']}",
                severity="medium",
                category="cancelamento",
                title=f"Cancelamento fora da curva: {hub['label']}",
                detail=(
                    f"{fmt.pct(hub['cancel_rate'])} de cancelamento ({_times(hub['cancel_rate'] / cancel)} o recorte) "
                    f"em {fmt.integer(hub['orders'])} pedidos, {fmt.integer(hub['canceled'])} cancelados."
                ),
                action=f"Abrir as lojas do hub {hub['label']} por cancelamento e ligar para as duas primeiras hoje.",
                drilldown=DrillDown(label=f"Ver só {hub['label']}", filters={"hub": [int(hub["key"])]}),
                evidence=Evidence(view="scatter", metric="cancel_rate", hub_label=hub["label"]),
            ))

    # 3. Loja crítica -------------------------------------------------------
    # >= 90% com STORE_MIN é absoluto: vale com uma loja só e mesmo que o recorte já esteja alto.
    # O múltiplo de 2,5× fica para quem está alto sem estar quebrado, e só quando há com quem comparar.
    relative: list[dict] = []
    if len(stores) > 1:
        relative = [
            s for s in stores
            if (s["cancel_rate"] or 0) < BROKEN_CANCEL
            and (s["cancel_rate"] or 0) >= max(2.5 * cancel, 0.10)
        ]
    critical = sorted(broken_stores, key=lambda s: -s["canceled"])[:2]
    if len(critical) < 2:
        relative.sort(key=lambda s: -s["canceled"])
        critical.extend(relative[: 2 - len(critical)])
    for store in critical:
        broken = (store["cancel_rate"] or 0) >= BROKEN_CANCEL
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
    if peak and sla is not None and not stuck_blocks_sla:
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
                    action=thin_sla_action if thin_sla else (
                        f"Antecipar a escala de entregadores em 30 min antes das {min(peak):02d}h "
                        "nos hubs com pior SLA e segurar promoções nesse intervalo."
                    ),
                    evidence=Evidence(view="heatmap", metric="sla_rate", hours=peak),
                ))

    # 5. Pedidos presos no fluxo -------------------------------------------
    if stuck is not None and stuck >= STUCK_WARN:
        all_hubs = repo.breakdown(f, "hub", sort="stuck_rate", limit=1, min_orders=100)
        hub = all_hubs[0] if all_hubs else None
        stuck_n = round(stuck * base["delivered"])
        # SLA do recorte entra aqui: com tanto pedido preso, cobrar prazo ou frota contradiz o dado.
        sla_fold = ""
        if stuck_blocks_sla and sla is not None and sla < SLA_WARN:
            sla_fold = (
                f" SLA medido de {fmt.pct(sla)} fica de fora: com {fmt.pct(stuck)} das entregas presas, "
                "não cobrar prazo nem reforçar frota."
            )
        alerts.append(Alert(
            id="dados-presos",
            severity="medium",
            category="dados",
            title="Pedidos presos no fluxo",
            detail=(
                f"{fmt.integer(stuck_n)} entregas ({fmt.pct(stuck)}) com ciclo acima de 4h"
                + (f"; pior hub: {hub['label']} com {fmt.pct(hub['stuck_rate'])}." if hub else ".")
                + " Ficam fora das medianas de tempo."
                + sla_fold
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


# --------------------------------------------------------- leitura dos KPIs herói


def rate_reference(current: float, network: float) -> str:
    """Vão de taxa contra a rede, em pontos percentuais, sem sinal."""
    delta = current - network
    if abs(delta) < _FLAT_RATE:
        return "igual à rede"
    side = "acima" if delta > 0 else "abaixo"
    return f"{fmt.decimal(abs(delta) * 100, 1)} p.p. {side} da rede"


def minute_reference(current: float, network: float) -> str:
    """Vão da mediana de ciclo contra a rede, em minutos."""
    delta = current - network
    if abs(delta) < _FLAT_MIN:
        return "igual à rede"
    side = "acima" if delta > 0 else "abaixo"
    return f"{fmt.decimal(abs(delta), 1)} min {side} da rede"


def hub_spread(values: list[float], unit: Literal["rate", "minutes"]) -> str | None:
    """Faixa entre hubs com base firme. Menos de dois hubs não sustenta a frase."""
    if len(values) < 2:
        return None
    lo, hi = min(values), max(values)
    if unit == "rate":
        a, b = fmt.pct(lo), fmt.pct(hi)
        return f"hubs em {a}" if a == b else f"hubs de {a} a {b}"
    a, b = fmt.decimal(lo, 1), fmt.decimal(hi, 1)
    return f"hubs em {a} min" if a == b else f"hubs de {a} a {b} min"


def _gap_ok(key: str, row: dict) -> bool:
    """Amostra que sustenta o vão. Cancelamento usa o total de pedidos; SLA e ciclo, a base medida."""
    if row.get(key) is None:
        return False
    if key == "cancel_rate":
        return row.get("orders", 0) >= MIN_MEASURED
    return not row.get("low_sample")


def _hero_verdict(key: str, row: dict) -> Verdict | None:
    """Mesma régua da comanda do recorte. Null quando a comanda não chamaria o número de firme."""
    if key == "cycle_p50":
        # 60/120 min são o prazo de cada pedido, não uma meta da mediana.
        return None
    if key == "sla_rate":
        sla = row.get("sla_rate")
        if sla is None or row.get("low_sample"):
            return None
        if (row.get("stuck_rate") or 0) > STUCK_HUB_MAX:
            return None
        return sla_band(float(sla))
    cancel = row.get("cancel_rate")
    if cancel is None:
        return None
    if row.get("orders", 0) < MIN_MEASURED and not _extreme_cancel(row):
        return None
    return cancel_band(float(cancel))


def _hub_values(rows: list[dict], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None or not _gap_ok(key, row):
            continue
        # Hub preso não entra na faixa de SLA: a comanda trata isso como dado, não como prazo.
        if key == "sla_rate" and (row.get("stuck_rate") or 0) > STUCK_HUB_MAX:
            continue
        values.append(float(value))
    return values


def _hero_reference(
    key: str,
    base: dict,
    network: dict,
    hubs: list[dict],
    full_network: bool,
) -> tuple[str | None, float | None]:
    """Frase da referência e, se for a rede, o valor cru para o traço do minigráfico."""
    if not _gap_ok(key, base):
        return None, None
    current = float(base[key])
    if not full_network:
        if not _gap_ok(key, network):
            return None, None
        net = float(network[key])
        text = minute_reference(current, net) if key == "cycle_p50" else rate_reference(current, net)
        return text, net
    unit: Literal["rate", "minutes"] = "minutes" if key == "cycle_p50" else "rate"
    return hub_spread(_hub_values(hubs, key), unit), None


def hero_readings(repo: Repository, f: Filters) -> list[dict]:
    """Veredito e referência dos três KPIs de operação, na ordem da faixa."""
    base = repo.metrics(f)
    full_network = f.is_full_network()
    if full_network:
        network = base
        hubs = repo.breakdown(f, "hub", sort="orders", limit=500, min_orders=0)
    else:
        start, end = repo.period(f)
        network = repo.metrics(Filters(start=start, end=end))
        hubs = []
    readings: list[dict] = []
    for key in ("sla_rate", "cycle_p50", "cancel_rate"):
        reference, network_value = _hero_reference(key, base, network, hubs, full_network)
        readings.append({
            "key": key,
            "verdict": _hero_verdict(key, base),
            "reference": reference,
            "network_value": network_value,
        })
    return readings
