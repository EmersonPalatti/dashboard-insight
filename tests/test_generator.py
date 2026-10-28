from __future__ import annotations

import pandas as pd

from dashboard.filters import (
    Filters,
    active_filter_chips,
    apply_filters,
    is_default_recorte,
    period_label,
    recorte_fingerprint,
)
from data.generator import CITIES, COLUMNS, generate_orders

END = pd.Timestamp("2026-10-27")


def test_generate_shape_and_columns():
    df = generate_orders(n=800, seed=0, end=END, n_restaurants=40)
    assert len(df) == 800
    assert list(df.columns) == COLUMNS
    assert df["order_id"].is_unique
    assert df["ordered_at"].is_monotonic_increasing


def test_date_window_is_90_days():
    df = generate_orders(n=600, seed=1, end=END, n_restaurants=30)
    span = (df["ordered_at"].max().normalize() - df["ordered_at"].min().normalize()).days
    assert 70 <= span <= 89
    assert df["ordered_at"].max() < END + pd.Timedelta(days=1)
    assert df["ordered_at"].min() >= END - pd.Timedelta(days=89)


def test_domains_and_distributions():
    df = generate_orders(n=1000, seed=2, end=END, n_restaurants=50)
    cities = {c for c, _ in CITIES}
    assert set(df["city"]).issubset(cities)
    assert (df["order_value"] > 0).all()
    delivered = df[df["status"] == "Entregue"]
    cancelled = df[df["status"] == "Cancelado"]
    assert delivered["delivery_minutes"].between(12, 95).all()
    assert delivered["rating"].between(1, 5).all()
    assert cancelled["rating"].isna().all()
    assert cancelled["delivery_minutes"].isna().all()
    assert df["status"].isin(["Entregue", "Cancelado"]).all()
    assert df["customer_type"].isin(["Novo", "Recorrente", "VIP"]).all()
    assert 0.02 <= float((df["status"] == "Cancelado").mean()) <= 0.20


def test_seed_reproducible():
    a = generate_orders(n=200, seed=7, end=END, n_restaurants=20)
    b = generate_orders(n=200, seed=7, end=END, n_restaurants=20)
    pd.testing.assert_frame_equal(a, b)


def test_apply_filters_city_and_status():
    df = generate_orders(n=400, seed=3, end=END, n_restaurants=25)
    city = df["city"].iloc[0]
    filters = Filters(
        start=END - pd.Timedelta(days=89),
        end=END,
        cities=(city,),
        cuisines=(),
        restaurants=(),
        customer_types=(),
        statuses=("Entregue",),
    )
    out = apply_filters(df, filters)
    assert not out.empty
    assert set(out["city"]) == {city}
    assert set(out["status"]) == {"Entregue"}


def _filters(**overrides) -> Filters:
    base = dict(
        start=END - pd.Timedelta(days=89),
        end=END,
        cities=(),
        cuisines=(),
        restaurants=(),
        customer_types=(),
        statuses=(),
    )
    base.update(overrides)
    return Filters(**base)


def test_recorte_fingerprint_changes_with_city():
    a = recorte_fingerprint(_filters())
    b = recorte_fingerprint(_filters(cities=("São Paulo",)))
    assert a != b
    assert recorte_fingerprint(_filters()) == a


def test_period_label_single_day():
    one = _filters(start=END, end=END)
    assert "um dia" in period_label(one)
    assert END.date().isoformat() in period_label(one)


def test_active_chips_and_default_recorte():
    min_day = END - pd.Timedelta(days=89)
    full = _filters(start=min_day, end=END)
    assert is_default_recorte(full, min_day, END)
    assert active_filter_chips(full, min_day, END) == []
    tight = _filters(start=END, end=END, cities=("Recife",), statuses=("Cancelado",))
    chips = active_filter_chips(tight, min_day, END)
    assert any("um dia" in c for c in chips)
    assert "Recife" in chips
    assert "Cancelado" in chips
    assert not is_default_recorte(tight, min_day, END)
