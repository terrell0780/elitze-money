"""Unit tests for pure metric computations."""

from __future__ import annotations

from decimal import Decimal

from elitze.domain.metrics import conversion_rate, money, profit, roi


def test_money_rounds_half_up() -> None:
    assert money("12.345") == Decimal("12.35")
    assert money("12.344") == Decimal("12.34")
    assert money(7) == Decimal("7.00")


def test_profit() -> None:
    assert profit(Decimal("100"), Decimal("40")) == Decimal("60.00")


def test_roi() -> None:
    assert roi(Decimal("150"), Decimal("100")) == Decimal("50.00")
    assert roi(Decimal("50"), Decimal("100")) == Decimal("-50.00")
    assert roi(Decimal("100"), Decimal("0")) is None


def test_conversion_rate() -> None:
    assert conversion_rate(3, 100) == Decimal("3.00")
    assert conversion_rate(0, 0) is None
