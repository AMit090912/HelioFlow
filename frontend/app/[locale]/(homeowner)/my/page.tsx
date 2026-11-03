"use client";

import { Check } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { EmptyState } from "@/components/empty-state";
import { HomeownerOnly } from "@/components/homeowner-only";
import { SpotBill, SpotEmptyRoof } from "@/components/illustrations/spot";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatKw, formatNumber, formatRupees } from "@/lib/format";
import { useMyLeads, useReading, type LeadMine } from "@/lib/leads";
import { cn } from "@/lib/utils";

export default function MySolarPage() {
  const t = useTranslations("home");

  return (
    <>
      <SiteHeader />
      <main className="flex-1 bg-surface">
        <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
          <HomeownerOnly>
            {(user) => (
              <div className="space-y-8">
                <div>
                  <p className="text-ink-2">{t("greeting", { name: user.full_name.split(" ")[0] })}</p>
                  <h1 className="font-display mt-1 text-[2.25rem] font-semibold text-ink">{t("title")}</h1>
                </div>
                <Dashboard />
              </div>
            )}
          </HomeownerOnly>
        </div>
      </main>
    </>
  );
}

function Dashboard() {
  const t = useTranslations("home");
  const td = useTranslations("dashboard");
  const te = useTranslations("errors");
  const tc = useTranslations("common");
  const { data: leads, error, refetch } = useMyLeads();

  if (error && !leads) {
    const code = error instanceof ApiError ? error.code : "UNKNOWN";
    return (
      <div role="alert" className="flex flex-col items-start gap-4">
        <p className="text-ink">{te.has(code) ? te(code) : te("UNKNOWN")}</p>
        <Button variant="outline" className="h-11" onClick={() => refetch()}>
          {tc("retry")}
        </Button>
      </div>
    );
  }
  if (!leads) return <Skeleton className="h-56 w-full rounded-3xl" />;

  const lead = leads[0];
  if (!lead) {
    return (
      <EmptyState
        illustration={<SpotEmptyRoof className="w-full" />}
        title={t("emptyTitle")}
        message={t("empty")}
        action={
          <Button asChild size="lg" className="h-12 px-6 text-base">
            <Link href="/get-solar">{td("start")}</Link>
          </Button>
        }
      />
    );
  }
  return lead.next_action ? <Qualified lead={lead} /> : <ContinueCard lead={lead} />;
}

function ContinueCard({ lead }: { lead: LeadMine }) {
  const t = useTranslations("dashboard");
  const reading = lead.latest_reading;
  const [title, body, href] = !reading
    ? [t("continue.bill"), t("continue.billBody"), { pathname: "/get-solar", query: { lead: lead.id } } as const]
    : reading.status === "processing"
      ? [t("continue.reading"), t("continue.readingBody"), `/my/bill/${reading.id}`]
      : [t("continue.check"), t("continue.checkBody"), `/my/bill/${reading.id}`];

  return (
    <section className="flex flex-col gap-6 rounded-3xl border border-border bg-background p-6 sm:flex-row sm:items-center sm:p-8">
      <SpotBill className="w-24 shrink-0" />
      <div className="flex-1">
        <p className="text-sm text-ink-2">{t("continue.title")}</p>
        <h2 className="font-display mt-1 text-[1.5rem] font-semibold text-ink">{title}</h2>
        <p className="mt-1 text-ink-2">{body}</p>
        <p className="mt-3 text-sm text-ink-2">{t("reference", { code: lead.code })}</p>
      </div>
      <Button asChild size="lg" className="h-12 px-8 text-base">
        <Link href={href}>{t("continue.cta")}</Link>
      </Button>
    </section>
  );
}

/**
 * The qualified state. Only the next step and the provisional size are shown; the score label
 * stays with staff (§2). A tenant or small bill reads "We'll call you first", never "Low".
 */
function Qualified({ lead }: { lead: LeadMine }) {
  const t = useTranslations("dashboard");
  const locale = useLocale();
  const survey = lead.next_action === "survey_visit";
  const body = survey ? t("next.surveyBody") : lead.ownership === "tenant" ? t("next.tenantBody") : t("next.callBody");

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-night p-6 text-white sm:p-9">
        <SunriseMark className="pointer-events-none absolute -right-8 bottom-0 w-44 opacity-80 sm:w-60" />
        <div className="relative max-w-md">
          <p className="text-gold-soft">{t("next.kicker")}</p>
          <h2 className="font-display mt-1 text-[1.875rem] font-semibold leading-[1.15] sm:text-[2.25rem]">
            {survey ? t("next.survey") : t("next.call")}
          </h2>
          <p className="mt-3 text-white/80">{body}</p>
          <p className="mt-5 text-sm text-white/60">{t("reference", { code: lead.code })}</p>
        </div>
      </section>

      <div className="grid gap-6 sm:grid-cols-2">
        <section className="rounded-3xl border border-border bg-background p-6">
          <p className="text-sm text-ink-2">{t("size.label")}</p>
          {lead.recommended_kw ? (
            <>
              <p className="font-display mt-1 text-[2.25rem] font-semibold text-ink tabular">
                {t("size.value", { kw: formatKw(lead.recommended_kw, locale) })}
              </p>
              <p className="text-sm text-ink-2">
                {lead.recommendation_status === "final" ? t("size.final") : t("size.provisional")}
              </p>
            </>
          ) : (
            <p className="mt-2 text-ink">{t("size.none")}</p>
          )}
        </section>
        {lead.current_reading ? <BillSummary lead={lead} readingId={lead.current_reading.id} /> : null}
      </div>

      <Timeline />
    </div>
  );
}

function BillSummary({ lead, readingId }: { lead: LeadMine; readingId: string }) {
  const t = useTranslations("dashboard.bill");
  const tu = useTranslations("billCheck.units");
  const tr = useTranslations("leadForm.roofArea");
  const locale = useLocale();
  const values = useReading(readingId).data?.confirmed;
  const rows: [string, string][] = [
    [t("units"), values ? `${formatNumber(values.avg_monthly_units, locale, 0)} ${tu("units")}` : "…"],
    [t("amount"), values ? formatRupees(values.bill_amount, locale) : "…"],
    [t("roof"), `${formatNumber(lead.roof_area_sqft, locale, 0)} ${tr("unit")}`],
  ];
  return (
    <section className="rounded-3xl border border-border bg-background p-6">
      <h2 className="text-sm text-ink-2">{t("title")}</h2>
      <dl className="mt-2 divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-4 py-2">
            <dt className="text-ink-2">{k}</dt>
            <dd className="font-medium text-ink tabular">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Timeline() {
  const t = useTranslations("dashboard.timeline");
  const steps = ["bill", "contact", "survey", "quote", "install"] as const;
  return (
    <section className="rounded-3xl border border-border bg-background p-6 sm:p-8">
      <h2 className="font-display text-xl font-semibold text-ink">{t("title")}</h2>
      <ol className="mt-5 space-y-4">
        {steps.map((step, i) => {
          const state = i === 0 ? "done" : i === 1 ? "current" : "todo";
          return (
            <li key={step} className="relative flex items-center gap-4" aria-current={state === "current" ? "step" : undefined}>
              {i < steps.length - 1 ? (
                <span aria-hidden className={cn("absolute left-[0.6875rem] top-7 h-4 w-0.5", i === 0 ? "bg-teal" : "bg-border")} />
              ) : null}
              <span
                aria-hidden
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full",
                  state === "done" && "bg-teal text-white",
                  state === "current" && "bg-gold ring-4 ring-gold/25",
                  state === "todo" && "border-2 border-border bg-background",
                )}
              >
                {state === "done" ? <Check className="size-3.5" /> : null}
              </span>
              <span className={cn(state === "todo" ? "text-ink-2" : "font-medium text-ink")}>{t(step)}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** The sun on the hero's horizon: the one drawing on the dashboard. */
function SunriseMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 220 120" className={className} aria-hidden focusable="false">
      <circle cx="120" cy="120" r="88" fill="#E5B257" opacity="0.1" />
      <circle cx="120" cy="120" r="56" fill="#E5B257" />
      <path d="M0 119 H220" stroke="#F6DFA8" strokeWidth="2" opacity="0.6" />
    </svg>
  );
}
