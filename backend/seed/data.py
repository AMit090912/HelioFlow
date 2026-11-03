"""Seed values. Sources: client brief [CLIENT], ARCHITECTURE assumptions [A-n], or synthetic.

Synthetic values (staff names, emails, phones, roof areas, pincodes) are fictional and
labelled; they contain no real personal data.
"""

from datetime import date
from decimal import Decimal

STAFF = [
    {"role": "sales", "full_name": "HelioFlow Sales Desk", "email": "sales@helioflow.example"},
    {"role": "admin", "full_name": "HelioFlow Admin", "email": "admin@helioflow.example"},
]

# Names, ownership and monthly bill are from the brief's sample table [CLIENT].
HOMEOWNER_LEADS = [
    {
        "user": {
            "full_name": "Prashant Wankhede",
            "email": "prashant@helioflow.example",
            "phone": "9000000001",
        },
        "lead": {
            "code": "LD-30881",
            "ownership": "owner",
            "declared_monthly_bill": Decimal("3200"),
            "avg_monthly_units": Decimal("340"),
            "roof_area_sqft": Decimal("450"),
            "pincode": "440010",
        },
    },
    {
        "user": {
            "full_name": "Rohit Meshram",
            "email": "rohit@helioflow.example",
            "phone": "9000000002",
        },
        "lead": {
            "code": "LD-30902",
            "ownership": "tenant",
            "declared_monthly_bill": Decimal("1900"),
            "avg_monthly_units": Decimal("210"),
            "roof_area_sqft": Decimal("300"),
            "pincode": "440022",
        },
    },
    {
        "user": {
            "full_name": "Ayesha Siddiqui",
            "email": "ayesha@helioflow.example",
            "phone": "9000000003",
        },
        "lead": {
            "code": "LD-30915",
            "ownership": "owner",
            "declared_monthly_bill": Decimal("650"),
            "avg_monthly_units": Decimal("85"),
            "roof_area_sqft": Decimal("200"),
            "pincode": "440013",
        },
    },
]

LEAD_SEED_NOTE = (
    "Synthetic seed values: roof area, roof type, pincode, contact details. Not from brief. "
    "Ownership and monthly bill are from the brief."
)
CONSENT_VERSION = "2026-11-v1"

# §3.7. Decimals are stored as strings so JSON never turns them into floats.
SETTINGS = {
    "generation_kwh_per_kw_year": 1400,  # [CLIENT]
    "roof_sqft_per_kw": 100,  # [A-2]
    "min_monthly_bill_for_survey": 1000,  # [A-1]
    "capacity_options_kw": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # [A-9]
    "usable_generation_pct": "0.90",  # [A-6]
    "default_fixed_charge_monthly": 150,  # [A-8]
    "quote_option_offsets": [-1, 0, 1],  # [A-10]
}

PRICE_RULE = {
    "min_kw": Decimal("1"),
    "max_kw": Decimal("10"),
    "price_per_kw": Decimal("60000"),
    "gst_inclusive": True,
    "effective_from": date(2026, 1, 1),
    "effective_to": None,
    "note": "Placeholder (A-3). Client to confirm.",
}

SUBSIDY_RULE = {
    "scheme_code": "CENTRAL_RESIDENTIAL",
    "segment": "residential",
    "slabs": [
        {"from_kw": "0", "to_kw": "2", "amount_per_kw": "30000"},
        {"from_kw": "2", "to_kw": "3", "amount_per_kw": "18000"},
    ],
    "cap_amount": Decimal("78000"),
    "effective_from": date(2024, 2, 13),
    "effective_to": None,
    "source_note": (
        "Client-stated figures. Verify amounts and eligibility against the current "
        "official scheme before launch."
    ),
}
