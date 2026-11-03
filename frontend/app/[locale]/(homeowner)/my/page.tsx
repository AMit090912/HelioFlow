"use client";

import { Check } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { EmptyState } from "@/components/empty-state";
import { HomeownerOnly } from "@/components/homeowner-only";
import { SpotBill, SpotEmptyRoof, SpotProgress } from "@/components/illustrations/spot";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatDay, formatKw, formatNumber, formatRupees } from "@/lib/format";
import { useMyLeads, useReading, type LeadMine } from "@/lib/leads";
import { focusOption, useQuote } from "@/lib/quotes";
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
  if (lead.status === "closed_lost") {
    return (
      <EmptyState
        illustration={<SpotEmptyRoof className="w-full" />}
        title={td("closed.title")}
        message={td("closed.body")}
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
 * Layout: the hero says where things stand; below, the journey on the left and the facts
 * (system, bill) on the right.
 */
function Qualified({ lead }: { lead: LeadMine }) {
  const t = useTranslations("dashboard");
  const survey = lead.next_action === "survey_visit";
  const body = survey ? t("next.surveyBody") : lead.ownership === "tenant" ? t("next.tenantBody") : t("next.callBody");

  return (
    <div className="space-y-6">
      {lead.project ? (
        <ProjectCard project={lead.project} code={lead.code} />
      ) : lead.current_quote ? (
        <QuoteCard quoteId={lead.current_quote.id} code={lead.code} />
      ) : (
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
      )}

      <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Journey lead={lead} />
        <div className="space-y-6">
          <SystemCard lead={lead} />
          {lead.current_reading ? <BillSummary lead={lead} readingId={lead.current_reading.id} /> : null}
        </div>
      </div>
    </div>
  );
}

/** The size that counts: the quoted one once there is a quote, else our provisional suggestion. */
function SystemCard({ lead }: { lead: LeadMine }) {
  const t = useTranslations("dashboard");
  const tq = useTranslations("quote");
  const locale = useLocale();
  const { data: quote } = useQuote(lead.current_quote?.id ?? "", !!lead.current_quote);

  if (lead.current_quote) {
    if (!quote) return <Skeleton className="h-44 w-full rounded-3xl" />;
    const option = focusOption(quote);
    const accepted = quote.status === "accepted";
    const savings = option.savings.annual_savings;
    const pb = option.payback;
    return (
      <section className="rounded-3xl border border-border bg-background p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm text-ink-2">{t("system.title")}</h2>
          {accepted ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-teal-wash px-2.5 py-0.5 text-[0.8125rem] font-medium text-teal">
              <Check className="size-3.5" aria-hidden /> {t("system.accepted")}
            </span>
          ) : null}
        </div>
        <p className="font-display mt-1 text-[2.25rem] font-semibold text-ink tabular">{formatKw(option.kw, locale)}</p>
        <dl className="mt-2 divide-y divide-border">
          <div className="flex items-baseline justify-between gap-4 py-2">
            <dt className="text-ink-2">{tq("net")}</dt>
            <dd className="font-medium text-ink tabular">{formatRupees(option.net, locale)}</dd>
          </div>
          {savings ? (
            <div className="flex items-baseline justify-between gap-4 py-2">
              <dt className="text-ink-2">{tq("b.savings")}</dt>
              <dd className="font-medium text-ink tabular">{formatRupees(savings, locale)}</dd>
            </div>
          ) : null}
          {pb.status === "ok" && pb.years ? (
            <div className="flex items-baseline justify-between gap-4 py-2">
              <dt className="text-ink-2">{tq("payback")}</dt>
              <dd className="font-medium text-ink tabular">{tq("paybackYears", { years: formatNumber(pb.years, locale, 1) })}</dd>
            </div>
          ) : null}
        </dl>
        <Link href={`/my/quote/${quote.id}`} className="mt-1 inline-flex min-h-11 items-center font-medium text-teal hover:underline">
          {t("quote.cta")}
        </Link>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-border bg-background p-6">
      <h2 className="text-sm text-ink-2">{t("size.label")}</h2>
      {lead.recommended_kw ? (
        <>
          <p className="font-display mt-1 text-[2.25rem] font-semibold text-ink tabular">
            {t("size.value", { kw: formatKw(lead.recommended_kw, locale) })}
          </p>
          <p className="text-sm text-ink-2">{lead.recommendation_status === "final" ? t("size.final") : t("size.provisional")}</p>
        </>
      ) : (
        <p className="mt-2 text-ink">{t("size.none")}</p>
      )}
    </section>
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
    <section className="rounded-3xl border border-border bg-background px-6 py-5">
      <h2 className="text-sm text-ink-2">{t("title")}</h2>
      <dl className="mt-1 divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-4 py-1.5 text-[0.9375rem]">
            <dt className="text-ink-2">{k}</dt>
            <dd className="font-medium text-ink tabular">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Before a project: where the lead is on the way to installation (index into PRE_STEPS). */
const PRE_STEPS = ["bill", "contact", "survey", "quote", "install"] as const;
function preStage(lead: LeadMine): number {
  if (lead.current_quote?.status === "accepted") return 4;
  if (lead.current_quote || lead.status === "surveyed") return 3;
  return 1;
}

/** Once the advance is in, the installation's real stages replace the quote card (§12, §13). */
function ProjectCard({ project, code }: { project: NonNullable<LeadMine["project"]>; code: string }) {
  const t = useTranslations("dashboard");
  const tp = useTranslations("project");
  const locale = useLocale();
  const current = project.stages.findIndex((s) => s.stage === project.stage);
  const finished = project.stage === "subsidy_credited";
  return (
    <section className="relative overflow-hidden rounded-3xl bg-night p-6 text-white sm:p-9">
      {finished ? (
        <SunriseMark className="pointer-events-none absolute -right-8 bottom-0 w-44 sm:w-64" />
      ) : (
        <SpotProgress className="pointer-events-none absolute -right-4 bottom-0 hidden w-48 opacity-80 sm:block" />
      )}
      <div className="relative max-w-md">
        <p className="text-gold-soft">{finished ? t("done.kicker") : t("project.kicker")}</p>
        <h2 className="font-display mt-1 text-[1.875rem] font-semibold leading-[1.15] sm:text-[2.25rem]">
          {finished ? t("done.title") : tp(`stages.${project.stage}`)}
        </h2>
        <p className="mt-3 text-white/80">{finished ? t("done.body") : t(`stageNote.${project.stage}`)}</p>
        {project.scheduled_for && project.stage === "installation_scheduled" ? (
          <p className="mt-2 font-medium text-gold-soft">{tp("planned", { date: formatDay(project.scheduled_for, locale) })}</p>
        ) : null}
        <ol className="mt-5 flex gap-1.5" aria-hidden>
          {project.stages.map((s, i) => (
            <li key={s.stage} className={cn("h-1.5 flex-1 rounded-full", i <= current ? "bg-gold" : "bg-white/20")} />
          ))}
        </ol>
        {finished ? null : <p className="mt-4 text-sm text-white/70">{t("project.whatsapp")}</p>}
        <p className="mt-2 text-sm text-white/60">{t("reference", { code })}</p>
      </div>
    </section>
  );
}

type Row = { key: string; label: string; state: "done" | "current" | "todo"; date?: string | null };

/** The whole way to solar in one list: the real project stages, with dates, once the project starts. */
function Journey({ lead }: { lead: LeadMine }) {
  const t = useTranslations("dashboard");
  const tp = useTranslations("project");
  const locale = useLocale();
  const project = lead.project;
  let rows: Row[];
  if (project) {
    const at = project.stages.findIndex((s) => s.stage === project.stage);
    const finished = project.stage === "subsidy_credited";
    rows = [
      { key: "earlier", label: t("timelineEarlier"), state: "done" },
      ...project.stages.map(
        (s, i): Row => ({
          key: s.stage,
          label: tp(`stages.${s.stage}`),
          state: i < at || finished ? "done" : i === at ? "current" : "todo",
          date: s.done_at,
        }),
      ),
    ];
  } else {
    const at = preStage(lead);
    rows = PRE_STEPS.map((step, i) => ({
      key: step,
      label: t(`timeline.${step}`),
      state: i < at ? "done" : i === at ? "current" : "todo",
    }));
  }

  return (
    <section className="rounded-3xl border border-border bg-background p-6 sm:p-7">
      <h2 className="font-display text-xl font-semibold text-ink">
        {project?.stage === "subsidy_credited" ? t("timelineDone") : t("timeline.title")}
      </h2>
      <ol className="mt-5">
        {rows.map((row, i) => (
          <li key={row.key} className="relative flex gap-4 pb-5 last:pb-0" aria-current={row.state === "current" ? "step" : undefined}>
            {i < rows.length - 1 ? (
              <span aria-hidden className={cn("absolute bottom-0 left-[0.6875rem] top-7 w-0.5", row.state === "done" ? "bg-teal" : "bg-border")} />
            ) : null}
            <span
              aria-hidden
              className={cn(
                "relative flex size-6 shrink-0 items-center justify-center rounded-full",
                row.state === "done" && "bg-teal text-white",
                row.state === "current" && "bg-gold ring-4 ring-gold/25",
                row.state === "todo" && "border-2 border-border bg-background",
              )}
            >
              {row.state === "done" ? <Check className="size-3.5" /> : null}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={cn("flex flex-wrap items-center gap-2 leading-snug", row.state === "todo" ? "text-ink-2" : "font-medium text-ink")}>
                {row.label}
                {row.state === "current" ? (
                  <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[0.75rem] font-semibold text-night">{tp("now")}</span>
                ) : null}
              </p>
              {row.date && row.state === "done" ? (
                <p className="mt-0.5 text-[0.8125rem] text-ink-2">{tp("doneOn", { date: formatDay(row.date, locale) })}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function QuoteCard({ quoteId, code }: { quoteId: string; code: string }) {
  const t = useTranslations("dashboard");
  const locale = useLocale();
  const { data: quote } = useQuote(quoteId);
  if (!quote) return <Skeleton className="h-48 w-full rounded-3xl" />;
  const option = focusOption(quote);
  const accepted = quote.status === "accepted";
  const kw = formatKw(option.kw, locale);
  return (
    <section className="relative overflow-hidden rounded-3xl bg-night p-6 text-white sm:p-9">
      <SunriseMark className="pointer-events-none absolute -right-8 bottom-0 w-44 opacity-80 sm:w-60" />
      <div className="relative max-w-md">
        <p className="text-gold-soft">{accepted ? t("quote.acceptedKicker") : t("quote.readyKicker")}</p>
        <h2 className="font-display mt-1 text-[1.875rem] font-semibold leading-[1.15] sm:text-[2.25rem]">
          {accepted
            ? t("quote.acceptedTitle", { kw })
            : t("quote.readyTitle", { kw, net: formatRupees(option.net, locale) })}
        </h2>
        <p className="mt-3 text-white/80">{accepted ? t("quote.acceptedBody") : t("quote.readyBody")}</p>
        <Button asChild size="lg" className="mt-5 h-12 bg-gold px-6 text-base text-night hover:bg-gold-soft">
          <Link href={`/my/quote/${quote.id}`}>{t("quote.cta")}</Link>
        </Button>
        <p className="mt-4 text-sm text-white/60">{t("reference", { code })}</p>
      </div>
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
