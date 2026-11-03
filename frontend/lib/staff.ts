"use client";

/** Staff API (backend/app/api/staff.py): inbox, lead detail, verification, quotes. */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Reading } from "@/lib/leads";
import type { OverrideIn, OverrideRecord, QuoteOption, QuoteView, Removed } from "@/lib/quotes";

export type ScoreReason = { code: string; value?: string; threshold?: string; source?: string };

export type StaffLeadRow = {
  id: string;
  code: string;
  homeowner_name: string;
  created_at: string;
  status: string;
  score: "high" | "low" | null;
  score_reasons: ScoreReason[];
  recommended_kw: string | null;
  recommendation_status: "provisional" | "final" | null;
  next_action: "survey_visit" | "call" | null;
  flags: string[];
};

export type LeadEvent = {
  id: string;
  kind: "verified" | "upgraded" | "closed" | "quote_sent" | "quote_accepted" | "converted" | "link_regenerated" | "link_revoked";
  from_status: string | null;
  to_status: string | null;
  actor_name: string;
  note: string | null;
  created_at: string;
};

export type StaffLeadDetail = StaffLeadRow & {
  homeowner: { full_name: string; phone: string | null; email: string | null; preferred_locale: string };
  ownership: "owner" | "tenant";
  property_type: "home" | "business";
  roof_type: string;
  roof_area_sqft: string;
  declared_monthly_bill: string;
  pincode: string;
  seed_note: string | null;
  sizing_detail: Record<string, unknown> | null;
  verified_roof_area_sqft: string | null;
  roof_verified_via: "survey" | "call" | null;
  roof_verified_at: string | null;
  survey_notes: string | null;
  sanctioned_load: { value: string | null; source: "staff" | "bill" | null };
  current_reading: Reading | null;
  events: LeadEvent[];
  quotes: { id: string; number: string; status: QuoteView["status"]; sent_at: string; selected_kw: string | null }[];
};

export type QuotePreview = {
  priced_on: string;
  recommended_kw: string;
  provisional_kw: string | null;
  max_allowed_kw: string;
  removed: Removed[];
  options: QuoteOption[];
  sanctioned_load: { value: string | null; source: "staff" | "bill" | null };
  verified_roof_sqft: string | null;
  overrides: OverrideRecord[];
};

export type InboxFilters = { score?: "high" | "low"; status?: string };

const staffKeys = {
  inbox: (f: InboxFilters) => ["staff", "leads", f] as const,
  lead: (id: string) => ["staff", "lead", id] as const,
  preview: (id: string, overrides: OverrideIn[]) => ["staff", "preview", id, overrides] as const,
};

export function useStaffLeads(filters: InboxFilters) {
  const params = new URLSearchParams();
  if (filters.score) params.set("score", filters.score);
  if (filters.status) params.set("status", filters.status);
  const qs = params.toString();
  return useQuery({
    queryKey: staffKeys.inbox(filters),
    queryFn: () => api<StaffLeadRow[]>(`/api/staff/leads${qs ? `?${qs}` : ""}`),
    placeholderData: keepPreviousData,
  });
}

export function useStaffLead(id: string) {
  return useQuery({ queryKey: staffKeys.lead(id), queryFn: () => api<StaffLeadDetail>(`/api/staff/leads/${id}`) });
}

function useLeadAction<Body>(id: string, path: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Body) => api<StaffLeadDetail>(`/api/staff/leads/${id}/${path}`, { json: body }),
    onSuccess: (lead) => {
      client.setQueryData(staffKeys.lead(id), lead);
      client.invalidateQueries({ queryKey: ["staff", "leads"] });
      client.invalidateQueries({ queryKey: ["staff", "preview", id] });
    },
  });
}

export type VerificationIn = {
  roof_area_sqft: string;
  via: "survey" | "call";
  sanctioned_load_kw?: string | null;
  notes?: string | null;
};

export const useVerify = (id: string) => useLeadAction<VerificationIn>(id, "verification");
export const useUpgrade = (id: string) => useLeadAction<{ reason: string }>(id, "upgrade");
export const useCloseLead = (id: string) => useLeadAction<{ reason: string }>(id, "close");

/** Live builder numbers. Debounced so typing an override doesn't fire a request per key. */
export function useQuotePreview(id: string, overrides: OverrideIn[], enabled: boolean) {
  // Keyed by content, not array identity, and without reasons (they don't change the numbers),
  // so a new array each render never restarts the debounce.
  const key = JSON.stringify(overrides.map(({ field, value }) => ({ field, value })));
  const [debounced, setDebounced] = useState(key);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(key), 300);
    return () => window.clearTimeout(timer);
  }, [key]);
  const numeric = JSON.parse(debounced) as OverrideIn[];
  const query = useQuery({
    queryKey: staffKeys.preview(id, numeric),
    queryFn: () => api<QuotePreview>(`/api/staff/leads/${id}/quote-preview`, { json: { overrides: numeric } }),
    enabled,
    placeholderData: keepPreviousData,
    retry: false,
  });
  // False while typing: the numbers on screen don't yet reflect the latest overrides.
  return { ...query, settled: key === debounced };
}

export function useSendQuote(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (overrides: OverrideIn[]) => api<QuoteView>(`/api/staff/leads/${id}/quotes`, { json: { overrides } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: staffKeys.lead(id) });
      client.invalidateQueries({ queryKey: ["staff", "leads"] });
    },
  });
}
