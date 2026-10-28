"""Pedidos mock de food delivery no Brasil (últimos 90 dias)."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

CITIES: list[tuple[str, float]] = [
    ("São Paulo", 0.26),
    ("Rio de Janeiro", 0.14),
    ("Belo Horizonte", 0.09),
    ("Curitiba", 0.08),
    ("Porto Alegre", 0.07),
    ("Brasília", 0.08),
    ("Salvador", 0.07),
    ("Recife", 0.07),
    ("Fortaleza", 0.07),
    ("Campinas", 0.07),
]

CUISINE_WEIGHTS: dict[str, float] = {
    "Brasileira": 0.16,
    "Pizza": 0.14,
    "Hambúrguer": 0.13,
    "Japonesa": 0.11,
    "Italiana": 0.09,
    "Árabe": 0.08,
    "Mexicana": 0.07,
    "Saudável": 0.08,
    "Doces & Sobremesas": 0.07,
    "Chinesa": 0.07,
}

CUISINE_TICKET: dict[str, float] = {
    "Brasileira": 1.00,
    "Pizza": 1.05,
    "Hambúrguer": 0.90,
    "Japonesa": 1.35,
    "Italiana": 1.20,
    "Árabe": 0.95,
    "Mexicana": 0.95,
    "Saudável": 1.15,
    "Doces & Sobremesas": 0.70,
    "Chinesa": 0.90,
}

CITY_SLA_PENALTY: dict[str, float] = {
    "São Paulo": 6.0,
    "Rio de Janeiro": 5.0,
    "Belo Horizonte": 2.0,
    "Curitiba": 1.5,
    "Porto Alegre": 2.0,
    "Brasília": 2.5,
    "Salvador": 3.0,
    "Recife": 3.0,
    "Fortaleza": 2.5,
    "Campinas": 1.5,
}

_NAME_PARTS: dict[str, tuple[list[str], list[str]]] = {
    "Brasileira": (
        ["Sabor", "Tempero", "Fogão", "Casa", "Quitute"],
        ["Mineiro", "da Vila", "do Sertão", "Caseiro", "da Palhoça"],
    ),
    "Pizza": (
        ["Pizzaria", "Forno", "Pizza"],
        ["Napolitana", "da Esquina", "90", "Prime", "do Bairro"],
    ),
    "Hambúrguer": (
        ["Burger", "Grill", "Smash"],
        ["House", "do Parque", "Lab", "Station", "da Rua"],
    ),
    "Japonesa": (
        ["Sushi", "Temaki", "Wasabi"],
        ["Express", "Garden", "da Praça", "Ko", "Bar"],
    ),
    "Italiana": (
        ["Cantina", "Trattoria", "Pasta"],
        ["Nonna", "di Roma", "do Centro", "Verde", "da Nonna"],
    ),
    "Árabe": (
        ["Esfiha", "Kebab", "Mezze"],
        ["do Líbano", "Express", "da Vila", "Golden", "House"],
    ),
    "Mexicana": (
        ["Taco", "Burrito", "Chili"],
        ["Loco", "del Sol", "Fiesta", "da Esquina", "Bar"],
    ),
    "Saudável": (
        ["Green", "Fit", "Horta"],
        ["Bowl", "Kitchen", "da Praça", "Light", "Company"],
    ),
    "Doces & Sobremesas": (
        ["Doce", "Açaí", "Chocolataria"],
        ["da Esquina", "House", "Berry", "do Parque", "Factory"],
    ),
    "Chinesa": (
        ["Wok", "Dragon", "Bao"],
        ["Express", "Garden", "da Liberdade", "House", "Box"],
    ),
}

CUSTOMER_TYPES = np.array(["Novo", "Recorrente", "VIP"])
CUSTOMER_PROBS = np.array([0.22, 0.63, 0.15])
PAYMENTS = np.array(["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"])
PAYMENT_PROBS = np.array([0.46, 0.32, 0.14, 0.08])

COLUMNS = [
    "order_id",
    "ordered_at",
    "city",
    "cuisine",
    "restaurant",
    "customer_type",
    "status",
    "order_value",
    "delivery_minutes",
    "rating",
    "promo",
    "payment",
    "distance_km",
]


def _weighted_choice(rng: np.random.Generator, items: Iterable[tuple[str, float]], size: int) -> np.ndarray:
    labels, weights = zip(*items)
    probs = np.array(weights, dtype=float)
    probs = probs / probs.sum()
    return rng.choice(np.array(labels), size=size, p=probs)


def _unique_restaurant_name(
    rng: np.random.Generator, cuisine: str, city: str, used: set[str]
) -> str:
    prefixes, suffixes = _NAME_PARTS[cuisine]
    for _ in range(40):
        name = f"{rng.choice(prefixes)} {rng.choice(suffixes)}"
        if name not in used:
            used.add(name)
            return name
    fallback = f"{prefixes[0]} {city}"
    used.add(fallback)
    return fallback


def _build_restaurants(rng: np.random.Generator, n: int = 100) -> pd.DataFrame:
    cities = _weighted_choice(rng, CITIES, n)
    cuisine_items = list(CUISINE_WEIGHTS.items())
    cuisines = _weighted_choice(rng, cuisine_items, n)
    used: set[str] = set()
    names = [
        _unique_restaurant_name(rng, cuisine, city, used)
        for cuisine, city in zip(cuisines, cities)
    ]
    popularity = rng.lognormal(mean=0.0, sigma=0.55, size=n)
    quality = rng.beta(7.5, 2.2, size=n)  # maioria boa, cauda ruim
    return pd.DataFrame(
        {
            "restaurant": names,
            "city": cities,
            "cuisine": cuisines,
            "popularity": popularity,
            "quality": quality,
        }
    )


def _sample_datetimes(
    rng: np.random.Generator, n: int, start: pd.Timestamp, end: pd.Timestamp
) -> np.ndarray:
    """Mais pedidos sexta–domingo e nos picos de almoço/jantar."""
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    dow = days.day_of_week.to_numpy()
    day_w = np.where(dow == 4, 1.35, np.where(dow >= 5, 1.45, 1.0))
    day_w = day_w / day_w.sum()
    chosen_days = rng.choice(days.to_numpy(), size=n, p=day_w)

    hours = np.arange(8, 24)
    hour_w = np.array(
        [0.4, 0.6, 1.1, 1.8, 2.2, 1.6, 1.0, 0.8, 0.7, 1.2, 2.4, 2.6, 2.1, 1.5, 1.1, 0.7],
        dtype=float,
    )
    hour_w = hour_w / hour_w.sum()
    chosen_hours = rng.choice(hours, size=n, p=hour_w)
    minutes = rng.integers(0, 60, size=n)
    seconds = rng.integers(0, 60, size=n)

    base = pd.to_datetime(chosen_days)
    return (
        base
        + pd.to_timedelta(chosen_hours, unit="h")
        + pd.to_timedelta(minutes, unit="m")
        + pd.to_timedelta(seconds, unit="s")
    ).to_numpy()


def generate_orders(
    n: int = 12_000,
    seed: int = 42,
    end: pd.Timestamp | None = None,
    n_restaurants: int = 100,
) -> pd.DataFrame:
    """Gera `n` pedidos nos 90 dias até `end` (padrão: hoje)."""
    if n <= 0:
        raise ValueError("n deve ser positivo")
    if n_restaurants <= 0:
        raise ValueError("n_restaurants deve ser positivo")

    rng = np.random.default_rng(seed)
    end_ts = pd.Timestamp(end) if end is not None else pd.Timestamp.now().normalize()
    start_ts = end_ts - pd.Timedelta(days=89)

    restaurants = _build_restaurants(rng, n=n_restaurants)
    weights = restaurants["popularity"].to_numpy()
    weights = weights / weights.sum()
    picked_idx = rng.choice(len(restaurants), size=n, p=weights)
    picked = restaurants.iloc[picked_idx].reset_index(drop=True)

    ordered_at = _sample_datetimes(rng, n, start_ts, end_ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    hours = pd.to_datetime(ordered_at).hour.to_numpy()

    customer_type = rng.choice(CUSTOMER_TYPES, size=n, p=CUSTOMER_PROBS)
    payment = rng.choice(PAYMENTS, size=n, p=PAYMENT_PROBS)

    novo = customer_type == "Novo"
    vip = customer_type == "VIP"
    promo = rng.random(n) < np.where(novo, 0.34, 0.20)

    cuisine_mult = picked["cuisine"].map(CUISINE_TICKET).to_numpy()
    ticket_mult = cuisine_mult * np.where(vip, 1.18, np.where(novo, 0.92, 1.0))
    ticket_mult = ticket_mult * np.where(promo, 0.88, 1.0)
    order_value = rng.lognormal(mean=3.72, sigma=0.42, size=n) * ticket_mult
    order_value = np.clip(order_value, 12.0, 280.0).round(2)

    distance_km = rng.gamma(shape=2.2, scale=1.7, size=n)
    distance_km = np.clip(distance_km, 0.6, 14.0).round(2)

    peak = ((hours >= 12) & (hours <= 14)).astype(float) * 3.0 + (
        (hours >= 18) & (hours <= 21)
    ).astype(float) * 6.5
    city_pen = picked["city"].map(CITY_SLA_PENALTY).to_numpy()
    quality = picked["quality"].to_numpy()

    delivery = (
        rng.gamma(shape=7.2, scale=3.4, size=n)
        + 2.6 * distance_km
        + city_pen
        + peak
        - 10.0 * quality
        + rng.normal(0, 2.4, size=n)
    )
    delivery = np.clip(delivery, 12.0, 95.0)

    cancel_p = (
        0.035
        + 0.09 * (1.0 - quality)
        + 0.015 * novo.astype(float)
        + 0.002 * np.maximum(0.0, delivery - 50.0)
    )
    cancel_p = np.clip(cancel_p, 0.015, 0.22)
    cancelled = rng.random(n) < cancel_p
    status = np.where(cancelled, "Cancelado", "Entregue")

    rating_raw = (
        2.7
        + 2.15 * quality
        - 0.028 * np.maximum(0.0, delivery - 32.0)
        + rng.normal(0, 0.28, size=n)
    )
    rating = np.clip(np.round(rating_raw * 2) / 2, 1.0, 5.0)
    rating = np.where(cancelled, np.nan, rating)
    delivery_out = np.where(cancelled, np.nan, delivery.round(1))

    order_id = np.array([f"PED-{i:06d}" for i in range(1, n + 1)])

    df = pd.DataFrame(
        {
            "order_id": order_id,
            "ordered_at": pd.to_datetime(ordered_at),
            "city": picked["city"].to_numpy(),
            "cuisine": picked["cuisine"].to_numpy(),
            "restaurant": picked["restaurant"].to_numpy(),
            "customer_type": customer_type,
            "status": status,
            "order_value": order_value,
            "delivery_minutes": delivery_out,
            "rating": rating,
            "promo": promo,
            "payment": payment,
            "distance_km": distance_km,
        }
    )
    return df.sort_values("ordered_at").reset_index(drop=True)
