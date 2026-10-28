"""Filtros da sidebar. Seleção vazia = todas as opções."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st


@dataclass(frozen=True)
class Filters:
    start: pd.Timestamp
    end: pd.Timestamp
    cities: tuple[str, ...]
    cuisines: tuple[str, ...]
    restaurants: tuple[str, ...]
    customer_types: tuple[str, ...]
    statuses: tuple[str, ...]


def recorte_fingerprint(filters: Filters) -> str:
    return "|".join(
        [
            filters.start.date().isoformat(),
            filters.end.date().isoformat(),
            ",".join(filters.cities),
            ",".join(filters.cuisines),
            ",".join(filters.restaurants),
            ",".join(filters.customer_types),
            ",".join(filters.statuses),
        ]
    )


def period_label(filters: Filters) -> str:
    start = filters.start.date().isoformat()
    end = filters.end.date().isoformat()
    if start == end:
        return f"um dia · {start}"
    return f"{start} a {end}"


def is_default_recorte(filters: Filters, min_day: pd.Timestamp, max_day: pd.Timestamp) -> bool:
    return (
        filters.start.normalize() == min_day.normalize()
        and filters.end.normalize() == max_day.normalize()
        and not filters.cities
        and not filters.cuisines
        and not filters.restaurants
        and not filters.customer_types
        and not filters.statuses
    )


def active_filter_chips(
    filters: Filters, min_day: pd.Timestamp, max_day: pd.Timestamp
) -> list[str]:
    chips: list[str] = []
    full_range = (
        filters.start.normalize() == min_day.normalize()
        and filters.end.normalize() == max_day.normalize()
    )
    if not full_range:
        chips.append(f"Período: {period_label(filters)}")
    chips.extend(filters.cities)
    chips.extend(filters.cuisines)
    chips.extend(filters.restaurants[:8])
    chips.extend(filters.customer_types)
    chips.extend(filters.statuses)
    return chips


def reset_filter_state(min_day: pd.Timestamp, max_day: pd.Timestamp) -> None:
    st.session_state.flt_period = (min_day.date(), max_day.date())
    st.session_state.flt_cities = []
    st.session_state.flt_cuisines = []
    st.session_state.flt_restaurants = []
    st.session_state.flt_customers = []
    st.session_state.flt_status = []


def _init_filter_state(min_day: pd.Timestamp, max_day: pd.Timestamp) -> None:
    if "flt_period" not in st.session_state:
        st.session_state.flt_period = (min_day.date(), max_day.date())
    st.session_state.setdefault("flt_cities", [])
    st.session_state.setdefault("flt_cuisines", [])
    st.session_state.setdefault("flt_restaurants", [])
    st.session_state.setdefault("flt_customers", [])
    st.session_state.setdefault("flt_status", [])


def render_filters(df: pd.DataFrame) -> tuple[Filters, pd.Timestamp, pd.Timestamp]:
    min_day = pd.Timestamp(df["ordered_at"].min()).normalize()
    max_day = pd.Timestamp(df["ordered_at"].max()).normalize()
    _init_filter_state(min_day, max_day)

    st.sidebar.header("Recorte")
    st.sidebar.caption("Tudo na página usa só este recorte.")
    if st.sidebar.button("Limpar recorte", width="stretch", key="clear_recorte_side"):
        reset_filter_state(min_day, max_day)
        st.rerun()

    period = st.sidebar.date_input(
        "Período",
        min_value=min_day.date(),
        max_value=max_day.date(),
        key="flt_period",
    )
    if isinstance(period, tuple) and len(period) == 2:
        start_date, end_date = period
    else:
        start_date = end_date = period
    if start_date == end_date:
        st.sidebar.caption(f"Um dia: {start_date.isoformat()}")

    empty_all = "Vazio = todas"
    cities = st.sidebar.multiselect(
        "Cidade",
        sorted(df["city"].unique()),
        help=empty_all,
        key="flt_cities",
    )
    cuisines = st.sidebar.multiselect(
        "Culinária",
        sorted(df["cuisine"].unique()),
        help=empty_all,
        key="flt_cuisines",
    )

    restaurant_pool = df
    if cities:
        restaurant_pool = restaurant_pool[restaurant_pool["city"].isin(cities)]
    if cuisines:
        restaurant_pool = restaurant_pool[restaurant_pool["cuisine"].isin(cuisines)]
    restaurants = st.sidebar.multiselect(
        "Restaurante",
        sorted(restaurant_pool["restaurant"].unique()),
        help="Vazio = todos",
        key="flt_restaurants",
    )

    customer_types = st.sidebar.multiselect(
        "Tipo de cliente",
        ["Novo", "Recorrente", "VIP"],
        help=empty_all,
        key="flt_customers",
    )
    statuses = st.sidebar.multiselect(
        "Status",
        ["Entregue", "Cancelado"],
        help=empty_all,
        key="flt_status",
    )

    filters = Filters(
        start=pd.Timestamp(start_date),
        end=pd.Timestamp(end_date),
        cities=tuple(cities),
        cuisines=tuple(cuisines),
        restaurants=tuple(restaurants),
        customer_types=tuple(customer_types),
        statuses=tuple(statuses),
    )
    return filters, min_day, max_day


def apply_filters(df: pd.DataFrame, filters: Filters) -> pd.DataFrame:
    end_exclusive = filters.end + pd.Timedelta(days=1)
    out = df[(df["ordered_at"] >= filters.start) & (df["ordered_at"] < end_exclusive)]
    if filters.cities:
        out = out[out["city"].isin(filters.cities)]
    if filters.cuisines:
        out = out[out["cuisine"].isin(filters.cuisines)]
    if filters.restaurants:
        out = out[out["restaurant"].isin(filters.restaurants)]
    if filters.customer_types:
        out = out[out["customer_type"].isin(filters.customer_types)]
    if filters.statuses:
        out = out[out["status"].isin(filters.statuses)]
    return out.copy()


def describe_filters(filters: Filters, n_total: int, n_filtered: int) -> str:
    bits = [
        f"período {period_label(filters)}",
        f"{n_filtered} de {n_total} pedidos",
    ]
    if filters.cities:
        bits.append("cidades: " + ", ".join(filters.cities))
    if filters.cuisines:
        bits.append("culinárias: " + ", ".join(filters.cuisines))
    if filters.restaurants:
        bits.append("restaurantes: " + ", ".join(filters.restaurants[:8]))
    if filters.customer_types:
        bits.append("clientes: " + ", ".join(filters.customer_types))
    if filters.statuses:
        bits.append("status: " + ", ".join(filters.statuses))
    return " · ".join(bits)
