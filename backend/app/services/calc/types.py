"""Engine inputs. Frozen and Decimal-only: the calc package never sees ORM rows or floats."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Settings:
    """Business settings (ARCHITECTURE §3.7), already validated by rules_repo."""

    generation_kwh_per_kw_year: Decimal  # [CLIENT] 1,400
    roof_sqft_per_kw: Decimal  # [A-2]
    min_monthly_bill_for_survey: Decimal  # [A-1]
    capacity_options_kw: tuple[Decimal, ...]  # [A-9], ascending
    usable_generation_pct: Decimal  # [A-6], 0 < U ≤ 1
    default_fixed_charge_monthly: Decimal  # [A-8]
    quote_option_offsets: tuple[int, ...]  # [A-10]


@dataclass(frozen=True)
class PriceRule:
    id: str
    min_kw: Decimal
    max_kw: Decimal
    price_per_kw: Decimal
    gst_inclusive: bool
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True)
class SubsidySlab:
    from_kw: Decimal
    to_kw: Decimal
    amount_per_kw: Decimal


@dataclass(frozen=True)
class SubsidyRule:
    id: str
    scheme_code: str
    segment: str
    slabs: tuple[SubsidySlab, ...]
    cap_amount: Decimal
    effective_from: date
    effective_to: date | None
    source_note: str
