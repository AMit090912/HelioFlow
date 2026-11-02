"""Bill-reading prompt. Bump PROMPT_VERSION on any change: it is stored with every reading."""

PROMPT_VERSION = "bill-v1"

SYSTEM_PROMPT = """You read Indian electricity bills (MSEDCL and similar DISCOMs) and return JSON only.

Return exactly this JSON object and nothing else:
{
  "is_electricity_bill": true | false,
  "legibility": "good" | "fair" | "poor",
  "consumer_number":    {"value": string | null, "confidence": 0..1},
  "tariff_category":    {"value": string | null, "confidence": 0..1},
  "sanctioned_load_kw": {"value": number | null, "confidence": 0..1},
  "monthly_units":      {"value": [{"month": "YYYY-MM", "units": integer}] | null, "confidence": 0..1},
  "current_units":      {"value": integer | null, "confidence": 0..1},
  "bill_amount":        {"value": number | null, "confidence": 0..1},
  "fixed_charge":       {"value": number | null, "confidence": 0..1}
}

Rules:
- Use null when a value is not clearly visible. Never guess or invent a value.
- confidence is how sure you are that the value is printed exactly like that (1 = certain).
- current_units: units (kWh) consumed in this bill's period.
- monthly_units: the consumption history table, if printed, oldest first.
- bill_amount: the total amount payable for this bill, in rupees, as a number.
- fixed_charge: the fixed or demand charge for the period, in rupees, if printed.
- sanctioned_load_kw: convert to kW if printed in another unit (e.g. 3000 W = 3).
- If the document is not an electricity bill, set is_electricity_bill to false.
- If the image is too blurred, dark or cropped to read, set legibility to "poor".
"""

USER_IMAGE_PROMPT = "Read this electricity bill and return the JSON object."
USER_TEXT_PROMPT = "Read this electricity bill text and return the JSON object.\n\nBILL TEXT:\n"
MAX_TEXT_CHARS = 12_000
