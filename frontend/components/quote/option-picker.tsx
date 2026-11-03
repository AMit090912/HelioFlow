"use client";

import { useLocale, useTranslations } from "next-intl";

import { paybackText } from "@/components/quote/quote-hero";
import { formatKw, formatRupees } from "@/lib/format";
import type { QuoteOption } from "@/lib/quotes";
import { cn } from "@/lib/utils";

/** Native radios as large cards: one per size the quote offers. */
export function OptionPicker({
  options,
  value,
  onChange,
  disabled,
}: {
  options: QuoteOption[];
  value: string;
  onChange: (kw: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("quote");
  const locale = useLocale();
  return (
    <fieldset>
      <legend className="font-display text-xl font-semibold text-ink">{t("options")}</legend>
      <p className="mt-1 text-[0.9375rem] text-ink-2">{t("optionsHint")}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {options.map((o) => {
          const checked = Number(o.kw) === Number(value);
          return (
            <label
              key={o.kw}
              className={cn(
                "relative flex cursor-pointer flex-col gap-1 rounded-2xl border bg-background p-4 transition-colors",
                "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-teal",
                checked ? "border-teal bg-teal-wash/50 ring-1 ring-teal" : "border-border hover:border-teal/50",
                disabled && "cursor-default",
              )}
            >
              <input
                type="radio"
                name="size"
                value={o.kw}
                checked={checked}
                onChange={() => onChange(o.kw)}
                disabled={disabled}
                className="sr-only"
              />
              <span className="flex items-center justify-between gap-2">
                <span className="font-display text-2xl font-semibold text-ink tabular">{formatKw(o.kw, locale)}</span>
                {o.recommended ? (
                  <span className="rounded-full bg-night px-2 py-0.5 text-[0.75rem] font-medium text-gold-soft">{t("suggested")}</span>
                ) : null}
              </span>
              <span className="font-medium text-ink tabular">{formatRupees(o.net, locale)}</span>
              <span className="text-sm text-ink-2">
                {o.savings.annual_savings ? t("savesYear", { amount: formatRupees(o.savings.annual_savings, locale) }) : t("notAvailable")}
              </span>
              <span className="text-sm text-ink-2">
                {t("payback")}: {paybackText(o, t)}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
