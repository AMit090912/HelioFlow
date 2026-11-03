"use client";

import { ArrowLeft, CheckCircle2, Download, Loader2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { HomeownerOnly } from "@/components/homeowner-only";
import { Breakdown } from "@/components/quote/breakdown";
import { OptionPicker } from "@/components/quote/option-picker";
import { QuoteHero } from "@/components/quote/quote-hero";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatKw, formatRupees } from "@/lib/format";
import { focusOption, pdfUrl, useAcceptQuote, useQuote, type QuoteView } from "@/lib/quotes";

export function QuoteScreen({ id }: { id: string }) {
  const t = useTranslations("quote");
  return (
    <>
      <SiteHeader />
      <main className="flex-1 bg-surface">
        <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
          <Link
            href="/my"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md text-[0.9375rem] font-medium text-teal underline-offset-4 hover:underline"
          >
            <ArrowLeft className="size-4" aria-hidden />
            {t("back")}
          </Link>
          <HomeownerOnly>
            {() => (
              <Suspense>
                <QuoteLoader id={id} />
              </Suspense>
            )}
          </HomeownerOnly>
        </div>
      </main>
    </>
  );
}

function QuoteLoader({ id }: { id: string }) {
  const te = useTranslations("errors");
  const tc = useTranslations("common");
  const { data: quote, error, refetch } = useQuote(id);
  const jumping = useJumpToLatest(quote);
  if (error && !quote) {
    // A malformed id in the URL (422) is, to the person, the same as a missing one.
    const code = error instanceof ApiError ? (error.status === 422 ? "NOT_FOUND" : error.code) : "UNKNOWN";
    return (
      <div role="alert" className="mt-6 flex flex-col items-start gap-4">
        <p className="text-ink">{te.has(code) ? te(code) : te("UNKNOWN")}</p>
        {code !== "NOT_FOUND" ? (
          <Button variant="outline" className="h-11" onClick={() => refetch()}>
            {tc("retry")}
          </Button>
        ) : null}
      </div>
    );
  }
  if (!quote || jumping) {
    return (
      <div className="mt-6 space-y-4" aria-busy="true">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-48 w-full rounded-3xl" />
        <Skeleton className="h-40 w-full rounded-3xl" />
      </div>
    );
  }
  return <QuoteBody key={quote.id} quote={quote} />;
}

/** A replaced quote opens the newest one directly, however many revisions followed. */
function useJumpToLatest(quote: QuoteView | undefined) {
  const router = useRouter();
  const latest = quote?.status === "superseded" ? quote.latest_quote_id : null;
  useEffect(() => {
    if (latest) router.replace(`/my/quote/${latest}?updated=1`);
  }, [latest, router]);
  return latest !== null && latest !== undefined;
}

function QuoteBody({ quote }: { quote: QuoteView }) {
  const t = useTranslations("quote");
  const te = useTranslations("errors");
  const locale = useLocale();
  const updated = useSearchParams().get("updated") === "1" && quote.status !== "superseded";
  const accept = useAcceptQuote(quote.id);
  const [chosen, setChosen] = useState(() => focusOption(quote).kw);
  const [confirming, setConfirming] = useState(false);
  const option = focusOption(quote, quote.status === "accepted" ? quote.selected_kw : chosen);
  const sent = new Intl.DateTimeFormat(locale === "en" ? "en-IN" : `${locale}-IN`, {
    day: "numeric",
    month: "long",
    year: "numeric",
    numberingSystem: "latn",
  }).format(new Date(quote.sent_at));
  const kw = formatKw(option.kw, locale);

  const doAccept = async () => {
    try {
      await accept.mutateAsync(option.kw);
      setConfirming(false);
    } catch {
      /* message below */
    }
  };
  const closed = quote.lead_status === "closed_lost" && quote.status === "sent";
  const acceptError = accept.error instanceof ApiError ? accept.error.code : accept.error ? "UNKNOWN" : null;

  return (
    <div className="mt-2 space-y-8">
      <div>
        <h1 className="font-display text-[2rem] font-semibold text-ink sm:text-[2.25rem]">{t("title")}</h1>
        <p className="mt-1 text-sm text-ink-2 tabular">{t("meta", { number: quote.number, date: sent })}</p>
      </div>

      {updated ? (
        <div role="status" className="rounded-2xl border border-teal/30 bg-teal-wash/60 px-5 py-4">
          <p className="font-semibold text-teal">{t("updated.title")}</p>
          <p className="mt-1 text-[0.9375rem] text-ink">{t("updated.body")}</p>
        </div>
      ) : null}

      {quote.status === "superseded" ? (
        <div role="status" className="rounded-2xl border border-attention/30 bg-attention-bg px-5 py-4">
          <p className="font-semibold text-attention">{t("superseded.title")}</p>
          <p className="mt-1 text-[0.9375rem] text-ink">{t("superseded.body")}</p>
          {quote.latest_quote_id ? (
            <Link href={`/my/quote/${quote.latest_quote_id}`} className="mt-2 inline-flex min-h-11 items-center font-medium text-teal underline-offset-4 hover:underline">
              {t("superseded.cta")}
            </Link>
          ) : null}
        </div>
      ) : null}

      {closed ? (
        <div role="status" className="rounded-2xl border border-attention/30 bg-attention-bg px-5 py-4">
          <p className="font-semibold text-attention">{t("closed.title")}</p>
          <p className="mt-1 text-[0.9375rem] text-ink">{t("closed.body")}</p>
        </div>
      ) : null}

      {quote.status === "accepted" ? (
        <div role="status" className="flex gap-3 rounded-2xl border border-teal/30 bg-teal-wash/60 px-5 py-4">
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-teal" aria-hidden />
          <div>
            <p className="font-semibold text-ink">{t("accepted.title", { kw })}</p>
            <p className="mt-1 text-[0.9375rem] text-ink-2">{t("accepted.body")}</p>
          </div>
        </div>
      ) : null}

      <QuoteHero option={option} />

      {quote.options.length > 1 ? (
        <OptionPicker options={quote.options} value={option.kw} onChange={setChosen} disabled={quote.status !== "sent" || closed} />
      ) : null}

      <Breakdown option={option} quote={quote} />

      <p className="text-sm text-ink-2">{t("disclaimer")}</p>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {quote.status === "sent" && !closed ? (
          <Button size="lg" className="h-12 text-base sm:px-8" onClick={() => setConfirming(true)} aria-expanded={confirming}>
            {t("accept.cta", { kw })}
          </Button>
        ) : null}
        <Button asChild size="lg" variant="outline" className="h-12 text-base">
          <a href={pdfUrl(quote.id, locale)} target="_blank" rel="noopener noreferrer">
            <Download className="size-4" aria-hidden />
            {t("download")}
          </a>
        </Button>
      </div>

      {confirming && quote.status === "sent" && !closed ? (
        <section role="dialog" aria-labelledby="accept-title" className="rounded-3xl border border-teal bg-background p-5 sm:p-6">
          <h2 id="accept-title" className="font-display text-xl font-semibold text-ink">
            {t("accept.confirmTitle", { kw, net: formatRupees(option.net, locale) })}
          </h2>
          <p className="mt-2 text-[0.9375rem] text-ink-2">{t("accept.confirmBody")}</p>
          {acceptError ? (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {te.has(acceptError) ? te(acceptError) : te("UNKNOWN")}
            </p>
          ) : null}
          <div className="mt-4 flex flex-col-reverse gap-3 sm:flex-row">
            <Button variant="ghost" className="h-12 text-base" onClick={() => setConfirming(false)} disabled={accept.isPending}>
              {t("accept.cancel")}
            </Button>
            <Button className="h-12 text-base sm:px-8" onClick={doAccept} disabled={accept.isPending} autoFocus>
              {accept.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  {t("accept.accepting")}
                </>
              ) : (
                t("accept.confirm")
              )}
            </Button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
