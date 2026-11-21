"""Formatação pt-BR para textos de alerta e do agente."""

from __future__ import annotations

import math
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import TypeGuard

WEEKDAYS: tuple[str, ...] = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
WEEKDAYS_SHORT: tuple[str, ...] = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def fold_text(text: str | None) -> str:
    """Minúsculas sem acento (NFD), mantendo espaços e sinais."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _br(text: str) -> str:
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _is_finite(value: float | None) -> TypeGuard[float]:
    return value is not None and math.isfinite(value)


def _format(value: float, digits: int) -> str:
    """Arredonda half-up e evita o zero negativo ('-0,00')."""
    if not math.isfinite(value):
        return "—"
    quantum = Decimal(1).scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = Decimal(0).quantize(quantum)
    return _br(f"{rounded:,.{digits}f}")


def brl(value: float | None) -> str:
    return "R$ " + _format(value, 2) if _is_finite(value) else "—"


def integer(value: float | None) -> str:
    return _format(value, 0) if _is_finite(value) else "—"


def decimal(value: float | None, digits: int = 1) -> str:
    """Número pt-BR sem unidade, para razões como '6,7×'."""
    return _format(value, digits) if _is_finite(value) else "—"


def pct(value: float | None, digits: int = 1) -> str:
    if not _is_finite(value):
        return "—"
    scaled = value * 100
    return _format(scaled, digits) + "%" if math.isfinite(scaled) else "—"


def minutes(value: float | None) -> str:
    return _format(value, 1) + " min" if _is_finite(value) else "—"


def km(value: float | None) -> str:
    return _format(value, 1) + " km" if _is_finite(value) else "—"


def pp(delta: float | None) -> str:
    """Diferença de taxas em pontos percentuais, com sinal (sem −0,0)."""
    if not _is_finite(delta):
        return "—"
    rounded = (Decimal(str(delta)) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if rounded == 0:
        return "+0,0 p.p."
    sign = "+" if rounded > 0 else "−"
    return sign + _br(f"{abs(rounded):,.1f}") + " p.p."
