"""Agente local: intenção (camada semântica + palavras-chave) e estatísticas do recorte. Sem API key.

Roteamento (`_plan`), em ordem: recorte vazio → fora do escopo → chargeback → entidade citada
(hub/loja/cidade; "por que" e janela dentro dela) → "por que mudou" → janela de tempo → rotas por
palavra-chave → métrica × dimensão (`local_answers.by_dimension`) quando a rota não cobre o par
pedido → métrica sozinha → pergunta anterior do histórico → briefing.
"""

from __future__ import annotations

import re
import unicodedata

from app import fmt
from app.agent import local_answers as la
from app.agent.local_intent import Entity, Intent, has_any, parse
from app.agent.reading import Reading, validate_drilldowns
from app.alerts import STAGES, STORE_MIN, detect_alerts
from app.filters import Filters
from app.repository import MIN_MEASURED, VALUE_LABELS, Repository
from app.schemas import DrillDown

SEVERITY = {"high": "Crítico", "medium": "Atenção", "low": "Observar"}
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
SUGGESTIONS = (
    "Tente perguntar: \"quais os alertas?\", \"onde está o gargalo?\", \"quais lojas cancelam mais?\", "
    "\"como está o pico do jantar?\", \"quanto estamos subsidiando de frete?\"."
)


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _only_canceled(f: Filters) -> bool:
    return set(f.status) == {"canceled"}


def _only_delivered(f: Filters) -> bool:
    return set(f.status) == {"delivered"}


def _canceled_delivery_notice(m: dict, subject: str) -> str:
    return (
        f"O recorte atual filtra apenas pedidos com status cancelado ({fmt.integer(m['canceled'])} pedidos), "
        f"sem entregas concluídas para medir {subject}.\n\n"
        "**Ação:** Operador deve remover o filtro de status cancelado para avaliar entregas concluídas neste período."
    )


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
    if _only_canceled(f):
        hubs = repo.breakdown(f, "hub", sort="orders", limit=1)
        top_hub = f" Hub com maior volume: {hubs[0]['label']} ({fmt.integer(hubs[0]['orders'])} cancelados)." if hubs else ""
        return (
            f"**Briefing do recorte** ({repo.describe(f)})\n\n"
            f"- {fmt.integer(m['canceled'])} pedidos cancelados (filtro status = cancelado; sem entregas concluídas neste recorte).{top_hub}\n\n"
            "**Ação:** Operador deve remover o filtro de status cancelado para comparar taxas e SLA, ou atuar no hub com maior volume de cancelamentos."
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
        # A ação do alerta que fecha a resposta sai da lista; os outros mantêm o próximo passo na linha.
        lead = _lead_alert(repo, alerts)
        lines += ["", "**Alertas**"]
        for a in [lead, *[x for x in alerts if x is not lead]][:4]:
            tail = "" if a is lead else f" Próximo passo: {a.action}"
            lines.append(f"- **{a.title}** ({SEVERITY[a.severity].lower()}): {a.detail}{tail}")
        lines += ["", f"**Ação:** {lead.action}"]
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


def _alert_count(n: int) -> str:
    return "1 alerta" if n == 1 else f"{n} alertas"


_lead_alert = la.lead_alert


def _alerts(repo: Repository, f: Filters) -> str:
    alerts = detect_alerts(repo, f)
    if not alerts:
        m = repo.metrics(f)
        return (
            f"Nenhum alerta no recorte ({repo.describe(f)}). SLA {fmt.pct(m['sla_rate'])}, "
            f"cancelamento {fmt.pct(m['cancel_rate'])}, ciclo mediano {fmt.minutes(m['cycle_p50'])}.\n\n"
            "**Ação:** Time de operações deve manter acompanhamento preventivo no pico de hoje."
        )
    lines = [f"{_alert_count(len(alerts))} no recorte ({repo.describe(f)}):", ""]
    for a in alerts:
        lines += [f"**{a.title}** (severidade {SEVERITY[a.severity]})", a.detail, f"**Ação:** {a.action}", ""]
    return "\n".join(lines).strip()


def _stages(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    if _only_canceled(f):
        return _canceled_delivery_notice(m, "as etapas do ciclo")
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
        # Mesma régua de amostra das lojas nos alertas; sem loja com base, a de maior volume no recorte.
        stores = repo.breakdown(f, "store", sort="production_p50", limit=1, min_orders=STORE_MIN, min_measured=MIN_MEASURED)
        if not stores:
            stores = repo.breakdown(f, "store", sort="production_p50", limit=1, min_orders=10)
        if not stores:
            stores = repo.breakdown(f, "store", sort="production_p50", limit=1, min_orders=1)
        lead_store = stores[0] if stores and stores[0].get("key") is not None else None
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
    if _only_canceled(f):
        return _canceled_delivery_notice(m, "SLA e ciclo")
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
    if _only_delivered(f):
        return (
            f"O recorte atual filtra apenas pedidos com status concluído ({fmt.integer(m['delivered'])} entregas), "
            "portanto o cancelamento é 0,0% por definição do filtro.\n\n"
            "**Ação:** Operador deve remover o filtro de status concluído para analisar os cancelamentos do período."
        )
    if _only_canceled(f):
        stores = repo.breakdown(f, "store", sort="orders", limit=5, min_orders=1)
        hubs = repo.breakdown(f, "hub", sort="orders", limit=3, min_orders=1)
        lines = [f"Cancelamentos no recorte (filtro status = cancelado): {fmt.integer(m['canceled'])} pedidos."]
        if hubs:
            lines += [
                "",
                "Hubs com mais pedidos cancelados:",
                *[f"- {h['label']} ({h['parent']}): {fmt.integer(h['orders'])} cancelados" for h in hubs],
            ]
        if stores:
            lines += [
                "",
                "Lojas com mais pedidos cancelados:",
                *[f"- {s['label']} ({s['parent']}): {fmt.integer(s['orders'])} cancelados" for s in stores],
            ]
        if stores:
            action = (
                f"**Ação:** Gerente de contas deve priorizar a loja {stores[0]['label']} "
                f"({fmt.integer(stores[0]['orders'])} cancelamentos) e checar ruptura ou cardápio aberto com loja fechada."
            )
        elif hubs:
            action = f"**Ação:** Líder do hub {hubs[0]['label']} deve auditar os {fmt.integer(hubs[0]['orders'])} cancelamentos."
        else:
            action = "**Ação:** Operador deve remover o filtro de status cancelado para comparar a taxa sobre o total de pedidos."
        lines += ["", action]
        return "\n".join(lines)
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

    broken = [s for s in stores if la.is_broken(s)]
    if broken:
        # Mesma família de ação do alerta de loja sem entregas: tirar do ar, não ligar para checar ruptura.
        names = ", ".join(s["label"] for s in broken[1:3])
        also = f" Fazer o mesmo com {names}." if names else ""
        lines += ["", f"**Ação:** {la.broken_store_action(repo, f, broken[0]['key'], broken[0]['label'])}{also}"]
        return "\n".join(lines)
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

    if _only_canceled(f):
        lead = hubs[0]
        lines += [
            "",
            f"**Ação:** Líder do hub {lead['label']} deve auditar os {fmt.integer(lead['orders'])} pedidos cancelados deste recorte ou remover o filtro de status para comparar taxas.",
        ]
        return "\n".join(lines)

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
    if _only_canceled(f):
        stores = repo.breakdown(f, "store", sort="orders", limit=5)
        if not stores:
            return (
                "Nenhuma loja no recorte.\n\n"
                "**Ação:** Operador deve afrouxar os filtros para analisar dados de lojas."
            )
        lines = [
            "Lojas com mais cancelamentos no recorte (filtro status = cancelado):",
            *[f"- {s['label']} ({s['parent']}): {fmt.integer(s['orders'])} cancelados" for s in stores],
            "",
            f"**Ação:** Gerente de contas da loja {stores[0]['label']} deve checar os {fmt.integer(stores[0]['orders'])} pedidos cancelados neste recorte.",
        ]
        return "\n".join(lines)
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


def _peak(repo: Repository, f: Filters, window=None) -> str:
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
    if window is not None and window.hours:
        # "pico do jantar": a faixa citada entra inteira, hora a hora, e a ação mira a pior hora dela.
        band = repo.query_metrics(f, metrics=["sla_rate"], where={"hour": list(window.hours)})["total"]
        inside = [h for h in hours if h.get("key") is not None and int(h["key"]) in window.hours and h["sla_rate"] is not None]
        parts = " · ".join(f"{int(h['key']):02d}h {fmt.pct(h['sla_rate'])}" for h in sorted(inside, key=lambda h: int(h["key"])))
        lines.append(
            f"{window.label} ({min(window.hours):02d}h–{max(window.hours) + 1:02d}h): SLA {fmt.pct(band['sla_rate'])}"
            + (f" · por hora: {parts}" if parts else "")
        )
        worst = min(inside, key=lambda h: h["sla_rate"], default=worst)
    if days:
        lines.append(f"Dia mais forte: {WEEKDAYS[int(days[0]['key'])]} ({fmt.integer(days[0]['orders'])} pedidos).")
    if worst:
        lines += ["", f"**Ação:** Time de frota deve escalar entregadores 30 min antes das {int(worst['key']):02d}h no dia mais forte."]
    else:
        lines += ["", "**Ação:** Time de frota deve monitorar a alocação de entregadores nos horários de maior demanda hoje."]
    return "\n".join(lines)


def _freight(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    if _only_canceled(f):
        return _canceled_delivery_notice(m, "frete e subsídio")
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


def _channel_types(repo: Repository, f: Filters) -> list[dict]:
    return [r for r in repo.breakdown(f, "channel_type", sort="orders", limit=3) if r.get("key") is not None]


def _channels(repo: Repository, f: Filters, by_type: bool = False) -> str:
    rows = repo.breakdown(f, "channel", sort="orders", limit=6)
    if not rows:
        return (
            "Nenhum canal no recorte.\n\n"
            "**Ação:** Time comercial deve revisar o período para analisar os canais."
        )
    types = _channel_types(repo, f)
    lines = []
    if types:
        lines += [
            "Por tipo de canal:",
            *[
                f"- {VALUE_LABELS.get(t['label'], t['label'])}: {fmt.integer(t['orders'])} pedidos · cancelamento "
                f"{fmt.pct(t['cancel_rate'])} · SLA {fmt.pct(t['sla_rate'])} · ticket {fmt.brl(t['ticket'])}"
                for t in types
            ],
            "",
        ]
    lines.append("Canais por volume:")
    for r in rows:
        kind = "próprio" if r["parent"] == "own" else "marketplace"
        lines.append(f"- {r['label']} ({kind}): {fmt.integer(r['orders'])} pedidos · cancelamento {fmt.pct(r['cancel_rate'])} · ticket {fmt.brl(r['ticket'])}")

    worst_cancel = max((r for r in rows if r.get("cancel_rate") is not None), key=lambda r: r["cancel_rate"], default=None)
    worst_sla = min((r for r in rows if r.get("sla_rate") is not None), key=lambda r: r["sla_rate"], default=None)

    if by_type and len(types) > 1:
        # Pergunta "marketplace ou canal próprio": a ação fica no tipo que cancela mais e no canal dele que puxa.
        worst_type = max(types, key=lambda t: t["cancel_rate"] or 0.0)
        other = next(t for t in types if t is not worst_type)
        shown = VALUE_LABELS.get(worst_type["label"], worst_type["label"])
        inside = max(
            (r for r in rows if r["parent"] == worst_type["key"] and r.get("cancel_rate") is not None),
            key=lambda r: r["cancel_rate"] * r["orders"],
            default=None,
        )
        lead = f", começando pelo canal {inside['label']} ({fmt.pct(inside['cancel_rate'])})" if inside else ""
        action = (
            f"**Ação:** Time comercial deve revisar hoje os cancelamentos do {shown} ({fmt.pct(worst_type['cancel_rate'])} "
            f"contra {fmt.pct(other['cancel_rate'])} do {VALUE_LABELS.get(other['label'], other['label'])}){lead}."
        )
    elif worst_cancel and (worst_cancel.get("cancel_above") or (worst_cancel.get("cancel_rate") or 0) > 0.06):
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
    if _only_canceled(f):
        return _canceled_delivery_notice(repo.metrics(f), "os modais de entrega")
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
    if _only_canceled(f):
        return (
            f"O recorte atual filtra apenas status cancelado ({fmt.integer(m['canceled'])} pedidos), "
            "por isso GMV e ticket de entregas concluídas são R$ 0,00 / —.\n\n"
            "**Ação:** Operador deve remover o filtro de status cancelado para analisar o faturamento das entregas."
        )
    seg = repo.breakdown(f, "segment", sort="gmv", limit=2)
    lines = [f"GMV {fmt.brl(m['gmv'])} em {fmt.integer(m['delivered'])} entregas · ticket {fmt.brl(m['ticket'])}."]
    lines += [f"- {VALUE_LABELS.get(s['label'], s['label'])}: {fmt.brl(s['gmv'])} · ticket {fmt.brl(s['ticket'])}" for s in seg]

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


def _payments(repo: Repository, f: Filters) -> str:
    rows = repo.breakdown(f, "payment_method", sort="orders", limit=6)
    if not rows:
        return (
            "Nenhuma forma de pagamento no recorte.\n\n"
            "**Ação:** Time comercial deve afrouxar os filtros para analisar as formas de pagamento."
        )
    lines = ["Formas de pagamento por volume:"]
    for r in rows:
        lines.append(
            f"- {la.value_label('payment_method', r['key'], r['label'])}: {fmt.integer(r['orders'])} pedidos · "
            f"cancelamento {fmt.pct(r['cancel_rate'])} · ticket {fmt.brl(r['ticket'])}"
        )
    # "Sem pagamento" é o balde nulo: aparece na lista, mas não é forma de pagamento para acionar.
    named = [r for r in rows if r.get("key") is not None] or rows
    empty = next((r for r in rows if r.get("key") is None), None)
    if empty is not None:
        lines.append(
            f"{empty['label']}: pedido sem pagamento registrado ({fmt.pct(empty['cancel_rate'])} cancelado); "
            "fica fora da ação."
        )
    if _only_canceled(f):
        lead = named[0]
        action = (
            f"**Ação:** Time de pagamentos deve auditar os {fmt.integer(lead['orders'])} pedidos cancelados "
            f"em {lead['label']} ou remover o filtro de status para comparar taxas."
        )
    else:
        rows = named
        worst = max(
            (r for r in rows if r.get("cancel_rate") is not None and r["orders"] >= MIN_MEASURED),
            key=lambda r: r["cancel_rate"],
            default=None,
        )
        if worst and (worst.get("cancel_above") or worst["cancel_rate"] > 0.06):
            action = (
                f"**Ação:** Time de pagamentos e time comercial devem revisar hoje as falhas de autorização "
                f"e cancelamentos em {worst['label']} ({fmt.pct(worst['cancel_rate'])})."
            )
        else:
            lead = rows[0]
            action = (
                f"**Ação:** Time de pagamentos deve monitorar a aprovação de {lead['label']} "
                f"({fmt.integer(lead['orders'])} pedidos) durante o pico de hoje."
            )
    lines += ["", action]
    return "\n".join(lines)


def _stuck(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    if _only_canceled(f):
        return _canceled_delivery_notice(m, "pedidos presos")
    stuck_rate = m["stuck_rate"] or 0.0
    stuck_n = round(stuck_rate * m["delivered"])
    hubs = [
        h for h in repo.breakdown(f, "hub", sort="stuck_rate", limit=5, min_orders=50)
        if h.get("delivered", 0) >= 50 and h.get("stuck_rate") is not None
    ]
    lines = [
        f"Pedidos presos no fluxo (ciclo > 4h): {fmt.integer(stuck_n)} entregas ({fmt.pct(stuck_rate)}), excluídos das medianas e do SLA."
    ]
    if hubs:
        lines += ["", "Hubs com maior taxa de presos:", *_rank_lines(hubs[:3], "stuck_rate", fmt.pct)]
        lead = hubs[0]
        action = (
            f"**Ação:** Líder do hub {lead['label']} deve conferir hoje a rotina de baixa manual e agendamentos "
            f"({fmt.pct(lead['stuck_rate'])} de presos) antes de cobrar SLA."
        )
    else:
        action = (
            "**Ação:** Líder de operações deve auditar hoje a rotina de finalização manual e pedidos agendados "
            "para evitar ciclos acima de 4h."
        )
    lines += ["", action]
    return "\n".join(lines)


def _volume(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    if _only_canceled(f):
        hubs = repo.breakdown(f, "hub", sort="orders", limit=3)
        lines = [f"Volume de cancelamentos no recorte: {fmt.integer(m['canceled'])} pedidos (filtro status = cancelado)."]
        if hubs:
            lines += ["", "Hubs com maior volume:", *[f"- {h['label']}: {fmt.integer(h['orders'])} pedidos" for h in hubs]]
            action = f"**Ação:** Líder do hub {hubs[0]['label']} deve priorizar hoje a apuração dos {fmt.integer(hubs[0]['orders'])} pedidos cancelados."
        else:
            action = "**Ação:** Operador deve remover o filtro de status cancelado para comparar o volume total."
        lines += ["", action]
        return "\n".join(lines)
    vol_alert = next((a for a in detect_alerts(repo, f) if a.id == "volume-queda"), None)
    if vol_alert:
        return f"**{vol_alert.title}**: {vol_alert.detail}\n\n**Ação:** {vol_alert.action}"
    hubs = repo.breakdown(f, "hub", sort="orders", limit=3)
    lines = [f"Volume no recorte: {fmt.integer(m['orders'])} pedidos ({fmt.integer(m['delivered'])} entregues) · GMV {fmt.brl(m['gmv'])}."]
    if hubs:
        lines += ["", "Hubs com maior volume:", *[
            f"- {h['label']} ({h['parent']}): {fmt.integer(h['orders'])} pedidos · SLA {fmt.pct(h['sla_rate'])}" for h in hubs
        ]]
        action = f"**Ação:** Líder do hub {hubs[0]['label']} deve acompanhar a demanda e o dimensionamento de entregadores no pico de hoje."
    else:
        action = "**Ação:** Time de operações deve acompanhar a demanda horária durante o pico de hoje."
    lines += ["", action]
    return "\n".join(lines)


# `token*` casa o começo da palavra. Frases valem mais que um token solto, então
# "tempo de trânsito por modal" cai em modal e não em etapa. `acao` saiu: entra
# em situação, operação, duração, informação e avaliação. `moto` e `hora` são
# palavra inteira, não pedaço de motorista ou melhorar.
_INTENT_ROUTES: list[tuple[tuple[str, ...], object]] = [
    (("alerta", "alertas", "problema", "problemas", "risco", "riscos", "prioridade"), _alerts),
    (("preso", "presos"), _stuck),
    (("pagamento*", "chargeback"), _payments),
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
    (("queda de volume", "queda na semana"), _volume),
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


resolve_handler = _route


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


def _top(repo: Repository, f: Filters, dimension: str, sort: str, desc: bool = True) -> dict | None:
    rows = repo.breakdown(f, dimension, sort=sort, desc=desc, limit=1, min_orders=1)
    if not rows:
        rows = repo.breakdown(f, dimension, sort=sort, desc=desc, limit=1, min_orders=0)
    return rows[0] if rows else None


def _hub_drill(row: dict) -> DrillDown:
    return DrillDown(label=f"Ver só {row['label']}", filters={"hub": [int(row["key"])]})


def _store_drill(row: dict) -> DrillDown:
    return DrillDown(label=f"Ver só {row['label']}", filters={"store": [int(row["key"])]})


def _drills_for(handler, repo: Repository, f: Filters) -> list[DrillDown]:
    """Atalhos montados com linhas do recorte. A validação descarta o que não existir."""
    if handler in (_peak, _payments):
        return []
    if handler is _stuck:
        if _only_canceled(f):
            return []
        hub = _top(repo, f, "hub", "stuck_rate")
        return [_hub_drill(hub)] if hub and hub.get("key") is not None else []
    if handler is _volume:
        hub = _top(repo, f, "hub", "orders")
        return [_hub_drill(hub)] if hub and hub.get("key") is not None else []
    if handler is _cancel:
        out = []
        store = _top(repo, f, "store", "cancel_rate")
        hub = _top(repo, f, "hub", "cancel_rate")
        if store and store.get("key") is not None:
            out.append(_store_drill(store))
        if hub and hub.get("key") is not None:
            out.append(_hub_drill(hub))
        return out
    if handler is _stores:
        store = _top(repo, f, "store", "cycle_p50")
        return [_store_drill(store)] if store and store.get("key") is not None else []
    if handler is _stages:
        out = []
        store = _top(repo, f, "store", "cycle_p50")
        hub = _top(repo, f, "hub", "cycle_p50")
        if store and store.get("key") is not None:
            out.append(_store_drill(store))
        if hub and hub.get("key") is not None:
            out.append(_hub_drill(hub))
        return out
    if handler is _sla:
        hub = _top(repo, f, "hub", "sla_rate", desc=False)
        return [_hub_drill(hub)] if hub and hub.get("key") is not None else []
    if handler is _hubs:
        hub = _top(repo, f, "hub", "orders")
        return [_hub_drill(hub)] if hub and hub.get("key") is not None else []
    if handler is _freight:
        hub = _top(repo, f, "hub", "subsidy")
        return [_hub_drill(hub)] if hub and hub.get("key") is not None else []
    if handler is _modal:
        rows = [row for row in repo.breakdown(f, "modal", sort="orders", limit=4) if row.get("key") in ("moto", "bike")]
        if not rows:
            return []
        worst = min(rows, key=lambda row: row["sla_rate"] if row["sla_rate"] is not None else 1)
        return [DrillDown(label=f"Ver só {worst['label']}", filters={"modal": [str(worst["key"])]})]
    if handler is _channels:
        rows = repo.breakdown(f, "channel_type", sort="cancel_rate", limit=1)
        if not rows or rows[0].get("key") is None:
            return []
        key = str(rows[0]["key"])
        shown = "canal próprio" if key == "own" else key
        return [DrillDown(label=f"Ver só {shown}", filters={"channel_type": [key]})]
    if handler is _revenue:
        rows = repo.breakdown(f, "segment", sort="gmv", limit=1)
        if not rows or rows[0].get("key") is None:
            return []
        key = str(rows[0]["key"])
        return [DrillDown(label=f"Ver só {key}", filters={"segment": [key]})]
    out = []
    for alert in detect_alerts(repo, f):
        if alert.drilldown:
            out.append(alert.drilldown)
        if len(out) == 2:
            break
    return out


def _headline(handler, metrics: dict) -> str:
    if handler is briefing:
        return "Briefing do recorte"
    if handler is _stages:
        return "Gargalo do ciclo"
    if handler is _cancel:
        return f"Cancelamento em {fmt.pct(metrics.get('cancel_rate'))}"
    if handler is _freight:
        return f"Subsídio de {fmt.brl(metrics.get('subsidy'))}"
    if handler is _peak:
        return "Pico do recorte"
    if handler is _sla:
        return f"SLA em {fmt.pct(metrics.get('sla_rate'))}"
    if handler is _channels:
        return "Canais do recorte"
    if handler is _modal:
        return "Modais do recorte"
    if handler is _stores:
        return "Lojas do recorte"
    if handler is _hubs:
        return "Hubs do recorte"
    if handler is _revenue:
        return f"GMV de {fmt.brl(metrics.get('gmv'))}"
    if handler is _payments:
        return "Formas de pagamento"
    if handler is _stuck:
        return "Pedidos presos no fluxo"
    if handler is _volume:
        return "Volume do recorte"
    return "Leitura do recorte"


_ROUTE_TOOLS = {
    _alerts: ["get_alerts", "get_kpis"],
    _payments: ["get_breakdown(payment_method)"],
    _stuck: ["get_kpis", "get_breakdown(hub)"],
    _volume: ["get_kpis", "get_alerts", "get_breakdown(hub)"],
    _stages: ["get_kpis", "get_breakdown(hub)", "get_breakdown(store)"],
    _cancel: ["get_kpis", "get_breakdown(store)", "get_breakdown(hub)"],
    _freight: ["get_kpis", "get_breakdown(hub)"],
    _peak: ["get_breakdown(hour)", "get_breakdown(weekday)"],
    _sla: ["get_kpis", "get_breakdown(hub)", "get_alerts"],
    _channels: ["get_breakdown(channel_type)"],
    _modal: ["get_breakdown(modal)"],
    _stores: ["get_breakdown(store)"],
    _hubs: ["get_breakdown(hub)"],
    _revenue: ["get_kpis", "get_breakdown(segment)"],
    briefing: ["get_kpis", "get_alerts"],
}


_ACTION_LINE = re.compile(r"(?m)^[ \t]*\*\*Ação:\*\*[ \t]*(.*)$")


def _plain_parts(text: str) -> tuple[str, str]:
    """A primeira ação em linha própria vira o bloco impresso. As outras saem do diagnóstico."""
    found = list(_ACTION_LINE.finditer(text))
    if found:
        action = found[0].group(1).strip() or "Operador deve revisar este recorte hoje."
        body = _ACTION_LINE.sub("", text)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        return body, action
    marker = "**Ação:**"
    index = text.rfind(marker)
    if index == -1:
        return text.strip(), "Operador deve revisar este recorte hoje."
    return text[:index].rstrip(), text[index + len(marker):].strip()


# Pares métrica × dimensão que cada rota por palavra-chave já responde bem. Fora disso, a pergunta
# "X por Y" vai para a resposta genérica (`local_answers.by_dimension`). None = qualquer métrica.
_COVERS: dict = {
    _cancel: ({"cancel_rate", "canceled"}, {"store", "hub", "channel_type"}),
    _sla: ({"sla_rate", "cycle_p50", "cycle_p90"}, {"hub"}),
    # _stages é o panorama das etapas; "etapa X por hub/loja" vai para a quebra genérica.
    _stages: (set(), set()),
    _freight: ({"subsidy", "fee_avg", "cost_avg"}, {"hub"}),
    _peak: ({"orders"}, {"hour", "weekday"}),
    _channels: (None, {"channel", "channel_type"}),
    _modal: (None, {"modal"}),
    _payments: (None, {"payment_method"}),
    _stores: ({"gmv", "cycle_p50", "sla_rate", "cancel_rate", "orders", "ticket"}, {"store"}),
    _hubs: ({"orders", "sla_rate", "cancel_rate", "cycle_p50"}, {"hub"}),
    _revenue: ({"gmv", "ticket"}, {"segment"}),
    _stuck: ({"stuck_rate"}, {"hub"}),
    _volume: ({"orders"}, {"hub"}),
}
# Métrica citada sem rota por palavra-chave: quem responde.
_METRIC_ROUTES = {
    "orders": _volume, "delivered": _volume, "canceled": _cancel, "cancel_rate": _cancel, "gmv": _revenue,
    "ticket": _revenue, "sla_rate": _sla, "cycle_p50": _sla, "cycle_p90": _sla, "measured": _sla,
    "stuck_rate": _stuck, "fee_avg": _freight, "cost_avg": _freight, "subsidy": _freight,
    **{stage: _stages for stage in STAGES},
}


def _covers(handler, metric: str, dim: str) -> bool:
    metrics, dims = _COVERS.get(handler, (set(), set()))
    return dim in dims and (metrics is None or metric in metrics)


def _legacy(handler, repo: Repository, f: Filters, intent: Intent | None = None) -> la.Answer:
    """Rota antiga (texto pronto) embrulhada no mesmo formato das respostas novas."""
    hour_windows = [w for w in (intent.windows if intent else []) if w.hours]
    if handler is _channels and intent is not None and "channel_type" in intent.dimensions:
        text = _channels(repo, f, by_type=True)
    elif handler is _peak and hour_windows:
        text = _peak(repo, f, window=hour_windows[0])
    else:
        text = handler(repo, f)
    metrics = repo.metrics(f)
    if handler is _alerts:
        alerts = detect_alerts(repo, f)
        # Título próprio: a comanda do agente fica no trilho ao lado da Nº 01 e não pode repetir o título dela.
        title = f"{_alert_count(len(alerts))} no recorte" if alerts else "Nenhum alerta no recorte"
    else:
        title = _headline(handler, metrics)
    return la.Answer(text, title, _ROUTE_TOOLS.get(handler, ["get_kpis", "get_alerts"]), _drills_for(handler, repo, f))


def _unrouted_answer(repo: Repository, f: Filters) -> la.Answer:
    return la.Answer(_unrouted(repo, f), "Leitura do recorte", ["get_kpis", "get_alerts"], _drills_for(None, repo, f))


def _with_previous_metric(intent: Intent, history: list | None) -> Intent:
    """"e o hub X?" depois de "qual hub cancela mais?": a entidade herda a métrica da pergunta anterior."""
    if intent.metrics or not history:
        return intent
    previous = _previous_user_question(history)
    if previous:
        intent.metrics = parse(previous).metrics
    return intent


def _entity_route(repo: Repository, f: Filters, intent: Intent, handler) -> la.Answer:
    entity = intent.entity
    fe = la.narrow(f, entity)
    if fe is not None and repo.metrics(fe)["orders"]:
        if intent.change and (intent.metrics or intent.previous or intent.week):
            scope = {"hub": "no hub", "store": "na loja", "city": "em"}[entity.dimension]
            return la.why(repo, fe, intent, scope_label=f"{scope} {entity.label}")
        if handler is _alerts or has_any(intent.tokens, ("alerta*", "problema*", "risco*")):
            return _legacy(_alerts, repo, fe)
        if intent.windows and "pico" not in intent.tokens:
            return la.windows(repo, fe, intent)
    return la.entity_answer(repo, f, intent)


_DEICTIC = ("desse", "deste", "esse", "este", "nesse", "neste", "dessa", "desta", "essa", "nessa", "nesta")
_DEICTIC_DIMS = {"hub": ("hub", "shopping"), "store": ("loja",), "city": ("cidade", "praca")}


def _deictic_entity(repo: Repository, f: Filters, intent: Intent) -> Entity | None:
    """"me dá um resumo desse hub" com um hub só no filtro: a entidade é a do recorte."""
    for dim, words in _DEICTIC_DIMS.items():
        values = list(getattr(f, dim))
        if len(values) != 1:
            continue
        if any(has_any(intent.tokens, (f"{d} {w}",)) for d in _DEICTIC for w in words):
            label = repo.names(dim, values)[0] if dim in ("hub", "store") else str(values[0])
            return Entity(dim, tuple(values), label, label)
    return None


def _plan(question: str, repo: Repository, f: Filters, history: list | None = None, *, depth: int = 0) -> la.Answer | None:
    """Escolhe quem responde. None = nada na pergunta (o chamador tenta o histórico ou o briefing)."""
    intent = parse(question, repo)
    if intent.out_of_scope:
        return la.out_of_scope(repo, f, intent.out_of_scope)
    if "chargeback_rate" in intent.metrics:
        return la.chargeback(repo, f, intent.dimension, intent)
    handler = _route(question)
    if intent.entity is None:
        intent.entity = _deictic_entity(repo, f, intent)
    if intent.entity is not None:
        return _entity_route(repo, f, _with_previous_metric(intent, history), handler)
    # "por que/caiu/subiu" só vira decomposição com algo para decompor (métrica ou período citado).
    if intent.change and (intent.metrics or intent.previous or intent.week):
        return la.why(repo, f, intent)
    if intent.windows and "pico" not in intent.tokens:
        return la.windows(repo, f, intent)
    metric, dim = intent.metric, intent.dimension
    # "melhor"/"menos" inverte a ordem: as rotas antigas só listam o pior primeiro.
    if metric and dim and (intent.best or intent.low):
        return la.by_dimension(repo, f, metric, dim, intent)
    if handler is not None and handler not in (_alerts, briefing) and metric and dim and not _covers(handler, metric, dim):
        return la.by_dimension(repo, f, metric, dim, intent)
    if handler is not None:
        return _legacy(handler, repo, f, intent)
    if metric and dim:
        return la.by_dimension(repo, f, metric, dim, intent)
    if metric:
        routed = _METRIC_ROUTES.get(metric)
        return _legacy(routed, repo, f, intent) if routed else la.by_dimension(repo, f, metric, "hub", intent)
    if depth == 0:
        previous = _previous_user_question(history)
        if previous:
            return _plan(previous, repo, f, None, depth=1)
    return None


_EMPTY = (
    "Nenhum pedido no recorte atual. Afrouxe os filtros para o agente ter o que analisar.\n\n"
    "**Ação:** Operador deve afrouxar os filtros de período, hub ou cidade para carregar dados da operação."
)


def _compose(question: str, repo: Repository, f: Filters, history: list | None = None) -> la.Answer:
    metrics = repo.metrics(f)
    if metrics["orders"] == 0:
        return la.Answer(_EMPTY, "Recorte sem pedidos", ["get_kpis"])
    result = _plan(question, repo, f, history) or _unrouted_answer(repo, f)
    if _is_thin(metrics) and not (_only_canceled(f) and (metrics.get("orders") or 0) >= MIN_MEASURED):
        result.text = _apply_thin(result.text, metrics)
    return result


def build_reading(question: str, repo: Repository, f: Filters, history: list | None = None) -> Reading:
    """A mesma leitura de `answer`, já separada em comanda. Não chama o modelo."""
    metrics = repo.metrics(f)
    result = _compose(question, repo, f, history)
    diagnosis, action = _plain_parts(result.text)
    return Reading(
        answer=result.text,
        title=result.title,
        diagnosis=diagnosis,
        action=action or "Operador deve revisar este recorte hoje.",
        drilldowns=validate_drilldowns(repo, f, result.drills) if metrics["orders"] else [],
        n=int(metrics.get("orders") or 0),
        measured=int(metrics.get("measured") or 0),
        low_sample=bool(metrics.get("low_sample")),
        tools=result.tools or ["get_kpis"],
    )


def answer(question: str, repo: Repository, f: Filters, history: list | None = None) -> str:
    return _compose(question, repo, f, history).text
