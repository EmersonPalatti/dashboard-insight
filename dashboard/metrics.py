"""KPIs do recorte filtrado."""

from __future__ import annotations

import pandas as pd


def _empty_kpis() -> dict[str, float]:
    return {
        "orders": 0.0,
        "gmv": 0.0,
        "avg_ticket": 0.0,
        "avg_delivery": 0.0,
        "avg_rating": 0.0,
        "cancel_rate": 0.0,
        "promo_rate": 0.0,
        "delivered": 0.0,
    }


def compute_kpis(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return _empty_kpis()

    delivered = df[df["status"] == "Entregue"]
    n = float(len(df))
    n_deliv = float(len(delivered))
    gmv = float(delivered["order_value"].sum()) if n_deliv else 0.0
    return {
        "orders": n,
        "gmv": gmv,
        "avg_ticket": gmv / n_deliv if n_deliv else 0.0,
        "avg_delivery": float(delivered["delivery_minutes"].mean()) if n_deliv else 0.0,
        "avg_rating": float(delivered["rating"].mean()) if n_deliv else 0.0,
        "cancel_rate": float((df["status"] == "Cancelado").mean()),
        "promo_rate": float(df["promo"].mean()),
        "delivered": n_deliv,
    }


def format_brl(value: float) -> str:
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_int(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", ".")


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def format_minutes(value: float) -> str:
    return f"{value:.1f} min".replace(".", ",")


def format_rating(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")
