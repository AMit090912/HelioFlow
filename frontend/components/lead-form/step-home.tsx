"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { ChoiceGroup } from "@/components/lead-form/choice-card";
import { saveHome, type HomeDraft } from "@/components/lead-form/draft";
import { describedBy, Field, UnitInput } from "@/components/lead-form/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";

const INPUT = "h-12 rounded-xl bg-background text-base md:text-base";

/**
 * Step 1. Also used to edit the details later (from the bill step or the check-bill screen):
 * then `onDone` saves to the server, may fail, and `onBack` returns without saving.
 */
export function StepHome({
  initial,
  onDone,
  onBack,
  submitLabel,
}: {
  initial: Partial<HomeDraft> | null;
  onDone: (home: HomeDraft) => void | Promise<void>;
  onBack?: () => void;
  submitLabel?: string;
}) {
  const t = useTranslations("leadForm");
  const te = useTranslations("errors");
  const [formError, setFormError] = useState<string | null>(null);

  const amount = (max: number, message: string) =>
    z
      .string()
      .transform((raw) => parseDecimalInput(raw) ?? "")
      .refine((v) => v !== "" && Number(v) > 0 && Number(v) <= max, message);

  const schema = z.object({
    ownership: z.enum(["owner", "tenant"], { error: t("errors.choose") }),
    property_type: z.enum(["home", "business"], { error: t("errors.choose") }),
    roof_type: z.enum(["rcc_flat", "metal_sheet", "tiled", "other"], { error: t("errors.choose") }),
    roof_area_sqft: amount(100_000, t("errors.roofArea")),
    monthly_bill: amount(1_000_000, t("errors.monthlyBill")),
    pincode: z
      .string()
      .trim()
      .regex(/^[1-9][0-9]{5}$/, t("errors.pincode")),
  });

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      ownership: initial?.ownership,
      property_type: initial?.property_type,
      roof_type: initial?.roof_type,
      roof_area_sqft: initial?.roof_area_sqft ?? "",
      monthly_bill: initial?.monthly_bill ?? "",
      pincode: initial?.pincode ?? "",
    },
  });

  // Every change is remembered, so a reload mid-step keeps what was typed (Review Focus 1).
  const watched = useWatch({ control });
  useEffect(() => {
    saveHome(watched as Partial<HomeDraft>);
  }, [watched]);

  const onSubmit = async (values: z.output<typeof schema>) => {
    setFormError(null);
    saveHome(values);
    try {
      await onDone(values);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "UNKNOWN";
      setFormError(te.has(code) ? te(code) : te("UNKNOWN"));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-8">
      <Controller
        control={control}
        name="ownership"
        render={({ field }) => (
          <ChoiceGroup
            name="ownership"
            legend={t("ownership.label")}
            value={field.value}
            onChange={field.onChange}
            error={errors.ownership?.message}
            options={[
              { value: "owner", label: t("ownership.owner"), hint: t("ownership.ownerHint"), icon: <KeyIcon /> },
              { value: "tenant", label: t("ownership.tenant"), hint: t("ownership.tenantHint"), icon: <DoorIcon /> },
            ]}
          />
        )}
      />
      <Controller
        control={control}
        name="property_type"
        render={({ field }) => (
          <ChoiceGroup
            name="property_type"
            legend={t("propertyType.label")}
            value={field.value}
            onChange={field.onChange}
            error={errors.property_type?.message}
            options={[
              { value: "home", label: t("propertyType.home"), hint: t("propertyType.homeHint"), icon: <HouseIcon /> },
              { value: "business", label: t("propertyType.business"), hint: t("propertyType.businessHint"), icon: <ShopIcon /> },
            ]}
          />
        )}
      />
      <Controller
        control={control}
        name="roof_type"
        render={({ field }) => (
          <ChoiceGroup
            name="roof_type"
            legend={t("roofType.label")}
            value={field.value}
            onChange={field.onChange}
            error={errors.roof_type?.message}
            columns={4}
            options={[
              { value: "rcc_flat", label: t("roofType.rcc_flat"), icon: <RoofIcon kind="flat" /> },
              { value: "metal_sheet", label: t("roofType.metal_sheet"), icon: <RoofIcon kind="metal" /> },
              { value: "tiled", label: t("roofType.tiled"), icon: <RoofIcon kind="tiled" /> },
              { value: "other", label: t("roofType.other"), icon: <RoofIcon kind="other" /> },
            ]}
          />
        )}
      />

      <div className="grid gap-6 sm:grid-cols-2">
        <Field id="roof_area_sqft" label={t("roofArea.label")} hint={t("roofArea.hint")} error={errors.roof_area_sqft?.message}>
          <UnitInput unit={t("roofArea.unit")}>
            <Input
              id="roof_area_sqft"
              inputMode="decimal"
              autoComplete="off"
              className={`${INPUT} pr-20 tabular`}
              aria-invalid={!!errors.roof_area_sqft}
              aria-describedby={describedBy("roof_area_sqft", errors.roof_area_sqft, true)}
              {...register("roof_area_sqft")}
            />
          </UnitInput>
        </Field>
        <Field id="monthly_bill" label={t("monthlyBill.label")} hint={t("monthlyBill.hint")} error={errors.monthly_bill?.message}>
          <UnitInput unit={t("monthlyBill.unit")} position="start">
            <Input
              id="monthly_bill"
              inputMode="decimal"
              autoComplete="off"
              className={`${INPUT} pl-8 tabular`}
              aria-invalid={!!errors.monthly_bill}
              aria-describedby={describedBy("monthly_bill", errors.monthly_bill, true)}
              {...register("monthly_bill")}
            />
          </UnitInput>
        </Field>
        <Field id="pincode" label={t("pincode.label")} hint={t("pincode.hint")} error={errors.pincode?.message}>
          <Input
            id="pincode"
            inputMode="numeric"
            autoComplete="postal-code"
            maxLength={6}
            className={`${INPUT} tabular tracking-wider`}
            aria-invalid={!!errors.pincode}
            aria-describedby={describedBy("pincode", errors.pincode, true)}
            {...register("pincode")}
          />
        </Field>
      </div>

      {formError ? (
        <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive">
          {formError}
        </p>
      ) : null}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
        {onBack ? (
          <Button type="button" variant="ghost" className="h-12 text-base text-ink-2" onClick={onBack} disabled={isSubmitting}>
            {t("back")}
          </Button>
        ) : null}
        <Button type="submit" size="lg" className="h-12 w-full text-base sm:w-auto sm:px-10" disabled={isSubmitting}>
          {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {submitLabel ?? t("next")}
        </Button>
      </div>
    </form>
  );
}

/* Small line icons for the choice cards: 28 px, brand teal via currentColor. */
const ICON = { width: 28, height: 28, viewBox: "0 0 28 28", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;

function KeyIcon() {
  return (
    <svg {...ICON}>
      <circle cx="9" cy="14" r="5" />
      <path d="M14 14 H25 M21 14 V18 M24 14 V17" />
    </svg>
  );
}
function DoorIcon() {
  return (
    <svg {...ICON}>
      <path d="M7 25 V4 H21 V25 M4 25 H24" />
      <circle cx="17" cy="15" r="1" fill="currentColor" />
    </svg>
  );
}
function HouseIcon() {
  return (
    <svg {...ICON}>
      <path d="M4 13 L14 5 L24 13 M7 11 V24 H21 V11 M12 24 V17 H16 V24" />
    </svg>
  );
}
function ShopIcon() {
  return (
    <svg {...ICON}>
      <path d="M4 10 L6 4 H22 L24 10 Z M5 10 V24 H23 V10 M11 24 V17 H17 V24" />
    </svg>
  );
}
function RoofIcon({ kind }: { kind: "flat" | "metal" | "tiled" | "other" }) {
  return (
    <svg {...ICON}>
      {kind === "flat" ? <path d="M3 10 H25 M5 10 V24 H23 V10 M3 7 H25" /> : null}
      {kind === "metal" ? <path d="M3 13 L14 5 L25 13 M5 12 V24 H23 V12 M9 9 V12 M14 6 V12 M19 9 V12" /> : null}
      {kind === "tiled" ? <path d="M3 13 L14 5 L25 13 M5 12 V24 H23 V12 M7 11 Q9 13 11 11 Q13 13 15 11 Q17 13 19 11 Q21 13 22 11" /> : null}
      {kind === "other" ? <path d="M3 13 L14 5 L25 13 M5 12 V24 H23 V12 M12 17 Q14 14 16 17 Q16 19 14 20 M14 22.5 V22.6" /> : null}
    </svg>
  );
}
