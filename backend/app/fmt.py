"""Formatação pt-BR para textos de alerta e do agente."""

from __future__ import annotations


def _br(text: str) -> str:
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def brl(value: float | None) -> str:
    return "—" if value is None else "R$ " + _br(f"{value:,.2f}")


def integer(value: float | None) -> str:
    return "—" if value is None else _br(f"{value:,.0f}")


def pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else _br(f"{value * 100:.{digits}f}") + "%"


def minutes(value: float | None) -> str:
    return "—" if value is None else _br(f"{value:.1f}") + " min"


def km(value: float | None) -> str:
    return "—" if value is None else _br(f"{value:.1f}") + " km"


def pp(delta: float) -> str:
    """Diferença de taxas em pontos percentuais, com sinal."""
    return ("+" if delta >= 0 else "−") + _br(f"{abs(delta) * 100:.1f}") + " p.p."
