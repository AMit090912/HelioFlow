"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Logo } from "@/components/brand/logo";
import { SunFlowHome } from "@/components/illustrations/sun-flow-home";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError, safeNextPath, type UserOut } from "@/lib/api";
import { homeFor, SESSION_KEY, useSession } from "@/lib/use-session";

export function SignInForm() {
  const t = useTranslations("auth");
  const tc = useTranslations("common");
  const te = useTranslations("errors");
  const router = useRouter();
  const queryClient = useQueryClient();
  const next = safeNextPath(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const { user: existing } = useSession();
  const [signingIn, setSigningIn] = useState(false);

  // Already signed in (e.g. staff clicking a link to /sign-in): go home instead of re-asking.
  // Skipped while this form is signing someone in, so its own `next` redirect wins.
  useEffect(() => {
    if (existing && !signingIn) router.replace(homeFor(existing));
  }, [existing, signingIn, router]);

  const schema = z.object({
    identifier: z.string().trim().min(1, t("identifierRequired")),
    password: z.string().min(8, t("passwordShort")),
  });
  type Values = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: Values) => {
    setFormError(null);
    setSigningIn(true);
    try {
      const user = await api<UserOut>("/api/auth/login", { json: values });
      queryClient.setQueryData(SESSION_KEY, user);
      router.replace(user.role === "homeowner" ? (next ?? homeFor(user)) : homeFor(user));
    } catch (error) {
      setSigningIn(false);
      const code = error instanceof ApiError ? error.code : "UNKNOWN";
      setFormError(te.has(code) ? te(code) : te("UNKNOWN"));
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* Desktop: the sun → panel → home "flow" illustration with the brand promise */}
      <aside className="relative hidden overflow-hidden bg-night lg:block">
        <SunFlowHome className="absolute inset-0 size-full" />
        {/* Text sits in the open sky, top left; the illustration's sun, array and home stay clear. */}
        <div className="relative flex h-full min-h-dvh flex-col gap-14 p-12">
          <Link href="/" aria-label={tc("appName")} className="self-start rounded-md">
            <Logo tone="dark" />
          </Link>
          <div className="max-w-[19rem] xl:max-w-[22rem]">
            <p className="font-display text-[2.25rem] font-semibold leading-[1.1] text-white">{tc("tagline")}</p>
            <p className="mt-4 text-lg text-white/75">{t("panelBody")}</p>
          </div>
        </div>
      </aside>

      <div className="flex flex-col bg-surface">
        {/* Phone: a short band of the same illustration */}
        <div className="relative h-44 overflow-hidden bg-night lg:hidden">
          <SunFlowHome className="absolute inset-0 size-full" />
          <div className="relative flex h-16 items-center justify-between px-4">
            <Link href="/" aria-label={tc("appName")} className="rounded-md">
              <Logo tone="dark" />
            </Link>
            <LanguageSwitcher className="text-white/80 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white" />
          </div>
        </div>
        <div className="hidden h-[4.5rem] items-center justify-end px-8 lg:flex">
          <LanguageSwitcher />
        </div>

        <main className="flex flex-1 items-start px-4 pb-16 lg:items-center lg:px-8">
          <div className="relative z-10 mx-auto -mt-10 w-full max-w-md rounded-3xl border border-border bg-background p-6 shadow-[0_24px_60px_-32px_rgba(1,46,43,0.35)] sm:p-9 lg:mt-0">
            <h1 className="font-display text-[2rem] font-semibold text-ink">{t("title")}</h1>
            <p className="mt-2 text-ink-2">{t("subtitle")}</p>

            <form className="mt-8 space-y-5" onSubmit={handleSubmit(onSubmit)} noValidate>
              <div className="space-y-2">
                <Label htmlFor="identifier">{t("identifier")}</Label>
                <Input
                  id="identifier"
                  autoComplete="username"
                  inputMode="email"
                  className="h-12 text-base"
                  aria-invalid={!!errors.identifier}
                  aria-describedby={errors.identifier ? "identifier-error" : undefined}
                  {...register("identifier")}
                />
                {errors.identifier ? (
                  <p id="identifier-error" className="text-sm text-destructive">
                    {errors.identifier.message}
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">{t("password")}</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  className="h-12 text-base"
                  aria-invalid={!!errors.password}
                  aria-describedby={errors.password ? "password-error" : undefined}
                  {...register("password")}
                />
                {errors.password ? (
                  <p id="password-error" className="text-sm text-destructive">
                    {errors.password.message}
                  </p>
                ) : null}
              </div>

              {formError ? (
                <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
                  {formError}
                </p>
              ) : null}

              <Button type="submit" size="lg" className="h-12 w-full text-base" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    {t("submitting")}
                  </>
                ) : (
                  t("submit")
                )}
              </Button>
            </form>

            <p className="mt-8 text-sm text-ink-2">
              <Link href="/get-solar" className="font-medium text-teal underline-offset-4 hover:underline">
                {t("noAccount")}
              </Link>
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
