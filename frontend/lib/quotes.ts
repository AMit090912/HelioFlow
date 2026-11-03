"use client";

/**
 * Quote shapes shared by the staff builder and the homeowner quote screen. They mirror the
 * backend snapshot (backend/app/services/quotes.py): every number is a plain decimal string.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export type QuoteOption = {
  kw: string;
  recommended: boolean;
  gross: string;
  subsidy: { status: "ELIGIBLE" | "NOT_ELIGIBLE"; amount: string; raw: string; capped: boolean };
  net: string;
  savings: {
    annual_generation: string | number;
    usable_generation: string;
    usable_generation_pct: string;
    fixed_charge: string;
    fixed_charge_source: "bill" | "default" | "override";
    savings_rate: string | null;
    annual_savings: string | null;
    status: "ok" | "not_available";
    reason: string | null;
  };
  payback: { years: string | null; status: "ok" | "immediate" | "not_available" };
  flags: string[];
};

export type Removed = { kw: string; reason: "roof" | "sanctioned_load" | string };

export type OverrideField = "usable_generation_pct" | "fixed_charge_monthly" | "savings_rate";
export type OverrideIn = { field: OverrideField; value: string; reason?: string };
/** Staff see who changed a value and why; homeowners only which value changed. */
export type OverrideRecord = { field: OverrideField; from: string | null; to: string; by?: string | null; reason?: string | null };

export type QuoteView = {
  id: string;
  number: string;
  status: "sent" | "accepted" | "superseded";
  lead_id: string;
  lead_code: string;
  lead_status: string;
  sent_at: string;
  priced_on: string;
  selected_kw: string | null;
  accepted_at: string | null;
  superseded_by_quote_id: string | null;
  recommended_kw: string;
  options: QuoteOption[];
  removed: Removed[];
  assumptions: string[];
  overrides: OverrideRecord[];
  subsidy_rule: { scheme_code: string; effective_from: string; source_note: string } | null;
  inputs: Record<string, unknown>;
};

export const quoteKeys = { one: (id: string) => ["quotes", id] as const };

export const pdfUrl = (id: string, lang?: string) => `/api/quotes/${id}/pdf${lang ? `?lang=${lang}` : ""}`;

export function useQuote(id: string, enabled = true) {
  return useQuery({
    queryKey: quoteKeys.one(id),
    queryFn: () => api<QuoteView>(`/api/quotes/${id}`),
    enabled: enabled && !!id,
  });
}

export function useAcceptQuote(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (selected_kw: string) => api<QuoteView>(`/api/quotes/${id}/accept`, { json: { selected_kw } }),
    onSuccess: (quote) => {
      client.setQueryData(quoteKeys.one(id), quote);
      client.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

/** The option a quote is about: the accepted size, else the suggested one. */
export function focusOption(quote: Pick<QuoteView, "options" | "selected_kw">, chosen?: string | null): QuoteOption {
  const wanted = chosen ?? quote.selected_kw;
  return (
    quote.options.find((o) => wanted !== null && wanted !== undefined && Number(o.kw) === Number(wanted)) ??
    quote.options.find((o) => o.recommended) ??
    quote.options[0]
  );
}
