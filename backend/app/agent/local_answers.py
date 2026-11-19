"""Respostas do agente local montadas sobre a camada semântica e a consulta estruturada.

Cada função devolve um `Answer` (texto que fecha em **Ação:**, título, consultas usadas e atalhos).
Toda conta sai de `Repository.query_metrics`, `analytics.explain_change` e `analytics.drill_cause`
sobre o recorte recebido; os limiares de amostra e de loja quebrada são os mesmos dos alertas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app import fmt, semantic
from app.agent.local_intent import Entity, Intent, Window
from app.alerts import BROKEN_CANCEL, HUB_MIN, STAGES, STORE_MIN, detect_alerts
from app.analytics import OTHERS_LABEL, drill_cause, explain_change
from app.filters import Filters
from app.repository import (
    CANCEL_ABOVE_FLOOR,
    CANCEL_ABOVE_RATIO,
    MIN_MEASURED,
    SLA_BELOW_GAP,
    VALUE_LABELS,
    Repository,
)
from app.schemas import DrillDown

WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
# Dimensões que viram filtro do painel (atalho "Ver só").
FILTER_KEYS = {"city", "hub", "store", "segment", "channel_type", "modal"}
# Onde dá para cobrar alguém pelo "por que mudou". Hora e dia da semana são sazonalidade.
ACTIONABLE = ("hub", "store", "channel", "city", "channel_type", "segment", "payment_method", "modal")
STAGE_KEYS = tuple(STAGES)
SHORT = {
    "sla_rate": "SLA", "cancel_rate": "cancelamento", "cycle_p50": "ciclo mediano", "cycle_p90": "ciclo p90",
    "orders": "pedidos", "delivered": "entregas", "canceled": "cancelados", "gmv": "GMV", "ticket": "ticket médio",
    "stuck_rate": "pedidos presos", "production_p50": "preparo", "collected_p50": "coleta",
    "expedition_p50": "expedição", "transit_p50": "trânsito", "distance_p50_km": "distância mediana",
    "fee_avg": "frete cobrado", "cost_avg": "custo logístico", "subsidy": "subsídio de frete",
    "chargeback_rate": "chargeback", "multi_attempt_rate": "entregas com mais de uma tentativa",
    "walking_p50": "caminhada no hub", "measured": "entregas medidas",
}


@dataclass
class Answer:
    text: str
    title: str
    tools: list[str]
    drills: list[DrillDown] = field(default_factory=list)


# ------------------------------------------------------------------ formatação


def _layer() -> semantic.SemanticLayer:
    return semantic.load()


def short(metric: str) -> str:
    return SHORT.get(metric, _layer().metrics[metric].label.lower())


def show(metric: str, value: float | None) -> str:
    unit = _layer().metrics[metric].unit
    if unit == "pct":
        return fmt.pct(value, 2) if metric == "chargeback_rate" else fmt.pct(value)
    if unit == "brl":
        return fmt.brl(value)
    if unit == "min":
        return fmt.minutes(value)
    if unit == "km":
        return fmt.km(value)
    return fmt.integer(value)


def show_delta(metric: str, delta: float) -> str:
    """Variação sem sinal (o sentido vai em palavra): p.p. para taxa, unidade da métrica no resto."""
    unit = _layer().metrics[metric].unit
    if unit == "pct":
        return f"{fmt.decimal(abs(delta) * 100, 2 if metric == 'chargeback_rate' else 1)} p.p."
    return show(metric, abs(delta))


def signed(metric: str, delta: float | None) -> str:
    if delta is None:
        return "—"
    shown = show_delta(metric, delta)
    if not any(ch in "123456789" for ch in shown):
        return shown  # arredondou para zero: sem sinal
    return ("+" if delta > 0 else "−") + shown


# Sujeito da frase de variação ("O SLA subiu", "O volume de pedidos caiu").
SUBJECT = {
    "orders": "O volume de pedidos", "delivered": "O número de entregas", "canceled": "O número de cancelados",
    "gmv": "O GMV", "ticket": "O ticket médio", "cancel_rate": "O cancelamento", "sla_rate": "O SLA",
    "cycle_p50": "O ciclo mediano", "cycle_p90": "O ciclo p90", "stuck_rate": "A taxa de pedidos presos",
    "production_p50": "O preparo na loja", "collected_p50": "A coleta", "expedition_p50": "A expedição",
    "transit_p50": "O trânsito", "distance_p50_km": "A distância mediana", "fee_avg": "O frete cobrado",
    "cost_avg": "O custo logístico", "subsidy": "O subsídio de frete", "chargeback_rate": "O chargeback",
    "multi_attempt_rate": "A taxa de entregas com mais de uma tentativa", "walking_p50": "A caminhada no hub",
    "measured": "A base medida",
}


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def on_weekday(index: int) -> str:
    return f"no {WEEKDAYS[index]}" if index >= 5 else f"na {WEEKDAYS[index]}"


def named(word: str, label: str) -> str:
    """'hub' + 'Golden Shopping' -> 'hub Golden Shopping'; sem repetir quando o nome já começa pela palavra."""
    return label if label.lower().startswith(word.lower() + " ") else f"{word} {label}"


def dim_label(dim: str) -> str:
    return _layer().dimensions[dim].label


def value_label(dim: str, key, label) -> str:
    """Rótulo de exibição de uma linha. Hora vira '09h'; código cru ganha o nome em pt-BR."""
    if dim == "hour" and key is not None:
        return f"{int(key):02d}h"
    if dim == "weekday" and key is not None:
        return WEEKDAYS[int(key)]
    text = str(label)
    if dim in ("channel_type", "segment", "modal"):
        return VALUE_LABELS.get(text, text)
    if dim in ("payment_method", "driver_type"):
        pt = _layer().dimensions[dim].values.get(text)
        return f"{text} ({pt})" if pt and pt != text else text
    return text


def describe_dates(start: date, end: date) -> str:
    return f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"


def only_canceled(f: Filters) -> bool:
    return set(f.status) == {"canceled"}


def _measured_based(metric: str) -> bool:
    return _layer().metrics[metric].base in ("measured", "valid")


def drill(dim: str, key, label: str) -> DrillDown | None:
    if dim not in FILTER_KEYS or key is None:
        return None
    value = int(key) if dim in ("hub", "store") else str(key)
    return DrillDown(label=f"Ver só {label}", filters={dim: [value]})


def peak_start(repo: Repository, f: Filters) -> int | None:
    """Primeira hora das 4 de maior volume do recorte (mesma régua dos alertas)."""
    hours = repo.breakdown(f, "hour", sort="orders", limit=24)
    top = sorted(int(h["key"]) for h in hours[:4] if h.get("key") is not None)
    return top[0] if top else None


def _peak_phrase(repo: Repository, f: Filters) -> str:
    start = peak_start(repo, f)
    return f"antes das {start:02d}h" if start is not None else "antes do pico de hoje"


# --------------------------------------------------------------- ações reutilizadas


def broken_store_action(repo: Repository, f: Filters, key, label: str) -> str:
    """Mesma ação do alerta de loja sem entregas (alerts.py); só refaz o texto se o alerta não listou a loja."""
    alert_id = f"cancel-store-{key}"
    alert = next((a for a in detect_alerts(repo, f) if a.id == alert_id), None)
    if alert is not None and "do ar" in alert.action:
        return alert.action
    return (
        f"Tirar {label} do ar hoje: com quase todo pedido cancelado, o problema é cadastro, "
        "integração ou loja fechada recebendo pedido. Reativar só depois de um pedido de teste."
    )


def is_broken(row: dict) -> bool:
    return (row.get("cancel_rate") or 0) >= BROKEN_CANCEL and (row.get("orders") or 0) >= STORE_MIN


def stage_action(repo: Repository, f: Filters, stage: str | None, gap: float | None, *, dim: str, label: str,
                 hub_label: str | None, peak: str) -> str:
    """Quem resolve cada etapa: preparo é a loja, coleta e expedição são o hub, trânsito é a frota."""
    scope = _scope(dim, label, hub_label if dim != "store" else None)
    extra = f" (+{fmt.minutes(gap)} sobre o resto do recorte)" if gap and gap > 0 else ""
    if stage == "production_p50":
        if dim == "store":
            return (f"Gerente de contas deve alinhar hoje com a loja {label} o tempo de preparo informado{extra} "
                    f"e a pausa de cardápio {peak}.")
        return (f"Gerente de contas deve ligar hoje para as lojas de preparo mais lento {scope}{extra} e revisar "
                f"o tempo de preparo informado {peak}.")
    if stage in ("collected_p50", "expedition_p50"):
        if hub_label:
            where = f" na loja {label}" if dim == "store" else ""
            return (f"Líder do hub {hub_label} deve revisar hoje a fila de {STAGES[stage]}{where} e o posicionamento "
                    f"de entregadores{extra}, {peak}.")
        return (f"Líder de operações deve revisar hoje a fila de {STAGES[stage]} e o posicionamento de entregadores "
                f"{scope}{extra}, {peak}.")
    if stage == "transit_p50":
        target = f"no hub {hub_label}" if hub_label else scope
        return f"Time de frota deve reforçar motos {target} {peak} ou reduzir o raio de entrega{extra}."
    return f"{owner_for(dim, label)} deve revisar hoje a escala de entregadores e o tempo de preparo informado {peak}."


def plain_label(dim: str, label: str) -> str:
    """Nome pt-BR sem o código cru, para frase de ação ("operador logístico", não "operator")."""
    if dim in ("payment_method", "driver_type"):
        return _layer().dimensions[dim].values.get(label, label)
    return label


def owner_for(dim: str, label: str, metric: str | None = None) -> str:
    if dim in ("hour", "weekday") and metric in ("cancel_rate", "canceled", "chargeback_rate", "subsidy", "ticket"):
        return "Líder de operações"
    label = plain_label(dim, label)
    return {
        "hub": f"Líder do {named('hub', label)}",
        "store": f"Gerente de contas da {named('loja', label)}",
        "city": f"Líder de operações de {label}",
        "channel": f"Time comercial, com o parceiro do canal {label},",
        "channel_type": f"Time comercial do {label}",
        "segment": f"Time comercial do segmento {label}",
        "modal": f"Time de frota do modal {label}",
        "driver_type": f"Time de frota, com os entregadores {label},",
        "payment_method": f"Time de pagamentos, no {label},",
        "hour": "Time de frota",
        "weekday": "Time de frota",
    }.get(dim, "Time de operações")


def metric_verb(metric: str, value: str, low: bool = False) -> str:
    if metric in ("orders", "gmv", "delivered") and low:
        return f"checar lojas fechadas ou pausadas e a cobertura de entregadores ({short(metric)}: {value})"
    if metric == "ticket":
        return f"revisar pedido mínimo e combos com as lojas ({short(metric)} de {value})"
    if metric == "sla_rate":
        return f"atacar os atrasos para recuperar o SLA ({value} no prazo)"
    if metric in ("cancel_rate", "canceled"):
        return f"apurar os cancelamentos ({value}): ruptura de itens e loja fechada com cardápio aberto"
    if metric == "stuck_rate":
        return f"conferir a baixa manual dos pedidos presos ({value}) antes de cobrar SLA"
    if metric in ("subsidy", "cost_avg", "fee_avg"):
        return f"revisar frete mínimo e raio de entrega ({short(metric)} em {value})"
    if metric in ("orders", "gmv", "delivered", "ticket"):
        return f"dimensionar entregadores e lojas abertas para a demanda ({short(metric)}: {value})"
    if metric == "chargeback_rate":
        return f"acionar o antifraude para os pagamentos contestados ({value})"
    if metric == "multi_attempt_rate":
        return f"revisar endereço e contato com o cliente antes da saída ({value})"
    if metric == "distance_p50_km":
        return f"revisar o raio de entrega ({value} de distância mediana)"
    return f"reduzir o tempo de {short(metric)} ({value})"


def _when(dim: str, key) -> str:
    if dim == "hour" and key is not None:
        return f"30 min antes das {int(key):02d}h"
    if dim == "weekday" and key is not None:
        return f"na próxima {WEEKDAYS[int(key)]}" if int(key) < 5 else f"no próximo {WEEKDAYS[int(key)]}"
    return "hoje"


def _scope(dim: str, label: str, hub_label: str | None) -> str:
    if hub_label:
        return f"no {named('hub', hub_label)}"
    if dim == "store":
        return f"na {named('loja', label)}"
    if dim == "hour":
        return f"na faixa das {label}"
    if dim == "weekday":
        return on_weekday(WEEKDAYS.index(label)) if label in WEEKDAYS else f"em {label}"
    return f"em {label}"


def _data_labels(repo: Repository) -> frozenset[str]:
    def build() -> frozenset[str]:
        meta = repo.meta()
        return frozenset(str(o["label"]) for key in ("hubs", "stores", "cities") for o in meta[key] if o["label"])

    return repo.cached("local:labels", build)


_HOUR_IN_TEXT = re.compile(r"(?<!\d)\d{1,2}h(?![a-z])")


def lead_alert(repo: Repository, alerts: list):
    """Alerta que fecha a resposta: na severidade mais alta, o que aponta uma entidade (tem atalho);
    senão o primeiro cuja ação nomeia hub, loja, cidade ou horário; senão o primeiro."""
    top = [a for a in alerts if a.severity == alerts[0].severity]
    pointed = next((a for a in top if a.drilldown), None)
    if pointed is not None:
        return pointed
    labels = _data_labels(repo)
    for alert in alerts:
        if alert.drilldown or _HOUR_IN_TEXT.search(alert.action) or any(label in alert.action for label in labels):
            return alert
    return alerts[0]


# ----------------------------------------------------------------- fora do escopo

_OOS_TEXT = {
    "motivo": "O dataset não registra o motivo do cancelamento: cada pedido traz só o status (concluído ou cancelado).",
    "cardapio": "O dataset não traz itens do pedido nem cardápio: só o valor total de cada pedido.",
    "avaliacao": "O dataset não tem avaliação, nota ou NPS de cliente.",
    "clima": "O dataset não registra clima nem chuva por dia ou por praça.",
    "entregador": ("O dataset não identifica o entregador individual: só o modal (moto ou bike) e o vínculo "
                   "(freelancer ou operador logístico)."),
    "reclamacao": "O dataset não registra reclamações nem contatos de atendimento.",
}


def out_of_scope(repo: Repository, f: Filters, topic: str) -> Answer:
    lead = _OOS_TEXT[topic]
    if topic == "motivo":
        body, action, tools, drills = _oos_cancel(repo, f)
    elif topic == "cardapio":
        body, action, tools, drills = _oos_menu(repo, f)
    elif topic == "clima":
        body, action, tools, drills = _oos_weather(repo, f)
    elif topic == "entregador":
        body, action, tools, drills = _oos_courier(repo, f)
    else:
        body, action, tools, drills = _oos_experience(repo, f)
    text = f"{lead} Não dá para responder isso sem inventar número.\n\n{body}\n\n**Ação:** {action}"
    return Answer(text, "Fora do que o dataset registra", tools, drills)


def _oos_cancel(repo: Repository, f: Filters):
    m = repo.metrics(f)
    lines = [(f"O mais perto disso no recorte: cancelamento de {fmt.pct(m['cancel_rate'])} "
              f"({fmt.integer(m['canceled'])} pedidos).")]
    modal = {r["key"]: r for r in repo.breakdown(f, "modal", sort="orders", limit=10)}
    if None in modal and m["canceled"]:
        share = (modal[None]["canceled"] or 0) / m["canceled"]
        lines.append(f"- {fmt.pct(share)} dos cancelados caíram antes de alocar entregador (sem modal registrado).")
    stores = [s for s in repo.breakdown(f, "store", sort="cancel_rate", limit=3, min_orders=STORE_MIN) if s["key"] is not None]
    for s in stores:
        lines.append(f"- Loja {s['label']} ({s['parent']}): {fmt.pct(s['cancel_rate'])} de cancelamento em "
                     f"{fmt.integer(s['orders'])} pedidos")
    if stores and is_broken(stores[0]):
        action = broken_store_action(repo, f, stores[0]["key"], stores[0]["label"])
    elif stores:
        s = stores[0]
        action = (f"Gerente de contas deve ligar hoje para a loja {s['label']} ({fmt.pct(s['cancel_rate'])}) e perguntar "
                  f"a causa: ruptura de itens ou loja fechada com cardápio aberto.")
    else:
        action = "Gerente de contas deve ligar hoje para as lojas com mais cancelamentos e registrar a causa de cada um."
    drills = [d for d in (drill("store", s["key"], s["label"]) for s in stores[:1]) if d]
    return "\n".join(lines), action, ["get_kpis", "get_breakdown(store)", "get_breakdown(modal)"], drills


def _oos_menu(repo: Repository, f: Filters):
    stores = [s for s in repo.breakdown(f, "store", sort="gmv", limit=3) if s["key"] is not None]
    lines = ["O mais perto disso no recorte: lojas por GMV e ticket médio."]
    lines += [f"- {s['label']} ({s['parent']}): GMV {fmt.brl(s['gmv'])} · ticket {fmt.brl(s['ticket'])} · "
              f"{fmt.integer(s['orders'])} pedidos" for s in stores]
    if stores:
        s = stores[0]
        action = (f"Time comercial deve pedir hoje à loja {s['label']} (maior GMV do recorte) o relatório de vendas "
                  f"por item, que não chega a este painel.")
    else:
        action = "Time comercial deve pedir às lojas o relatório de vendas por item, que não chega a este painel."
    drills = [d for d in (drill("store", s["key"], s["label"]) for s in stores[:1]) if d]
    return "\n".join(lines), action, ["get_breakdown(store)"], drills


def _reliable_hubs(repo: Repository, f: Filters) -> list[dict]:
    return [h for h in repo.breakdown(f, "hub", sort="sla_rate", desc=False, limit=50, min_orders=HUB_MIN,
                                      min_measured=MIN_MEASURED) if h["sla_rate"] is not None]


def _oos_experience(repo: Repository, f: Filters):
    m = repo.metrics(f)
    lines = [(f"O mais perto da experiência do cliente no recorte: SLA {fmt.pct(m['sla_rate'])} no prazo e "
              f"cancelamento {fmt.pct(m['cancel_rate'])}.")]
    hubs = _reliable_hubs(repo, f)
    for h in hubs[:3]:
        lines.append(f"- Hub {h['label']}: SLA {fmt.pct(h['sla_rate'])} · cancelamento {fmt.pct(h['cancel_rate'])}")
    if hubs:
        h = hubs[0]
        action = (f"Líder do hub {h['label']} deve atacar hoje os atrasos (SLA {fmt.pct(h['sla_rate'])}), o indicador "
                  "deste dataset mais ligado à satisfação do cliente.")
    else:
        action = "Time de operações deve acompanhar SLA e cancelamento do recorte como sinal da experiência do cliente."
    drills = [d for d in (drill("hub", h["key"], h["label"]) for h in hubs[:1]) if d]
    return "\n".join(lines), action, ["get_kpis", "get_breakdown(hub)"], drills


def _oos_weather(repo: Repository, f: Filters):
    days = [d for d in repo.timeseries(f, "day") if d["sla_rate"] is not None and d["orders"] >= MIN_MEASURED]
    days.sort(key=lambda d: d["sla_rate"])
    m = repo.metrics(f)
    lines = [f"O mais perto disso: os dias de pior SLA do recorte (SLA médio {fmt.pct(m['sla_rate'])})."]
    for d in days[:3]:
        day = d["t"].date() if hasattr(d["t"], "date") else d["t"]
        lines.append(f"- {day:%d/%m} ({WEEKDAYS[day.weekday()]}): SLA {fmt.pct(d['sla_rate'])} · "
                     f"{fmt.integer(d['orders'])} pedidos")
    peak = _peak_phrase(repo, f)
    if days:
        day = days[0]["t"].date() if hasattr(days[0]["t"], "date") else days[0]["t"]
        action = (f"Time de frota deve cruzar o dia {day:%d/%m} ({WEEKDAYS[day.weekday()]}, pior SLA) com o histórico "
                  f"de chuva da praça e, quando houver previsão de chuva, reforçar motos {peak}.")
    else:
        action = f"Time de frota deve reforçar motos {peak} quando houver previsão de chuva na praça."
    return "\n".join(lines), action, ["get_timeseries", "get_kpis"], []


def _oos_courier(repo: Repository, f: Filters):
    lines = ["O mais perto disso no recorte: entregas por modal e por vínculo do entregador."]
    worst = None
    for dim in ("modal", "driver_type"):
        for r in repo.breakdown(f, dim, sort="orders", limit=5, min_measured=MIN_MEASURED):
            if r["key"] is None or r["sla_rate"] is None:
                continue
            shown = value_label(dim, r["key"], r["label"])
            plain = plain_label(dim, str(r["label"]))
            lines.append(f"- {shown}: SLA {fmt.pct(r['sla_rate'])} · trânsito {fmt.minutes(r['transit_p50'])} · "
                         f"{fmt.integer(r['delivered'])} entregas")
            if worst is None or r["sla_rate"] < worst[2]["sla_rate"]:
                worst = (dim, plain, r)
    if worst:
        dim, shown, r = worst
        action = (f"Time de frota deve revisar hoje a escala e o raio dos entregadores {shown} (SLA "
                  f"{fmt.pct(r['sla_rate'])}), o grupo de pior prazo do recorte.")
    else:
        action = "Time de frota deve pedir ao operador logístico o relatório por entregador, que não chega a este painel."
    return "\n".join(lines), action, ["get_breakdown(modal)", "get_breakdown(driver_type)"], []


# ------------------------------------------------------------------ chargeback


def chargeback(repo: Repository, f: Filters, dim: str | None = None, intent: Intent | None = None) -> Answer:
    if dim and dim != "payment_method":
        return by_dimension(repo, f, "chargeback_rate", dim, intent)
    total = repo.query_metrics(f, metrics=["chargeback_rate"])["total"]
    rate = total["chargeback_rate"] or 0.0
    n = round(rate * total["orders"])
    head = (f"Chargeback no recorte: {fmt.pct(rate, 2)} dos pedidos ({fmt.integer(n)} pedidos com pagamento "
            f"contestado em {fmt.integer(total['orders'])}). O dataset traz só a marca de chargeback por pedido: "
            "não há valor contestado nem motivo.")
    if n == 0:
        text = (f"{head}\n\nNenhum pedido com chargeback neste recorte.\n\n**Ação:** Time financeiro deve manter o "
                "acompanhamento semanal de chargeback por forma de pagamento.")
        return Answer(text, "Chargeback do recorte", ["query_metrics(chargeback_rate)"])
    qm = repo.query_metrics(f, metrics=["chargeback_rate"], group_by=["payment_method"], sort="chargeback_rate", limit=20)
    rows = [r for r in qm["rows"] if r["keys"]["payment_method"]["key"] is not None and (r["chargeback_rate"] or 0) > 0]
    rows.sort(key=lambda r: -(r["chargeback_rate"] or 0) * r["orders"])
    lines = [head, "", "Onde se concentra (forma de pagamento):"]
    for r in rows[:4]:
        k = r["keys"]["payment_method"]
        count = round((r["chargeback_rate"] or 0) * r["orders"])
        lines.append(f"- {value_label('payment_method', k['key'], k['label'])}: {fmt.pct(r['chargeback_rate'], 2)} "
                     f"com pagamento contestado ({fmt.integer(count)} de {fmt.integer(r['orders'])} pedidos)")
    if n < 30:
        lines.append(f"Evento raro: {fmt.integer(n)} casos não sustentam cobrança de ninguém.")
    if rows:
        k = rows[0]["keys"]["payment_method"]
        count = round((rows[0]["chargeback_rate"] or 0) * rows[0]["orders"])
        share = count / n if n else 0
        action = (f"Time financeiro e antifraude devem revisar hoje os pedidos pagos com "
                  f"{value_label('payment_method', k['key'], k['label'])}, que concentram {fmt.pct(share, 0)} dos "
                  "pagamentos contestados.")
    else:
        action = "Time financeiro deve revisar hoje os pedidos contestados do recorte com o antifraude."
    lines += ["", f"**Ação:** {action}"]
    return Answer("\n".join(lines), "Chargeback do recorte", ["query_metrics(chargeback_rate)", "query_metrics(chargeback_rate:payment_method)"])


# ------------------------------------------------------------- métrica × dimensão


def _thresholds(metric: str, dim: str) -> tuple[int, int]:
    kind = _layer().metrics[metric].kind
    if kind in ("count", "sum"):
        return 0, 0
    min_orders = {"hub": HUB_MIN, "store": STORE_MIN}.get(dim, MIN_MEASURED)
    return (min_orders, MIN_MEASURED) if _measured_based(metric) else (min_orders, 0)


def _worst_first(metric: str, intent: Intent | None) -> bool:
    """desc? Contagem: maior primeiro (salvo "menos"). Taxa e tempo: o pior primeiro (salvo "melhor")."""
    m = _layer().metrics[metric]
    if m.kind in ("count", "sum"):
        return not (intent and intent.low)
    worst_desc = m.better != "up"
    return (not worst_desc) if (intent and intent.best) else worst_desc


def _cause_line(repo: Repository, f: Filters, metric: str, dim: str, key, label: str) -> tuple[str | None, str | None, float | None]:
    """Etapa que explica o SLA/ciclo de um grupo contra o resto do recorte."""
    if metric not in ("sla_rate", "cycle_p50", "cycle_p90", *STAGE_KEYS):
        return None, None, None
    target = "sla_rate" if metric == "sla_rate" else "cycle_p50"
    cause = drill_cause(repo, f, metric=target, group={dim: [key]})
    stage = cause["top_stage_vs_rest"] if cause["group"] else None
    if metric in STAGE_KEYS:
        stage = metric
    row = next((s for s in cause["stages"] if s["metric"] == stage), None)
    if not row or row["current"] is None:
        return None, stage, None
    gap = row["vs_rest"]
    tail = f" (+{fmt.minutes(gap)} sobre o resto do recorte)" if gap is not None and gap > 0 else ""
    return f"Em {label}, a etapa que mais pesa é {STAGES[stage]}: {fmt.minutes(row['current'])}{tail}.", stage, gap


def _hub_of_store(repo: Repository, key) -> str | None:
    meta = repo.meta()
    hub_id = next((o["parent"] for o in meta["stores"] if o["value"] == key), None)
    return next((o["label"] for o in meta["hubs"] if o["value"] == hub_id), None)


def _cancel_group_action(repo: Repository, f: Filters, dim: str, key, label: str, value: str) -> str:
    """Cancelamento alto num grupo (cidade, hub, hora...): a ação desce para a loja que mais cancela nele."""
    qm = repo.query_metrics(f, metrics=["cancel_rate"], group_by=["store"], where={dim: [key]}, sort="cancel_rate",
                            limit=1, min_orders=STORE_MIN)
    row = next((r for r in qm["rows"] if r["keys"]["store"]["key"] is not None and r["cancel_rate"]), None)
    if row is None:
        return f"{owner_for(dim, label, 'cancel_rate')} deve {metric_verb('cancel_rate', value)} {_when(dim, key)}."
    store_key, store = row["keys"]["store"]["key"], row["keys"]["store"]["label"]
    if is_broken(row):
        return broken_store_action(repo, f, store_key, store)
    return (f"{owner_for(dim, label, 'cancel_rate')} deve apurar os cancelamentos ({value}) {_when(dim, key)}, começando pela loja "
            f"{store} ({fmt.pct(row['cancel_rate'])}): ruptura de itens e loja fechada com cardápio aberto.")


def by_dimension(repo: Repository, f: Filters, metric: str, dim: str, intent: Intent | None = None) -> Answer:
    """Qualquer métrica do glossário quebrada por qualquer dimensão, com amostra mínima e ação no topo."""
    title = f"{cap(short(metric))} por {dim_label(dim).lower()}"
    tools = ["get_kpis", f"query_metrics({metric}:{dim})"]
    if only_canceled(f) and _measured_based(metric):
        m = repo.metrics(f)
        text = (f"O recorte filtra só pedidos cancelados ({fmt.integer(m['canceled'])}), sem entregas para medir "
                f"{short(metric)}.\n\n**Ação:** Operador deve remover o filtro de status cancelado para comparar "
                f"{short(metric)} por {dim_label(dim).lower()}.")
        return Answer(text, title, tools)
    desc = _worst_first(metric, intent)
    min_orders, min_measured = _thresholds(metric, dim)
    qm = repo.query_metrics(f, metrics=[metric], group_by=[dim], sort=metric, desc=desc, limit=15,
                            min_orders=min_orders, min_measured=min_measured)
    note = ""
    rows = [r for r in qm["rows"] if r[metric] is not None]
    if not [r for r in rows if r["keys"][dim]["key"] is not None] and (min_orders or min_measured):
        qm = repo.query_metrics(f, metrics=[metric], group_by=[dim], sort=metric, desc=desc, limit=15)
        rows = [r for r in qm["rows"] if r[metric] is not None]
        note = (f" Nenhum grupo chega a {fmt.integer(min_orders or min_measured)} pedidos: leitura de amostra pequena.")
    named = [r for r in rows if r["keys"][dim]["key"] is not None]
    nulls = [r for r in rows if r["keys"][dim]["key"] is None]
    total = qm["total"][metric]
    floor = ""
    if min_orders or min_measured:
        floor = f" (mín. {fmt.integer(min_measured or min_orders)} {'entregas medidas' if min_measured else 'pedidos'})"
    lines = [f"{title} no recorte{floor}: recorte em {show(metric, total)}.{note}"]
    for r in named[:5]:
        k = r["keys"][dim]
        tail = f" · {fmt.integer(r['measured'])} medidas" if _measured_based(metric) else ""
        volume = "" if metric == "orders" else f" · {fmt.integer(r['orders'])} pedidos"
        lines.append(f"- {_row_label(repo, dim, k)}: {show(metric, r[metric])}{volume}{tail}")
    if nulls:
        k = nulls[0]["keys"][dim]
        lines.append(f"Fora do ranking: {k['label']} ({fmt.integer(nulls[0]['orders'])} pedidos sem {dim_label(dim).lower()} "
                     "registrado), que não é alguém para acionar.")
    if not named:
        lines += ["", (f"**Ação:** Operador deve ampliar o período para comparar {short(metric)} por "
                       f"{dim_label(dim).lower()} com base suficiente.")]
        return Answer("\n".join(lines), title, tools)

    lead = named[0]
    key, raw_label = lead["keys"][dim]["key"], lead["keys"][dim]["label"]
    label = value_label(dim, key, raw_label)
    best = bool(intent and intent.best)
    cause, stage, gap = (None, None, None) if best else _cause_line(repo, f, metric, dim, key, label)
    if cause:
        lines += ["", cause]
    value = show(metric, lead[metric])
    if cause:
        tools.append(f"drill_cause({'sla_rate' if metric == 'sla_rate' else 'cycle_p50'})")
    if best:
        # Pergunta pelo melhor: a ação é levar a rotina dele para quem está pior, não "corrigir" o melhor.
        action = (f"{owner_for(dim, raw_label, metric)} deve registrar hoje a rotina que sustenta {short(metric)} de "
                  f"{value} para o time de operações levar aos grupos de pior resultado.")
    elif metric in ("cancel_rate", "canceled") and dim == "store" and is_broken(lead):
        action = broken_store_action(repo, f, key, raw_label)
    elif metric in ("cancel_rate", "canceled") and dim != "store":
        action = _cancel_group_action(repo, f, dim, key, label, value)
    elif stage and metric in ("sla_rate", "cycle_p50", "cycle_p90", *STAGE_KEYS):
        hub_label = raw_label if dim == "hub" else (_hub_of_store(repo, key) if dim == "store" else None)
        when = "a partir de hoje" if dim in ("hour", "weekday") else _peak_phrase(repo, f)
        action = stage_action(repo, f, stage, gap, dim=dim, label=label, hub_label=hub_label, peak=when)
    else:
        low = bool(intent and intent.low)
        action = f"{owner_for(dim, raw_label, metric)} deve {metric_verb(metric, value, low)} {_when(dim, key)}."
    lines += ["", f"**Ação:** {action}"]
    drills = [d for d in (drill(dim, key, label),) if d]
    return Answer("\n".join(lines), title, tools, drills)


# ------------------------------------------------------------------ entidade


def narrow(f: Filters, entity: Entity) -> Filters | None:
    """Recorte restrito à entidade, sem sair do recorte: se o filtro já exclui a entidade, None."""
    current = list(getattr(f, entity.dimension))
    wanted = list(entity.ids)
    if current:
        keep = [v for v in wanted if v in current]
        if not keep:
            return None
    else:
        keep = wanted
    return f.model_copy(update={entity.dimension: keep[:50]})


_KIND = {"hub": "Hub", "store": "Loja", "city": "Cidade"}


def _parent(repo: Repository, entity: Entity) -> str | None:
    meta = repo.meta()
    if entity.dimension == "hub":
        return next((str(o["parent"]) for o in meta["hubs"] if o["value"] in entity.ids), None)
    if entity.dimension == "city":
        return next((str(o["parent"]) for o in meta["cities"] if o["value"] in entity.ids), None)
    hubs = {o["value"]: o["label"] for o in meta["hubs"]}
    names = sorted({hubs.get(o["parent"]) for o in meta["stores"] if o["value"] in entity.ids} - {None})
    if not names:
        return None
    return f"hub {names[0]}" if len(names) == 1 else f"{len(names)} hubs"


def _kpi_line(label: str, m: dict) -> str:
    return (f"- {label}: {fmt.integer(m['orders'])} pedidos · SLA {fmt.pct(m['sla_rate'])} · cancelamento "
            f"{fmt.pct(m['cancel_rate'])} · ciclo mediano {fmt.minutes(m['cycle_p50'])} · GMV {fmt.brl(m['gmv'])}")


def entity_answer(repo: Repository, f: Filters, intent: Intent) -> Answer:
    entity = intent.entity
    assert entity is not None
    kind = _KIND[entity.dimension]
    title = named(kind, entity.label)[:80]
    tools = ["get_kpis", "drill_cause(sla_rate)"]
    fe = narrow(f, entity)
    me = repo.metrics(fe) if fe is not None else None
    if fe is None or not me["orders"]:
        text = (f"{title} não tem pedidos no recorte atual ({repo.describe(f)}).\n\n"
                f"**Ação:** Operador deve ajustar os filtros do recorte para incluir {entity.label} antes de avaliar.")
        return Answer(text, title, tools)
    m = repo.metrics(f)
    same = fe.cache_key() == f.cache_key()
    parent = _parent(repo, entity)
    lines = [f"**{named(kind, entity.label)}**" + (f" ({parent})" if parent else "") + f" no recorte ({repo.describe(f)}):",
             _kpi_line(entity.label, me)]
    if not same:
        lines.append(f"- Recorte inteiro: SLA {fmt.pct(m['sla_rate'])} · cancelamento {fmt.pct(m['cancel_rate'])} · "
                     f"ciclo mediano {fmt.minutes(m['cycle_p50'])}")
    group = {entity.dimension: list(entity.ids)[:50]}
    units: list[dict] = []
    if entity.dimension == "store" and len(entity.ids) > 1:
        tools.append("query_metrics(sla_rate,cancel_rate,gmv:store)")
        qm = repo.query_metrics(fe, metrics=["sla_rate", "cancel_rate", "gmv", "cycle_p50"], group_by=["store"],
                                sort="orders", limit=5)
        units = qm["rows"]
        lines.append(f"{entity.label} tem {fmt.integer(len(entity.ids))} unidades com esse nome; as maiores no recorte:")
        for r in units[:3]:
            key = r["keys"]["store"]["key"]
            hub = _hub_of_store(repo, key)
            lines.append(f"- {entity.label} (loja {key}{', hub ' + hub if hub else ''}): {fmt.integer(r['orders'])} pedidos · "
                         f"SLA {fmt.pct(r['sla_rate'])} · cancelamento {fmt.pct(r['cancel_rate'])} · GMV {fmt.brl(r['gmv'])}")

    cause = drill_cause(repo, f, metric="sla_rate", group=group)
    # Entidade = recorte inteiro: o resto fica vazio e a referência passa a ser o período anterior.
    ref = "vs_rest" if (cause["sample"]["rest"] or {}).get("orders") else "vs_previous"
    ref_text = "o resto do recorte" if ref == "vs_rest" else "o período anterior"
    ref_of = "do resto do recorte" if ref == "vs_rest" else "do período anterior"
    stages = [s for s in cause["stages"] if s["current"] is not None]
    has_ref = any(s[ref] is not None for s in stages)
    if stages:
        parts = [f"{STAGES[s['metric']]} {fmt.minutes(s['current'])}"
                 + (f" ({signed('production_p50', s[ref])})" if s[ref] is not None else "") for s in stages]
        tail = f" (diferença contra {ref_text})" if has_ref else ""
        lines.append(f"- Etapas em {entity.label}{tail}: " + " · ".join(parts))
    stage = cause["top_stage_vs_rest"] if ref == "vs_rest" else cause["top_stage_vs_previous"]
    gap = next((s[ref] for s in stages if s["metric"] == stage), None)

    focus = intent.metric
    focus_row = None
    if focus and focus not in ("sla_rate", "cancel_rate", "cycle_p50", "orders", "gmv", *STAGE_KEYS) and not same:
        qf = repo.query_metrics(f, metrics=[focus], where=group, compare="rest")
        focus_row = (qf["total"][focus], (qf["total_compare"] or {}).get(focus))
        lines.append(f"- {cap(short(focus))}: {show(focus, focus_row[0])} em {entity.label} contra "
                     f"{show(focus, focus_row[1])} no resto do recorte")

    # Leitura e ação: loja quebrada > cancelamento fora da curva > SLA abaixo (pela etapa) > acompanhamento.
    base_sla = cause["headline"]["rest"] if ref == "vs_rest" else cause["headline"]["previous"]
    base_cancel = m["cancel_rate"]
    if not same:
        rest = repo.query_metrics(f, metrics=["cancel_rate"], where=group, compare="rest")["total_compare"] or {}
        base_cancel = rest.get("cancel_rate")
    sla, cancel = me["sla_rate"], me["cancel_rate"] or 0.0
    # Mesma régua dos alertas: sem entrega nenhuma ou com 90%+ cancelado, a taxa já é o problema, não a amostra.
    thin = bool(me["low_sample"]) and me["delivered"] != 0 and cancel < BROKEN_CANCEL
    peak = _peak_phrase(repo, fe)
    hub_label = entity.label if entity.dimension == "hub" else None
    if entity.dimension == "store" and len(entity.ids) == 1:
        hub_label = _hub_of_store(repo, entity.ids[0])
    findings: list[str] = []
    cancel_hot = (me["orders"] >= MIN_MEASURED and cancel >= CANCEL_ABOVE_FLOOR
                  and (base_cancel is None or cancel > base_cancel * CANCEL_ABOVE_RATIO))
    sla_low = (not thin and sla is not None and base_sla is not None and sla < base_sla - SLA_BELOW_GAP)
    broken = entity.dimension == "store" and is_broken(me)
    if broken:
        findings.append(f"{fmt.pct(cancel)} dos pedidos cancelados: loja quebrada")
        action = broken_store_action(repo, f, entity.ids[0], entity.label)
    elif cancel_hot:
        findings.append(f"cancelamento de {fmt.pct(cancel)}, fora da curva (resto do recorte em {fmt.pct(base_cancel)})")
        if entity.dimension == "store":
            action = (f"Gerente de contas deve ligar hoje para a loja {entity.label}: checar ruptura de itens e loja "
                      f"fechada com cardápio aberto ({fmt.pct(cancel)} de cancelamento) {peak}.")
        else:
            stores = [s for s in repo.breakdown(fe, "store", sort="cancel_rate", limit=1, min_orders=STORE_MIN)
                      if s["key"] is not None]
            first = f", começando pela loja {stores[0]['label']} ({fmt.pct(stores[0]['cancel_rate'])})" if stores else ""
            action = (f"{owner_for(entity.dimension, entity.label)} deve abrir as lojas por cancelamento e ligar hoje "
                      f"para as primeiras{first}.")
    elif sla_low or (intent.metric in ("cycle_p50", *STAGE_KEYS) or "etapas_ciclo" in intent.concepts) and stage:
        if sla_low:
            findings.append(f"SLA {fmt.decimal((base_sla - sla) * 100, 1)} p.p. abaixo {ref_of}")
        if stage:
            findings.append(f"a etapa que mais pesa é {STAGES[stage]}"
                            + (f" (+{fmt.minutes(gap)})" if gap and gap > 0 else ""))
        action = stage_action(repo, fe, stage, gap, dim=entity.dimension, label=entity.label,
                              hub_label=hub_label, peak=peak)
    else:
        if has_ref:
            findings.append(f"sem desvio forte contra {ref_text} (SLA {fmt.pct(sla)}, cancelamento {fmt.pct(cancel)})")
        else:
            findings.append(f"sem referência para comparar: o recorte já é só {entity.label} e não há período anterior")
        if stage:
            findings.append(f"a etapa mais acima {ref_of} é {STAGES[stage]}"
                            + (f" (+{fmt.minutes(gap)})" if gap and gap > 0 else ""))
            action = (f"{owner_for(entity.dimension, entity.label)} deve acompanhar a etapa de {STAGES[stage]} {peak}"
                      + (f" ({fmt.minutes(gap)} acima {ref_of})" if gap and gap > 0 else "")
                      + ", antes que vire atraso.")
        else:
            action = (f"{owner_for(entity.dimension, entity.label)} deve manter a escala e o acompanhamento do pico "
                      f"{peak}: SLA {fmt.pct(sla)} e cancelamento {fmt.pct(cancel)} dentro do recorte.")
    if focus_row and focus_row[0] is not None and focus_row[1] is not None and not (broken or cancel_hot):
        # Pergunta sobre outra métrica (subsídio, ticket, presos...): a ação responde a ela, salvo loja
        # quebrada ou cancelamento fora da curva, que vêm antes.
        value, rest_value = focus_row
        better = _layer().metrics[focus].better
        worse = value > rest_value if better != "up" else value < rest_value
        owner = owner_for(entity.dimension, entity.label)
        if worse:
            findings.insert(0, f"{short(focus)} pior que o resto do recorte ({show(focus, value)} contra "
                               f"{show(focus, rest_value)})")
            action = f"{owner} deve {metric_verb(focus, show(focus, value))} hoje."
        else:
            findings.insert(0, f"{short(focus)} melhor que o resto do recorte ({show(focus, value)} contra "
                               f"{show(focus, rest_value)})")
            action = (f"{owner} deve manter a rotina atual de {short(focus)} ({show(focus, value)} contra "
                      f"{show(focus, rest_value)} no resto do recorte) e acompanhar {peak} o SLA ({fmt.pct(sla)}).")
    if same and not stage and not cancel_hot and not broken:
        # O recorte já é a entidade e não há período anterior: a referência que resta são os alertas dela.
        alerts = detect_alerts(repo, f)
        if alerts:
            lead = lead_alert(repo, alerts)
            findings.append(f"alerta mais urgente: {lead.title}")
            action = lead.action
    if thin:
        findings.append(f"amostra pequena ({fmt.integer(me['measured'])} entregas medidas)")
        action = (f"Operador deve ampliar o período antes de cobrar {entity.label}: só "
                  f"{fmt.integer(me['measured'])} entregas medidas neste recorte.")
    lines += ["", "Leitura: " + "; ".join(findings) + ".", "", f"**Ação:** {action}"]
    drills = []
    if not same:
        drills.append(DrillDown(label=f"Ver só {entity.label}"[:80], filters={entity.dimension: list(entity.ids)[:50]}))
    return Answer("\n".join(lines), title, tools, drills)


# ------------------------------------------------------------- por que mudou


def _change_dims(metric: str, intent: Intent, f: Filters) -> list[str]:
    layer = _layer()
    pinned = {d for d in ("hub", "store", "city", "segment", "channel_type", "modal") if len(getattr(f, d)) == 1}
    asked = [d for d in intent.dimensions if d not in pinned]
    link = layer.causal.get(metric)
    causal = list(link.dimensions) if link else ["hub", "store"]
    out: list[str] = []
    for d in [*asked, *causal, "hub", "store"]:
        if d in out or d in pinned or d not in ACTIONABLE:
            continue
        # Cancelamento por modal é seleção (cancela antes de alocar entregador), não causa.
        if metric in ("cancel_rate", "canceled") and d == "modal":
            continue
        out.append(d)
    return out[: max(2, len(asked))]


def _windowed(repo: Repository, f: Filters, intent: Intent) -> tuple[Filters, str, bool]:
    """Recorte atual da comparação: a última semana se a pergunta pede; senão o recorte inteiro."""
    start, end = repo.period(f)
    end = min(end, repo.max_date)
    start = max(start, repo.min_date)
    weekly = intent.week and not intent.previous
    fallback = False
    if not weekly and repo.previous_period(f) is None and (end - start).days >= 13:
        weekly, fallback = True, True
    if weekly and (end - start).days >= 6:
        return f.with_period(end - timedelta(days=6), end), "semana", fallback
    return f, "período", False


def moved(metric: str, previous: float | None, current: float | None) -> str:
    before = show(metric, previous) if previous is not None else "sem base antes"
    after = show(metric, current) if current is not None else "sem base agora"
    return f"{before} → {after}"


def _row_label(repo: Repository, dim: str, row: dict) -> str:
    """Loja homônima aparece em vários hubs: o hub entra no rótulo."""
    label = value_label(dim, row["key"], row["label"])
    if dim == "store":
        hub = _hub_of_store(repo, row["key"])
        return f"{label} ({hub})" if hub else label
    return label


def _contribution_text(metric: str, method: str, d: dict) -> str:
    if method == "shift_share":
        effect = "efeito taxa" if abs(d["rate_effect"] or 0) >= abs(d["mix_effect"] or 0) else "efeito mix (mudou o peso)"
        share = f"; {fmt.pct(abs(d['share_of_change']), 0)} da variação" if d["share_of_change"] is not None else ""
        return f"{moved(metric, d['previous'], d['current'])} ({signed(metric, d['contribution'])}{share}, {effect})"
    if method == "additive":
        share = f"; {fmt.pct(abs(d['share_of_change']), 0)} da variação" if d["share_of_change"] is not None else ""
        return f"{moved(metric, d['previous'], d['current'])} ({signed(metric, d['contribution'])}{share})"
    return f"{moved(metric, d['previous'], d['current'])} ({signed(metric, d['delta'])})"


def why(repo: Repository, f: Filters, intent: Intent, scope_label: str | None = None) -> Answer:
    layer = _layer()
    metric = intent.metric or "sla_rate"
    if metric not in layer.metrics:
        metric = "sla_rate"
    tools = ["get_kpis"]
    if only_canceled(f) and _measured_based(metric):
        m = repo.metrics(f)
        text = (f"O recorte filtra só pedidos cancelados ({fmt.integer(m['canceled'])}), sem entregas para medir "
                f"{short(metric)}.\n\n**Ação:** Operador deve remover o filtro de status cancelado para comparar "
                f"{short(metric)} com o período anterior.")
        return Answer(text, f"{cap(short(metric))} sem base", tools)
    cur_f, unit, fallback = _windowed(repo, f, intent)
    dims = _change_dims(metric, intent, cur_f)
    results = []
    error = None
    for d in dims:
        r = explain_change(repo, cur_f, metric=metric, by=d, limit=5, min_orders=30)
        if "error" in r:
            error = r["error"]
            break
        results.append((d, r))
        tools.append(f"explain_change({metric}:{d})")
    where = f" {scope_label}" if scope_label else ""
    if error or not results:
        total = repo.query_metrics(cur_f, metrics=[metric])["total"][metric]
        text = (f"{cap(short(metric))}{where} no recorte: {show(metric, total)}. {error or 'Sem base para comparar.'}"
                f"\n\n**Ação:** Operador deve escolher um período que não comece em {repo.min_date:%d/%m/%Y} "
                "para comparar com o período anterior.")
        return Answer(text, f"{cap(short(metric))} sem período anterior", tools)

    first = results[0][1]
    total = first["total"]
    delta = total["delta"]
    prev = first["previous_period"]
    better = layer.metrics[metric].better
    flat = abs(delta) < (0.0005 if layer.metrics[metric].unit == "pct" else 1e-9)
    word = "ficou estável" if flat else ("subiu" if delta > 0 else "caiu")
    bad = (not flat) and ((delta < 0) if better == "up" else (delta > 0))
    ref = "na semana anterior" if unit == "semana" else "no período anterior"
    period = describe_dates(*repo.period(cur_f))
    lines = []
    if fallback:
        lines.append(f"O recorte começa no primeiro dia da base ({repo.min_date:%d/%m/%Y}), então não há período anterior "
                     "do mesmo tamanho: comparo a última semana com a semana anterior.")
    change_txt = ""
    if not flat:
        change_txt = f" {show_delta(metric, delta)}"
        if layer.metrics[metric].kind in ("count", "sum") and total["previous"]:
            change_txt = f" {fmt.pct(abs(delta) / total['previous'])} ({show_delta(metric, delta)})"
    lines.append(f"{SUBJECT.get(metric, cap(short(metric)))}{where} {word}{change_txt}: {show(metric, total['current'])} em {period} "
                 f"contra {show(metric, total['previous'])} {ref} ({describe_dates(prev['start'], prev['end'])}).")

    target = None
    for d, r in results:
        drivers = [x for x in r["drivers"] if x["key"] is not None and x["label"] != OTHERS_LABEL
                   and x["contribution"] is not None]
        same = sorted((x for x in drivers if x["contribution"] * delta > 0), key=lambda x: -abs(x["contribution"]))
        other = sorted((x for x in drivers if x["contribution"] * delta < 0), key=lambda x: -abs(x["contribution"]))
        if flat or not drivers:
            continue
        lines += ["", f"Por {dim_label(d).lower()}, quem mais puxou para {'cima' if delta > 0 else 'baixo'}:"]
        for x in same[:3]:
            lines.append(f"- {_row_label(repo, d, x)}: {_contribution_text(metric, r['method'], x)}")
        if other:
            x = other[0]
            lines.append(f"Na contramão: {_row_label(repo, d, x)}, {_contribution_text(metric, r['method'], x)}.")
        # Piorou: age em quem mais puxou. Melhorou: age em quem foi na contramão (piorou no grupo);
        # se ninguém piorou, registra o que mais puxou a melhora para replicar.
        if bad and same:
            pick, worsened = same[0], True
        elif not bad and other:
            pick, worsened = other[0], True
        else:
            pick, worsened = (same[0] if same else None), False
        if target is None and pick is not None:
            target = (d, pick, worsened)
    if first["method"] == "approx" and not flat:
        lines.append("Mediana não se decompõe em soma: a ordem acima usa a variação de cada grupo pesada pelo volume.")

    drills: list[DrillDown] = []
    if target is None:
        action = (f"Time de operações deve acompanhar {short(metric)} ao longo desta semana: a variação {ref} "
                  "não se concentra em nenhum grupo.")
    else:
        d, x, worsened = target
        label = value_label(d, x["key"], x["label"])
        action = _change_action(repo, cur_f, metric, d, x, label, worsened)
        dd = drill(d, x["key"], label)
        if dd:
            drills.append(dd)
    lines += ["", f"**Ação:** {action}"]
    subject = SUBJECT.get(metric, cap(short(metric)))
    subject = cap(subject.split(" ", 1)[1]) if subject.split(" ", 1)[0] in ("O", "A") else subject
    head = f"{subject} {word}" + (f"{change_txt}" if not flat else "")
    return Answer("\n".join(lines), head[:80], tools, drills)


def _change_action(repo: Repository, f: Filters, metric: str, dim: str, x: dict, label: str, worsened: bool) -> str:
    change = moved(metric, x["previous"], x["current"])
    if not worsened:
        return (f"{owner_for(dim, label)} deve registrar hoje o que puxou a melhora ({short(metric)} {change}) "
                "para o time de operações replicar nos demais.")
    if metric in ("sla_rate", "cycle_p50", "cycle_p90", *STAGE_KEYS):
        cause = drill_cause(repo, f, metric="sla_rate" if metric == "sla_rate" else "cycle_p50", group={dim: [x["key"]]})
        # Etapa que mais piorou contra o período anterior; se nenhuma andou 0,5 min, a mais lenta contra o resto.
        stage, gap, versus = None, None, ""
        for field, text in (("vs_previous", "contra o período anterior"), ("vs_rest", "contra o resto do recorte")):
            moved_rows = [r for r in cause["stages"] if r[field] is not None and r[field] >= 0.5]
            if moved_rows:
                top = max(moved_rows, key=lambda r: r[field])
                stage, gap, versus = top["metric"], top[field], text
                break
        hub_label = x["label"] if dim == "hub" else (_hub_of_store(repo, x["key"]) if dim == "store" else None)
        base = stage_action(repo, f, stage, None, dim=dim, label=label, hub_label=hub_label, peak=_peak_phrase(repo, f))
        detail = f" {cap(STAGES[stage])} {signed(stage, gap)} {versus}." if stage and gap else ""
        return f"{base.rstrip('.')} ({short(metric)} {change}).{detail}"
    if metric in ("cancel_rate", "canceled"):
        if dim == "store" and is_broken({"cancel_rate": x["current"], "orders": x["orders_current"]}):
            return broken_store_action(repo, f, x["key"], x["label"])
        if dim == "store":
            return (f"Gerente de contas deve ligar hoje para a loja {label} (cancelamento {change}) e checar "
                    f"ruptura de itens e loja fechada com cardápio aberto {_peak_phrase(repo, f)}.")
        return (f"{owner_for(dim, label)} deve abrir as lojas por cancelamento e ligar hoje para as primeiras "
                f"(cancelamento {change}).")
    if metric in ("orders", "gmv", "delivered"):
        if dim == "channel":
            return f"Time comercial deve falar hoje com o parceiro do canal {label}: {short(metric)} {change}."
        if dim == "store":
            return f"Gerente de contas deve ligar hoje para a loja {label} ({short(metric)} {change}) e checar se ficou fechada ou pausada."
        return (f"{owner_for(dim, label)} deve checar hoje lojas fechadas ou pausadas e a cobertura de entregadores "
                f"({short(metric)} {change}).")
    return f"{owner_for(dim, label)} deve {metric_verb(metric, show(metric, x['current']))} hoje (antes: {show(metric, x['previous'])})."


# ------------------------------------------------------------- janelas de tempo


def _where(w: Window) -> dict:
    out: dict = {}
    if w.hours:
        out["hour"] = list(w.hours)
    if w.weekdays:
        out["weekday"] = list(w.weekdays)
    return out


def _window_text(w: Window) -> str:
    parts = []
    if w.hours:
        parts.append(f"{min(w.hours):02d}h–{max(w.hours) + 1:02d}h")
    if w.weekdays:
        parts.append(", ".join(WEEKDAYS[d] for d in sorted(w.weekdays)))
    return " · ".join(parts)


def _days_in(repo: Repository, f: Filters, weekdays: tuple[int, ...]) -> int:
    start, end = repo.period(f)
    start, end = max(start, repo.min_date), min(end, repo.max_date)
    if end < start:
        return 0
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() in weekdays)


def in_window(name: str) -> str:
    """'almoço' -> 'no almoço', 'sexta' -> 'na sexta', 'dias úteis' -> 'nos dias úteis', '19h–21h' -> 'na faixa 19h–21h'."""
    low = name.lower()
    if low[:1].isdigit():
        return f"na faixa {low}"
    for article, prep in (("o ", "no "), ("a ", "na "), ("os ", "nos "), ("as ", "nas ")):
        if low.startswith(article):
            return prep + low[len(article):]
    first = low.split(" ", 1)[0]
    feminine = first.endswith(("a", "as")) and not first.startswith("dia")
    if first.endswith("s") and " " in low:
        return f"nas {low}" if feminine else f"nos {low}"
    return f"na {low}" if feminine else f"no {low}"


def _complement(a: Window, b: Window) -> bool:
    if a.weekdays and b.weekdays and not a.hours and not b.hours:
        return set(a.weekdays).isdisjoint(b.weekdays) and set(a.weekdays) | set(b.weekdays) == set(range(7))
    if a.hours and b.hours and not a.weekdays and not b.weekdays:
        return set(a.hours).isdisjoint(b.hours) and set(a.hours) | set(b.hours) == set(range(24))
    return False


_WINDOW_METRICS = ("orders", "sla_rate", "cancel_rate", "cycle_p50")


def _merge(wins: list[Window]) -> list[Window]:
    """"jantar de sexta": janela de horas + janela de dias viram uma fatia só (horas daquele dia)."""
    hours = [w for w in wins if w.hours and not w.weekdays]
    days = [w for w in wins if w.weekdays and not w.hours]
    if len(hours) == 1 and len(days) == 1 and len(wins) == 2:
        h, d = hours[0], days[0]
        return [Window(f"{h.label} de {d.label.lower()}", h.hours, d.weekdays)]
    return wins


def _window_action(repo: Repository, f: Filters, w: Window, focus: str, value, other_value, other_name: str) -> str:
    start = min(w.hours) if w.hours else peak_start(repo, f)
    when = f"30 min antes das {start:02d}h" if start is not None else "antes do pico"
    days = f" {' e '.join(on_weekday(d) for d in sorted(w.weekdays))}" if w.weekdays else ""
    compare = f"{short(focus)} de {show(focus, value)} contra {show(focus, other_value)} {in_window(other_name)}"
    if focus == "cancel_rate":
        return (f"Líder de operações deve checar {when}{days} as lojas fechadas com cardápio aberto e a ruptura "
                f"de itens: {compare}.")
    cause = drill_cause(repo, f, metric="sla_rate", group=_where(w))
    stage = cause["top_stage_vs_rest"]
    if stage == "production_p50":
        return f"Gerente de contas deve revisar com as lojas{days}, {when}, o tempo de preparo informado: {compare}."
    tail = f", com {STAGES[stage]} como a etapa que mais pesa" if stage else ""
    return f"Time de frota deve antecipar a escala de entregadores {when}{days}: {compare}{tail}."


def windows(repo: Repository, f: Filters, intent: Intent) -> Answer:
    """Janela do glossário (almoço, jantar, fim de semana...) ou faixa escrita contra o resto ou outra janela."""
    wins: list[Window] = []
    for w in intent.windows:
        if w.label not in [x.label for x in wins]:
            wins.append(w)
    wins = _merge(wins)
    a = wins[0]
    second = wins[1] if len(wins) > 1 else None
    b = second if second is not None and not _complement(a, second) else None
    layer = _layer()
    focus = intent.metric if intent.metric and layer.metrics[intent.metric].kind not in ("count", "sum") else "sla_rate"
    metrics = list(dict.fromkeys([focus, *_WINDOW_METRICS]))
    tools = [f"query_metrics({','.join(metrics[:3])})", "get_breakdown(hour)" if a.hours else "get_breakdown(weekday)"]
    if b is None:
        qm = repo.query_metrics(f, metrics=metrics, where=_where(a), compare="rest")
        sa, sb = qm["total"], qm["total_compare"] or {}
        # Complemento: "dias úteis" quando a pergunta nomeou; senão o resto do recorte.
        other_name = second.label.lower() if second is not None else "o resto do recorte"
        other_days = second.weekdays if second is not None else tuple(d for d in range(7) if d not in a.weekdays)
    else:
        sa = repo.query_metrics(f, metrics=metrics, where=_where(a))["total"]
        sb = repo.query_metrics(f, metrics=metrics, where=_where(b))["total"]
        other_name, other_days = b.label.lower(), b.weekdays

    def per_day(s: dict, days: tuple[int, ...]) -> str:
        n = _days_in(repo, f, days) if days else 0
        return f" ({fmt.integer(s['orders'] / n)} por dia)" if n and s.get("orders") else ""

    def row(name: str, s: dict, days: tuple[int, ...]) -> str:
        extra = f" · {short(focus)} {show(focus, s.get(focus))}" if focus not in _WINDOW_METRICS else ""
        return (f"- {cap(name)}: SLA {fmt.pct(s.get('sla_rate'))} · cancelamento {fmt.pct(s.get('cancel_rate'))} · "
                f"ciclo mediano {fmt.minutes(s.get('cycle_p50'))} · {fmt.integer(s.get('orders'))} pedidos"
                f"{per_day(s, days if a.weekdays or (b and b.weekdays) else ())}{extra}")

    text_a = _window_text(a)
    head = f"{a.label}" + (f" ({text_a})" if text_a.lower() != a.label.lower() else "")
    lines = [f"{cap(head)} contra {other_name} ({repo.describe(f)}):",
             row(a.label, sa, a.weekdays), row(other_name.removeprefix("o "), sb, other_days)]
    va, vb = sa.get(focus), sb.get(focus)
    if a.hours and not a.weekdays:
        hours = {int(h["key"]): h for h in repo.breakdown(f, "hour", sort="orders", limit=24)}
        parts = [f"{h:02d}h {show(focus, hours[h][focus])}" for h in a.hours
                 if h in hours and hours[h].get(focus) is not None]
        if parts:
            lines.append(f"{cap(short(focus))} por hora na faixa: " + " · ".join(parts))
    target = None
    if va is not None and vb is not None:
        diff = va - vb
        lines.append(f"Diferença de {short(focus)}: {signed(focus, diff)} {in_window(a.label)} contra {other_name}.")
        threshold = 0.01 if layer.metrics[focus].unit == "pct" else 1.0
        if abs(diff) >= threshold:
            a_worse = (diff < 0) if layer.metrics[focus].better == "up" else (diff > 0)
            target = (a, va, vb, other_name) if a_worse else ((b, vb, va, a.label.lower()) if b else None)
    if target is not None:
        w, v_w, v_o, o_name = target
        action = _window_action(repo, f, w, focus, v_w, v_o, o_name)
    else:
        start = min(a.hours) if a.hours else peak_start(repo, f)
        when = f"a partir das {start:02d}h" if start is not None else "no pico"
        days = f" {' e '.join(on_weekday(d) for d in sorted(a.weekdays))}" if a.weekdays else ""
        action = (f"Time de operações deve manter a escala atual{days} {when}: {short(focus)} de {show(focus, va)} "
                  f"{in_window(a.label)} contra {show(focus, vb)} {in_window(other_name)}, sem diferença que peça reforço.")
    lines += ["", f"**Ação:** {action}"]
    return Answer("\n".join(lines), f"{cap(a.label)} contra {other_name.removeprefix('o ')}"[:80], tools)
