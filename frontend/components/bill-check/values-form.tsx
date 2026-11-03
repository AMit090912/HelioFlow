"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Loader2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { describedBy, Field, UnitInput } from "@/components/lead-form/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { formatBillMonth, formatNumber, parseDecimalInput, plainDecimal } from "@/lib/format";
import { useConfirmReading, type ConfirmValues, type Reading } from "@/lib/leads";
import { cn } from "@/lib/utils";

type FieldName =
  | "avg_monthly_units"
  | "bill_amount"
  | "sanctioned_load_kw"
  | "consumer_number"
  | "tariff_category"
  | "fixed_charge_monthly";

// The AI reports flags against what it read; map them onto the fields the person edits.
const FLAG_FIELD: Record<string, FieldName> = {
  current_units: "avg_monthly_units",
  monthly_units: "avg_monthly_units",
  bill_amount: "bill_amount",
  sanctioned_load_kw: "sanctioned_load_kw",
  consumer_number: "consumer_number",
  tariff_category: "tariff_category",
  fixed_charge: "fixed_charge_monthly",
};
const FLAG_ORDER = ["missing", "out_of_range", "differs_from_declared", "rate_unusual", "format_unusual", "low_confidence"];

function flagsByField(reading: Reading): Partial<Record<FieldName, string>> {
  const out: Partial<Record<FieldName, string>> = {};
  for (const [source, codes] of Object.entries(reading.flags ?? {})) {
    const field = FLAG_FIELD[source];
    if (!field) continue;
    const best = [...codes].sort((a, b) => FLAG_ORDER.indexOf(a) - FLAG_ORDER.indexOf(b))[0];
    const existing = out[field];
    if (!existing || FLAG_ORDER.indexOf(best) < FLAG_ORDER.indexOf(existing)) out[field] = best;
  }
  return out;
}

const s = plainDecimal;

/**
 * The values a person confirms. In "review" mode the AI's reading pre-fills the form; in
 * "manual" mode it starts empty. Either way confirm sends every field explicitly (empty → null),
 * so what is on screen is exactly what is saved (Review Focus 4).
 */
export function ValuesForm({
  reading,
  mode,
  onConfirmed,
}: {
  reading: Reading;
  mode: "review" | "manual";
  onConfirmed: (reading: Reading) => void;
}) {
  const t = useTranslations("billCheck");
  const te = useTranslations("errors");
  const locale = useLocale();
  const confirm = useConfirmReading(reading.id);
  const [formError, setFormError] = useState<string | null>(null);

  const ai = mode === "review" ? reading.ai : null;
  const months = ai?.monthly_units.value ?? null;
  const flags = mode === "review" ? flagsByField(reading) : {};

  const optionalDecimal = (check: (n: number) => boolean, message: string) =>
    z
      .string()
      // "" → null (left empty); unparseable → undefined, which is an error, never "empty".
      .transform((raw) => (raw.trim() === "" ? null : (parseDecimalInput(raw) ?? undefined)))
      .refine((v) => v !== undefined, t("fieldErrors.number"))
      .refine((v) => v === null || v === undefined || check(Number(v)), message);
  const requiredDecimal = (check: (n: number) => boolean, message: string) =>
    z
      .string()
      .refine((raw) => raw.trim() !== "", t("fieldErrors.required"))
      .transform((raw) => parseDecimalInput(raw) ?? "")
      .refine((v) => v !== "", t("fieldErrors.number"))
      .refine((v) => check(Number(v)), message);
  const optionalText = (max: number, pattern?: RegExp, message?: string) =>
    z
      .string()
      .transform((raw) => (raw.trim() === "" ? null : raw.trim()))
      .refine((v) => v === null || (v.length <= max && (!pattern || pattern.test(v))), message ?? t("fieldErrors.number"));

  const schema = z.object({
    avg_monthly_units: requiredDecimal((n) => n >= 0 && n <= 5000, t("fieldErrors.units")),
    bill_amount: requiredDecimal((n) => n > 0 && n <= 1_000_000, t("fieldErrors.amount")),
    sanctioned_load_kw: optionalDecimal((n) => n > 0 && n <= 100, t("fieldErrors.load")),
    consumer_number: optionalText(30, /^[0-9 -]*$/, t("fieldErrors.consumer")),
    tariff_category: optionalText(60),
    fixed_charge_monthly: optionalDecimal((n) => n >= 0 && n <= 100_000, t("fieldErrors.number")),
  });
  type In = z.input<typeof schema>;
  type Out = z.output<typeof schema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<In, unknown, Out>({
    resolver: zodResolver(schema),
    defaultValues: {
      avg_monthly_units: s(ai ? reading.suggested_avg_monthly_units : null),
      bill_amount: s(ai?.bill_amount.value),
      sanctioned_load_kw: s(ai?.sanctioned_load_kw.value),
      consumer_number: s(ai?.consumer_number.value),
      tariff_category: s(ai?.tariff_category.value),
      fixed_charge_monthly: s(ai?.fixed_charge.value),
    },
  });

  const onSubmit = async (values: Out) => {
    setFormError(null);
    const body: ConfirmValues = {
      avg_monthly_units: values.avg_monthly_units,
      bill_amount: values.bill_amount,
      sanctioned_load_kw: values.sanctioned_load_kw ?? null,
      consumer_number: values.consumer_number ?? null,
      tariff_category: values.tariff_category ?? null,
      fixed_charge_monthly: values.fixed_charge_monthly ?? null,
      // Shown read-only above; sent as shown so nothing hidden is saved.
      monthly_units: months ? months.map((m) => m.units) : null,
    };
    try {
      const saved = await confirm.mutateAsync(body);
      onConfirmed(saved);
    } catch (error) {
      if (error instanceof ApiError && error.code === "READING_ALREADY_CONFIRMED") {
        onConfirmed(reading);
        return;
      }
      const code = error instanceof ApiError ? error.code : "UNKNOWN";
      setFormError(te.has(code) ? te(code) : error instanceof ApiError && error.status >= 500 ? te("INTERNAL_ERROR") : te("UNKNOWN"));
    }
  };

  const flagged = Object.keys(flags).length > 0;
  const field = (
    name: FieldName,
    opts: { unit?: string; unitAt?: "start" | "end"; inputMode?: "decimal" | "numeric" | "text"; optional?: boolean; hint?: string },
  ) => {
    const flag = flags[name];
    const error = errors[name]?.message;
    const hint = flag ? t(`flags.${flag}` as "flags.low_confidence") : opts.hint;
    const label = (
      <>
        {t(`fields.${name}`)}
        {opts.optional ? <span className="ml-1.5 font-normal text-ink-2">({t("review.optional")})</span> : null}
      </>
    );
    const input = (
      <Input
        id={name}
        inputMode={opts.inputMode ?? "decimal"}
        autoComplete="off"
        className={cn(
          "h-12 rounded-xl bg-background text-base tabular md:text-base",
          opts.unit && (opts.unitAt === "start" ? "pl-8" : "pr-16"),
          flag && !error && "border-attention/60 bg-attention-bg/40",
        )}
        aria-invalid={!!error}
        aria-describedby={describedBy(name, error, hint)}
        {...register(name)}
      />
    );
    return (
      <div className={cn(flag && !error && "[&_p[id$=-hint]]:text-attention")}>
        <Field id={name} label={label} hint={hint} error={error}>
          {opts.unit ? (
            <UnitInput unit={opts.unit} position={opts.unitAt}>
              {input}
            </UnitInput>
          ) : (
            input
          )}
        </Field>
      </div>
    );
  };

  const method = ai ? reading.suggested_method : null;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
      {flagged ? (
        <p className="flex items-start gap-2 rounded-xl bg-attention-bg px-3.5 py-3 text-sm text-attention">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {t("review.checkNote")}
        </p>
      ) : null}

      {field("avg_monthly_units", {
        unit: t("units.units"),
        hint: method ? t(`review.suggested.${method}`, { count: months?.length ?? 0 }) : undefined,
      })}
      {months && months.length > 0 ? (
        <div className="-mt-2">
          <p className="text-[0.8125rem] font-medium text-ink-2">{t("review.monthsTitle")}</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {months.map((m, i) => (
              <li key={`${m.month}-${i}`} className="rounded-lg bg-surface px-2.5 py-1 text-sm text-ink tabular">
                <span className="text-ink-2">{formatBillMonth(m.month, locale)}</span> {formatNumber(m.units, locale, 0)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {field("bill_amount", { unit: t("units.rupees"), unitAt: "start" })}
      {field("sanctioned_load_kw", { unit: t("units.kw"), optional: true })}
      {field("consumer_number", { inputMode: "numeric", optional: true })}
      {field("tariff_category", { inputMode: "text", optional: true })}
      {field("fixed_charge_monthly", { unit: t("units.rupees"), unitAt: "start", optional: true })}

      {formError ? (
        <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive">
          {formError}
        </p>
      ) : null}

      <Button type="submit" size="lg" className="h-12 w-full text-base" disabled={confirm.isPending}>
        {confirm.isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {t("review.confirming")}
          </>
        ) : (
          t("review.confirm")
        )}
      </Button>
    </form>
  );
}
