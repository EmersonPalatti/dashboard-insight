"""Formatação pt-BR para textos de alerta e do agente."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def _br(text: str) -> str:
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _format(value: float, digits: int) -> str:
    """Arredonda half-up e evita o zero negativo ('-0,00')."""
    quantum = Decimal(1).scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = Decimal(0).quantize(quantum)
    return _br(f"{rounded:,.{digits}f}")


def brl(value: float | None) -> str:
    return "—" if value is None else "R$ " + _format(value, 2)


def integer(value: float | None) -> str:
    return "—" if value is None else _format(value, 0)


def decimal(value: float | None, digits: int = 1) -> str:
    """Número pt-BR sem unidade, para razões como '6,7×'."""
    return "—" if value is None else _format(value, digits)


def pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else _format(value * 100, digits) + "%"


def minutes(value: float | None) -> str:
    return "—" if value is None else _format(value, 1) + " min"


def km(value: float | None) -> str:
    return "—" if value is None else _format(value, 1) + " km"


def pp(delta: float) -> str:
    """Diferença de taxas em pontos percentuais, com sinal."""
    return ("+" if delta >= 0 else "−") + _format(abs(delta) * 100, 1) + " p.p."
