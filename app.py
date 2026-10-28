"""Central de Operações — food delivery analytics + agente de insights."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agent.insights import answer_question, detect_alerts, llm_label
from dashboard.charts import (
    cancel_by_customer,
    delivery_by_city,
    orders_and_gmv_over_time,
    ranking_restaurants,
    ranking_restaurants_by_note,
    rating_distribution,
    weekday_hour_heatmap,
)
from dashboard.filters import (
    active_filter_chips,
    apply_filters,
    describe_filters,
    is_default_recorte,
    recorte_fingerprint,
    render_filters,
    reset_filter_state,
)
from dashboard.metrics import (
    compute_kpis,
    format_brl,
    format_int,
    format_minutes,
    format_pct,
    format_rating,
)
from data.generator import generate_orders

load_dotenv()

st.set_page_config(
    page_title="Central de Operações · Delivery",
    layout="wide",
    initial_sidebar_state="expanded",
)

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}

SUGGESTED = [
    "Quais alertas e ações agora?",
    "Como está o tempo de entrega por cidade?",
    "Quem são os piores restaurantes em nota?",
]


def _hydrate_secrets() -> None:
    try:
        for key in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL"):
            value = st.secrets.get(key)
            if value and key not in os.environ:
                os.environ[key] = str(value)
    except Exception:
        return


@st.cache_data(show_spinner=False)
def load_orders() -> object:
    return generate_orders(n=12_000, seed=42)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.4rem; padding-bottom: 5rem; max-width: 1400px; }
          h1 { font-size: 1.55rem !important; letter-spacing: -0.02em; }
          div[data-testid="stMetric"] {
            background: #F3EBE3;
            border: 1px solid #E7D8C9;
            border-left: 3px solid #C2410C;
            padding: 0.7rem 0.9rem;
            border-radius: 2px;
          }
          div[data-testid="stMetric"] label { color: #78716C; }
          [data-testid="stSidebar"] { background: #F3EBE3; }
          .hint { color: #78716C; font-size: 0.92rem; margin: 0 0 0.6rem 0; }
          .chips { color: #1C1917; font-size: 0.92rem; margin: 0.2rem 0 0.8rem 0; }
          [class*="st-key-open_agent"] {
            position: fixed !important;
            right: 1.5rem;
            bottom: 1.5rem;
            z-index: 1000;
            width: auto !important;
          }
          [class*="st-key-open_agent"] button {
            border-radius: 6px;
            min-height: 44px;
            min-width: 44px;
            padding: 0.7rem 1.15rem;
            box-shadow: none;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_chat() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("messages_fp", None)
    st.session_state.setdefault("agent_open", False)


def _chat_stale(fp: str) -> bool:
    messages = st.session_state.messages
    bound = st.session_state.get("messages_fp")
    return bool(messages) and bound is not None and bound != fp


def _clear_chat(fp: str) -> None:
    st.session_state.messages = []
    st.session_state.messages_fp = fp


def _dismiss_agent() -> None:
    st.session_state.agent_open = False


def _ask(prompt: str, filtered, filter_desc: str, fp: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages_fp = fp
    with st.spinner("Analisando o recorte…"):
        reply = answer_question(prompt, filtered, filter_desc=filter_desc)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


def _chart(fig) -> None:
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def _render_hero_kpis(kpis: dict[str, float]) -> None:
    st.caption("Operação neste recorte")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tempo de entrega", format_minutes(kpis["avg_delivery"]))
    c2.metric("Nota média", format_rating(kpis["avg_rating"]))
    c3.metric("Cancelamento", format_pct(kpis["cancel_rate"]))


def _render_volume_kpis(kpis: dict[str, float]) -> None:
    st.caption("Volume")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pedidos", format_int(kpis["orders"]))
    c2.metric("GMV", format_brl(kpis["gmv"]))
    c3.metric("Ticket médio", format_brl(kpis["avg_ticket"]))
    st.caption(
        f"Promo em {format_pct(kpis['promo_rate'])} dos pedidos · "
        f"{format_int(kpis['delivered'])} entregues."
    )


def _render_alerts(alerts) -> None:
    st.subheader("Alertas do recorte")
    if not alerts:
        st.success("Nenhum alerta crítico neste recorte. SLA, nota e cancelamento dentro do teto interno.")
        return
    for alert in alerts:
        body = f"**{alert.title}** — {alert.detail}\n\nAção: {alert.action}"
        if alert.severity == "high":
            st.error(body)
        else:
            st.warning(body)


def _render_recorte_bar(
    filters,
    min_day: pd.Timestamp,
    max_day: pd.Timestamp,
    filter_desc: str,
    mode: str,
) -> None:
    chips = active_filter_chips(filters, min_day, max_day)
    left, right = st.columns([5, 1.3], vertical_alignment="bottom")
    if chips:
        left.markdown(
            f'<p class="chips"><span class="hint">Recorte ativo · </span>{" · ".join(chips)}</p>',
            unsafe_allow_html=True,
        )
    else:
        left.markdown(
            f'<p class="hint">{filter_desc} · agente em {mode} · vazio nos filtros = todas</p>',
            unsafe_allow_html=True,
        )
    if not is_default_recorte(filters, min_day, max_day):
        if right.button("Limpar recorte", width="stretch", key="clear_recorte_main"):
            reset_filter_state(min_day, max_day)
            st.rerun()


@st.dialog("Agente de insights", width="large", on_dismiss=_dismiss_agent)
def _agent_dialog(filtered, filter_desc: str, fp: str, stale: bool, empty: bool) -> None:
    head, clear = st.columns([3.2, 1.3], vertical_alignment="bottom")
    head.caption("Respostas usam só o recorte da página — não o dataset inteiro.")
    if clear.button(
        "Nova conversa",
        width="stretch",
        disabled=not st.session_state.messages,
        key="clear_chat",
    ):
        _clear_chat(fp)
        st.rerun()

    if empty:
        st.warning("Sem pedidos neste recorte. Afrouxe o filtro para perguntar.")
        return
    if stale:
        st.warning("Recorte mudou. Nova conversa para analisar este recorte.")
        st.caption("O histórico anterior volta se você desfizer o filtro.")
        return

    for suggestion in SUGGESTED:
        if st.button(suggestion, width="stretch", key=f"ask_{suggestion}"):
            _ask(suggestion, filtered, filter_desc, fp)

    with st.container(height=320, border=True):
        if not st.session_state.messages:
            st.caption("Nenhuma pergunta ainda neste recorte.")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    prompt = st.chat_input("Pergunte sobre o recorte filtrado…")
    if prompt:
        _ask(prompt, filtered, filter_desc, fp)


def _render_agent_fab() -> None:
    if st.button("Agente", type="primary", key="open_agent"):
        st.session_state.agent_open = True


def main() -> None:
    _hydrate_secrets()
    _inject_css()
    _init_chat()

    orders = load_orders()
    filters, min_day, max_day = render_filters(orders)
    filtered = apply_filters(orders, filters)
    kpis = compute_kpis(filtered)
    alerts = detect_alerts(filtered)
    filter_desc = describe_filters(filters, n_total=len(orders), n_filtered=len(filtered))
    mode = llm_label()
    fp = recorte_fingerprint(filters)
    stale = _chat_stale(fp)
    empty = filtered.empty

    st.title("Central de Operações")
    st.caption(
        "SLA, qualidade e ação no recorte filtrado. "
        "Alertas e agente usam os mesmos filtros — não o dataset inteiro."
    )
    _render_recorte_bar(filters, min_day, max_day, filter_desc, mode)

    if empty:
        st.warning(
            "Nenhum pedido neste recorte. "
            "Use Limpar recorte para voltar ao período completo, ou afrouxe cidade / culinária / status."
        )
    else:
        _render_alerts(alerts)
        _render_hero_kpis(kpis)
        st.divider()
        _render_volume_kpis(kpis)

        st.subheader("Evidência")
        tab_trend, tab_rank, tab_ops = st.tabs(["Tendência", "Ranking", "Operação"])
        with tab_trend:
            left, right = st.columns((1.35, 1))
            with left:
                _chart(orders_and_gmv_over_time(filtered))
            with right:
                _chart(weekday_hour_heatmap(filtered))
        with tab_rank:
            left, right = st.columns((1.2, 1))
            with left:
                _chart(ranking_restaurants_by_note(filtered))
            with right:
                _chart(ranking_restaurants(filtered))
        with tab_ops:
            a, b, c = st.columns(3)
            with a:
                _chart(delivery_by_city(filtered))
            with b:
                _chart(rating_distribution(filtered))
            with c:
                _chart(cancel_by_customer(filtered))

    _render_agent_fab()
    if st.session_state.agent_open:
        _agent_dialog(filtered, filter_desc, fp, stale, empty)


main()
