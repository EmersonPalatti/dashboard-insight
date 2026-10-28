"""Agente local (regras + estatísticas) com LLM opcional."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from dashboard.metrics import compute_kpis, format_brl, format_int, format_minutes, format_pct, format_rating

PROMPTS_PATH = Path(__file__).with_name("prompts.md")
SYSTEM_PROMPT = PROMPTS_PATH.read_text(encoding="utf-8")
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

DELIVERY_WARN = 42.0
DELIVERY_HIGH = 48.0
RATING_WARN = 4.20
RATING_LOW = 4.00
CANCEL_WARN = 0.07
CANCEL_HIGH = 0.10
RESTAURANT_MIN_N = 25
CITY_MIN_N = 40


@dataclass
class Alert:
    severity: str
    title: str
    detail: str
    action: str


def llm_enabled() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def llm_label() -> str:
    if not llm_enabled():
        return "regras locais (sem API key)"
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
    return f"OpenRouter · {model}"


def _norm(text: str) -> str:
    text = text.lower().strip()
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _delivered(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"] == "Entregue"]


def summarize(df: pd.DataFrame) -> dict:
    kpis = compute_kpis(df)
    if df.empty:
        return {"kpis": kpis, "top_restaurants": [], "worst_restaurants": [], "cities": [], "cuisines": []}

    delivered = _delivered(df)

    def restaurant_table(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["restaurant", "gmv", "pedidos", "nota", "tempo"])
        return (
            frame.groupby("restaurant", as_index=False)
            .agg(
                gmv=("order_value", "sum"),
                pedidos=("order_id", "count"),
                nota=("rating", "mean"),
                tempo=("delivery_minutes", "mean"),
            )
        )

    rest = restaurant_table(delivered)
    rest_ok = rest[rest["pedidos"] >= RESTAURANT_MIN_N] if not rest.empty else rest
    pool = rest_ok if not rest_ok.empty else rest

    cities = (
        df.groupby("city")
        .agg(
            pedidos=("order_id", "count"),
            cancel_rate=("status", lambda s: float((s == "Cancelado").mean())),
        )
        .reset_index()
    )
    if not delivered.empty:
        city_ops = delivered.groupby("city").agg(
            tempo=("delivery_minutes", "mean"),
            nota=("rating", "mean"),
            gmv=("order_value", "sum"),
        )
        cities = cities.merge(city_ops, on="city", how="left")
    else:
        cities["tempo"] = float("nan")
        cities["nota"] = float("nan")
        cities["gmv"] = 0.0

    cuisines = (
        df.groupby("cuisine")
        .size()
        .sort_values(ascending=False)
        .head(8)
        .rename("pedidos")
        .reset_index()
        .to_dict(orient="records")
    )

    top = pool.sort_values("gmv", ascending=False).head(5).to_dict(orient="records") if not pool.empty else []
    worst = pool.sort_values("nota", ascending=True).head(5).to_dict(orient="records") if not pool.empty else []

    hour_peak = None
    if not df.empty:
        hour_counts = df["ordered_at"].dt.hour.value_counts()
        if not hour_counts.empty:
            hour_peak = int(hour_counts.idxmax())

    return {
        "kpis": kpis,
        "top_restaurants": top,
        "worst_restaurants": worst,
        "cities": cities.sort_values("pedidos", ascending=False).to_dict(orient="records"),
        "cuisines": cuisines,
        "hour_peak": hour_peak,
        "n_restaurants": int(df["restaurant"].nunique()),
        "n_cities": int(df["city"].nunique()),
    }


def detect_alerts(df: pd.DataFrame) -> list[Alert]:
    alerts: list[Alert] = []
    if df.empty:
        return alerts

    kpis = compute_kpis(df)
    delivered = _delivered(df)

    if kpis["avg_delivery"] >= DELIVERY_HIGH:
        alerts.append(
            Alert(
                "high",
                "SLA de entrega estourado",
                f"Tempo médio de {format_minutes(kpis['avg_delivery'])} no recorte (limite interno 48 min).",
                "Reforçar frota no jantar (18h–21h) nas praças mais lentas e revisar distância média dos pedidos.",
            )
        )
    elif kpis["avg_delivery"] >= DELIVERY_WARN:
        alerts.append(
            Alert(
                "medium",
                "Tempo de entrega acima do confortável",
                f"Tempo médio de {format_minutes(kpis['avg_delivery'])}. Risco de nota e cancelamento no pico.",
                "Olhar o heatmap de hora × dia e deslocar motoboys 30 min antes do pico da praça.",
            )
        )

    if kpis["avg_rating"] and kpis["avg_rating"] < RATING_LOW:
        alerts.append(
            Alert(
                "high",
                "Qualidade abaixo da meta",
                f"Nota média {format_rating(kpis['avg_rating'])} (meta interna 4,20).",
                "Abrir os restaurantes com mais volume e nota < 3,8: atraso, item em falta ou embalagem.",
            )
        )
    elif kpis["avg_rating"] and kpis["avg_rating"] < RATING_WARN:
        alerts.append(
            Alert(
                "medium",
                "Nota no limite da meta",
                f"Nota média {format_rating(kpis['avg_rating'])}. Pouca folga para o SLA piorar.",
                "Tratar os 3 piores restaurantes do recorte nesta semana, não a média geral.",
            )
        )

    if kpis["cancel_rate"] >= CANCEL_HIGH:
        alerts.append(
            Alert(
                "high",
                "Cancelamento elevado",
                f"Taxa de {format_pct(kpis['cancel_rate'])} (teto interno 7%).",
                "Separar recusa do restaurante vs. atraso vs. cliente: o mix muda a ação.",
            )
        )
    elif kpis["cancel_rate"] >= CANCEL_WARN:
        alerts.append(
            Alert(
                "medium",
                "Cancelamento acima do teto",
                f"Taxa de {format_pct(kpis['cancel_rate'])}.",
                "Checar se o excesso está em clientes novos ou em uma praça específica.",
            )
        )

    if not delivered.empty:
        rest = (
            delivered.groupby("restaurant")
            .agg(pedidos=("order_id", "count"), nota=("rating", "mean"), tempo=("delivery_minutes", "mean"))
            .reset_index()
        )
        rest = rest[rest["pedidos"] >= RESTAURANT_MIN_N]
        bad = rest[rest["nota"] < 3.8].sort_values("nota")
        if not bad.empty:
            row = bad.iloc[0]
            alerts.append(
                Alert(
                    "high",
                    f"Restaurante crítico: {row['restaurant']}",
                    f"Nota {format_rating(float(row['nota']))} em {int(row['pedidos'])} pedidos entregues · "
                    f"tempo médio {format_minutes(float(row['tempo']))}.",
                    f"Chamar o parceiro {row['restaurant']} e pausar destaque no app até a nota subir de 3,8.",
                )
            )

    city_stats = df.groupby("city").agg(
        pedidos=("order_id", "count"),
        cancel_rate=("status", lambda s: float((s == "Cancelado").mean())),
    )
    if not delivered.empty:
        city_stats = city_stats.join(delivered.groupby("city")["delivery_minutes"].mean().rename("tempo"))
    city_stats = city_stats[city_stats["pedidos"] >= CITY_MIN_N]
    if not city_stats.empty and kpis["cancel_rate"] > 0:
        city_stats = city_stats.copy()
        city_stats["cancel_lift"] = city_stats["cancel_rate"] / max(kpis["cancel_rate"], 1e-6)
        hotspot = city_stats.sort_values("cancel_lift", ascending=False).iloc[0]
        if hotspot["cancel_lift"] >= 1.45 and hotspot["cancel_rate"] >= CANCEL_WARN:
            alerts.append(
                Alert(
                    "medium",
                    f"Praça com cancelamento fora da curva: {hotspot.name}",
                    f"{format_pct(float(hotspot['cancel_rate']))} de cancelamento "
                    f"({hotspot['cancel_lift']:.1f}× a média do recorte) em {int(hotspot['pedidos'])} pedidos.",
                    f"Investigar {hotspot.name} isolando culinária e faixa noturna antes de agir no nacional.",
                )
            )
        if "tempo" in city_stats.columns:
            slow = city_stats.dropna(subset=["tempo"]).sort_values("tempo", ascending=False)
            if not slow.empty and float(slow.iloc[0]["tempo"]) >= DELIVERY_WARN:
                row = slow.iloc[0]
                alerts.append(
                    Alert(
                        "medium",
                        f"Praça lenta: {row.name}",
                        f"Tempo médio {format_minutes(float(row['tempo']))} em {int(row['pedidos'])} pedidos.",
                        f"Revisar raio de entrega e lotação de motoboys em {row.name} no jantar.",
                    )
                )

    # dedup by title, keep first
    seen: set[str] = set()
    unique: list[Alert] = []
    for alert in alerts:
        if alert.title in seen:
            continue
        seen.add(alert.title)
        unique.append(alert)
    return unique


def _fmt_rest_line(row: dict, kind: str) -> str:
    if kind == "gmv":
        return f"- {row['restaurant']}: {format_brl(row['gmv'])} · {int(row['pedidos'])} pedidos · nota {format_rating(row['nota'])}"
    return (
        f"- {row['restaurant']}: nota {format_rating(row['nota'])} · "
        f"{int(row['pedidos'])} pedidos · {format_minutes(row['tempo'])}"
    )


def format_briefing(df: pd.DataFrame, filter_desc: str = "") -> str:
    if df.empty:
        return "Nenhum pedido no recorte. Afrouxe cidade, culinária ou período."

    summary = summarize(df)
    k = summary["kpis"]
    alerts = detect_alerts(df)
    lines = [
        "Briefing do recorte filtrado" + (f" ({filter_desc})" if filter_desc else "") + ".",
        "",
        f"- Pedidos: {format_int(k['orders'])} · GMV: {format_brl(k['gmv'])} · ticket {format_brl(k['avg_ticket'])}",
        f"- Entrega: {format_minutes(k['avg_delivery'])} · nota {format_rating(k['avg_rating'])} · "
        f"cancelamento {format_pct(k['cancel_rate'])} · promo {format_pct(k['promo_rate'])}",
    ]
    if summary.get("hour_peak") is not None:
        lines.append(f"- Pico de volume por volta das {summary['hour_peak']:02d}h.")
    if summary["top_restaurants"]:
        lines.append("")
        lines.append("Maiores GMV:")
        lines.extend(_fmt_rest_line(r, "gmv") for r in summary["top_restaurants"][:3])
    if summary["worst_restaurants"]:
        lines.append("")
        lines.append("Piores notas (com volume):")
        lines.extend(_fmt_rest_line(r, "nota") for r in summary["worst_restaurants"][:3])
    if alerts:
        lines.append("")
        lines.append("Alertas e ações:")
        for alert in alerts:
            lines.append(f"- **{alert.title}** — {alert.detail} Ação: {alert.action}")
    else:
        lines.append("")
        lines.append("Nenhum alerta crítico neste recorte. Manter olho no jantar e nas praças mais lentas.")
    return "\n".join(lines)


def _local_answer(question: str, df: pd.DataFrame, filter_desc: str) -> str:
    if df.empty:
        return "Nenhum pedido no recorte atual. Afrouxe os filtros para o agente ter o que analisar."

    q = _norm(question)
    k = compute_kpis(df)
    summary = summarize(df)

    if any(token in q for token in ("alerta", "acao", "problema", "risco")):
        alerts = detect_alerts(df)
        if not alerts:
            return (
                f"Nenhum alerta crítico no recorte ({filter_desc}). "
                f"Tempo {format_minutes(k['avg_delivery'])}, nota {format_rating(k['avg_rating'])}, "
                f"cancelamento {format_pct(k['cancel_rate'])}."
            )
        lines = [f"Alertas no recorte ({filter_desc}):", ""]
        for alert in alerts:
            lines.append(f"**{alert.title}** ({alert.severity})")
            lines.append(alert.detail)
            lines.append(f"Ação: {alert.action}")
            lines.append("")
        return "\n".join(lines).strip()

    if any(token in q for token in ("ticket", "gmv", "receita", "faturamento", "valor medio")):
        return (
            f"No recorte ({filter_desc}): GMV {format_brl(k['gmv'])} em {format_int(k['delivered'])} "
            f"entregas, ticket médio {format_brl(k['avg_ticket'])}. "
            f"{format_pct(k['promo_rate'])} dos pedidos entraram com promo."
        )

    if any(token in q for token in ("tempo", "entrega", "sla", "atras")):
        cities = summary["cities"]
        slow = sorted(
            [c for c in cities if pd.notna(c.get("tempo"))],
            key=lambda c: c["tempo"],
            reverse=True,
        )
        extra = ""
        if slow:
            top = slow[0]
            extra = (
                f" Praça mais lenta: {top['city']} com {format_minutes(top['tempo'])} "
                f"({int(top['pedidos'])} pedidos)."
            )
        return (
            f"Tempo médio de entrega no recorte: {format_minutes(k['avg_delivery'])}."
            + extra
            + " Ação: cruzar com o heatmap — se o atraso for só no jantar, é capacidade, não média do dia."
        )

    if any(token in q for token in ("nota", "avaliacao", "qualidade", "pior")):
        lines = [
            f"Nota média no recorte: {format_rating(k['avg_rating'])} ({filter_desc}).",
            "",
        ]
        if summary["worst_restaurants"]:
            lines.append("Piores restaurantes com volume:")
            lines.extend(_fmt_rest_line(r, "nota") for r in summary["worst_restaurants"])
            lines.append("")
            lines.append("Ação: tratar o primeiro da lista nesta semana; média geral esconde parceiro ruim.")
        return "\n".join(lines)

    if any(token in q for token in ("cancel", "recusa")):
        novo = df[df["customer_type"] == "Novo"]
        novo_rate = float((novo["status"] == "Cancelado").mean()) if not novo.empty else 0.0
        cities = sorted(summary["cities"], key=lambda c: c.get("cancel_rate", 0), reverse=True)
        extra = ""
        if cities:
            extra = (
                f" Maior taxa: {cities[0]['city']} com {format_pct(cities[0]['cancel_rate'])}."
            )
        return (
            f"Cancelamento no recorte: {format_pct(k['cancel_rate'])}."
            f" Clientes novos: {format_pct(novo_rate)}."
            + extra
            + " Ação: se o excesso for em novos, revisar ETA na primeira compra; se for praça, olhar ruptura."
        )

    if any(token in q for token in ("cidade", "praca")):
        lines = [f"Praças no recorte ({filter_desc}):", ""]
        for c in summary["cities"][:8]:
            tempo = format_minutes(c["tempo"]) if pd.notna(c.get("tempo")) else "—"
            nota = format_rating(c["nota"]) if pd.notna(c.get("nota")) else "—"
            lines.append(
                f"- {c['city']}: {int(c['pedidos'])} pedidos · GMV {format_brl(c.get('gmv') or 0)} · "
                f"{tempo} · nota {nota} · cancel {format_pct(c['cancel_rate'])}"
            )
        return "\n".join(lines)

    if any(token in q for token in ("culinaria", "cozinha", "categoria")):
        lines = ["Volume por culinária no recorte:", ""]
        for row in summary["cuisines"]:
            lines.append(f"- {row['cuisine']}: {int(row['pedidos'])} pedidos")
        return "\n".join(lines)

    if any(token in q for token in ("promo", "cupom", "desconto")):
        promo = df[df["promo"]]
        no_promo = df[~df["promo"]]
        t_promo = compute_kpis(promo)["avg_ticket"] if not promo.empty else 0.0
        t_full = compute_kpis(no_promo)["avg_ticket"] if not no_promo.empty else 0.0
        return (
            f"{format_pct(k['promo_rate'])} dos pedidos no recorte usaram promo. "
            f"Ticket com promo {format_brl(t_promo)} vs. {format_brl(t_full)} sem promo. "
            "Ação: se o gap for grande em VIP, revisar stacking de cupom — não subsidiar quem já converteria."
        )

    if any(token in q for token in ("top", "ranking", "melhor", "maior")):
        lines = ["Maiores GMV no recorte:", ""]
        lines.extend(_fmt_rest_line(r, "gmv") for r in summary["top_restaurants"])
        return "\n".join(lines) if summary["top_restaurants"] else "Volume insuficiente para ranking estável."

    if any(token in q for token in ("cliente", "vip", "novo", "recorrente")):
        lines = ["Por tipo de cliente no recorte:", ""]
        for ctype in ("Novo", "Recorrente", "VIP"):
            part = df[df["customer_type"] == ctype]
            pk = compute_kpis(part)
            lines.append(
                f"- {ctype}: {format_int(pk['orders'])} pedidos · ticket {format_brl(pk['avg_ticket'])} · "
                f"cancel {format_pct(pk['cancel_rate'])} · nota {format_rating(pk['avg_rating'])}"
            )
        return "\n".join(lines)

    return format_briefing(df, filter_desc)


def _context_blob(df: pd.DataFrame, filter_desc: str) -> str:
    summary = summarize(df)
    alerts = [asdict(a) for a in detect_alerts(df)]
    k = summary["kpis"]
    return (
        f"Recorte: {filter_desc}\n"
        f"KPIs: pedidos={k['orders']:.0f}, gmv={k['gmv']:.2f}, ticket={k['avg_ticket']:.2f}, "
        f"entrega_min={k['avg_delivery']:.1f}, nota={k['avg_rating']:.2f}, "
        f"cancel={k['cancel_rate']:.3f}, promo={k['promo_rate']:.3f}\n"
        f"Pico de hora: {summary.get('hour_peak')}\n"
        f"Top GMV: {summary['top_restaurants'][:5]}\n"
        f"Piores notas: {summary['worst_restaurants'][:5]}\n"
        f"Praças: {summary['cities'][:8]}\n"
        f"Culinárias: {summary['cuisines']}\n"
        f"Alertas: {alerts}\n"
    )


def _llm_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None, None

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=60.0,
            default_headers={
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "Central de Operacoes Delivery",
            },
        )
        return client, os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)

    return None, None


def _llm_answer(question: str, df: pd.DataFrame, filter_desc: str) -> str | None:
    client, model = _llm_client()
    if client is None or model is None:
        return None

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Contexto estatístico do recorte (não é o dataset bruto):\n"
                        f"{_context_blob(df, filter_desc)}\n\n"
                        f"Pergunta do operador: {question}"
                    ),
                },
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def answer_question(question: str, df: pd.DataFrame, filter_desc: str = "") -> str:
    llm = _llm_answer(question, df, filter_desc)
    if llm:
        return llm
    return _local_answer(question, df, filter_desc)
