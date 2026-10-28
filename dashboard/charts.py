"""Figuras Plotly a partir do DataFrame filtrado."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ACCENT = "#C2410C"
INK = "#1C1917"
MUTED = "#78716C"
GRID = "#E7D8C9"
PALETTE = [
    "#C2410C",
    "#9A3412",
    "#B45309",
    "#A16207",
    "#44403C",
    "#57534E",
    "#D97706",
    "#7C2D12",
    "#CA8A04",
    "#292524",
]

WEEKDAY_LABELS = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}


def _layout(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=INK), x=0, xanchor="left"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFBF7",
        font=dict(color=INK, size=12),
        margin=dict(l=16, r=16, t=48, b=16),
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        colorway=PALETTE,
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def _empty(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="Sem dados no recorte", showarrow=False, font=dict(color=MUTED, size=14))
    return _layout(fig, title)


def orders_and_gmv_over_time(df: pd.DataFrame) -> go.Figure:
    title = "Pedidos e GMV por dia"
    if df.empty:
        return _empty(title)

    delivered = df[df["status"] == "Entregue"]
    daily_orders = (
        df.assign(day=df["ordered_at"].dt.normalize())
        .groupby("day")
        .size()
        .rename("pedidos")
    )
    daily_gmv = (
        delivered.assign(day=delivered["ordered_at"].dt.normalize())
        .groupby("day")["order_value"]
        .sum()
        .rename("gmv")
        if not delivered.empty
        else pd.Series(dtype=float, name="gmv")
    )
    daily = pd.concat([daily_orders, daily_gmv], axis=1).fillna(0).reset_index()
    daily = daily.rename(columns={"index": "day"})
    if "day" not in daily.columns:
        daily = daily.rename(columns={daily.columns[0]: "day"})

    fig = go.Figure()
    fig.add_bar(x=daily["day"], y=daily["pedidos"], name="Pedidos", marker_color="#E7D8C9")
    fig.add_scatter(
        x=daily["day"],
        y=daily["gmv"],
        name="GMV (R$)",
        yaxis="y2",
        line=dict(color=ACCENT, width=2),
        mode="lines",
    )
    fig.update_layout(
        yaxis=dict(title="Pedidos"),
        yaxis2=dict(title="GMV (R$)", overlaying="y", side="right", showgrid=False),
        barmode="overlay",
    )
    return _layout(fig, title)


def weekday_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    title = "Volume por hora e dia da semana"
    if df.empty:
        return _empty(title)

    tmp = df.copy()
    tmp["hour"] = tmp["ordered_at"].dt.hour
    tmp["weekday"] = tmp["ordered_at"].dt.day_of_week.map(WEEKDAY_LABELS)
    pivot = (
        tmp.groupby(["weekday", "hour"])
        .size()
        .unstack(fill_value=0)
        .reindex(list(WEEKDAY_LABELS.values()), fill_value=0)
    )
    hours = list(range(8, 24))
    for h in hours:
        if h not in pivot.columns:
            pivot[h] = 0
    pivot = pivot[hours]

    fig = px.imshow(
        pivot,
        color_continuous_scale=["#FFFBF7", "#FDBA74", "#C2410C", "#7C2D12"],
        aspect="auto",
        labels=dict(x="Hora", y="", color="Pedidos"),
    )
    fig.update_coloraxes(colorbar=dict(thickness=12, len=0.7))
    return _layout(fig, title)


def ranking_restaurants_by_note(df: pd.DataFrame, n: int = 12, min_orders: int = 25) -> go.Figure:
    title = "Piores notas entre parceiros com volume"
    delivered = df[df["status"] == "Entregue"] if not df.empty else df
    if delivered.empty:
        return _empty(title)

    ranked = (
        delivered.groupby("restaurant", as_index=False)
        .agg(pedidos=("order_id", "count"), nota=("rating", "mean"), tempo=("delivery_minutes", "mean"))
    )
    ranked = ranked[ranked["pedidos"] >= min_orders]
    if ranked.empty:
        ranked = (
            delivered.groupby("restaurant", as_index=False)
            .agg(pedidos=("order_id", "count"), nota=("rating", "mean"), tempo=("delivery_minutes", "mean"))
        )
    worst = ranked.sort_values("nota", ascending=True).head(n).sort_values("nota", ascending=False)
    fig = px.bar(
        worst,
        x="nota",
        y="restaurant",
        orientation="h",
        hover_data={"nota": ":.2f", "pedidos": True, "tempo": ":.1f"},
        color_discrete_sequence=[ACCENT],
    )
    fig.update_layout(xaxis_title="Nota", yaxis_title="", xaxis=dict(range=[1, 5]))
    return _layout(fig, title, height=420)


def ranking_restaurants(df: pd.DataFrame, top_n: int = 12) -> go.Figure:
    title = "GMV por restaurante (volume)"
    delivered = df[df["status"] == "Entregue"] if not df.empty else df
    if delivered.empty:
        return _empty(title)

    ranked = (
        delivered.groupby("restaurant", as_index=False)
        .agg(gmv=("order_value", "sum"), pedidos=("order_id", "count"), nota=("rating", "mean"))
        .sort_values("gmv", ascending=True)
        .tail(top_n)
    )
    fig = px.bar(
        ranked,
        x="gmv",
        y="restaurant",
        orientation="h",
        hover_data={"gmv": ":.0f", "pedidos": True, "nota": ":.2f"},
        color_discrete_sequence=[ACCENT],
    )
    fig.update_layout(xaxis_title="GMV (R$)", yaxis_title="")
    return _layout(fig, title, height=420)


def cuisine_mix(df: pd.DataFrame) -> go.Figure:
    title = "Pedidos por culinária"
    if df.empty:
        return _empty(title)
    counts = (
        df.groupby("cuisine", as_index=False)
        .size()
        .rename(columns={"size": "pedidos"})
        .sort_values("pedidos", ascending=False)
    )
    fig = px.bar(
        counts,
        x="cuisine",
        y="pedidos",
        color="cuisine",
        color_discrete_sequence=PALETTE,
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Pedidos")
    return _layout(fig, title)


def delivery_by_city(df: pd.DataFrame) -> go.Figure:
    title = "Tempo médio de entrega por cidade"
    delivered = df[df["status"] == "Entregue"] if not df.empty else df
    if delivered.empty:
        return _empty(title)

    stats = (
        delivered.groupby("city", as_index=False)
        .agg(tempo=("delivery_minutes", "mean"), pedidos=("order_id", "count"))
        .sort_values("tempo", ascending=False)
    )
    # cancel rate precisa do df completo por cidade
    cancel = df.groupby("city")["status"].apply(lambda s: (s == "Cancelado").mean())
    stats["cancel_rate"] = stats["city"].map(cancel)

    fig = px.bar(
        stats,
        x="tempo",
        y="city",
        orientation="h",
        hover_data={"tempo": ":.1f", "pedidos": True, "cancel_rate": ":.1%"},
        color="tempo",
        color_continuous_scale=["#FED7AA", "#C2410C"],
    )
    fig.update_layout(xaxis_title="Minutos", yaxis_title="", coloraxis_showscale=False)
    return _layout(fig, title)


def rating_distribution(df: pd.DataFrame) -> go.Figure:
    title = "Distribuição de notas"
    delivered = df[df["status"] == "Entregue"] if not df.empty else df
    if delivered.empty or delivered["rating"].dropna().empty:
        return _empty(title)

    counts = (
        delivered.dropna(subset=["rating"])
        .groupby("rating")
        .size()
        .reset_index(name="pedidos")
        .sort_values("rating")
    )
    fig = px.bar(
        counts,
        x="rating",
        y="pedidos",
        color_discrete_sequence=[ACCENT],
    )
    fig.update_layout(xaxis_title="Nota", yaxis_title="Pedidos", xaxis=dict(dtick=0.5))
    return _layout(fig, title)


def cancel_by_customer(df: pd.DataFrame) -> go.Figure:
    title = "Taxa de cancelamento por tipo de cliente"
    if df.empty:
        return _empty(title)
    stats = (
        df.groupby("customer_type", as_index=False)
        .agg(pedidos=("order_id", "count"))
    )
    cancel = df.groupby("customer_type")["status"].apply(lambda s: (s == "Cancelado").mean())
    stats["cancel_rate"] = stats["customer_type"].map(cancel)
    order = ["Novo", "Recorrente", "VIP"]
    stats["customer_type"] = pd.Categorical(stats["customer_type"], categories=order, ordered=True)
    stats = stats.sort_values("customer_type")

    fig = px.bar(
        stats,
        x="customer_type",
        y="cancel_rate",
        hover_data={"pedidos": True, "cancel_rate": ":.1%"},
        color_discrete_sequence=[ACCENT],
    )
    fig.update_layout(xaxis_title="", yaxis_title="Taxa de cancelamento", yaxis_tickformat=".0%")
    return _layout(fig, title)
