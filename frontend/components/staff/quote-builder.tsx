"use client";

import { AlertTriangle, FileText, Loader2, Send } from "lucide-react";
import { useMemo, useState } from "react";

import { errorText, when } from "@/components/staff/copy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { formatNumber, formatRupees, parseDecimalInput } from "@/lib/format";
import { pdfUrl, type OverrideField, type OverrideIn, type QuoteOption } from "@/lib/quotes";
import { useQuotePreview, useSendQuote, type StaffLeadDetail } from "@/lib/staff";
import { cn } from "@/lib/utils";

const QUOTABLE = new Set(["survey_pending", "call_pending", "surveyed", "quoted"]);

type Draft = Record<OverrideField, { value: string; reason: string }>;
const EMPTY: Draft = {
  usable_generation_pct: { value: "", reason: "" },
  fixed_charge_monthly: { value: "", reason: "" },
  savings_rate: { value: "", reason: "" },
};

const FIELDS: { field: OverrideField; label: string; unit: string; hint: (o: QuoteOption) => string }[] = [
  {
    field: "usable_generation_pct",
    label: "Share of generation used",
    unit: "%",
    hint: (o) => `Now ${formatNumber(Number(o.savings.usable_generation_pct) * 100, "en")}%`,
  },
  {
    field: "fixed_charge_monthly",
    label: "Fixed charge per month",
    unit: "₹",
    hint: (o) => `Now ₹${formatNumber(o.savings.fixed_charge, "en")} (${o.savings.fixed_charge_source})`,
  },
  {
    field: "savings_rate",
    label: "Saving per unit",
    unit: "₹/unit",
    hint: (o) => (o.savings.savings_rate ? `Now ₹${Number(o.savings.savings_rate).toFixed(2)}` : "Not available"),
  },
];

const squash = (text: string) => text.split(/s+/).join(" ").trim();

/** What the API takes: percent typed by people → fraction; other values as typed. A value that
 * doesn't parse is reported, never silently dropped (it would send a quote without it). */
function toOverrides(draft: Draft): { overrides: OverrideIn[]; invalid: OverrideField[] } {
  const overrides: OverrideIn[] = [];
  const invalid: OverrideField[] = [];
  for (const field of Object.keys(draft) as OverrideField[]) {
    const raw = draft[field].value.replace(/%/g, "").trim();
    if (raw === "") continue;
    const parsed = parseDecimalInput(raw);
    if (parsed === null) {
      invalid.push(field);
      continue;
    }
    const value = field === "usable_generation_pct" ? String(Number(parsed) / 100) : parsed;
    overrides.push({ field, value, reason: squash(draft[field].reason) || undefined });
  }
  return { overrides, invalid };
}

function payback(o: QuoteOption): string {
  if (o.payback.status === "ok") return `${o.payback.years} yrs`;
  if (o.payback.status === "immediate") return "Immediate";
  return "Not available";
}

/**
 * Live, constraint-filtered options (§8) with reasoned overrides (§10). Sending freezes the
 * numbers into an immutable snapshot (§11); a later send supersedes the open quote.
 */
export function QuoteBuilder({ lead }: { lead: StaffLeadDetail }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [sentNumber, setSentNumber] = useState<string | null>(null);
  const { overrides, invalid } = useMemo(() => toOverrides(draft), [draft]);
  const quotable = QUOTABLE.has(lead.status) && lead.ownership === "owner";
  const preview = useQuotePreview(lead.id, overrides, quotable);
  const send = useSendQuote(lead.id);

  const missingReason = overrides.some((o) => (o.reason ?? "").length < 5);
  const hasDraft = Object.values(draft).some((row) => row.value.trim() !== "");
  const blockCode = preview.error instanceof ApiError ? preview.error.code : null;
  const data = preview.isError ? null : preview.data;
  const reference = data?.options.find((o) => o.recommended) ?? data?.options[0];
  const openQuote = lead.quotes.find((q) => q.status === "sent");

  const doSend = async () => {
    setSentNumber(null);
    try {
      const quote = await send.mutateAsync(overrides);
      setSentNumber(quote.number);
      setDraft(EMPTY);
    } catch {
      /* shown below from send.error */
    }
  };

  if (!quotable) {
    return (
      <div className="space-y-4">
        <p className="text-ink-2">
          {lead.ownership === "tenant"
            ? "Tenants aren't quoted under the current rules."
            : lead.status === "accepted"
              ? "The homeowner accepted a quote. Record the advance to start the project."
              : "This lead can't be quoted in its current status."}
        </p>
        <QuoteHistory lead={lead} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {blockCode ? (
        <p role="status" className="flex items-start gap-2 rounded-xl bg-attention-bg px-4 py-3 text-[0.9375rem] text-attention">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {errorText(blockCode, preview.error?.message)}
        </p>
      ) : null}

      {data ? (
        <div className={cn("space-y-3 transition-opacity", preview.isFetching && "opacity-70")}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm text-ink-2">
            <p>
              Final size <span className="font-semibold text-ink">{data.recommended_kw} kW</span>
              {data.provisional_kw && data.provisional_kw !== data.recommended_kw
                ? ` (provisional was ${data.provisional_kw} kW: ${Number(data.recommended_kw) < Number(data.provisional_kw) ? "roof or load limits it" : "verified roof allows more"})`
                : ""}
              . Roof {data.verified_roof_sqft} sq ft · load {data.sanctioned_load.value} kW ({data.sanctioned_load.source}). Priced on{" "}
              {data.priced_on}.
            </p>
          </div>
          <ul className="grid gap-3 sm:grid-cols-3">
            {data.options.map((o) => (
              <li
                key={o.kw}
                className={cn(
                  "relative rounded-2xl border bg-background p-4",
                  o.recommended ? "border-teal ring-1 ring-teal" : "border-border",
                )}
              >
                {o.recommended ? (
                  <span className="absolute -top-2.5 left-4 rounded-full bg-night px-2 py-0.5 text-[0.75rem] font-medium text-gold-soft">
                    Suggested
                  </span>
                ) : null}
                <p className="font-display text-2xl font-semibold text-ink tabular">{o.kw} kW</p>
                <dl className="mt-3 space-y-1 text-sm">
                  <Row label="Price" value={formatRupees(o.gross, "en")} />
                  <Row label="Subsidy" value={`− ${formatRupees(o.subsidy.amount, "en")}`} />
                  <Row label="Net" value={formatRupees(o.net, "en")} strong />
                  <Row label="Savings / yr" value={o.savings.annual_savings ? formatRupees(o.savings.annual_savings, "en") : "Not available"} />
                  <Row label="Payback" value={payback(o)} />
                </dl>
              </li>
            ))}
          </ul>
          {data.removed.length ? (
            <p className="text-sm text-ink-2">
              Not offered:{" "}
              {data.removed
                .map((r) =>
                  r.reason === "sanctioned_load"
                    ? `${r.kw} kW (sanctioned load is ${data.sanctioned_load.value} kW)`
                    : `${r.kw} kW (roof fits ${data.max_allowed_kw} kW)`,
                )
                .join(", ")}
            </p>
          ) : null}
        </div>
      ) : preview.isPending && !blockCode ? (
        <div className="flex items-center gap-2 text-ink-2" aria-busy="true">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Working out the options…
        </div>
      ) : null}

      {/* Stays mounted when an override is rejected, so it can be corrected without a reload. */}
      {reference || hasDraft ? (
        <details className="group rounded-2xl border border-border bg-background">
          <summary className="flex min-h-11 cursor-pointer items-center px-4 text-[0.9375rem] font-medium text-ink">
            Adjust assumptions{overrides.length ? ` (${overrides.length})` : ""}
          </summary>
          <div className="space-y-4 border-t border-border p-4">
            {FIELDS.map(({ field, label, unit, hint }) => {
              const row = draft[field];
              const needsReason = row.value.trim() !== "" && squash(row.reason).length < 5;
              return (
                <div key={field} className="grid gap-2 sm:grid-cols-[12rem_8rem_1fr] sm:items-start">
                  <div>
                    <label htmlFor={`ov-${field}`} className="text-sm font-medium text-ink">
                      {label}
                    </label>
                    {reference ? <p className="text-[0.8125rem] text-ink-2">{hint(reference)}</p> : null}
                    {invalid.includes(field) ? <p className="text-[0.8125rem] text-destructive">Enter a number.</p> : null}
                  </div>
                  <div className="relative">
                    <Input
                      id={`ov-${field}`}
                      inputMode="decimal"
                      placeholder={unit}
                      value={row.value}
                      onChange={(e) => setDraft((d) => ({ ...d, [field]: { ...d[field], value: e.target.value } }))}
                      className="h-10 tabular"
                      aria-invalid={invalid.includes(field)}
                    />
                  </div>
                  <Input
                    aria-label={`Reason for ${label.toLowerCase()}`}
                    placeholder="Reason (required to send)"
                    value={row.reason}
                    onChange={(e) => setDraft((d) => ({ ...d, [field]: { ...d[field], reason: e.target.value } }))}
                    aria-invalid={needsReason}
                    className="h-10"
                  />
                </div>
              );
            })}
          </div>
        </details>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          className="h-11"
          onClick={doSend}
          disabled={!data || !!blockCode || missingReason || invalid.length > 0 || !preview.settled || send.isPending || preview.isFetching}
        >
          {send.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
          {openQuote ? "Send revised quote" : "Send quote"}
        </Button>
        {missingReason ? <p className="text-sm text-attention">Each override needs a reason before sending.</p> : null}
        {openQuote && !missingReason ? <p className="text-sm text-ink-2">Replaces {openQuote.number}.</p> : null}
      </div>
      {send.error ? (
        <p role="alert" className="text-sm text-destructive">
          {send.error instanceof ApiError ? errorText(send.error.code, send.error.message) : "Couldn't send. Try again."}
        </p>
      ) : null}
      {sentNumber ? (
        <p role="status" className="text-sm text-teal">
          Sent {sentNumber}. The homeowner was notified (simulated WhatsApp).
        </p>
      ) : null}

      <QuoteHistory lead={lead} />
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-ink-2">{label}</dt>
      <dd className={cn("tabular", strong ? "font-semibold text-ink" : "text-ink")}>{value}</dd>
    </div>
  );
}

function QuoteHistory({ lead }: { lead: StaffLeadDetail }) {
  if (!lead.quotes.length) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-ink-2">Quotes sent</h3>
      <ul className="divide-y divide-border rounded-2xl border border-border bg-background">
        {lead.quotes.map((q) => (
          <li key={q.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm">
            <span className="font-medium text-ink tabular">{q.number}</span>
            <span className="text-ink-2">
              {q.status === "accepted" ? `Accepted · ${q.selected_kw} kW` : q.status === "sent" ? "Open" : "Superseded"} · {when(q.sent_at)}
            </span>
            <a
              href={pdfUrl(q.id, lead.homeowner.preferred_locale)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center gap-1.5 font-medium text-teal hover:underline"
            >
              <FileText className="size-4" aria-hidden /> PDF ({lead.homeowner.preferred_locale})
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
