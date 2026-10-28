from __future__ import annotations

import pandas as pd

from agent.insights import answer_question, detect_alerts, format_briefing
from dashboard.metrics import compute_kpis


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _order(
    *,
    city="São Paulo",
    restaurant="Casa Teste",
    status="Entregue",
    value=50.0,
    delivery=30.0,
    rating=4.5,
    customer="Recorrente",
    cuisine="Pizza",
    promo=False,
    hour=19,
) -> dict:
    return {
        "order_id": "x",
        "ordered_at": pd.Timestamp("2026-10-01") + pd.Timedelta(hours=hour),
        "city": city,
        "cuisine": cuisine,
        "restaurant": restaurant,
        "customer_type": customer,
        "status": status,
        "order_value": value,
        "delivery_minutes": delivery if status == "Entregue" else float("nan"),
        "rating": rating if status == "Entregue" else float("nan"),
        "promo": promo,
        "payment": "Pix",
        "distance_km": 3.0,
    }


def test_kpis_ignore_cancelled_in_gmv():
    df = _frame(
        [
            _order(status="Entregue", value=40),
            _order(status="Cancelado", value=80),
        ]
    )
    kpis = compute_kpis(df)
    assert kpis["orders"] == 2
    assert kpis["gmv"] == 40
    assert kpis["cancel_rate"] == 0.5


def test_empty_briefing():
    text = format_briefing(pd.DataFrame())
    assert "Nenhum pedido" in text


def test_high_cancel_raises_alert():
    rows = [_order(status="Cancelado", restaurant=f"R{i % 3}") for i in range(40)]
    rows += [_order(status="Entregue", restaurant=f"R{i % 3}") for i in range(10)]
    alerts = detect_alerts(_frame(rows))
    titles = " ".join(a.title.lower() for a in alerts)
    assert "cancelamento" in titles


def test_slow_delivery_raises_alert():
    rows = [_order(delivery=55, rating=4.6, restaurant="Lento") for _ in range(30)]
    alerts = detect_alerts(_frame(rows))
    assert any("entrega" in a.title.lower() or "sla" in a.title.lower() for a in alerts)


def test_local_ticket_question_uses_filtered_numbers():
    df = _frame([_order(value=80), _order(value=120)])
    reply = answer_question("Qual o ticket médio?", df, filter_desc="teste")
    assert "R$" in reply
    assert "100" in reply.replace(".", "").replace(",", "") or "100,00" in reply
