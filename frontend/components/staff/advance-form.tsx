"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { projectError } from "@/components/staff/copy";
import { LiveProjectPanel } from "@/components/staff/project-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatRupees, parseDecimalInput } from "@/lib/format";
import { useProjects, useRecordAdvance, type ProjectDetail } from "@/lib/projects";
import { focusOption, useQuote } from "@/lib/quotes";
import type { StaffLeadDetail } from "@/lib/staff";

/** Record the (simulated) advance on an accepted quote: starts the project (§12 stage 1). */
export function AdvanceForm({ lead }: { lead: StaffLeadDetail }) {
  const accepted = lead.quotes.find((q) => q.status === "accepted");
  const { data: quote } = useQuote(accepted?.id ?? "", !!accepted);
  const record = useRecordAdvance(lead.id);
  const { data: projects } = useProjects();
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ project: ProjectDetail; token: string } | null>(null);

  if (created) {
    return (
      <div className="space-y-3">
        <p role="status" className="text-sm font-medium text-teal">
          Advance recorded. The project has started and the homeowner was told (simulated).
        </p>
        <LiveProjectPanel id={created.project.id} freshToken={created.token} homeownerLocale={lead.homeowner.preferred_locale} onLeadPage />
      </div>
    );
  }
  if (lead.status === "converted") {
    // The stage controls live here too, so the lead's next step can be done on the lead's page.
    const project = projects?.find((p) => p.lead_id === lead.id);
    if (project) return <LiveProjectPanel id={project.id} homeownerLocale={lead.homeowner.preferred_locale} onLeadPage />;
    return (
      <Link
        href={{ pathname: "/staff/projects", query: { lead: lead.id } }}
        className="inline-flex min-h-11 items-center font-medium text-teal hover:underline"
      >
        Open the project
      </Link>
    );
  }
  if (!accepted) return null;
  const net = quote ? focusOption(quote).net : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const value = parseDecimalInput(amount);
    if (!value || Number(value) <= 0) return setError("Enter the advance amount in rupees.");
    try {
      const out = await record.mutateAsync(value);
      setCreated({ project: out.project, token: out.status_token });
    } catch (err) {
      setError(err instanceof ApiError ? projectError(err.code, err.message) : "Couldn't record the advance.");
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <p className="text-[0.9375rem] text-ink">
        {lead.homeowner.full_name} accepted {accepted.number} for {accepted.selected_kw} kW
        {net ? ` (${formatRupees(net, "en")} after subsidy)` : ""}. Payments are simulated: enter the amount
        received and a <span className="tabular">SIMULATED-</span> reference is created.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1 text-sm">
          <span className="block font-medium text-ink">Advance received (₹)</span>
          <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} className="h-11 w-48 tabular" />
        </label>
        <Button type="submit" className="h-11" disabled={record.isPending}>
          {record.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Record advance and start project
        </Button>
      </div>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </form>
  );
}
