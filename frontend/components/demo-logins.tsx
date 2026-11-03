"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, House, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { api, ApiError, type UserOut } from "@/lib/api";
import { homeFor, SESSION_KEY } from "@/lib/use-session";
import { cn } from "@/lib/utils";

type DemoAs = "new_homeowner" | "homeowner" | "sales" | "admin";

const ICONS = { new_homeowner: Sparkles, homeowner: House, sales: BriefcaseBusiness, admin: ShieldCheck };

/**
 * One-click sign-in for testing and reviewers. Shown only when the server says demo logins are
 * on (local development by default; DEMO_LOGINS=true on a deployed demo). No password is sent.
 */
export function DemoLogins({ onSigningIn }: { onSigningIn?: () => void }) {
  const t = useTranslations("auth.demo");
  const te = useTranslations("errors");
  const locale = useLocale();
  const router = useRouter();
  const client = useQueryClient();
  const [busy, setBusy] = useState<DemoAs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["demo-logins"],
    queryFn: () => api<{ enabled: boolean; accounts: { as: DemoAs }[] }>("/api/auth/demo-logins"),
    staleTime: Infinity,
    retry: false,
  });
  if (!data?.enabled) return null;

  const go = async (who: DemoAs) => {
    setBusy(who);
    setError(null);
    onSigningIn?.();
    try {
      const user = await api<UserOut>("/api/auth/demo-login", { json: { as: who, locale } });
      client.setQueryData(SESSION_KEY, user);
      router.replace(who === "new_homeowner" ? "/get-solar" : homeFor(user));
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "UNKNOWN";
      setError(te.has(code) ? te(code) : err instanceof ApiError ? err.message : te("UNKNOWN"));
      setBusy(null);
    }
  };

  return (
    <section aria-labelledby="demo-title" className="mt-8 rounded-2xl border border-dashed border-teal/40 bg-teal-wash/30 p-4">
      <h2 id="demo-title" className="text-sm font-semibold text-ink">
        {t("title")}
      </h2>
      <p className="mt-0.5 text-[0.8125rem] text-ink-2">{t("body")}</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {data.accounts.map(({ as }) => {
          const Icon = ICONS[as];
          return (
            <button
              key={as}
              type="button"
              onClick={() => go(as)}
              disabled={busy !== null}
              className={cn(
                "flex min-h-14 items-start gap-2 rounded-xl border border-border bg-background px-3 py-2 text-left",
                "hover:border-teal/60 disabled:opacity-60",
              )}
            >
              {busy === as ? (
                <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-teal" aria-hidden />
              ) : (
                <Icon className="mt-0.5 size-4 shrink-0 text-teal" aria-hidden />
              )}
              <span>
                <span className="block text-sm font-medium text-ink">{t(`${as}.label`)}</span>
                <span className="block text-[0.75rem] leading-snug text-ink-2">{t(`${as}.hint`)}</span>
              </span>
            </button>
          );
        })}
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </section>
  );
}
