"use client";

import { ChevronRight, Clock } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { SpotEmptyInbox } from "@/components/illustrations/spot";
import { age, FLAG_LABEL, reasonText, STATUS_LABEL } from "@/components/staff/copy";
import { nextStep, type NextStep } from "@/components/staff/next-step";
import { FlagChip, ScoreBadge } from "@/components/staff/score-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { useProjects, type Stage } from "@/lib/projects";
import { useStaffLeads, type InboxFilters, type StaffLeadRow } from "@/lib/staff";
import { cn } from "@/lib/utils";

const SCORES: { value: InboxFilters["score"]; label: string }[] = [
  { value: undefined, label: "All" },
  { value: "high", label: "High" },
  { value: "low", label: "Low" },
];
type Who = "you" | "homeowner" | "all";
const WHO: { value: Who; label: string }[] = [
  { value: "you", label: "Your move" },
  { value: "homeowner", label: "Waiting on homeowner" },
  { value: "all", label: "All" },
];
type Row = StaffLeadRow & { next: NextStep };

const STATUSES = ["survey_pending", "call_pending", "surveyed", "quoted", "accepted", "bill_review", "draft", "closed_lost"];

export default function LeadsInboxPage() {
  const t = useTranslations("staff");
  const [filters, setFilters] = useState<InboxFilters>({});
  const { data: rawLeads, error, isPending, isPlaceholderData, refetch } = useStaffLeads(filters);
  const { data: projects } = useProjects();
  const [who, setWho] = useState<Who>("you");

  // Each lead's next step; a started project's stage decides what "move it on" means.
  const rows = useMemo<Row[] | undefined>(() => {
    if (!rawLeads) return undefined;
    const stageOf = new Map<string, Stage>((projects ?? []).map((p) => [p.lead_id, p.stage]));
    return rawLeads.map((l) => ({ ...l, next: nextStep(l, stageOf.get(l.id)) }));
  }, [rawLeads, projects]);
  const count = (w: Who) => (rows ?? []).filter((r) => w === "all" || r.next.owner === w).length;
  const leads = rows?.filter((r) => who === "all" || r.next.owner === who);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[2.25rem] font-semibold text-ink">{t("leadsTitle")}</h1>
        <p className="mt-1 text-ink-2">{t("leadsSubtitle")}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Whose move" className="flex rounded-xl border border-border bg-background p-1">
          {WHO.map((w) => (
            <button
              key={w.value}
              type="button"
              aria-pressed={who === w.value}
              onClick={() => setWho(w.value)}
              className={cn(
                "inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium",
                who === w.value ? "bg-night text-white" : "text-ink-2 hover:bg-surface",
              )}
            >
              {w.label}
              {rows ? (
                <span
                  className={cn(
                    "rounded-full px-1.5 text-[0.75rem] tabular",
                    who === w.value ? "bg-gold text-night" : "bg-surface text-ink-2",
                  )}
                >
                  {count(w.value)}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Score" className="flex rounded-xl border border-border bg-background p-1">
          {SCORES.map((s) => (
            <button
              key={s.label}
              type="button"
              aria-pressed={filters.score === s.value}
              onClick={() => setFilters((f) => ({ ...f, score: s.value }))}
              className={cn(
                "h-9 min-w-14 rounded-lg px-3 text-sm font-medium",
                filters.score === s.value ? "bg-night text-white" : "text-ink-2 hover:bg-surface",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          Status
          <select
            value={filters.status ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined }))}
            className="h-11 rounded-xl border border-border bg-background px-3 text-ink"
          >
            <option value="">Open work</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        {leads ? (
          <p className="text-sm text-ink-2 sm:ml-auto" aria-live="polite">
            {leads.length} {leads.length === 1 ? "lead" : "leads"}
          </p>
        ) : null}
      </div>

      {error && !leads ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-ink">{error instanceof ApiError ? error.message : "Couldn't load leads."}</p>
          <Button variant="outline" className="h-11" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      ) : isPending ? (
        <div className="space-y-3" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-2xl" />
          ))}
        </div>
      ) : leads && leads.length === 0 ? (
        rows && rows.length > 0 ? (
          <EmptyState
            illustration={<SpotEmptyInbox className="w-full" />}
            title={who === "you" ? "Nothing waiting on you" : "Nobody to wait on"}
            message={
              who === "you"
                ? "Every open lead is with the homeowner for now. Check Waiting on homeowner if someone needs a nudge."
                : "No lead is waiting on a homeowner right now."
            }
          />
        ) : (
          <EmptyState
            illustration={<SpotEmptyInbox className="w-full" />}
            title={t("leadsEmptyTitle")}
            message={t("leadsEmpty")}
          />
        )
      ) : leads ? (
        <div className={cn("transition-opacity", isPlaceholderData && "opacity-60")}>
          <LeadTable leads={leads} />
          <ul className="space-y-3 md:hidden">
            {leads.map((lead) => (
              <li key={lead.id}>
                <LeadCard lead={lead} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SizeCell({ lead }: { lead: StaffLeadRow }) {
  if (!lead.recommended_kw) return <span className="text-ink-2">—</span>;
  return (
    <span>
      <span className="font-semibold text-ink tabular">{lead.recommended_kw} kW</span>
      {lead.recommendation_status === "provisional" ? <span className="ml-1.5 text-[0.8125rem] text-ink-2">provisional</span> : null}
    </span>
  );
}

function Flags({ lead }: { lead: StaffLeadRow }) {
  if (!lead.flags.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {lead.flags.map((f) => (
        <FlagChip key={f}>{FLAG_LABEL[f] ?? f}</FlagChip>
      ))}
    </div>
  );
}

function LeadTable({ leads }: { leads: Row[] }) {
  return (
    <div className="hidden overflow-hidden rounded-2xl border border-border bg-background md:block">
      <table className="w-full text-left text-[0.9375rem]">
        <thead className="border-b border-border bg-surface/70 text-[0.8125rem] text-ink-2">
          <tr>
            <th className="px-4 py-3 font-medium">Lead</th>
            <th className="px-4 py-3 font-medium">Score</th>
            <th className="px-4 py-3 font-medium">Why</th>
            <th className="px-4 py-3 font-medium">Size</th>
            <th className="px-4 py-3 font-medium">Next step</th>
            <th className="px-4 py-3 font-medium">Received</th>
            <th className="w-10" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {leads.map((lead) => (
            <tr key={lead.id} className="group relative align-top hover:bg-surface/50">
              <td className="px-4 py-3.5">
                <Link
                  href={`/staff/leads/${lead.id}`}
                  className="font-semibold text-ink after:absolute after:inset-0 focus-visible:outline-none group-has-[:focus-visible]:ring-2"
                >
                  {lead.homeowner_name}
                </Link>
                <p className="text-[0.8125rem] text-ink-2 tabular">
                  {lead.code} · {STATUS_LABEL[lead.status] ?? lead.status}
                </p>
              </td>
              <td className="px-4 py-3.5">
                <ScoreBadge score={lead.score} />
              </td>
              <td className="max-w-xs px-4 py-3.5 text-ink-2">
                {lead.score_reasons.length ? lead.score_reasons.map(reasonText).join("; ") : lead.score ? "Meets all checks" : "—"}
                <div className="mt-1.5">
                  <Flags lead={lead} />
                </div>
              </td>
              <td className="px-4 py-3.5">
                <SizeCell lead={lead} />
              </td>
              <td className="px-4 py-3.5">
                <NextCell next={lead.next} />
              </td>
              <td className="px-4 py-3.5 text-ink-2">{age(lead.created_at)}</td>
              <td className="px-2 py-3.5 text-ink-2">
                <ChevronRight className="size-4" aria-hidden />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LeadCard({ lead }: { lead: Row }) {
  return (
    <Link
      href={`/staff/leads/${lead.id}`}
      className="block rounded-2xl border border-border bg-background p-4 active:bg-surface"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-ink">{lead.homeowner_name}</p>
          <p className="text-[0.8125rem] text-ink-2 tabular">
            {lead.code} · {age(lead.created_at)}
          </p>
        </div>
        <ScoreBadge score={lead.score} />
      </div>
      <p className="mt-2 text-sm text-ink-2">
        {lead.score_reasons.length ? lead.score_reasons.map(reasonText).join("; ") : STATUS_LABEL[lead.status]}
      </p>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <SizeCell lead={lead} />
        <NextCell next={lead.next} />
      </div>
      <div className="mt-2">
        <Flags lead={lead} />
      </div>
    </Link>
  );
}

/** The task itself when it is the team's move; who it is waiting on otherwise. */
function NextCell({ next }: { next: NextStep }) {
  if (next.owner === "you") return <span className="font-semibold text-teal">{next.title}</span>;
  return (
    <span className="inline-flex items-start gap-1.5 text-ink-2">
      {next.owner === "homeowner" ? <Clock className="mt-0.5 size-3.5 shrink-0" aria-hidden /> : null}
      {next.title}
    </span>
  );
}
