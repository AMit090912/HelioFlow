"""Quote options filtered by verified roof capacity and sanctioned load (ARCHITECTURE §8).

An option above either limit is never offered; the reason is reported so the quote builder
can say why ("4 kW removed: sanctioned load is 3 kW"). A recommendation above the load is
flagged by sizing and simply not offered here — never silently capped.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.calc.errors import CalcError
from app.services.calc.sizing import kw_by_roof
from app.services.calc.types import Settings


@dataclass(frozen=True)
class OptionSet:
    offered: tuple[Decimal, ...]
    removed: tuple[dict[str, str], ...]  # {"kw": "4", "reason": "roof" | "sanctioned_load"}
    max_allowed_kw: Decimal


def quote_options(
    *,
    recommended_kw: Decimal | None,
    verified_roof_sqft: Decimal | None,
    sanctioned_load_kw: Decimal | None,
    settings: Settings,
) -> OptionSet:
    if verified_roof_sqft is None:
        raise CalcError("ROOF_NOT_VERIFIED", "Verify the roof area before quoting.")
    if sanctioned_load_kw is None:
        raise CalcError("SANCTIONED_LOAD_UNKNOWN", "Enter the sanctioned load before quoting.")
    roof_kw = kw_by_roof(verified_roof_sqft, settings)
    if recommended_kw is None or roof_kw is None:
        raise CalcError("NO_OPTION_FITS", "No system fits the verified roof.")

    # Offsets are steps through the configured option list (A-10), so "one either side" means
    # the neighbouring sizes even when options are 1, 2, 3, 5, 7… or in 0.5 kW steps.
    sizes = settings.capacity_options_kw
    if recommended_kw not in sizes:
        raise CalcError(
            "INVALID_INPUT",
            "The recommended size is not a configured option.",
            field="recommended_kw",
        )
    at = sizes.index(recommended_kw)
    picks = {at + step for step in settings.quote_option_offsets if 0 <= at + step < len(sizes)}
    candidates = [sizes[i] for i in sorted(picks)]
    offered: list[Decimal] = []
    removed: list[dict[str, str]] = []
    for kw in candidates:
        if kw > roof_kw:
            removed.append({"kw": str(kw), "reason": "roof"})
        elif kw > sanctioned_load_kw:
            removed.append({"kw": str(kw), "reason": "sanctioned_load"})
        else:
            offered.append(kw)

    if not offered:
        raise CalcError("NO_OPTION_FITS", "No system fits the verified roof and sanctioned load.")
    return OptionSet(
        offered=tuple(offered),
        removed=tuple(removed),
        max_allowed_kw=min(roof_kw, sanctioned_load_kw),
    )
