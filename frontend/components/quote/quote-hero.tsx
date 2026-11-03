"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatKw, formatRupees } from "@/lib/format";
import type { QuoteOption } from "@/lib/quotes";

export function paybackText(option: QuoteOption, t: ReturnType<typeof useTranslations<"quote">>): string {
  if (option.payback.status === "ok") return t("paybackYears", { years: option.payback.years ?? "" });
  if (option.payback.status === "immediate") return t("paybackImmediate");
  return t("notAvailable");
}

/**
 * The quote told in three numbers (§20): size → cost after subsidy → payback (estimate).
 * Stacked on a gold thread on phones, side by side on wider screens; follows the chosen size.
 */
export function QuoteHero({ option }: { option: QuoteOption }) {
  const t = useTranslations("quote");
  const locale = useLocale();
  const figures = [
    { label: t("size"), value: formatKw(option.kw, locale) },
    { label: t("net"), value: formatRupees(option.net, locale) },
    { label: t("payback"), value: paybackText(option, t), note: t("estimate") },
  ];
  return (
    <section aria-live="polite" className="relative overflow-hidden rounded-3xl bg-night px-6 py-7 text-white sm:px-9 sm:py-9">
      {/* The sun setting on the hero's edge: kept clear of the figures. */}
      <div aria-hidden className="pointer-events-none absolute -bottom-28 -right-20 size-56 rounded-full bg-gold/12" />
      <div aria-hidden className="pointer-events-none absolute -bottom-12 -right-6 size-20 rounded-full bg-gold/75" />
      <ol className="relative grid gap-6 sm:grid-cols-3 sm:gap-8 sm:pr-10">
        {figures.map((f, i) => (
          <li key={f.label} className="relative pl-6 sm:pl-0">
            {/* The thread joining the three numbers (phone): a sentence read top to bottom. */}
            <span aria-hidden className="absolute left-0 top-2 size-2.5 rounded-full bg-gold sm:hidden" />
            {i < figures.length - 1 ? (
              <span aria-hidden className="absolute left-[0.28rem] top-5 h-[calc(100%+0.5rem)] w-px bg-gold/50 sm:hidden" />
            ) : null}
            <p className="text-sm text-gold-soft">{f.label}</p>
            <p className="font-display mt-1 text-[2rem] font-semibold leading-tight tabular sm:text-[2.25rem]">{f.value}</p>
            {f.note ? <p className="mt-0.5 text-[0.8125rem] text-white/60">{f.note}</p> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
