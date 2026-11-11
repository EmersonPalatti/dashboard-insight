"""Agente local: intenção por palavras-chave + estatísticas do recorte. Funciona sem API key."""

from __future__ import annotations

import re
import unicodedata

from app import fmt
from app.alerts import STAGES, detect_alerts
from app.filters import Filters
from app.repository import MIN_MEASURED, Repository

SEVERITY = {"high": "Crítico", "medium": "Atenção", "low": "Observar"}
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
SUGGESTIONS = (
    "Tente perguntar: \"quais os alertas?\", \"onde está o gargalo?\", \"quais lojas cancelam mais?\", "
    "\"como está o pico do jantar?\", \"quanto estamos subsidiando de frete?\"."
)


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _weight(words: list[str], pattern: str) -> int:
    """Palavra inteira, prefixo explícito (`cancel*`) ou frase. Frase vale o número de palavras."""
    if pattern.endswith("*"):
        stem = pattern[:-1]
        return 1 if stem and any(word.startswith(stem) for word in words) else 0
    parts = pattern.split()
    if len(parts) == 1:
        return 1 if parts[0] in words else 0
    span = len(parts)
    for index in range(len(words) - span + 1):
        if words[index:index + span] == parts:
            return span
    return 0


def _score(words: list[str], patterns: tuple[str, ...]) -> tuple[int, int]:
    hits = 0
    specificity = 0
    for pattern in patterns:
        weight = _weight(words, pattern)
        if not weight:
            continue
        hits += weight
        specificity = max(specificity, len(pattern.rstrip("*")))
    return hits, specificity


def _best_handler(words: list[str], routes: list[tuple[tuple[str, ...], object]]):
    chosen = None
    best = (0, 0)
    for patterns, handler in routes:
        score = _score(words, patterns)
        if score[0] > best[0] or (score[0] and score[0] == best[0] and score[1] > best[1]):
            best = score
            chosen = handler
    return chosen


def _rank_lines(rows: list[dict], value: str, fmt_fn, extra: str = "") -> list[str]:
    lines = []
    for r in rows:
        tail = f" · {fmt.integer(r['orders'])} pedidos"
        if extra == "sla":
            tail += f" · SLA {fmt.pct(r['sla_rate'])}"
        lines.append(f"- {r['label']}" + (f" ({r['parent']})" if r.get("parent") else "") + f": {fmt_fn(r[value])}{tail}")
    return lines


def briefing(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    if m["orders"] == 0:
        return (
            "Nenhum pedido no recorte. Afrouxe período, hub ou loja.\n\n"
            "**Ação:** Operador deve afrouxar os filtros do recorte para carregar dados da operação."
        )
    alerts = detect_alerts(repo, f)
    lines = [
        f"**Briefing do recorte** ({repo.describe(f)})",
        "",
        f"- {fmt.integer(m['orders'])} pedidos · GMV {fmt.brl(m['gmv'])} · ticket {fmt.brl(m['ticket'])}",
        f"- SLA {fmt.pct(m['sla_rate'])} · ciclo mediano {fmt.minutes(m['cycle_p50'])} (p90 {fmt.minutes(m['cycle_p90'])})",
        f"- Cancelamento {fmt.pct(m['cancel_rate'])} · subsídio de frete {fmt.brl(m['subsidy'])} por entrega",
    ]
    if alerts:
        lines += ["", "**Alertas e ações**"]
        for a in alerts[:4]:
            lines.append(f"- **{a.title}**: {a.detail} **Ação:** {a.action}")
    else:
        hubs = repo.breakdown(f, "hub", sort="orders", limit=1)
        if hubs:
            lead = hubs[0]
            action = (
                f"**Ação:** Líder do hub {lead['label']} deve acompanhar o pico do jantar "
                f"e o volume desse hub hoje."
            )
        else:
            action = "**Ação:** Time de operações deve acompanhar o pico do jantar no recorte hoje."
        lines += ["", "Nenhum alerta neste recorte.", "", action]
    return "\n".join(lines)


def _alerts(repo: Repository, f: Filters) -> str:
    alerts = detect_alerts(repo, f)
    if not alerts:
        m = repo.metrics(f)
        return (
            f"Nenhum alerta no recorte ({repo.describe(f)}). SLA {fmt.pct(m['sla_rate'])}, "
            f"cancelamento {fmt.pct(m['cancel_rate'])}, ciclo mediano {fmt.minutes(m['cycle_p50'])}.\n\n"
            "**Ação:** Time de operações deve manter acompanhamento preventivo no pico de hoje."
        )
    lines = [f"{len(alerts)} alerta(s) no recorte ({repo.describe(f)}):", ""]
    for a in alerts:
        lines += [f"**{a.title}** (severidade {SEVERITY[a.severity]})", a.detail, f"**Ação:** {a.action}", ""]
    return "\n".join(lines).strip()


def _stages(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    parts = [f"- {label.capitalize()}: {fmt.minutes(m[key])}" for key, label in STAGES.items()]
    hubs = repo.breakdown(f, "hub", sort="orders", limit=100, min_orders=300)
    lines = [f"Mediana por etapa no recorte (ciclo {fmt.minutes(m['cycle_p50'])}):", *parts]
    if len(hubs) > 1:
        worst = max(hubs, key=lambda h: (h["production_p50"] or 0) - (m["production_p50"] or 0))
        lines += [
            "",
            f"Hub com preparo mais acima da mediana: {worst['label']} ({fmt.minutes(worst['production_p50'])}).",
        ]
        slow_transit = max(hubs, key=lambda h: h["transit_p50"] or 0)
        lines.append(
            f"Trânsito mais longo: {slow_transit['label']} ({fmt.minutes(slow_transit['transit_p50'])}, "
            f"distância mediana {fmt.km(slow_transit['distance_p50_km'])})."
        )

    # Identificar a etapa gargalo no recorte
    known_stages = {k: m[k] for k in STAGES if m.get(k) is not None}
    bottleneck_key = max(known_stages, key=known_stages.get) if known_stages else "production_p50"
    bottleneck_label = STAGES[bottleneck_key]

    hubs_all = hubs if hubs else repo.breakdown(f, "hub", sort="orders", limit=100, min_orders=0)
    lead_hub = max(hubs_all, key=lambda h: h.get(bottleneck_key) or 0.0) if hubs_all else None

    if bottleneck_key == "production_p50":
        stores = repo.breakdown(f, "store", sort="cycle_p50", limit=10, min_orders=10)
        if not stores:
            stores = repo.breakdown(f, "store", sort="cycle_p50", limit=10, min_orders=1)
        lead_store = max(stores, key=lambda s: s.get("production_p50") or 0.0) if stores else None
        if lead_store and (lead_store.get("production_p50") or 0) > 0:
            lines += [
                "",
                f"**Ação:** Gerente de contas deve alinhar hoje com a loja {lead_store['label']} a redução do tempo de {bottleneck_label} ({fmt.minutes(lead_store['production_p50'])}).",
            ]
        elif lead_hub:
            lines += [
                "",
                f"**Ação:** Líder do hub {lead_hub['label']} deve alinhar hoje com os restaurantes a redução do tempo de {bottleneck_label} ({fmt.minutes(lead_hub['production_p50'])}).",
            ]
        else:
            lines += [
                "",
                f"**Ação:** Gerente de contas deve alinhar hoje com as lojas a redução do tempo de {bottleneck_label}.",
            ]
    elif bottleneck_key == "transit_p50":
        if lead_hub:
            lines += [
                "",
                f"**Ação:** Time de frota deve reforçar entregadores e revisar raio no hub {lead_hub['label']} hoje para reduzir o tempo de {bottleneck_label} ({fmt.minutes(lead_hub['transit_p50'])}).",
            ]
        else:
            lines += [
                "",
                f"**Ação:** Time de frota deve reforçar a disponibilidade de entregadores hoje para reduzir o tempo de {bottleneck_label}.",
            ]
    else:  # collected_p50 ou expedition_p50
        stage_val = fmt.minutes(lead_hub.get(bottleneck_key)) if lead_hub else fmt.minutes(m.get(bottleneck_key))
        if lead_hub:
            lines += [
                "",
                f"**Ação:** Líder do hub {lead_hub['label']} deve intervir hoje no fluxo de {bottleneck_label} para reduzir o tempo de espera ({stage_val}).",
            ]
        else:
            lines += [
                "",
                f"**Ação:** Líder de operações deve auditar hoje o processo de {bottleneck_label} ({stage_val}).",
            ]

    return "\n".join(lines)


def _sla(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    hubs = repo.breakdown(f, "hub", sort="sla_rate", desc=False, limit=5, min_orders=300)
    lines = [
        (
            f"SLA do recorte: {fmt.pct(m['sla_rate'])} no prazo · ciclo mediano {fmt.minutes(m['cycle_p50'])} "
            f"· p90 {fmt.minutes(m['cycle_p90'])}."
        ),
    ]
    if hubs:
        lines += ["", "Hubs com pior SLA (mín. 300 pedidos):", *_rank_lines(hubs, "sla_rate", fmt.pct)]

    alert = next((a for a in detect_alerts(repo, f) if a.id.startswith("sla-hub")), None)
    if not alert:
        alert = next((a for a in detect_alerts(repo, f) if a.id.startswith("sla")), None)
    if alert:
        lines += ["", f"**Ação:** {alert.action}"]
        return "\n".join(lines)

    if hubs:
        worst_hub = hubs[0]
        lines += [
            "",
            f"**Ação:** Líder do hub {worst_hub['label']} deve investigar hoje os atrasos de expedição e rota para elevar o SLA ({fmt.pct(worst_hub['sla_rate'])}).",
        ]
        return "\n".join(lines)

    hubs_low = repo.breakdown(f, "hub", sort="sla_rate", desc=False, limit=5, min_orders=10)
    if not hubs_low:
        hubs_low = repo.breakdown(f, "hub", sort="sla_rate", desc=False, limit=5, min_orders=1)
    if hubs_low:
        worst_hub = hubs_low[0]
        note = f" (amostra reduzida de {fmt.integer(worst_hub['orders'])} pedidos)" if (worst_hub.get("orders") or 0) < 300 else ""
        lines += [
            "",
            f"**Ação:** Líder do hub {worst_hub['label']} deve acompanhar hoje a pontualidade das entregas para recuperar o SLA ({fmt.pct(worst_hub['sla_rate'])}){note}.",
        ]
        return "\n".join(lines)

    stores = repo.breakdown(f, "store", sort="sla_rate", desc=False, limit=1, min_orders=1)
    if stores:
        worst_store = stores[0]
        lines += [
            "",
            f"**Ação:** Gerente de contas deve verificar hoje os atrasos de preparo na loja {worst_store['label']} (SLA {fmt.pct(worst_store['sla_rate'])}).",
        ]
        return "\n".join(lines)

    lines += ["", "**Ação:** Time de operações deve manter o monitoramento de SLA durante o pico de hoje."]
    return "\n".join(lines)


def _cancel(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    stores = repo.breakdown(f, "store", sort="cancel_rate", limit=5, min_orders=150)
    hubs = repo.breakdown(f, "hub", sort="cancel_rate", limit=3, min_orders=300)
    channels = repo.breakdown(f, "channel_type", sort="cancel_rate", limit=2)
    lines = [f"Cancelamento no recorte: {fmt.pct(m['cancel_rate'])} ({fmt.integer(m['canceled'])} pedidos)."]
    if channels:
        lines.append("Por canal: " + " · ".join(
            f"{'canal próprio' if c['label'] == 'own' else c['label']} {fmt.pct(c['cancel_rate'])}" for c in channels
        ))
    if hubs:
        lines += ["", "Hubs que mais cancelam:", *_rank_lines(hubs, "cancel_rate", fmt.pct)]
    if stores:
        lines += ["", "Lojas que mais cancelam (mín. 150 pedidos):", *_rank_lines(stores, "cancel_rate", fmt.pct)]

    if stores and (stores[0].get("cancel_rate") or 0.0) > 0:
        lines += ["", f"**Ação:** Gerente de contas deve ligar para a loja {stores[0]['label']} hoje e checar ruptura e cardápio aberto com loja fechada."]
        return "\n".join(lines)

    alerts = detect_alerts(repo, f)
    cancel_alert = next((a for a in alerts if a.id.startswith("cancel")), None)
    if cancel_alert:
        lines += ["", f"**Ação:** {cancel_alert.action}"]
        return "\n".join(lines)

    stores_low = repo.breakdown(f, "store", sort="cancel_rate", limit=3, min_orders=10)
    if not stores_low:
        stores_low = repo.breakdown(f, "store", sort="cancel_rate", limit=3, min_orders=1)
    if stores_low and (stores_low[0].get("cancel_rate") or 0.0) > 0:
        worst_store = stores_low[0]
        note = f" (amostra de {fmt.integer(worst_store['orders'])} pedidos)" if (worst_store.get("orders") or 0) < 150 else ""
        lines += [
            "",
            f"**Ação:** Gerente de contas deve contatar a loja {worst_store['label']} hoje e verificar motivos de cancelamento ({fmt.pct(worst_store['cancel_rate'])}){note}.",
        ]
        return "\n".join(lines)

    if hubs and (hubs[0].get("cancel_rate") or 0.0) > 0:
        worst_hub = hubs[0]
        lines += [
            "",
            f"**Ação:** Líder do hub {worst_hub['label']} deve apurar hoje as causas operacionais de cancelamento ({fmt.pct(worst_hub['cancel_rate'])}).",
        ]
        return "\n".join(lines)

    lines += ["", "**Ação:** Time de operações deve manter o monitoramento de cancelamentos no pico de hoje."]
    return "\n".join(lines)


def _hubs(repo: Repository, f: Filters) -> str:
    hubs = repo.breakdown(f, "hub", sort="orders", limit=8)
    if not hubs:
        return (
            "Nenhum hub no recorte.\n\n"
            "**Ação:** Operador deve ajustar os filtros do recorte para incluir dados de operação."
        )
    lines = ["Hubs por volume no recorte:"]
    for h in hubs:
        lines.append(
            f"- {h['label']} ({h['parent']}): {fmt.integer(h['orders'])} pedidos · SLA {fmt.pct(h['sla_rate'])} "
            f"· cancelamento {fmt.pct(h['cancel_rate'])} · ciclo {fmt.minutes(h['cycle_p50'])}"
        )

    worst_sla = min((h for h in hubs if h.get("sla_below")), key=lambda h: h["sla_rate"] or 1.0, default=None)
    worst_cancel = max((h for h in hubs if h.get("cancel_above")), key=lambda h: h["cancel_rate"] or 0.0, default=None)

    if worst_cancel:
        action = f"**Ação:** Líder do hub {worst_cancel['label']} deve apurar hoje os cancelamentos ({fmt.pct(worst_cancel['cancel_rate'])}) e atuar com os parceiros da praça."
    elif worst_sla:
        action = f"**Ação:** Líder do hub {worst_sla['label']} deve revisar hoje os tempos de ciclo (mediana {fmt.minutes(worst_sla['cycle_p50'])}) para recuperar o SLA ({fmt.pct(worst_sla['sla_rate'])})."
    elif any(h.get("sla_rate") is not None and h["sla_rate"] < 0.85 for h in hubs):
        worst = min((h for h in hubs if h.get("sla_rate") is not None), key=lambda h: h["sla_rate"])
        action = f"**Ação:** Líder do hub {worst['label']} deve intervir hoje nas etapas com maior tempo de retenção para elevar o SLA ({fmt.pct(worst['sla_rate'])})."
    elif any(h.get("cancel_rate") is not None and h["cancel_rate"] > 0.06 for h in hubs):
        worst = max((h for h in hubs if h.get("cancel_rate") is not None), key=lambda h: h["cancel_rate"])
        action = f"**Ação:** Líder do hub {worst['label']} deve auditar hoje as recusas de pedidos ({fmt.pct(worst['cancel_rate'])} de cancelamento)."
    else:
        lead = hubs[0]
        action = f"**Ação:** Líder do hub {lead['label']} deve acompanhar o volume e os tempos de despacho no pico de hoje."

    lines += ["", action]
    return "\n".join(lines)


def _stores(repo: Repository, f: Filters) -> str:
    top = repo.breakdown(f, "store", sort="gmv", limit=5)
    slow = repo.breakdown(f, "store", sort="cycle_p50", limit=5, min_orders=150)
    if not top and not slow:
        return (
            "Nenhuma loja no recorte.\n\n"
            "**Ação:** Operador deve afrouxar os filtros para analisar dados de lojas."
        )
    lines = ["Lojas com maior GMV:", *_rank_lines(top, "gmv", fmt.brl, extra="sla")]
    if slow:
        lines += ["", "Lojas com ciclo mais longo (mín. 150 pedidos):", *_rank_lines(slow, "cycle_p50", fmt.minutes)]

    all_stores = slow + top
    worst_cancel = max((s for s in all_stores if s.get("cancel_rate") is not None), key=lambda s: s["cancel_rate"], default=None)
    worst_sla = min((s for s in all_stores if s.get("sla_rate") is not None), key=lambda s: s["sla_rate"], default=None)

    if slow and ((slow[0].get("cycle_p50") or 0) > 40 or slow[0].get("sla_below")):
        worst_slow = slow[0]
        action = f"**Ação:** Gerente de contas da loja {worst_slow['label']} deve alinhar hoje redução do tempo de preparo (ciclo mediano em {fmt.minutes(worst_slow['cycle_p50'])})."
    elif worst_cancel and (worst_cancel.get("cancel_above") or (worst_cancel.get("cancel_rate") or 0) > 0.06):
        action = f"**Ação:** Gerente de contas da loja {worst_cancel['label']} deve contatar o parceiro hoje para diagnosticar a taxa de cancelamento ({fmt.pct(worst_cancel['cancel_rate'])})."
    elif worst_sla and (worst_sla.get("sla_below") or (worst_sla.get("sla_rate") or 1.0) < 0.85):
        action = f"**Ação:** Gerente de contas da loja {worst_sla['label']} deve checar hoje a agilidade no despacho para recompor o SLA ({fmt.pct(worst_sla['sla_rate'])})."
    elif slow:
        worst_slow = slow[0]
        action = f"**Ação:** Gerente de contas da loja {worst_slow['label']} deve alinhar hoje redução do ciclo de entrega ({fmt.minutes(worst_slow['cycle_p50'])})."
    else:
        lead = top[0]
        action = f"**Ação:** Gerente de contas da loja {lead['label']} deve monitorar a operação e o fluxo de pedidos no pico de hoje."

    lines += ["", action]
    return "\n".join(lines)


def _peak(repo: Repository, f: Filters) -> str:
    hours = repo.breakdown(f, "hour", sort="orders", limit=24)
    if not hours:
        return (
            "Sem pedidos no recorte.\n\n"
            "**Ação:** Operador deve ajustar os filtros do recorte para avaliar os horários de pico."
        )
    top = sorted(hours[:4], key=lambda h: int(h["key"]))
    worst = min((h for h in hours[:6] if h["sla_rate"] is not None), key=lambda h: h["sla_rate"], default=None)
    days = repo.breakdown(f, "weekday", sort="orders", limit=7)
    lines = ["Horários de maior volume:"]
    lines += [f"- {int(h['key']):02d}h: {fmt.integer(h['orders'])} pedidos · SLA {fmt.pct(h['sla_rate'])}" for h in top]
    if worst:
        lines += ["", f"Pior SLA entre os horários de pico: {int(worst['key']):02d}h ({fmt.pct(worst['sla_rate'])})."]
    if days:
        lines.append(f"Dia mais forte: {WEEKDAYS[int(days[0]['key'])]} ({fmt.integer(days[0]['orders'])} pedidos).")
    if worst:
        lines += ["", f"**Ação:** Time de frota deve escalar entregadores 30 min antes das {int(worst['key']):02d}h no dia mais forte."]
    else:
        lines += ["", "**Ação:** Time de frota deve monitorar a alocação de entregadores nos horários de maior demanda hoje."]
    return "\n".join(lines)


def _freight(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    hubs = repo.breakdown(f, "hub", sort="subsidy", limit=3, min_orders=300)
    lines = [
        (
            f"Frete médio cobrado {fmt.brl(m['fee_avg'])} · custo logístico {fmt.brl(m['cost_avg'])} · "
            f"subsídio {fmt.brl(m['subsidy'])} por entrega."
        ),
    ]
    if hubs:
        lines += ["", "Hubs com maior subsídio:", *_rank_lines(hubs, "subsidy", fmt.brl)]

    hubs_sub = hubs if hubs else repo.breakdown(f, "hub", sort="subsidy", limit=3, min_orders=10)
    if not hubs_sub:
        hubs_sub = repo.breakdown(f, "hub", sort="subsidy", limit=3, min_orders=1)

    if hubs_sub and (hubs_sub[0].get("subsidy") or 0.0) > 0:
        worst_hub = hubs_sub[0]
        action = f"**Ação:** Time comercial e time de frota devem revisar hoje a tabela de frete e o raio de entrega do hub {worst_hub['label']} para conter o subsídio de {fmt.brl(worst_hub['subsidy'])} por pedido."
    elif (m.get("subsidy") or 0.0) > 0:
        action = f"**Ação:** Time comercial deve reavaliar hoje a política tarifária de entrega no recorte para cobrir o custo logístico médio ({fmt.brl(m['cost_avg'])})."
    else:
        lead = hubs_sub[0] if hubs_sub else None
        if lead:
            action = f"**Ação:** Time de frota deve acompanhar a relação de custo e frete no hub {lead['label']} durante esta semana para manter a margem equilibrada."
        else:
            action = "**Ação:** Time de frota deve acompanhar os custos de entrega no recorte durante esta semana para manter a operação equilibrada."

    lines += ["", action]
    return "\n".join(lines)


def _channels(repo: Repository, f: Filters) -> str:
    rows = repo.breakdown(f, "channel", sort="orders", limit=6)
    if not rows:
        return (
            "Nenhum canal no recorte.\n\n"
            "**Ação:** Time comercial deve revisar o período para analisar os canais."
        )
    lines = ["Canais por volume:"]
    for r in rows:
        kind = "próprio" if r["parent"] == "own" else "marketplace"
        lines.append(f"- {r['label']} ({kind}): {fmt.integer(r['orders'])} pedidos · cancelamento {fmt.pct(r['cancel_rate'])} · ticket {fmt.brl(r['ticket'])}")

    worst_cancel = max((r for r in rows if r.get("cancel_rate") is not None), key=lambda r: r["cancel_rate"], default=None)
    worst_sla = min((r for r in rows if r.get("sla_rate") is not None), key=lambda r: r["sla_rate"], default=None)

    if worst_cancel and (worst_cancel.get("cancel_above") or (worst_cancel.get("cancel_rate") or 0) > 0.06):
        action = f"**Ação:** Time comercial deve alinhar hoje com os parceiros do canal {worst_cancel['label']} os motivos de cancelamento ({fmt.pct(worst_cancel['cancel_rate'])})."
    elif worst_sla and (worst_sla.get("sla_below") or (worst_sla.get("sla_rate") or 1.0) < 0.85):
        action = f"**Ação:** Time comercial e operação devem auditar hoje a integração do canal {worst_sla['label']} para recuperar o SLA ({fmt.pct(worst_sla['sla_rate'])})."
    else:
        lead = rows[0]
        action = (
            f"**Ação:** Time comercial deve monitorar hoje o volume, o cancelamento ({fmt.pct(lead['cancel_rate'])}) "
            f"e o ticket ({fmt.brl(lead['ticket'])}) do canal {lead['label']}."
        )

    lines += ["", action]
    return "\n".join(lines)


def _modal(repo: Repository, f: Filters) -> str:
    rows = repo.breakdown(f, "modal", sort="orders", limit=2)
    if not rows:
        return (
            "Nenhum modal no recorte.\n\n"
            "**Ação:** Time de frota deve ajustar os filtros para avaliar modais de entrega."
        )
    lines = ["Entregas por modal:"]
    for r in rows:
        lines.append(
            f"- {r['label']}: {fmt.integer(r['delivered'])} entregas · trânsito {fmt.minutes(r['transit_p50'])} "
            f"· distância mediana {fmt.km(r['distance_p50_km'])} · SLA {fmt.pct(r['sla_rate'])}"
        )

    worst_sla = min((r for r in rows if r.get("sla_rate") is not None), key=lambda r: r["sla_rate"], default=None)
    slow_transit = max((r for r in rows if r.get("transit_p50") is not None), key=lambda r: r["transit_p50"], default=None)

    if worst_sla and (worst_sla.get("sla_below") or (worst_sla.get("sla_rate") or 1.0) < 0.85):
        action = f"**Ação:** Time de frota deve recalibrar hoje o raio de despacho para o modal {worst_sla['label']} (SLA em {fmt.pct(worst_sla['sla_rate'])} e trânsito mediano de {fmt.minutes(worst_sla['transit_p50'])})."
    elif slow_transit and (slow_transit.get("transit_p50") or 0) > 25:
        action = f"**Ação:** Time de frota deve limitar hoje o raio máximo do modal {slow_transit['label']} para reduzir o trânsito ({fmt.minutes(slow_transit['transit_p50'])})."
    else:
        lead = rows[0]
        action = f"**Ação:** Time de frota deve acompanhar o dimensionamento de entregadores do modal {lead['label']} durante o pico de hoje."

    lines += ["", action]
    return "\n".join(lines)


def _revenue(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    seg = repo.breakdown(f, "segment", sort="gmv", limit=2)
    lines = [f"GMV {fmt.brl(m['gmv'])} em {fmt.integer(m['delivered'])} entregas · ticket {fmt.brl(m['ticket'])}."]
    lines += [f"- {s['label']}: {fmt.brl(s['gmv'])} · ticket {fmt.brl(s['ticket'])}" for s in seg]

    worst_cancel = max((s for s in seg if s.get("cancel_rate") is not None), key=lambda s: s["cancel_rate"], default=None)

    if worst_cancel and (worst_cancel.get("cancel_above") or (worst_cancel.get("cancel_rate") or 0) > 0.06):
        action = f"**Ação:** Time comercial deve atuar hoje junto aos lojistas do segmento {worst_cancel['label']} para conter perdas de receita por cancelamento ({fmt.pct(worst_cancel['cancel_rate'])})."
    elif seg:
        lead = seg[0]
        action = (
            f"**Ação:** Time comercial deve revisar hoje com os lojistas do segmento {lead['label']} "
            f"o ticket ({fmt.brl(lead['ticket'])}) e o cancelamento ({fmt.pct(lead['cancel_rate'])})."
        )
    else:
        action = "**Ação:** Time comercial deve monitorar o faturamento e ticket médio no fechamento de hoje."

    lines += ["", action]
    return "\n".join(lines)


# `token*` casa o começo da palavra. Frases valem mais que um token solto, então
# "tempo de trânsito por modal" cai em modal e não em etapa. `acao` saiu: entra
# em situação, operação, duração, informação e avaliação. `moto` e `hora` são
# palavra inteira, não pedaço de motorista ou melhorar.
_INTENT_ROUTES: list[tuple[tuple[str, ...], object]] = [
    (("alerta", "alertas", "problema", "problemas", "risco", "riscos", "prioridade", "fazer hoje"), _alerts),
    (("gargalo", "etapa*", "preparo", "coleta", "expedicao", "transito"), _stages),
    (("cancel*",), _cancel),
    (("frete", "subsid*", "custo", "custos"), _freight),
    (("pico", "horario*", "hora", "horas", "jantar", "almoco", "dia da semana", "dias da semana"), _peak),
    (("sla", "prazo", "atras*", "demora", "tempo", "ciclo", "lent*"), _sla),
    (("canal*", "marketplace", "proprio"), _channels),
    (("moto", "bike", "modal*", "entregador", "por modal", "do modal", "no modal", "de modal"), _modal),
    (("loja*", "restaurante*", "parceiro*"), _stores),
    (("hub*", "praca*", "cidade*", "shopping*"), _hubs),
    (("gmv", "ticket", "receita", "faturamento", "venda*"), _revenue),
]
_BRIEFING_PATTERNS = ("resumo", "briefing", "visao geral", "panorama", "como esta")


def _route(question: str):
    words = _words(_norm(question))
    handler = _best_handler(words, _INTENT_ROUTES)
    if handler is not None:
        return handler
    if _score(words, _BRIEFING_PATTERNS)[0]:
        return briefing
    return None


def _turn_text(turn) -> tuple[str, str]:
    role = getattr(turn, "role", None)
    content = getattr(turn, "content", None)
    if role is None and isinstance(turn, dict):
        role = turn.get("role", "")
        content = turn.get("content", "")
    return str(role or ""), str(content or "")


def _previous_user_question(history: list | None) -> str | None:
    for turn in reversed(history or []):
        role, content = _turn_text(turn)
        if role == "user" and content.strip():
            return content
    return None


def _is_thin(metrics: dict) -> bool:
    """SLA e ciclo usam a base medida; cancelamento usa o total. Os dois pedem período maior."""
    return bool(metrics.get("low_sample")) or (metrics.get("orders") or 0) < MIN_MEASURED


def _split_closing_action(text: str) -> tuple[str, str | None]:
    """Separa a última linha que começa com **Ação:**. Ação no meio do parágrafo fica no corpo."""
    stripped = text.rstrip()
    marker = "**Ação:**"
    index = stripped.rfind(marker)
    if index == -1:
        return stripped, None
    line_start = stripped.rfind("\n", 0, index) + 1
    if stripped[line_start:index].strip() or "\n" in stripped[index:]:
        return stripped, None
    return stripped[:line_start].rstrip(), stripped[index:]


def _unrouted(repo: Repository, f: Filters) -> str:
    body, action = _split_closing_action(briefing(repo, f))
    if action is None:
        action = (
            "**Ação:** Operador deve usar uma das perguntas acima para apontar o problema deste recorte ainda hoje."
        )
    return f"{body}\n\n{SUGGESTIONS}\n\n{action}"


def _apply_thin(text: str, metrics: dict) -> str:
    note = (
        f"Atenção: amostra reduzida no recorte ({fmt.integer(metrics.get('measured'))} entregas medidas, "
        f"{fmt.integer(metrics.get('orders'))} pedidos; mínimo confiável {MIN_MEASURED})."
    )
    body, _action = _split_closing_action(text)
    if _action is None:
        marker = "**Ação:**"
        index = text.rfind(marker)
        body = text[:index].rstrip() if index != -1 else text.rstrip()
    action = "**Ação:** Operador deve ampliar o período neste recorte antes de acionar alguém hoje."
    return f"{note}\n\n{body}\n\n{action}"


def answer(question: str, repo: Repository, f: Filters, history: list | None = None) -> str:
    metrics = repo.metrics(f)
    if metrics["orders"] == 0:
        return (
            "Nenhum pedido no recorte atual. Afrouxe os filtros para o agente ter o que analisar.\n\n"
            "**Ação:** Operador deve afrouxar os filtros de período, hub ou cidade para carregar dados da operação."
        )
    handler = _route(question)
    if handler is None:
        previous = _previous_user_question(history)
        if previous:
            handler = _route(previous)
    text = handler(repo, f) if handler is not None else _unrouted(repo, f)
    if _is_thin(metrics):
        text = _apply_thin(text, metrics)
    return text
