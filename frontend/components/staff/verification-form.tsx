"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { errorText } from "@/components/staff/copy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { useVerify, type StaffLeadDetail } from "@/lib/staff";
import { cn } from "@/lib/utils";

const VERIFIABLE = new Set(["survey_pending", "call_pending", "surveyed", "quoted"]);

/** Roof capacity and sanctioned load confirmed by staff (§8, A-29). Required before a quote. */
export function VerificationForm({ lead }: { lead: StaffLeadDetail }) {
  const verify = useVerify(lead.id);
  const [roof, setRoof] = useState(lead.verified_roof_area_sqft ?? lead.roof_area_sqft);
  const [via, setVia] = useState<"survey" | "call">(lead.roof_verified_via ?? (lead.next_action === "call" ? "call" : "survey"));
  const [load, setLoad] = useState(lead.sanctioned_load.value ?? "");
  const [notes, setNotes] = useState(lead.survey_notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const locked = !VERIFIABLE.has(lead.status);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    const roofValue = parseDecimalInput(roof);
    const loadValue = load.trim() === "" ? null : parseDecimalInput(load);
    if (!roofValue || Number(roofValue) <= 0) return setError("Enter the measured roof area in sq ft.");
    if (load.trim() !== "" && (!loadValue || Number(loadValue) <= 0 || Number(loadValue) > 100))
      return setError("Sanctioned load must be between 0.1 and 100 kW.");
    try {
      await verify.mutateAsync({
        roof_area_sqft: roofValue,
        via,
        // Only send a load when staff typed one different from what the bill already says.
        sanctioned_load_kw: loadValue && !(lead.sanctioned_load.source === "bill" && loadValue === lead.sanctioned_load.value) ? loadValue : null,
        notes: notes.trim() || null,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err.code, err.message) : "Couldn't save. Try again.");
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="v-roof">Usable roof area (sq ft)</Label>
          <Input id="v-roof" inputMode="decimal" value={roof} onChange={(e) => setRoof(e.target.value)} className="h-11 tabular" disabled={locked} />
          <p className="text-[0.8125rem] text-ink-2">Homeowner said {lead.roof_area_sqft} sq ft.</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="v-load">Sanctioned load (kW)</Label>
          <Input id="v-load" inputMode="decimal" value={load} onChange={(e) => setLoad(e.target.value)} className="h-11 tabular" disabled={locked} />
          <p className="text-[0.8125rem] text-ink-2">
            {lead.sanctioned_load.source === "bill"
              ? "From the confirmed bill."
              : lead.sanctioned_load.source === "staff"
                ? "Entered by staff."
                : "Not on the bill: enter it from the DISCOM record."}
          </p>
        </div>
      </div>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium text-ink">Verified by</legend>
        <div className="flex gap-2">
          {(["survey", "call"] as const).map((v) => (
            <label
              key={v}
              className={cn(
                "flex h-11 cursor-pointer items-center gap-2 rounded-xl border px-4 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-teal",
                via === v ? "border-teal bg-teal-wash/60 font-medium text-ink" : "border-border text-ink-2",
              )}
            >
              <input type="radio" name="via" value={v} checked={via === v} onChange={() => setVia(v)} className="sr-only" disabled={locked} />
              {v === "survey" ? "Site survey" : "Phone call"}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1.5">
        <Label htmlFor="v-notes">Survey notes</Label>
        <textarea
          id="v-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          maxLength={2000}
          disabled={locked}
          className="w-full rounded-xl border border-input bg-background px-3 py-2 text-[0.9375rem] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      {saved && !error ? <p role="status" className="text-sm text-teal">Saved. The quote builder now uses these values.</p> : null}
      <Button type="submit" className="h-11" disabled={verify.isPending || locked}>
        {verify.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
        {lead.verified_roof_area_sqft ? "Update verification" : "Save verification"}
      </Button>
    </form>
  );
}
