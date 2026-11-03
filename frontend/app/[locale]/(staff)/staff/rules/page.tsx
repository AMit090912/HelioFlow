"use client";

import { Lock } from "lucide-react";
import { useState, type ReactNode } from "react";

import { projectError } from "@/components/staff/copy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { formatDay, formatNumber, formatRupees, parseDecimalInput } from "@/lib/format";
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
import { cn } from "@/lib/utils";

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
  const { data, isError, refetch } = usePriceRules();
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
        isError ? <LoadFailed onRetry={() => refetch()} /> : <Skeleton className="h-24 w-full" />
      ) : (
        <ul className="space-y-4">
          {data.map((r) => (
            <RuleBlock
              key={r.id}
              rule={r}
              note={r.note}
              noteLabel="Note"
              action={canEdit && !r.effective_to ? <EndDate rule={r} onSave={(to) => close.mutateAsync({ id: r.id, effective_to: to })} /> : null}
            >
              <p className="font-display text-2xl font-semibold text-ink tabular">
                {formatRupees(r.price_per_kw, "en")} <span className="text-base font-medium text-ink-2">per kW</span>
              </p>
              <dl className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-3">
                <Fact label="System sizes">
                  {formatNumber(r.min_kw, "en", 2)} to {formatNumber(r.max_kw, "en", 2)} kW
                </Fact>
                <Fact label="GST">{r.gst_inclusive ? "Included in the price" : "Added on top"}</Fact>
                <Fact label="In force">
                  <InForce rule={r} />
                </Fact>
              </dl>
            </RuleBlock>
          ))}
        </ul>
      )}
      {canEdit ? (
        <form onSubmit={add} className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-[repeat(4,minmax(0,1fr))_auto] sm:items-end" noValidate>
          <h3 className="font-medium text-ink sm:col-span-5">Add a price rule</h3>
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

/** "0–2" → "First 2 kW", "2–3" → "Next 1 kW (2 to 3 kW)": how the slabs actually add up. */
function slabRange(s: Slab) {
  const from = Number(s.from_kw);
  const to = Number(s.to_kw);
  const kw = (n: number) => formatNumber(String(n), "en", 2);
  return from === 0 ? `First ${kw(to)} kW` : `Next ${kw(to - from)} kW (${kw(from)} to ${kw(to)} kW)`;
}

/** "CENTRAL_RESIDENTIAL", "residential" → "Central scheme, residential homes". */
function schemeName(code: string, segment: string) {
  const scheme = code.split("_")[0].toLowerCase();
  return `${scheme.charAt(0).toUpperCase()}${scheme.slice(1)} scheme, ${segment} homes`;
}

type Dated = { effective_from: string; effective_to: string | null };

/** Today in India, as YYYY-MM-DD, to compare with rule dates (the end date is inclusive). */
function todayInIndia() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

function ruleState(rule: Dated): { label: string; className: string } {
  const today = todayInIndia();
  if (rule.effective_from > today) return { label: "Starts later", className: "bg-gold-soft/40 text-ink" };
  if (rule.effective_to && rule.effective_to < today) return { label: "Ended", className: "bg-surface text-ink-2" };
  return { label: "In use now", className: "bg-teal-wash text-teal-deep" };
}

function InForce({ rule }: { rule: Dated }) {
  return (
    <>
      From {formatDay(rule.effective_from, "en")}
      <span className="block text-ink-2">{rule.effective_to ? `until ${formatDay(rule.effective_to, "en")}` : "No end date set"}</span>
    </>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[0.8125rem] text-ink-2">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-ink tabular">{children}</dd>
    </div>
  );
}

/** One rule: its status, the figures, then the note or source set apart, and the end-date control. */
function RuleBlock({
  rule,
  note,
  noteLabel,
  action,
  children,
}: {
  rule: Dated;
  note: string | null;
  noteLabel: string;
  action: ReactNode;
  children: ReactNode;
}) {
  const state = ruleState(rule);
  const ended = state.label === "Ended";
  return (
    <li className={cn("rounded-xl border border-border p-4 sm:p-5", ended && "opacity-70")}>
      <span className={cn("inline-block rounded-full px-2.5 py-0.5 text-xs font-medium", state.className)}>{state.label}</span>
      <div className="mt-3">{children}</div>
      {note ? (
        <p className="mt-4 max-w-2xl rounded-lg bg-surface px-3 py-2 text-sm text-ink-2">
          <span className="font-medium text-ink">{noteLabel}: </span>
          {note}
        </p>
      ) : null}
      {action ? <div className="mt-4 border-t border-border pt-4">{action}</div> : null}
    </li>
  );
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
  const { data, isError, refetch } = useSubsidyRules();
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
        isError ? <LoadFailed onRetry={() => refetch()} /> : <Skeleton className="h-24 w-full" />
      ) : (
        <ul className="space-y-4">
          {data.map((r: SubsidyRule) => (
            <RuleBlock
              key={r.id}
              rule={r}
              note={r.source_note}
              noteLabel="Source"
              action={canEdit && !r.effective_to ? <EndDate rule={r} onSave={(to) => close.mutateAsync({ id: r.id, effective_to: to })} /> : null}
            >
              <p className="font-display text-xl font-semibold text-ink">{schemeName(r.scheme_code, r.segment)}</p>
              <table className="mt-3 w-full max-w-md text-sm tabular">
                <caption className="sr-only">Subsidy by system size</caption>
                <tbody className="divide-y divide-border">
                  {r.slabs.map((s) => (
                    <tr key={`${s.from_kw}-${s.to_kw}`}>
                      <th scope="row" className="py-2 pr-4 text-left font-normal text-ink-2">
                        {slabRange(s)}
                      </th>
                      <td className="py-2 text-right font-medium text-ink">{formatRupees(s.amount_per_kw, "en")} per kW</td>
                    </tr>
                  ))}
                  <tr>
                    <th scope="row" className="py-2 pr-4 text-left font-normal text-ink-2">
                      Most a home can get
                    </th>
                    <td className="py-2 text-right font-semibold text-ink">{formatRupees(r.cap_amount, "en")}</td>
                  </tr>
                </tbody>
              </table>
              <dl className="mt-4">
                <Fact label="In force">
                  <InForce rule={r} />
                </Fact>
              </dl>
            </RuleBlock>
          ))}
        </ul>
      )}
      {canEdit ? (
        <form onSubmit={add} className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-3" noValidate>
          <h3 className="font-medium text-ink sm:col-span-3">Add a subsidy rule</h3>
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

/** A card whose rows couldn't load: say so and offer a retry, never an endless placeholder. */
function LoadFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3">
      <p className="text-ink">Couldn&apos;t load this list. Check your connection and try again.</p>
      <Button variant="outline" className="h-11" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function show(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function Settings({ canEdit }: { canEdit: boolean }) {
  const { data, isError, refetch } = useSettingsRows();
  return (
    <Card title="Settings">
      {!data ? (
        isError ? <LoadFailed onRetry={() => refetch()} /> : <Skeleton className="h-24 w-full" />
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
