"use client";

/**
 * Typed calls and query hooks for the homeowner journey (ARCHITECTURE §2 screens 1–3).
 * Shapes mirror backend/app/schemas/{leads,bills}.py; decimals arrive as plain strings.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";

export type Ownership = "owner" | "tenant";
export type PropertyType = "home" | "business";
export type RoofType = "rcc_flat" | "metal_sheet" | "tiled" | "other";

export type LeadStatus =
  | "draft"
  | "bill_processing"
  | "bill_review"
  | "survey_pending"
  | "call_pending"
  | (string & {});

export type ReadingStatus =
  | "processing"
  | "needs_review"
  | "needs_reupload"
  | "failed_manual"
  | "confirmed";

export type ReadingRef = { id: string; status: ReadingStatus };

export type LeadMine = {
  id: string;
  code: string;
  status: LeadStatus;
  ownership: Ownership;
  property_type: PropertyType;
  roof_type: RoofType;
  roof_area_sqft: string;
  declared_monthly_bill: string;
  pincode: string;
  next_action: "survey_visit" | "call" | null;
  recommended_kw: string | null;
  recommendation_status: "provisional" | "final" | null;
  current_reading: ReadingRef | null;
  latest_reading: ReadingRef | null;
  created_at: string;
};

export type LeadIn = {
  ownership: Ownership;
  property_type: PropertyType;
  roof_type: RoofType;
  roof_area_sqft: string;
  monthly_bill: string;
  pincode: string;
  consent: boolean;
};

type Read<T> = { value: T | null; confidence: number };

/** What the AI read (BillExtraction). Only present once a reading has finished. */
export type AiValues = {
  is_electricity_bill: boolean;
  legibility: "good" | "fair" | "poor";
  consumer_number: Read<string>;
  tariff_category: Read<string>;
  sanctioned_load_kw: Read<string>;
  monthly_units: Read<{ month: string; units: number }[]>;
  current_units: Read<number>;
  bill_amount: Read<string>;
  fixed_charge: Read<string>;
};

export type ConfirmValues = {
  consumer_number: string | null;
  tariff_category: string | null;
  sanctioned_load_kw: string | null;
  monthly_units: number[] | null;
  avg_monthly_units: string;
  bill_amount: string;
  fixed_charge_monthly: string | null;
};

export type Reading = {
  id: string;
  lead_id: string;
  status: ReadingStatus;
  kind: "image" | "pdf";
  source_path: "vision" | "pdf_text" | "manual" | null;
  quality: { ok: boolean; reasons: string[]; metrics: Record<string, number> } | null;
  ai: AiValues | null;
  flags: Record<string, string[]>;
  suggested_avg_monthly_units: string | null;
  suggested_method: "history_mean" | "current_month" | null;
  confirmed: (Omit<ConfirmValues, "avg_monthly_units" | "bill_amount"> & {
    avg_monthly_units: string | null;
    bill_amount: string | null;
  }) | null;
  edited_fields: string[];
  provider: string | null;
  model: string | null;
  is_demo: boolean;
  attempts: { provider?: string; outcome?: string; error_code?: string; ms?: number }[];
  created_at: string;
};

export const leadKeys = {
  mine: ["leads", "mine"] as const,
  one: (id: string) => ["leads", id] as const,
  reading: (id: string) => ["bills", id] as const,
};

export const createLead = (body: LeadIn) => api<LeadMine>("/api/leads", { json: body });
export const fetchMyLeads = () => api<LeadMine[]>("/api/leads/mine");
export const fetchLead = (id: string) => api<LeadMine>(`/api/leads/${id}`);
export const fetchReading = (id: string) => api<Reading>(`/api/bills/${id}`);
export const previewUrl = (readingId: string) => `/api/bills/${readingId}/preview`;

/**
 * Sends every field, including nulls: the server keeps the AI's proposal for a field that is
 * *missing*, so omitting one would let a suggestion override what the person saw (Review Focus 4).
 */
export const confirmReading = (id: string, values: ConfirmValues) =>
  api<Reading>(`/api/bills/${id}/confirm`, { json: values });

/** Upload with real progress (fetch has no upload progress). Errors become ApiError. */
export function uploadBill(
  leadId: string,
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<Reading> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/leads/${leadId}/bills`);
    xhr.setRequestHeader("X-HF-CSRF", "1");
    xhr.setRequestHeader("Accept", "application/json");
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK", "Network error"));
    xhr.onload = () => {
      let payload: { error?: { code?: string; message?: string } } | null = null;
      try {
        payload = JSON.parse(xhr.responseText);
      } catch {
        payload = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(payload as Reading);
      else
        reject(
          new ApiError(
            xhr.status,
            payload?.error?.code ?? (xhr.status === 413 ? "FILE_TOO_LARGE" : "UNKNOWN"),
            payload?.error?.message ?? xhr.statusText,
          ),
        );
    };
    const form = new FormData();
    form.append("file", file, file.name);
    xhr.send(form);
  });
}

export function useMyLeads(enabled = true) {
  return useQuery({ queryKey: leadKeys.mine, queryFn: fetchMyLeads, enabled });
}

export function useLead(id: string) {
  return useQuery({ queryKey: leadKeys.one(id), queryFn: () => fetchLead(id) });
}

/** How long the check-bill screen waits on "processing" before treating the read as stuck.
 * The server's own AI budget is 75 s and it sweeps orphans after 2 min (§6). */
export const READING_GIVE_UP_MS = 150_000;
export const READING_POLL_MS = 1200;

export function useReading(id: string) {
  return useQuery({
    queryKey: leadKeys.reading(id),
    queryFn: () => fetchReading(id),
    refetchInterval: (query) => (query.state.data?.status === "processing" ? READING_POLL_MS : false),
    refetchIntervalInBackground: false,
  });
}

export function useConfirmReading(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (values: ConfirmValues) => confirmReading(id, values),
    onSuccess: (reading) => {
      client.setQueryData(leadKeys.reading(id), reading);
      client.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}
