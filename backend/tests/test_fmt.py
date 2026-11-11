"""Arredondamento pt-BR: half-up, sem zero negativo."""

from __future__ import annotations

from app.fmt import brl, decimal, integer, pct


def test_brl_groups_thousands_and_uses_comma():
    assert brl(1234.56) == "R$ 1.234,56"
    assert brl(None) == "—"


def test_brl_half_up_to_cents_and_no_negative_zero():
    assert brl(1.005) == "R$ 1,01"
    assert brl(-1.005) == "R$ -1,01"
    assert brl(-0.004) == "R$ 0,00"
    assert brl(-1234.5) == "R$ -1.234,50"


def test_integer_half_up():
    assert integer(2.5) == "3"
    assert integer(-1.5) == "-2"
    assert integer(-0.4) == "0"
    assert integer(1234.4) == "1.234"
    assert integer(None) == "—"


def test_pct_one_decimal():
    assert pct(0.046) == "4,6%"
    assert pct(-0.046) == "-4,6%"
    assert pct(None) == "—"


def test_decimal_helper_uses_comma():
    assert decimal(6.66) == "6,7"
    assert decimal(6.64) == "6,6"
    assert decimal(-1.25, digits=1) == "-1,3"
    assert decimal(None) == "—"
