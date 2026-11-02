"""Output rounding only (§15.1): intermediate values keep full Decimal precision."""

from decimal import ROUND_HALF_UP, Decimal

_RUPEE = Decimal("1")
_TENTH = Decimal("0.1")


def rupees(value: Decimal) -> Decimal:
    return value.quantize(_RUPEE, rounding=ROUND_HALF_UP)


def one_decimal(value: Decimal) -> Decimal:
    return value.quantize(_TENTH, rounding=ROUND_HALF_UP)


def whole(value: Decimal) -> int:
    return int(value.quantize(_RUPEE, rounding=ROUND_HALF_UP))
