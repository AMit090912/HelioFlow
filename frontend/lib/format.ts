/**
 * Numbers as people in India read them. The API sends decimals as plain strings ("3200.5"), so
 * these helpers take strings or numbers and never round money silently beyond what is shown.
 */

const LOCALE_TAG: Record<string, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };

/** For words (month names). */
function tag(locale: string): string {
  return LOCALE_TAG[locale] ?? "en-IN";
}

/**
 * For numbers: always en-IN. Western digits with Indian grouping (₹1,02,000) in every language
 * (A-27). mr-IN would group as ₹102,000, so the language must not pick the number format.
 */
const NUMBER_LOCALE = "en-IN";

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/** ₹1,02,000 — Indian digit grouping, Latin digits in every language (bills use them too). */
export function formatRupees(
  value: string | number | null | undefined,
  locale: string,
  fractionDigits = 0,
): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return new Intl.NumberFormat(NUMBER_LOCALE, {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
    numberingSystem: "latn",
  }).format(n);
}

/** 1,02,000 / 3.5 — plain grouped number with up to `maxDigits` decimals. */
export function formatNumber(
  value: string | number | null | undefined,
  locale: string,
  maxDigits = 2,
): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return new Intl.NumberFormat(NUMBER_LOCALE, {
    maximumFractionDigits: maxDigits,
    numberingSystem: "latn",
  }).format(n);
}

/** "3 kW" — the unit stays Latin; it is how it is written on bills and panels. */
export function formatKw(value: string | number | null | undefined, locale: string): string {
  const n = toNumber(value);
  return n === null ? "—" : `${formatNumber(n, locale, 2)} kW`;
}

const DEVANAGARI_DIGITS = /[०-९]/g;
// Thousands separators only: Indian (1,00,000) or Western (100,000) grouping. "3,5" is not a
// number here: as a decimal comma it would otherwise become 35.
const GROUPED = /^\d{1,3}(?:(?:,\d{2})*,\d{3}|(?:,\d{3})+)(?:\.\d+)?$/;

/** Turns what a person typed ("3,200", " ३२०० ", "₹1,00,000") into the plain decimal string the
 *  API takes, or null when it isn't a number. Hindi/Marathi digits are read as digits. */
export function parseDecimalInput(raw: string): string | null {
  const latin = raw.replace(DEVANAGARI_DIGITS, (d) => String(d.charCodeAt(0) - 0x0966));
  const compact = latin.replace(/[\s₹]/g, "");
  if (compact.includes(",") && !GROUPED.test(compact)) return null;
  const cleaned = compact.replace(/,/g, "");
  if (cleaned === "" || !/^\d+(\.\d+)?$/.test(cleaned)) return null;
  return cleaned;
}

/** At most two decimal places (paise, or a hundredth of a unit or kW): what the database keeps. */
export function hasAtMostTwoDecimals(value: string): boolean {
  return !/\.\d{3,}$/.test(value);
}

/** "340.00" → "340", "3.0" → "3": a decimal string as a person would type it. */
export function plainDecimal(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const s = String(value);
  if (!/^-?\d+(\.\d+)?$/.test(s)) return s;
  return s.includes(".") ? s.replace(/\.?0+$/, "") : s;
}

/** "2026-05" → "May 26" (localised month); anything else is shown as read. */
export function formatBillMonth(month: string, locale: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(month);
  if (!m) return month;
  const date = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, 1));
  return new Intl.DateTimeFormat(tag(locale), { month: "short", year: "2-digit", timeZone: "UTC", numberingSystem: "latn" }).format(date);
}

/** "3 November 2026" in the reader's language, Western digits, India time. Accepts
 * a date ("2026-11-08") or a timestamp. */
export function formatDay(iso: string, locale: string): string {
  const instant = iso.length === 10 ? `${iso}T00:00:00+05:30` : iso;
  return new Intl.DateTimeFormat(tag(locale), {
    day: "numeric",
    month: "long",
    year: "numeric",
    numberingSystem: "latn",
    timeZone: "Asia/Kolkata",
  }).format(new Date(instant));
}
