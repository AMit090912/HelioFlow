"use client";

import { Lock } from "lucide-react";
import { useState, type ReactNode } from "react";

import { projectError } from "@/components/staff/copy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { formatNumber, formatRupees, parseDecimalInput } from "@/lib/format";
import {
  useClosePriceRule,
  useCloseSubsidyRule,
  useCreatePriceRule,
  useCreateSubsidyRule,
  usePriceRules,
  useSettingsRows,
  useSubsidyRules,
  useUpdateSetting,
  type PriceRule,
  type Slab,
  type SubsidyRule,
} from "@/lib/rules";
import { useSession } from "@/lib/use-session";

const SETTING_LABEL: Record<string, { label: string; hint: string; id: string }> = {
  generation_kwh_per_kw_year: { label: "Generation per kW per year (kWh)", hint: "Client figure", id: "CLIENT" },
  roof_sqft_per_kw: { label: "Roof area per kW (sq ft)", hint: "Roof capacity check", id: "A-2" },
  min_monthly_bill_for_survey: { label: "Minimum monthly bill for a survey (₹)", hint: "Below this: call first", id: "A-1" },
  capacity_options_kw: { label: "System sizes offered (kW, comma-separated)", hint: "Ascending whole sizes", id: "A-9" },
  usable_generation_pct: { label: "Share of generation used (0–1)", hint: "e.g. 0.9 = 90%", id: "A-6" },
  default_fixed_charge_monthly: { label: "Default fixed charge per month (₹)", hint: "When the bill doesn't show it", id: "A-8" },
  quote_option_offsets: { label: "Options around the suggested size (comma-separated)", hint: "Must include 0", id: "A-10" },
};

function errText(err: unknown) {
  return err instanceof ApiError ? projectError(err.code, err.message) : "Couldn't save. Try again.";
}

const dateFmt = (d: string | null) => d ?? "open-ended";

export default function RulesPage() {
  const { user } = useSession();
  const canEdit = user?.role === "admin";
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[2.25rem] font-semibold text-ink">Rules and settings</h1>
        <p className="mt-1 max-w-2xl text-ink-2">
          Prices and subsidy are chosen by the quote date. A rule ends by giving it an end date; it is never deleted. Quotes
          already sent keep their own copy of the rules they used.
        </p>
        {!canEdit ? (
          <p className="mt-3 inline-flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-sm text-ink-2">
            <Lock className="size-4" aria-hidden /> View only. Only an admin can change rules.
          </p>
        ) : null}
      </div>
      <PriceRules canEdit={canEdit} />
      <SubsidyRules canEdit={canEdit} />
      <Settings canEdit={canEdit} />
    </div>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-background p-5 sm:p-6">
      <h2 className="mb-4 font-display text-xl font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

function EndDate({ rule, onSave }: { rule: { effective_to: string | null }; onSave: (to: string) => Promise<unknown> }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  if (rule.effective_to) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input type="date" aria-label="End date" value={value} onChange={(e) => setValue(e.target.value)} className="h-9 w-40" />
      <Button
        variant="outline"
        className="h-9"
        disabled={!value}
        onClick={async () => {
          setError(null);
          try {
            await onSave(value);
            setValue("");
          } catch (err) {
            setError(errText(err));
          }
        }}
      >
        End rule
      </Button>
      {error ? <p role="alert" className="w-full text-sm text-destructive">{error}</p> : null}
    </div>
  );
}

function PriceRules({ canEdit }: { canEdit: boolean }) {
  const { data } = usePriceRules();
  const close = useClosePriceRule();
  const create = useCreatePriceRule();
  const [form, setForm] = useState({ min_kw: "1", max_kw: "10", price_per_kw: "", effective_from: "", note: "" });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    const price = parseDecimalInput(form.price_per_kw);
    if (!price || !form.effective_from) return setError("Enter a price per kW and a start date.");
    try {
      await create.mutateAsync({ ...form, price_per_kw: price, gst_inclusive: true, effective_to: null, note: form.note || null } as Omit<PriceRule, "id">);
      setSaved(true);
      setForm((f) => ({ ...f, price_per_kw: "", effective_from: "", note: "" }));
    } catch (err) {
      setError(errText(err));
    }
  };

  return (
    <Card title="Price rules">
      {!data ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <ul className="divide-y divide-border">
          {data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <p className="font-medium text-ink tabular">
                  {formatRupees(r.price_per_kw, "en")} per kW · {r.min_kw}–{r.max_kw} kW · GST included
                </p>
                <p className="text-sm text-ink-2 tabular">
                  {r.effective_from} → {dateFmt(r.effective_to)}
                  {r.note ? ` · ${r.note}` : ""}
                </p>
              </div>
              {canEdit ? <EndDate rule={r} onSave={(to) => close.mutateAsync({ id: r.id, effective_to: to })} /> : null}
            </li>
          ))}
        </ul>
      )}
      {canEdit ? (
        <form onSubmit={add} className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-[repeat(4,minmax(0,1fr))_auto] sm:items-end" noValidate>
          <Labeled label="From kW">
            <Input value={form.min_kw} onChange={(e) => setForm({ ...form, min_kw: e.target.value })} inputMode="decimal" className="h-10" />
          </Labeled>
          <Labeled label="To kW">
            <Input value={form.max_kw} onChange={(e) => setForm({ ...form, max_kw: e.target.value })} inputMode="decimal" className="h-10" />
          </Labeled>
          <Labeled label="₹ per kW">
            <Input value={form.price_per_kw} onChange={(e) => setForm({ ...form, price_per_kw: e.target.value })} inputMode="decimal" className="h-10" />
          </Labeled>
          <Labeled label="Starts on">
            <Input type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} className="h-10" />
          </Labeled>
          <Button type="submit" className="h-10" disabled={create.isPending}>
            Add rule
          </Button>
          <div className="sm:col-span-5">
            <Labeled label="Note (optional)">
              <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className="h-10" />
            </Labeled>
          </div>
          {error ? <p role="alert" className="text-sm text-destructive sm:col-span-5">{error}</p> : null}
          {saved ? <p role="status" className="text-sm text-teal sm:col-span-5">Rule added.</p> : null}
        </form>
      ) : null}
    </Card>
  );
}

function slabText(slabs: Slab[]) {
  return slabs
    .map((s) => `${s.from_kw}–${s.to_kw} kW at ${formatRupees(s.amount_per_kw, "en")}/kW`)
    .join(", ");
}

/** "0-2:30000, 2-3:18000" → slabs. Returns null if a part doesn't parse. */
function parseSlabs(text: string): Slab[] | null {
  const parts = text.split(/[\n,;]+/).map((p) => p.trim()).filter(Boolean);
  const slabs: Slab[] = [];
  for (const part of parts) {
    const m = /^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*:\s*([\d,]+)$/.exec(part);
    if (!m) return null;
    slabs.push({ from_kw: m[1], to_kw: m[2], amount_per_kw: m[3].replace(/,/g, "") });
  }
  return slabs.length ? slabs : null;
}

function SubsidyRules({ canEdit }: { canEdit: boolean }) {
  const { data } = useSubsidyRules();
  const close = useCloseSubsidyRule();
  const create = useCreateSubsidyRule();
  const [form, setForm] = useState({ slabs: "", cap_amount: "", effective_from: "", source_note: "" });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    const slabs = parseSlabs(form.slabs);
    const cap = parseDecimalInput(form.cap_amount);
    if (!slabs) return setError('Write slabs like "0-2:30000, 2-3:18000" (kW range : ₹ per kW).');
    if (cap === null || !form.effective_from || form.source_note.trim().length < 3)
      return setError("Enter the cap, a start date and where the figures come from.");
    try {
      await create.mutateAsync({
        scheme_code: "CENTRAL_RESIDENTIAL",
        segment: "residential",
        slabs,
        cap_amount: cap,
        effective_from: form.effective_from,
        effective_to: null,
        source_note: form.source_note.trim(),
      });
      setSaved(true);
      setForm({ slabs: "", cap_amount: "", effective_from: "", source_note: "" });
    } catch (err) {
      setError(errText(err));
    }
  };

  return (
    <Card title="Subsidy rules">
      {!data ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <ul className="divide-y divide-border">
          {data.map((r: SubsidyRule) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="max-w-2xl">
                <p className="font-medium text-ink">
                  {r.scheme_code} · {r.segment}
                </p>
                <p className="text-sm text-ink tabular">
                  {slabText(r.slabs)} · cap {formatRupees(r.cap_amount, "en")}
                </p>
                <p className="text-sm text-ink-2 tabular">
                  {r.effective_from} → {dateFmt(r.effective_to)} · {r.source_note}
                </p>
              </div>
              {canEdit ? <EndDate rule={r} onSave={(to) => close.mutateAsync({ id: r.id, effective_to: to })} /> : null}
            </li>
          ))}
        </ul>
      )}
      {canEdit ? (
        <form onSubmit={add} className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-3" noValidate>
          <div className="sm:col-span-3">
            <Labeled label="Slabs (kW range : ₹ per kW)">
              <Input value={form.slabs} onChange={(e) => setForm({ ...form, slabs: e.target.value })} placeholder="0-2:30000, 2-3:18000" className="h-10" />
            </Labeled>
          </div>
          <Labeled label="Cap (₹)">
            <Input value={form.cap_amount} onChange={(e) => setForm({ ...form, cap_amount: e.target.value })} inputMode="decimal" className="h-10" />
          </Labeled>
          <Labeled label="Starts on">
            <Input type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} className="h-10" />
          </Labeled>
          <Labeled label="Source of the figures">
            <Input value={form.source_note} onChange={(e) => setForm({ ...form, source_note: e.target.value })} className="h-10" />
          </Labeled>
          <div className="sm:col-span-3">
            <Button type="submit" className="h-10" disabled={create.isPending}>
              Add subsidy rule
            </Button>
          </div>
          {error ? <p role="alert" className="text-sm text-destructive sm:col-span-3">{error}</p> : null}
          {saved ? <p role="status" className="text-sm text-teal sm:col-span-3">Rule added.</p> : null}
        </form>
      ) : null}
    </Card>
  );
}

function show(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function Settings({ canEdit }: { canEdit: boolean }) {
  const { data } = useSettingsRows();
  return (
    <Card title="Settings">
      {!data ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <ul className="divide-y divide-border">
          {data.map((row) => (
            <SettingRow key={row.key} name={row.key} value={row.value} canEdit={canEdit} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function SettingRow({ name, value, canEdit }: { name: string; value: unknown; canEdit: boolean }) {
  const update = useUpdateSetting();
  const meta = SETTING_LABEL[name] ?? { label: name, hint: "", id: "" };
  const [draft, setDraft] = useState(show(value));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const isList = Array.isArray(value);

  const save = async () => {
    setError(null);
    setSaved(false);
    const parsed = isList ? draft.split(",").map((v) => v.trim()).filter(Boolean).map((v) => (name === "quote_option_offsets" ? Number(v) : v)) : draft.trim();
    try {
      await update.mutateAsync({ key: name, value: parsed });
      setSaved(true);
    } catch (err) {
      setError(errText(err));
    }
  };

  return (
    <li className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_16rem_auto] sm:items-center">
      <div>
        <p className="font-medium text-ink">{meta.label}</p>
        <p className="text-[0.8125rem] text-ink-2">
          {meta.hint}
          {meta.id ? ` · ${meta.id}` : ""}
        </p>
      </div>
      {canEdit ? (
        <>
          <Input aria-label={meta.label} value={draft} onChange={(e) => setDraft(e.target.value)} className="h-10 tabular" />
          <Button variant="outline" className="h-10" onClick={save} disabled={update.isPending || draft === show(value)}>
            Save
          </Button>
        </>
      ) : (
        <p className="font-medium text-ink tabular sm:col-span-2">
          {isList ? show(value) : formatNumber(String(value), "en", 4)}
        </p>
      )}
      {error ? <p role="alert" className="text-sm text-destructive sm:col-span-3">{error}</p> : null}
      {saved && !error ? <p role="status" className="text-sm text-teal sm:col-span-3">Saved. New previews and quotes use it.</p> : null}
    </li>
  );
}

function Labeled({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="block font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}
