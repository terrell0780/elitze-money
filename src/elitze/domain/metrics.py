"""Pure metric computations shared by the engine.

All money math is performed with :class:`decimal.Decimal` to avoid float
rounding errors in revenue accounting.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_MONEY = Decimal("0.01")


def money(value: object, default: str = "0.00") -> Decimal:
    """Coerce a value to a 2-decimal money Decimal."""
    try:
        d = Decimal(str(value))
    except Exception:
        d = Decimal(default)
    return d.quantize(_MONEY, rounding=ROUND_HALF_UP)


def profit(revenue: Decimal, spend: Decimal) -> Decimal:
    return money(revenue - spend)


def roi(revenue: Decimal, spend: Decimal) -> Decimal | None:
    spend = money(spend)
    if spend == 0:
        return None
    return money(((money(revenue) - spend) / spend) * 100)


def conversion_rate(conversions: int, impressions: int) -> Decimal | None:
    if impressions <= 0:
        return None
    return money((Decimal(conversions) / Decimal(impressions)) * 100)


def clamp_roi(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value
