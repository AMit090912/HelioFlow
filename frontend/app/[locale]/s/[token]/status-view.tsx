"use client";

import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Logo } from "@/components/brand/logo";
import { SpotProgress } from "@/components/illustrations/spot";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDay } from "@/lib/format";
import type { PublicStatus } from "@/lib/projects";
import { cn } from "@/lib/utils";

/** Screen 5: what anyone holding the link may see — first name, code, stages, dates. */
export function StatusView({ token }: { token: string }) {
  const t = useTranslations("project");
  const te = useTranslations("errors");
  const locale = useLocale();
  const { data, error, isPending } = useQuery({
    queryKey: ["public-status", token],
    queryFn: () => api<PublicStatus>(`/api/public/status/${encodeURIComponent(token)}`),
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
  });

  const inactive = error instanceof ApiError && error.code === "LINK_INACTIVE";

  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <header className="bg-night">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4 sm:px-6">
          <Logo tone="dark" />
          <LanguageSwitcher className="text-white/80 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white" />
        </div>
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        {isPending ? (
          <div className="space-y-4" aria-busy="true">
            <Skeleton className="h-40 w-full rounded-3xl" />
            <Skeleton className="h-72 w-full rounded-3xl" />
          </div>
        ) : inactive || !data ? (
          <div role="status" className="rounded-3xl border border-border bg-background px-6 py-12 text-center">
            <h1 className="font-display text-2xl font-semibold text-ink">{inactive ? t("inactive.title") : te("UNKNOWN")}</h1>
            <p className="mx-auto mt-2 max-w-sm text-ink-2">
              {inactive ? t("inactive.body") : error instanceof ApiError && te.has(error.code) ? te(error.code) : te("UNKNOWN")}
            </p>
          </div>
        ) : (
          <Status data={data} locale={locale} />
        )}
      </main>
      <footer className="px-4 pb-8 text-center text-sm text-ink-2">{t("footer")}</footer>
    </div>
  );
}

function Status({ data, locale }: { data: PublicStatus; locale: string }) {
  const t = useTranslations("project");
  const current = data.stages.findIndex((s) => s.stage === data.current_stage);
  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-night px-6 pb-6 pt-7 text-white sm:px-9">
        <SpotProgress className="pointer-events-none absolute -right-4 bottom-0 w-40 opacity-90 sm:w-52" />
        <div className="relative max-w-[60%]">
          <p className="text-sm text-gold-soft tabular">{t("code", { code: data.code })}</p>
          <h1 className="font-display mt-1 text-[1.75rem] font-semibold leading-tight sm:text-[2.125rem]">
            {t("title", { name: data.first_name })}
          </h1>
          <p className="mt-4 text-sm text-white/70">{t("now")}</p>
          <p className="font-display text-xl font-semibold text-gold-soft">{t(`stages.${data.current_stage}`)}</p>
          {data.scheduled_for ? (
            <p className="mt-2 text-sm text-white/85">{t("planned", { date: formatDay(data.scheduled_for, locale) })}</p>
          ) : null}
        </div>
      </section>

      <ol className="rounded-3xl border border-border bg-background p-6 sm:p-8">
        {data.stages.map((s, i) => {
          const done = i <= current;
          const isCurrent = i === current;
          return (
            <li key={s.stage} className="relative flex gap-4 pb-6 last:pb-0" aria-current={isCurrent ? "step" : undefined}>
              {i < data.stages.length - 1 ? (
                <span aria-hidden className={cn("absolute left-[0.8125rem] top-8 h-[calc(100%-1.5rem)] w-0.5", i < current ? "bg-teal" : "bg-border")} />
              ) : null}
              <span
                aria-hidden
                className={cn(
                  "relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full",
                  done && !isCurrent && "bg-teal text-white",
                  isCurrent && "bg-gold text-night ring-4 ring-gold/25",
                  !done && "border-2 border-border bg-background",
                )}
              >
                {done ? <Check className="size-4" /> : null}
              </span>
              <div>
                <p className={cn("text-[1.0625rem]", isCurrent ? "font-semibold text-ink" : done ? "text-ink" : "text-ink-2")}>
                  {t(`stages.${s.stage}`)}
                </p>
                <p className="text-sm text-ink-2">
                  {s.done_at ? t("doneOn", { date: formatDay(s.done_at, locale) }) : i > current ? t("upcoming") : ""}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="text-center text-sm text-ink-2">{t("privacy")}</p>
    </div>
  );
}
