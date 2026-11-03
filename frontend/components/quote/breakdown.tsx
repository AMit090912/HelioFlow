"use client";

import { ChevronDown } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { formatNumber, formatRupees } from "@/lib/format";
import type { QuoteOption, QuoteView } from "@/lib/quotes";

/** "See how we calculated this": every step from price to yearly savings, then assumptions. */
export function Breakdown({ option, quote }: { option: QuoteOption; quote: QuoteView }) {
  const t = useTranslations("quote");
  const locale = useLocale();
  const sv = option.savings;
  const rate = sv.savings_rate ? `₹${Number(sv.savings_rate).toFixed(2)}` : null;
  const rows: [string, string][] = [
    [t("b.price"), formatRupees(option.gross, locale)],
    [t("b.subsidy"), `− ${formatRupees(option.subsidy.amount, locale)}`],
    [t("b.net"), formatRupees(option.net, locale)],
    [t("b.generation"), t("b.unitsYear", { units: formatNumber(sv.annual_generation, locale, 0) })],
    [
      t("b.usable", { pct: formatNumber(Number(sv.usable_generation_pct) * 100, locale, 1) }),
      t("b.unitsYear", { units: formatNumber(sv.usable_generation, locale, 0) }),
    ],
    [t("b.rate"), rate ? t("b.perUnit", { rate }) : t("notAvailable")],
    [`${t("b.fixed")} (${t(`b.source.${sv.fixed_charge_source}`)})`, formatRupees(sv.fixed_charge, locale)],
    [t("b.savings"), sv.annual_savings ? formatRupees(sv.annual_savings, locale) : t("notAvailable")],
  ];
  const assumptions = ["price", "subsidy", "usable", "surplus", "fixed", "simple"] as const;

  return (
    <details className="group rounded-3xl border border-border bg-background">
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 font-medium text-ink sm:px-6 [&::-webkit-details-marker]:hidden">
        {t("breakdownToggle")}
        <ChevronDown className="size-5 text-ink-2 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-6 border-t border-border px-5 py-5 sm:px-6">
        <dl className="divide-y divide-border">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-4 py-2.5">
              <dt className="text-ink-2">{k}</dt>
              <dd className="shrink-0 font-medium text-ink tabular">{v}</dd>
            </div>
          ))}
        </dl>
        {quote.subsidy_rule ? (
          <p className="text-sm text-ink-2">
            {t("b.subsidyRule", { scheme: quote.subsidy_rule.scheme_code, date: quote.subsidy_rule.effective_from })}
          </p>
        ) : null}
        <div>
          <h3 className="font-semibold text-ink">{t("assumptionsTitle")}</h3>
          <ul className="mt-2 space-y-1.5 text-[0.9375rem] text-ink-2">
            {assumptions.map((k) => (
              <li key={k} className="flex gap-2">
                <span aria-hidden className="mt-2.5 size-1.5 shrink-0 rounded-full bg-gold" />
                {t(`assumptions.${k}`, { pct: formatNumber(Number(sv.usable_generation_pct) * 100, locale, 1) })}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}
