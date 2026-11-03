"use client";

import { useTranslations } from "next-intl";

import { BillTips, BillUploader } from "@/components/lead-form/step-bill";
import type { Reading } from "@/lib/leads";

const KNOWN = ["too_small", "too_dark", "too_bright", "blurry", "not_electricity_bill", "legibility_poor"] as const;
type Reason = (typeof KNOWN)[number];

/** Why this copy can't be used — from the photo check or from what the AI saw — in plain words. */
export function reuploadReasons(reading: Reading): Reason[] {
  const raw = [...(reading.quality?.reasons ?? []), ...(reading.flags?.document ?? [])];
  return KNOWN.filter((r) => raw.includes(r));
}

export function ReuploadPanel({
  reading,
  onUploaded,
  onTypeInstead,
}: {
  reading: Reading;
  onUploaded: (reading: Reading) => void;
  onTypeInstead: () => void;
}) {
  const t = useTranslations("billCheck.reupload");
  const reasons = reuploadReasons(reading);
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-[1.5rem] font-semibold text-ink">{t("title")}</h2>
        <p className="mt-1 text-ink-2">{t("subtitle")}</p>
        {reasons.length ? (
          <ul className="mt-4 space-y-2">
            {reasons.map((r) => (
              <li key={r} className="rounded-xl bg-attention-bg px-3.5 py-2.5 text-[0.9375rem] text-attention">
                {t(`reasons.${r}`)}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <BillTips />
      <BillUploader leadId={reading.lead_id} onUploaded={onUploaded} submitLabel={t("cta")} />
      <button
        type="button"
        onClick={onTypeInstead}
        className="min-h-11 text-[0.9375rem] font-medium text-teal underline-offset-4 hover:underline"
      >
        {t("orType")}
      </button>
    </div>
  );
}
