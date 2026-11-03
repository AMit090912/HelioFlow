"use client";

/** Projects (§12): staff API, plus the public status shape (screen 5). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export const STAGES = [
  "advance_received",
  "installation_scheduled",
  "installation_completed",
  "net_metering_completed",
  "subsidy_applied",
  "subsidy_credited",
] as const;
export type Stage = (typeof STAGES)[number];

export type StageMark = { stage: Stage; done_at: string | null };

export type ProjectRow = {
  id: string;
  lead_id: string;
  code: string;
  homeowner_name: string;
  homeowner_locale: string;
  stage: Stage;
  stage_changed_at: string;
  days_in_stage: number;
  selected_kw: string | null;
};

export type ProjectDetail = ProjectRow & {
  advance_amount: string;
  advance_reference: string;
  scheduled_for: string | null;
  stages: StageMark[];
  events: {
    id: string;
    from_stage: Stage | null;
    to_stage: Stage;
    actor_name: string | null;
    note: string | null;
    scheduled_for: string | null;
    created_at: string;
  }[];
  notifications: {
    id: string;
    type: "quote_sent" | "status_link" | "stage_changed";
    channel: "whatsapp" | "sms";
    locale: string;
    recipient_masked: string;
    message: string;
    delivery_status: "simulated";
    created_at: string;
  }[];
  link: { active: boolean; created_at: string | null; revoked_at: string | null };
};

export type PublicStatus = {
  first_name: string;
  code: string;
  current_stage: Stage;
  stages: StageMark[];
  scheduled_for: string | null;
};

const keys = {
  list: ["staff", "projects"] as const,
  one: (id: string) => ["staff", "project", id] as const,
};

export function useProjects() {
  return useQuery({ queryKey: keys.list, queryFn: () => api<ProjectRow[]>("/api/staff/projects") });
}

export function useProject(id: string | null) {
  return useQuery({
    queryKey: keys.one(id ?? ""),
    queryFn: () => api<ProjectDetail>(`/api/staff/projects/${id}`),
    enabled: !!id,
  });
}

function useProjectWrite<Body, Out>(id: string, call: (body: Body) => Promise<Out>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    // Refresh on failure too: a 409 means someone else moved the project, so show their change.
    onSettled: () => {
      client.invalidateQueries({ queryKey: keys.one(id) });
      client.invalidateQueries({ queryKey: keys.list });
    },
  });
}

export const useMoveStage = (id: string) =>
  useProjectWrite(id, (body: { to: Stage; note?: string; scheduled_for?: string | null }) =>
    api<ProjectDetail>(`/api/staff/projects/${id}/stage`, { json: body }),
  );

export const useRegenerateLink = (id: string) =>
  useProjectWrite<void, { status_token: string }>(id, () => api<{ status_token: string }>(`/api/staff/projects/${id}/link`, { method: "POST" }));

export const useRevokeLink = (id: string) =>
  useProjectWrite<void, void>(id, () => api<void>(`/api/staff/projects/${id}/link`, { method: "DELETE" }));

export function useRecordAdvance(leadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (amount: string) =>
      api<{ project: ProjectDetail; status_token: string }>(`/api/staff/leads/${leadId}/advance`, { json: { amount } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["staff"] });
    },
  });
}

/** The shareable link. The token exists only in this response; the server keeps its hash. */
export function statusUrl(token: string, locale = "en"): string {
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}/${locale}/s/${token}`;
}
