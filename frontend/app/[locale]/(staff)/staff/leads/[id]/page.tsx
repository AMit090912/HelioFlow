"use client";

import { ArrowLeft, Check, ChevronDown, Phone } from "lucide-react";
import { use, type ReactNode } from "react";

import { AdvanceForm } from "@/components/staff/advance-form";
import { BillCompare } from "@/components/staff/bill-compare";
import { FLAG_LABEL, NEXT_ACTION_LABEL, reasonText, STATUS_LABEL, when } from "@/components/staff/copy";
import { LeadActions } from "@/components/staff/lead-actions";
import { nextStep, statusLabel, type SectionId } from "@/components/staff/next-step";
import { NextStepCard } from "@/components/staff/next-step-card";
import { QuoteBuilder } from "@/components/staff/quote-builder";
import { FlagChip, ScoreBadge } from "@/components/staff/score-badge";
import { VerificationForm } from "@/components/staff/verification-form";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatRupees } from "@/lib/format";
import { useProjects } from "@/lib/projects";
import { useStaffLead, type StaffLeadDetail } from "@/lib/staff";
import { cn } from "@/lib/utils";

const ROOF_LABEL: Record<string, string> = { rcc_flat: "Flat RCC", metal_sheet: "Metal sheet", tiled: "Tiled", other: "Other" };
const EVENT_LABEL: Record<string, string> = {
  verified: "Verified roof/load",
  upgraded: "Upgraded to survey visit",
  closed: "Closed",
  quote_sent: "Quote sent",
  quote_accepted: "Quote accepted",
  converted: "Advance recorded, project started",
  link_regenerated: "New status link made (old one stopped)",
  link_revoked: "Status link turned off",
};

export default function StaffLeadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: lead, error, refetch } = useStaffLead(id);

  return (
    <div className="space-y-6">
      <Link href="/staff/leads" className="inline-flex min-h-11 items-center gap-1.5 text-[0.9375rem] font-medium text-teal hover:underline">
        <ArrowLeft className="size-4" aria-hidden /> All leads
      </Link>
      {error && !lead ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          {error instanceof ApiError && (error.status === 404 || error.status === 422) ? (
            <p className="text-ink">This lead doesn&apos;t exist.</p>
          ) : (
            <>
              <p className="text-ink">Couldn&apos;t load this lead.</p>
              <Button variant="outline" className="h-11" onClick={() => refetch()}>
                Try again
              </Button>
            </>
          )}
        </div>
      ) : !lead ? (
        <div className="space-y-4" aria-busy="true">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      ) : (
        <LeadView lead={lead} />
      )}
    </div>
  );
}

type SectionState = "now" | "done" | undefined;

function Section({
  id,
  title,
  children,
  aside,
  state,
}: {
  id?: SectionId;
  title: string;
  children: ReactNode;
  aside?: ReactNode;
  state?: SectionState;
}) {
  const shell = cn(
    "scroll-mt-6 rounded-2xl border bg-background outline-none",
    state === "now" ? "border-gold shadow-[0_0_0_3px_rgba(229,178,87,0.25)]" : "border-border",
  );
  const heading = (
    <h2 id={id ? `section-${id}-title` : undefined} className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
      {title}
      {state === "now" ? (
        <span className="rounded-full bg-gold px-2.5 py-0.5 font-sans text-[0.75rem] font-semibold text-night">Do this now</span>
      ) : state === "done" ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-teal-wash px-2.5 py-0.5 font-sans text-[0.75rem] font-medium text-teal">
          <Check className="size-3" aria-hidden /> Done
        </span>
      ) : null}
    </h2>
  );
  const common = {
    id: id ? `section-${id}` : undefined,
    tabIndex: id ? -1 : undefined,
    "aria-labelledby": id ? `section-${id}-title` : undefined,
  };

  // Finished steps fold away (still one click to check or correct), so the page leads with what is left.
  if (state === "done") {
    return (
      <section {...common} className={shell}>
        <details className="group">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl p-5 hover:bg-surface/40 sm:px-6 [&::-webkit-details-marker]:hidden">
            {heading}
            <span className="inline-flex items-center gap-1 text-sm font-medium text-teal">
              <span className="group-open:hidden">Show</span>
              <span className="hidden group-open:inline">Hide</span>
              <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden />
            </span>
          </summary>
          <div className="px-5 pb-5 sm:px-6 sm:pb-6">
            {aside ? <div className="mb-3">{aside}</div> : null}
            {children}
          </div>
        </details>
      </section>
    );
  }
  return (
    <section {...common} className={cn(shell, "p-5 sm:p-6")}>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        {heading}
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Where each section sits in the work order; a section is done once the lead has moved past it. */
const SECTION_ORDER: SectionId[] = ["bill", "roof", "quote", "project"];

function LeadView({ lead }: { lead: StaffLeadDetail }) {
  // A started project's stage decides its next step; the list is small and already cached.
  const { data: projects } = useProjects();
  const stage = lead.status === "converted" ? (projects?.find((p) => p.lead_id === lead.id)?.stage ?? null) : null;
  const next = nextStep(lead, stage);
  const current = next.owner === "you" ? next.section : undefined;
  const reached = next.section ? SECTION_ORDER.indexOf(next.section) : -1;
  // Upgrade and close only apply before a quote is accepted (the API refuses them after).
  const canAct = !["accepted", "converted", "closed_lost"].includes(lead.status);
  const stateOf = (id: SectionId): SectionState =>
    id === current ? "now" : next.step === "done" || SECTION_ORDER.indexOf(id) < reached ? "done" : undefined;

  return (
    <>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-ink-2 tabular">
            {lead.code} · received {when(lead.created_at)}
          </p>
          <h1 className="font-display mt-1 text-[2rem] font-semibold leading-tight text-ink">{lead.homeowner.full_name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <ScoreBadge score={lead.score} />
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5",
                next.step === "done" ? "bg-teal-wash font-medium text-teal" : "bg-surface text-ink",
              )}
            >
              {next.step === "done" ? <Check className="size-3.5" aria-hidden /> : null}
              {statusLabel(lead, next, STATUS_LABEL)}
            </span>
            {lead.next_action && next.step === "check" ? (
              <span className="text-ink-2">Suggested check: {NEXT_ACTION_LABEL[lead.next_action]}</span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col items-start gap-1 text-sm sm:items-end">
          {lead.homeowner.phone ? (
            <a href={`tel:+91${lead.homeowner.phone}`} className="inline-flex min-h-11 items-center gap-2 font-medium text-teal hover:underline">
              <Phone className="size-4" aria-hidden /> +91 {lead.homeowner.phone}
            </a>
          ) : null}
          {lead.homeowner.email ? <span className="text-ink-2">{lead.homeowner.email}</span> : null}
          <span className="text-ink-2">Speaks {({ en: "English", hi: "Hindi", mr: "Marathi" } as Record<string, string>)[lead.homeowner.preferred_locale]}</span>
        </div>
      </header>

      <NextStepCard next={next} phone={lead.homeowner.phone} />

      {lead.seed_note ? <p className="rounded-xl bg-surface px-4 py-2.5 text-sm text-ink-2">Seed data: {lead.seed_note}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        {/* Top to bottom in the order the work happens. */}
        <div className="space-y-6">
          <Section id="bill" title="Bill" state={stateOf("bill")}>
            {lead.current_reading ? (
              <BillCompare reading={lead.current_reading} />
            ) : (
              <p className="text-ink-2">The homeowner hasn&apos;t confirmed a bill yet.</p>
            )}
          </Section>
          <Section id="roof" title="Roof and load" state={stateOf("roof")}>
            <VerificationForm key={lead.roof_verified_at ?? "new"} lead={lead} />
          </Section>
          <Section id="quote" title="Quote builder" state={stateOf("quote")} aside={<span className="text-sm text-ink-2">Prices are GST-inclusive</span>}>
            <QuoteBuilder lead={lead} />
          </Section>
          {lead.status === "accepted" || lead.status === "converted" ? (
            <Section id="project" title="Project" state={stateOf("project")}>
              {/* Stays mounted across the accepted → converted refetch so the one-time link stays visible. */}
              <AdvanceForm lead={lead} />
            </Section>
          ) : null}
        </div>
        <div className="space-y-6">
          <Section title="Why this score">
            {lead.score_reasons.length ? (
              <ul className="space-y-1.5 text-[0.9375rem] text-ink">
                {lead.score_reasons.map((r) => (
                  <li key={r.code}>{reasonText(r)}</li>
                ))}
              </ul>
            ) : (
              <p className="text-[0.9375rem] text-ink">{lead.score ? "Owner, bill above the survey threshold, usage known." : "Not scored yet."}</p>
            )}
            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-ink-2">Declared bill</dt>
              <dd className="text-ink tabular">{formatRupees(lead.declared_monthly_bill, "en")}</dd>
              <dt className="text-ink-2">Roof (declared)</dt>
              <dd className="text-ink tabular">
                {lead.roof_area_sqft} sq ft, {ROOF_LABEL[lead.roof_type]}
              </dd>
              <dt className="text-ink-2">Owner / type</dt>
              <dd className="text-ink">
                {lead.ownership === "owner" ? "Owner" : "Tenant"}, {lead.property_type}
              </dd>
              <dt className="text-ink-2">Pincode</dt>
              <dd className="text-ink tabular">{lead.pincode}</dd>
              <dt className="text-ink-2">Size</dt>
              <dd className="text-ink">
                {lead.accepted_kw
                  ? `${lead.accepted_kw} kW (accepted)`
                  : lead.recommended_kw
                    ? `${lead.recommended_kw} kW (${lead.recommendation_status})`
                    : "None"}
              </dd>
            </dl>
            {lead.flags.length ? (
              <div className="mt-3 flex flex-wrap gap-1">
                {lead.flags.map((f) => (
                  <FlagChip key={f}>{FLAG_LABEL[f] ?? f}</FlagChip>
                ))}
              </div>
            ) : null}
          </Section>
          <Section title={canAct ? "Actions" : "History"}>
            {canAct ? (
              <>
                <LeadActions lead={lead} />
                <h3 className="mt-5 border-t border-border pt-4 text-sm font-semibold text-ink">History</h3>
              </>
            ) : (
              <p className="text-sm text-ink-2">
                {lead.status === "closed_lost"
                  ? "This lead is closed, so there is nothing left to change."
                  : next.step === "done"
                    ? "This project is complete: the subsidy is credited. Nothing left to change."
                    :"The homeowner accepted a quote, so this lead can't be closed as lost. Its project carries on to Subsidy credited and then shows as Completed."}
              </p>
            )}
            {lead.events.length ? (
              <ol className="mt-3 space-y-3 text-sm">
                {lead.events.map((e) => (
                  <li key={e.id}>
                    <p className="font-medium text-ink">
                      {EVENT_LABEL[e.kind] ?? e.kind}
                      {e.to_status && e.from_status !== e.to_status ? (
                        <span className="font-normal text-ink-2"> → {STATUS_LABEL[e.to_status] ?? e.to_status}</span>
                      ) : null}
                    </p>
                    <p className="text-ink-2">
                      {e.actor_name} · {when(e.created_at)}
                    </p>
                    {e.note ? <p className="text-ink">{e.note}</p> : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-2 text-sm text-ink-2">Nothing has happened on this lead yet.</p>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}
