"use client";

import { ArrowLeft, Phone } from "lucide-react";
import { use, type ReactNode } from "react";

import { AdvanceForm } from "@/components/staff/advance-form";
import { BillCompare } from "@/components/staff/bill-compare";
import { FLAG_LABEL, NEXT_ACTION_LABEL, reasonText, STATUS_LABEL, when } from "@/components/staff/copy";
import { LeadActions } from "@/components/staff/lead-actions";
import { QuoteBuilder } from "@/components/staff/quote-builder";
import { FlagChip, ScoreBadge } from "@/components/staff/score-badge";
import { VerificationForm } from "@/components/staff/verification-form";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatRupees } from "@/lib/format";
import { useStaffLead, type StaffLeadDetail } from "@/lib/staff";

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
          <p className="text-ink">{error instanceof ApiError && error.status === 404 ? "This lead doesn't exist." : "Couldn't load this lead."}</p>
          <Button variant="outline" className="h-11" onClick={() => refetch()}>
            Try again
          </Button>
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

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-background p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-xl font-semibold text-ink">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function LeadView({ lead }: { lead: StaffLeadDetail }) {
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
            <span className="rounded-full bg-surface px-2.5 py-0.5 text-ink">{STATUS_LABEL[lead.status] ?? lead.status}</span>
            {lead.next_action ? <span className="text-ink-2">Next: {NEXT_ACTION_LABEL[lead.next_action]}</span> : null}
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

      {lead.seed_note ? <p className="rounded-xl bg-surface px-4 py-2.5 text-sm text-ink-2">Seed data: {lead.seed_note}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Section title="Bill">
            {lead.current_reading ? (
              <BillCompare reading={lead.current_reading} />
            ) : (
              <p className="text-ink-2">The homeowner hasn&apos;t confirmed a bill yet.</p>
            )}
          </Section>
          {lead.status === "accepted" || lead.status === "converted" ? (
            <Section title="Project">
              {/* Stays mounted across the accepted → converted refetch so the one-time link stays visible. */}
              <AdvanceForm lead={lead} />
            </Section>
          ) : null}
          <Section title="Quote builder" aside={<span className="text-sm text-ink-2">Prices are GST-inclusive</span>}>
            <QuoteBuilder lead={lead} />
          </Section>
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
              <dd className="text-ink">{lead.recommended_kw ? `${lead.recommended_kw} kW (${lead.recommendation_status})` : "None"}</dd>
            </dl>
            {lead.flags.length ? (
              <div className="mt-3 flex flex-wrap gap-1">
                {lead.flags.map((f) => (
                  <FlagChip key={f}>{FLAG_LABEL[f] ?? f}</FlagChip>
                ))}
              </div>
            ) : null}
          </Section>
          <Section title="Roof and load">
            <VerificationForm key={lead.roof_verified_at ?? "new"} lead={lead} />
          </Section>
          <Section title="Actions">
            <LeadActions lead={lead} />
            {lead.events.length ? (
              <ol className="mt-4 space-y-3 border-t border-border pt-4 text-sm">
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
              <p className="mt-3 text-sm text-ink-2">No actions yet.</p>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}
