"use client";

/** Rules and settings (§3.5–3.7). Sales read; admin writes. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export type PriceRule = {
  id: string;
  min_kw: string;
  max_kw: string;
  price_per_kw: string;
  gst_inclusive: boolean;
  effective_from: string;
  effective_to: string | null;
  note: string | null;
};

export type Slab = { from_kw: string; to_kw: string; amount_per_kw: string };

export type SubsidyRule = {
  id: string;
  scheme_code: string;
  segment: string;
  slabs: Slab[];
  cap_amount: string;
  effective_from: string;
  effective_to: string | null;
  source_note: string;
};

export type SettingRow = { key: string; value: unknown };

const keys = {
  price: ["rules", "price"] as const,
  subsidy: ["rules", "subsidy"] as const,
  settings: ["rules", "settings"] as const,
};

export const usePriceRules = () => useQuery({ queryKey: keys.price, queryFn: () => api<PriceRule[]>("/api/rules/price") });
export const useSubsidyRules = () =>
  useQuery({ queryKey: keys.subsidy, queryFn: () => api<SubsidyRule[]>("/api/rules/subsidy") });
export const useSettingsRows = () =>
  useQuery({ queryKey: keys.settings, queryFn: () => api<SettingRow[]>("/api/rules/settings") });

function useRulesWrite<Body>(key: readonly string[], call: (body: Body) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: key });
      client.invalidateQueries({ queryKey: ["staff", "preview"] });
    },
  });
}

export const useCreatePriceRule = () =>
  useRulesWrite(keys.price, (body: Omit<PriceRule, "id">) => api("/api/rules/price", { json: body }));
export const useClosePriceRule = () =>
  useRulesWrite(keys.price, ({ id, effective_to }: { id: string; effective_to: string | null }) =>
    api(`/api/rules/price/${id}`, { method: "PATCH", json: { effective_to } }),
  );
export const useCreateSubsidyRule = () =>
  useRulesWrite(keys.subsidy, (body: Omit<SubsidyRule, "id">) => api("/api/rules/subsidy", { json: body }));
export const useCloseSubsidyRule = () =>
  useRulesWrite(keys.subsidy, ({ id, effective_to }: { id: string; effective_to: string | null }) =>
    api(`/api/rules/subsidy/${id}`, { method: "PATCH", json: { effective_to } }),
  );
export const useUpdateSetting = () =>
  useRulesWrite(keys.settings, ({ key, value }: { key: string; value: unknown }) =>
    api(`/api/rules/settings/${key}`, { method: "PUT", json: { value } }),
  );
