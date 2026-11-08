"""Agente local: intenção por palavras-chave + estatísticas do recorte. Funciona sem API key."""

from __future__ import annotations

import unicodedata

from app import fmt
from app.alerts import STAGES, detect_alerts
from app.filters import Filters
from app.repository import Repository

SEVERITY = {"high": "alta", "medium": "média", "low": "baixa"}
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
SUGGESTIONS = (
    "Tente perguntar: \"quais os alertas?\", \"onde está o gargalo?\", \"quais lojas cancelam mais?\", "
    "\"como está o pico do jantar?\", \"quanto estamos subsidiando de frete?\"."
)


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _has(q: str, *tokens: str) -> bool:
    return any(t in q for t in tokens)


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
        return "Nenhum pedido no recorte. Afrouxe período, hub ou loja."
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
            lines.append(f"- **{a.title}**: {a.detail} Ação: {a.action}")
    else:
        lines += ["", "Nenhum alerta neste recorte. Vale acompanhar o pico do jantar e o hub de maior volume."]
    return "\n".join(lines)


def _alerts(repo: Repository, f: Filters) -> str:
    alerts = detect_alerts(repo, f)
    if not alerts:
        m = repo.metrics(f)
        return (
            f"Nenhum alerta no recorte ({repo.describe(f)}). SLA {fmt.pct(m['sla_rate'])}, "
            f"cancelamento {fmt.pct(m['cancel_rate'])}, ciclo mediano {fmt.minutes(m['cycle_p50'])}."
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
    lines += ["", "**Ação:** preparo alto se resolve com a loja; trânsito alto, com frota e raio de entrega."]
    return "\n".join(lines)


def _sla(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    hubs = repo.breakdown(f, "hub", sort="sla_rate", desc=False, limit=5, min_orders=300)
    lines = [
        f"SLA do recorte: {fmt.pct(m['sla_rate'])} no prazo · ciclo mediano {fmt.minutes(m['cycle_p50'])} "
        f"· p90 {fmt.minutes(m['cycle_p90'])}.",
    ]
    if hubs:
        lines += ["", "Hubs com pior SLA (mín. 300 pedidos):", *_rank_lines(hubs, "sla_rate", fmt.pct)]
    alert = next((a for a in detect_alerts(repo, f) if a.id.startswith("sla-hub")), None)
    if alert:
        lines += ["", f"**Ação:** {alert.action}"]
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
        lines += ["", f"**Ação:** ligar para {stores[0]['label']} hoje e checar ruptura e cardápio aberto com loja fechada."]
    return "\n".join(lines)


def _hubs(repo: Repository, f: Filters) -> str:
    hubs = repo.breakdown(f, "hub", sort="orders", limit=8)
    if not hubs:
        return "Nenhum hub no recorte."
    lines = ["Hubs por volume no recorte:"]
    for h in hubs:
        lines.append(
            f"- {h['label']} ({h['parent']}): {fmt.integer(h['orders'])} pedidos · SLA {fmt.pct(h['sla_rate'])} "
            f"· cancelamento {fmt.pct(h['cancel_rate'])} · ciclo {fmt.minutes(h['cycle_p50'])}"
        )
    return "\n".join(lines)


def _stores(repo: Repository, f: Filters) -> str:
    top = repo.breakdown(f, "store", sort="gmv", limit=5)
    slow = repo.breakdown(f, "store", sort="cycle_p50", limit=5, min_orders=150)
    lines = ["Lojas com maior GMV:", *_rank_lines(top, "gmv", fmt.brl, extra="sla")]
    if slow:
        lines += ["", "Lojas com ciclo mais longo (mín. 150 pedidos):", *_rank_lines(slow, "cycle_p50", fmt.minutes)]
    return "\n".join(lines)


def _peak(repo: Repository, f: Filters) -> str:
    hours = repo.breakdown(f, "hour", sort="orders", limit=24)
    if not hours:
        return "Sem pedidos no recorte."
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
        lines += ["", f"**Ação:** escalar entregadores 30 min antes das {int(worst['key']):02d}h no dia mais forte."]
    return "\n".join(lines)


def _freight(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    hubs = repo.breakdown(f, "hub", sort="subsidy", limit=3, min_orders=300)
    lines = [
        f"Frete médio cobrado {fmt.brl(m['fee_avg'])} · custo logístico {fmt.brl(m['cost_avg'])} · "
        f"subsídio {fmt.brl(m['subsidy'])} por entrega.",
    ]
    if hubs:
        lines += ["", "Hubs com maior subsídio:", *_rank_lines(hubs, "subsidy", fmt.brl)]
    return "\n".join(lines)


def _channels(repo: Repository, f: Filters) -> str:
    rows = repo.breakdown(f, "channel", sort="orders", limit=6)
    lines = ["Canais por volume:"]
    for r in rows:
        kind = "próprio" if r["parent"] == "own" else "marketplace"
        lines.append(f"- {r['label']} ({kind}): {fmt.integer(r['orders'])} pedidos · cancelamento {fmt.pct(r['cancel_rate'])} · ticket {fmt.brl(r['ticket'])}")
    return "\n".join(lines)


def _modal(repo: Repository, f: Filters) -> str:
    rows = repo.breakdown(f, "modal", sort="orders", limit=2)
    lines = ["Entregas por modal:"]
    for r in rows:
        lines.append(
            f"- {r['label']}: {fmt.integer(r['delivered'])} entregas · trânsito {fmt.minutes(r['transit_p50'])} "
            f"· distância mediana {fmt.km(r['distance_p50_km'])} · SLA {fmt.pct(r['sla_rate'])}"
        )
    return "\n".join(lines)


def _revenue(repo: Repository, f: Filters) -> str:
    m = repo.metrics(f)
    seg = repo.breakdown(f, "segment", sort="gmv", limit=2)
    lines = [f"GMV {fmt.brl(m['gmv'])} em {fmt.integer(m['delivered'])} entregas · ticket {fmt.brl(m['ticket'])}."]
    lines += [f"- {s['label']}: {fmt.brl(s['gmv'])} · ticket {fmt.brl(s['ticket'])}" for s in seg]
    return "\n".join(lines)


ROUTES = [
    (("alerta", "problema", "risco", "acao", "fazer hoje", "prioridade"), _alerts),
    (("gargalo", "etapa", "preparo", "coleta", "expedicao", "transito"), _stages),
    (("cancel",), _cancel),
    (("frete", "subsid", "custo"), _freight),
    (("pico", "horario", "hora", "jantar", "almoco", "dia da semana"), _peak),
    (("sla", "prazo", "atraso", "demora", "tempo", "ciclo", "lento"), _sla),
    (("canal", "marketplace", "proprio"), _channels),
    (("moto", "bike", "modal", "entregador"), _modal),
    (("loja", "restaurante", "parceiro"), _stores),
    (("hub", "praca", "cidade", "shopping"), _hubs),
    (("gmv", "ticket", "receita", "faturamento", "venda"), _revenue),
    (("resumo", "briefing", "visao geral", "panorama", "como esta"), briefing),
]


def answer(question: str, repo: Repository, f: Filters) -> str:
    if repo.metrics(f)["orders"] == 0:
        return "Nenhum pedido no recorte atual. Afrouxe os filtros para o agente ter o que analisar."
    q = _norm(question)
    for tokens, handler in ROUTES:
        if _has(q, *tokens):
            return handler(repo, f)
    return briefing(repo, f) + "\n\n" + SUGGESTIONS
