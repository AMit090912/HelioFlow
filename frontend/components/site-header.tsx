"use client";

import { useLocale, useTranslations } from "next-intl";

import { Logo } from "@/components/brand/logo";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";
import { homeFor, useSession, useSignOut } from "@/lib/use-session";

/** `tone="dark"` floats over a night-teal hero; `light` sits on white pages. */
export function SiteHeader({ tone = "light" }: { tone?: "light" | "dark" }) {
  const t = useTranslations("common");
  const locale = useLocale();
  const { user, isLoading } = useSession();
  const signOut = useSignOut();
  const dark = tone === "dark";
  const quiet = dark
    ? "text-white/80 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white"
    : "text-ink-2";

  return (
    <header className={cn(dark ? "bg-night" : "border-b border-border/70 bg-background")}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:h-[4.5rem] sm:px-6">
        <Link href={homeFor(user)} className="rounded-md" aria-label={t("appName")}>
          <Logo tone={tone} />
        </Link>
        <div className="flex items-center gap-1">
          <LanguageSwitcher className={quiet} />
          {user ? (
            <Button variant="ghost" className={cn("h-11 px-3", quiet)} onClick={() => signOut(locale)}>
              {t("signOut")}
            </Button>
          ) : !isLoading ? (
            <Button asChild variant="ghost" className={cn("h-11 px-3", quiet)}>
              <Link href="/sign-in">{t("signIn")}</Link>
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
