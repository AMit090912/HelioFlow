/** Staff screens are English (A-28). Labels for the codes the API returns live here, once. */

import type { ScoreReason } from "@/lib/staff";

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  bill_processing: "Reading bill",
  bill_review: "Bill to confirm",
  qualified: "Qualified",
  survey_pending: "Survey to schedule",
  call_pending: "Call first",
  surveyed: "Surveyed",
  quoted: "Quote sent",
  accepted: "Quote accepted",
  converted: "Project started",
  closed_lost: "Closed",
};

export const NEXT_ACTION_LABEL: Record<string, string> = {
  survey_visit: "Survey visit",
  call: "Call",
};

export const FLAG_LABEL: Record<string, string> = {
  roof_unverified: "Roof not verified",
  roof_too_small: "Roof too small for 1 kW",
  usage_zero: "Zero units on bill",
  usage_exceeds_max_option: "Usage above largest option",
  sanctioned_load_unknown: "Sanctioned load unknown",
  exceeds_sanctioned_load: "Above sanctioned load",
  bill_unverified: "Bill not confirmed",
};

export function reasonText(reason: ScoreReason): string {
  switch (reason.code) {
    case "tenant":
      return "Tenant: needs landlord's consent";
    case "bill_below_threshold":
      return `Bill ₹${reason.value} is below ₹${reason.threshold}`;
    case "roof_too_small":
      return "Roof too small for the smallest system";
    case "usage_unknown":
      return "Units not known";
    case "usage_zero":
      return "Zero units on the bill";
    default:
      return reason.code.replaceAll("_", " ");
  }
}

export const READING_FIELDS: { key: string; ai?: string; label: string; unit?: string }[] = [
  { key: "avg_monthly_units", label: "Average units / month", unit: "units" },
  { key: "bill_amount", ai: "bill_amount", label: "Bill amount", unit: "₹" },
  { key: "sanctioned_load_kw", ai: "sanctioned_load_kw", label: "Sanctioned load", unit: "kW" },
  { key: "fixed_charge_monthly", ai: "fixed_charge", label: "Fixed charge / month", unit: "₹" },
  { key: "consumer_number", ai: "consumer_number", label: "Consumer number" },
  { key: "tariff_category", ai: "tariff_category", label: "Tariff category" },
];

export const CALC_ERROR_TEXT: Record<string, string> = {
  ROOF_NOT_VERIFIED: "Verify the roof area (survey or call) before building a quote.",
  NO_RECOMMENDATION: "There is no size to recommend: the confirmed bill shows no usage. Check the units with the homeowner.",
  SANCTIONED_LOAD_UNKNOWN: "Enter the sanctioned load from the bill or the DISCOM record.",
  NO_OPTION_FITS: "No system fits the verified roof and sanctioned load.",
  NOT_QUOTABLE_TENANT: "Tenants aren't quoted under the current rules.",
  BILL_NOT_CONFIRMED: "The homeowner hasn't confirmed a bill yet.",
  PRICE_RULE_MISSING: "No price rule covers today's date. Add one in Rules.",
  SUBSIDY_RULE_MISSING: "No subsidy rule covers today's date. Add one in Rules.",
  USAGE_UNKNOWN: "Units are unknown, so savings can't be estimated.",
  INVALID_INPUT: "An override is out of range.",
  OVERRIDE_REASON_REQUIRED: "Give a reason for each override before sending.",
  OVERRIDE_DUPLICATE: "Each value can be overridden once.",
  LEAD_STATUS_CONFLICT: "This lead can't be quoted in its current status.",
  REASON_REQUIRED: "Give a short reason (at least 5 characters).",
};

export function errorText(code: string, fallback = "Something went wrong. Try again."): string {
  return CALC_ERROR_TEXT[code] ?? fallback;
}

export function age(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days} days ago`;
}

export function when(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export const STAGE_LABEL: Record<string, string> = {
  advance_received: "Advance received",
  installation_scheduled: "Installation scheduled",
  installation_completed: "Installation completed",
  net_metering_completed: "Net metering completed",
  subsidy_applied: "Subsidy application submitted",
  subsidy_credited: "Subsidy credited",
};

export const PROJECT_ERROR_TEXT: Record<string, string> = {
  STAGE_NOT_NEXT: "Someone else moved this project. Refresh to see the latest stage.",
  REASON_REQUIRED: "Give a short reason (at least 5 characters).",
  DATE_IN_PAST: "The installation date can't be in the past.",
  DATE_TOO_FAR: "Pick an installation date within two years.",
  ADVANCE_TOO_LARGE: "The advance can't be more than the cost after subsidy.",
  LEAD_STATUS_CONFLICT: "An advance can be recorded only after the homeowner accepts a quote.",
  RULE_INVALID: "The end date must be on or after the start date.",
  GST_EXCLUSIVE: "Prices must include GST (no GST rate is configured).",
  SETTING_INVALID: "That value isn't allowed for this setting.",
  VALIDATION_ERROR: "Some values need checking.",
  FORBIDDEN: "Only an admin can change rules.",
};

export function projectError(code: string, fallback = "Something went wrong. Try again."): string {
  return PROJECT_ERROR_TEXT[code] ?? CALC_ERROR_TEXT[code] ?? fallback;
}
