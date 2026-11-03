"use client";

import { ArrowLeft, CheckCircle2, FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";

import { BillPreview } from "@/components/bill-check/bill-preview";
import { ReadingProgress } from "@/components/bill-check/reading-progress";
import { ReuploadPanel } from "@/components/bill-check/reupload-panel";
import { ValuesForm } from "@/components/bill-check/values-form";
import { HomeownerOnly } from "@/components/homeowner-only";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { useReading, type Reading } from "@/lib/leads";

export function BillCheckScreen({ id }: { id: string }) {
  const t = useTranslations("billCheck");
  return (
    <>
      <SiteHeader />
      <main className="flex-1 bg-surface">
        <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
          <Link
            href="/my"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md text-[0.9375rem] font-medium text-teal underline-offset-4 hover:underline"
          >
            <ArrowLeft className="size-4" aria-hidden />
            {t("back")}
          </Link>
          <h1 className="font-display mt-2 text-[2rem] font-semibold text-ink sm:text-[2.25rem]">{t("title")}</h1>
          <div className="mt-6">
            <HomeownerOnly>{() => <ReadingView id={id} />}</HomeownerOnly>
          </div>
        </div>
      </main>
    </>
  );
}

function ReadingView({ id }: { id: string }) {
  const t = useTranslations("billCheck");
  const te = useTranslations("errors");
  const tc = useTranslations("common");
  const router = useRouter();
  const { data: reading, error, refetch } = useReading(id);
  // "Type the values in" from the re-upload panel; reset whenever a different reading is shown.
  const [manualFor, setManualFor] = useState<string | null>(null);

  const confirmed = reading?.status === "confirmed";
  useEffect(() => {
    if (!confirmed) return;
    const timer = window.setTimeout(() => router.replace("/my"), 1400);
    return () => window.clearTimeout(timer);
  }, [confirmed, router]);

  if (error && !reading) {
    const code = error instanceof ApiError ? error.code : "UNKNOWN";
    return (
      <div role="alert" className="flex max-w-md flex-col items-start gap-4">
        <p className="text-ink">{te.has(code) ? te(code) : te("UNKNOWN")}</p>
        {code === "NOT_FOUND" ? null : (
          <Button variant="outline" className="h-11" onClick={() => refetch()}>
            {tc("retry")}
          </Button>
        )}
      </div>
    );
  }
  if (!reading) {
    return (
      <div className="grid gap-6 md:grid-cols-2" aria-busy="true">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    );
  }

  const demo = reading.is_demo ? (
    <p className="mb-6 flex items-center gap-2 rounded-xl border border-gold/60 bg-gold-soft/40 px-3.5 py-2.5 text-sm text-night">
      <FlaskConical className="size-4 shrink-0" aria-hidden />
      {t("demo")}
    </p>
  ) : null;

  if (reading.status === "confirmed") {
    return (
      <Panel>
        <p role="status" className="flex items-center gap-3 text-lg text-ink">
          <CheckCircle2 className="size-6 shrink-0 text-teal" aria-hidden />
          {t("confirmed")}
        </p>
      </Panel>
    );
  }

  if (reading.status === "processing") {
    return (
      <Panel className="max-w-xl">
        <ReadingProgress key={reading.id} onRetry={() => refetch()} />
      </Panel>
    );
  }

  const goTo = (next: Reading) => router.replace(`/my/bill/${next.id}`);
  const manual = reading.status === "failed_manual" || manualFor === reading.id;

  let side: ReactNode;
  if (manual) {
    side = (
      <>
        <h2 className="font-display text-[1.5rem] font-semibold text-ink">{t("manual.title")}</h2>
        <p className="mb-6 mt-1 text-ink-2">{t("manual.subtitle")}</p>
        <ValuesForm key={`manual-${reading.id}`} reading={reading} mode="manual" onConfirmed={() => refetch()} />
      </>
    );
  } else if (reading.status === "needs_reupload") {
    side = <ReuploadPanel reading={reading} onUploaded={goTo} onTypeInstead={() => setManualFor(reading.id)} />;
  } else {
    side = (
      <>
        {demo}
        <h2 className="font-display text-[1.5rem] font-semibold text-ink">{t("review.title")}</h2>
        <p className="mb-6 mt-1 text-ink-2">{t("review.subtitle")}</p>
        <ValuesForm key={`review-${reading.id}`} reading={reading} mode="review" onConfirmed={() => refetch()} />
      </>
    );
  }

  return (
    <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-10">
      <div className="md:sticky md:top-6">
        <BillPreview readingId={reading.id} />
      </div>
      <Panel>{side}</Panel>
    </div>
  );
}

function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl border border-border bg-background p-5 sm:p-8 ${className ?? ""}`}>{children}</section>
  );
}
