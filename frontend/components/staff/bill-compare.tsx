"use client";

import { Pencil } from "lucide-react";

import { BillPreview } from "@/components/bill-check/bill-preview";
import { READING_FIELDS } from "@/components/staff/copy";
import { FlagChip } from "@/components/staff/score-badge";
import { plainDecimal } from "@/lib/format";
import type { Reading } from "@/lib/leads";

const FLAG_SOURCE: Record<string, string> = {
  avg_monthly_units: "current_units",
  bill_amount: "bill_amount",
  sanctioned_load_kw: "sanctioned_load_kw",
  fixed_charge_monthly: "fixed_charge",
  consumer_number: "consumer_number",
  tariff_category: "tariff_category",
};

function aiValue(reading: Reading, key: string, aiKey?: string): { text: string; confidence: number | null } {
  if (!reading.ai) return { text: "—", confidence: null };
  if (key === "avg_monthly_units") {
    return { text: plainDecimal(reading.suggested_avg_monthly_units) || "—", confidence: reading.ai.current_units.confidence };
  }
  const read = aiKey ? (reading.ai as unknown as Record<string, { value: unknown; confidence: number }>)[aiKey] : undefined;
  if (!read || read.value === null || read.value === undefined) return { text: "—", confidence: null };
  return { text: plainDecimal(String(read.value)), confidence: read.confidence };
}

/** What the AI read beside what the homeowner confirmed, with edits and sanity flags (§6.4). */
export function BillCompare({ reading }: { reading: Reading }) {
  const confirmed = (reading.confirmed ?? {}) as Record<string, unknown>;
  const source =
    reading.source_path === "manual" ? "Typed in by hand" : reading.is_demo ? "Demo reading (sample bill)" : `Read by ${reading.provider ?? "AI"}`;
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <BillPreview readingId={reading.id} />
      <div>
        <p className="mb-2 text-sm text-ink-2">{source}</p>
        <table className="w-full text-[0.9375rem]">
          <thead className="text-left text-[0.8125rem] text-ink-2">
            <tr className="border-b border-border">
              <th className="py-2 pr-3 font-medium">Field</th>
              <th className="py-2 pr-3 font-medium">AI read</th>
              <th className="py-2 font-medium">Confirmed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {READING_FIELDS.map((f) => {
              const ai = aiValue(reading, f.key, f.ai);
              const value = confirmed[f.key];
              const edited = reading.edited_fields.includes(f.key);
              const flags = reading.flags[FLAG_SOURCE[f.key]] ?? [];
              return (
                <tr key={f.key} className="align-top">
                  <th scope="row" className="py-2.5 pr-3 text-left font-normal text-ink-2">
                    {f.label}
                  </th>
                  <td className="py-2.5 pr-3 tabular text-ink-2">
                    {ai.text}
                    {ai.confidence !== null ? (
                      <span className="ml-1.5 text-[0.75rem]">{Math.round(ai.confidence * 100)}%</span>
                    ) : null}
                  </td>
                  <td className="py-2.5 tabular font-medium text-ink">
                    <span className="inline-flex items-center gap-1.5">
                      {value === null || value === undefined || value === "" ? "—" : plainDecimal(String(value))}
                      {f.unit && value ? <span className="text-[0.8125rem] font-normal text-ink-2">{f.unit}</span> : null}
                      {edited && reading.source_path !== "manual" ? (
                        <span title="Changed by the homeowner" className="inline-flex items-center gap-0.5 text-[0.75rem] font-normal text-attention">
                          <Pencil className="size-3" aria-hidden /> edited
                        </span>
                      ) : null}
                    </span>
                    {flags.length ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {flags.map((code) => (
                          <FlagChip key={code}>{code.replaceAll("_", " ")}</FlagChip>
                        ))}
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
