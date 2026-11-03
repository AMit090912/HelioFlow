"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { HomeDraft } from "@/components/lead-form/draft";
import { describedBy, Field } from "@/components/lead-form/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "@/i18n/navigation";
import { api, ApiError, type UserOut } from "@/lib/api";
import { createLead, leadKeys, type LeadMine } from "@/lib/leads";
import { SESSION_KEY } from "@/lib/use-session";

const INPUT = "h-12 rounded-xl bg-background text-base md:text-base";
const PHONE = /^(?:\+?91)?[6-9]\d{9}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Letters in any script (with Devanagari vowel signs), spaces and . ' ’ - only: the same rule as
// the server (app/core/names.py). Starts with a letter and has at least two letters.
const NAME = /^\p{L}[\p{L}\p{M} .'’-]*$/u;
const isName = (v: string) => NAME.test(v) && (v.match(/\p{L}/gu)?.length ?? 0) >= 2;

/**
 * Step 2. A new visitor creates an account and agrees to how their details are used; a homeowner
 * who is already signed in only gives consent (Review Focus 2). Either way this step creates the
 * lead, once.
 */
export function StepAccount({
  user,
  home,
  onBack,
  onCreated,
}: {
  user: UserOut | null;
  home: HomeDraft;
  onBack: () => void;
  onCreated: (lead: LeadMine) => void;
}) {
  const t = useTranslations("leadForm");
  const te = useTranslations("errors");
  const locale = useLocale() as UserOut["preferred_locale"];
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<{ code: string; text: string } | null>(null);
  const signedIn = user !== null;

  const consent = z.literal(true, { error: t("errors.consent") });
  const schema = signedIn
    ? z.object({ consent })
    : z.object({
        full_name: z
          .string()
          .transform((v) => v.split(/\s+/).filter(Boolean).join(" "))
          .refine((v) => v.length <= 120 && isName(v), t("errors.fullName")),
        phone: z
          .string()
          .transform((v) => v.replace(/[\s-]/g, ""))
          .refine((v) => PHONE.test(v), t("errors.phone")),
        email: z
          .string()
          .trim()
          .refine((v) => v === "" || EMAIL.test(v), t("errors.email")),
        password: z.string().min(8, t("errors.password")).max(128, t("errors.password")),
        consent,
      });
  type In = { full_name?: string; phone?: string; email?: string; password?: string; consent?: boolean };

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<In>({
    resolver: zodResolver(schema as unknown as z.ZodType<In, In>),
    defaultValues: { full_name: "", phone: "", email: "", password: "", consent: false },
  });

  const onSubmit = async (values: In) => {
    setFormError(null);
    try {
      if (!signedIn) {
        const created = await api<UserOut>("/api/auth/signup", {
          json: {
            full_name: values.full_name,
            phone: values.phone,
            email: values.email || null,
            password: values.password,
            preferred_locale: locale,
          },
        });
        // From here on the person is signed in: a failure below retries as "consent only".
        queryClient.setQueryData(SESSION_KEY, created);
      }
      const lead = await createLead({ ...home, consent: true });
      queryClient.invalidateQueries({ queryKey: leadKeys.mine });
      onCreated(lead);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "UNKNOWN";
      setFormError({ code, text: te.has(code) ? te(code) : te("UNKNOWN") });
    }
  };

  const err = errors as Partial<Record<keyof In, { message?: string }>>;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
      {signedIn ? (
        <div className="rounded-2xl bg-teal-wash/60 px-4 py-3 text-ink">
          <p className="font-medium">{t("account.signedInAs", { name: user.full_name })}</p>
          <p className="text-sm text-ink-2">{t("account.consentOnly")}</p>
        </div>
      ) : (
        <>
          <Field id="full_name" label={t("account.fullName")} error={err.full_name?.message}>
            <Input
              id="full_name"
              autoComplete="name"
              className={INPUT}
              aria-invalid={!!err.full_name}
              aria-describedby={describedBy("full_name", err.full_name)}
              {...register("full_name")}
            />
          </Field>
          <Field id="phone" label={t("account.phone")} hint={t("account.phoneHint")} error={err.phone?.message}>
            <Input
              id="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              className={`${INPUT} tabular`}
              aria-invalid={!!err.phone}
              aria-describedby={describedBy("phone", err.phone, true)}
              {...register("phone")}
            />
          </Field>
          <Field id="email" label={t("account.email")} error={err.email?.message}>
            <Input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              className={INPUT}
              aria-invalid={!!err.email}
              aria-describedby={describedBy("email", err.email)}
              {...register("email")}
            />
          </Field>
          <Field id="password" label={t("account.password")} hint={t("account.passwordHint")} error={err.password?.message}>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              className={INPUT}
              aria-invalid={!!err.password}
              aria-describedby={describedBy("password", err.password, true)}
              {...register("password")}
            />
          </Field>
        </>
      )}

      <div>
        <label className="flex cursor-pointer gap-3 rounded-2xl border border-border bg-background p-4 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-teal">
          <input
            type="checkbox"
            className="mt-1 size-5 shrink-0 accent-[var(--hf-teal)]"
            aria-invalid={!!err.consent}
            aria-describedby={err.consent ? "consent-error" : undefined}
            {...register("consent")}
          />
          <span className="text-[0.875rem] leading-relaxed text-ink">{t("account.consent")}</span>
        </label>
        {err.consent ? (
          <p id="consent-error" className="mt-2 text-sm text-destructive">
            {err.consent.message}
          </p>
        ) : null}
      </div>

      {formError ? (
        <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive">
          <p>{formError.text}</p>
          {formError.code === "ACCOUNT_EXISTS" ? (
            <Link
              href={{ pathname: "/sign-in", query: { next: "/get-solar" } }}
              className="mt-1 inline-block font-medium text-teal underline underline-offset-4"
            >
              {t("account.haveAccount")}
            </Link>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
        <Button type="button" variant="ghost" className="h-12 text-base text-ink-2" onClick={onBack} disabled={isSubmitting}>
          {t("back")}
        </Button>
        <Button type="submit" size="lg" className="h-12 flex-1 text-base sm:flex-none sm:px-10" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              {t("account.submitting")}
            </>
          ) : signedIn ? (
            t("next")
          ) : (
            t("account.submit")
          )}
        </Button>
      </div>

      {!signedIn ? (
        <p className="text-sm text-ink-2">
          <Link
            href={{ pathname: "/sign-in", query: { next: "/get-solar" } }}
            className="font-medium text-teal underline-offset-4 hover:underline"
          >
            {t("account.haveAccount")}
          </Link>
        </p>
      ) : null}
    </form>
  );
}
