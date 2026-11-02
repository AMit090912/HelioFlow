"use client";

import { Inbox, Lock, Menu } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageSwitcher } from "@/components/language-switcher";
import { RequireSession } from "@/components/require-session";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/utils";
import { useSignOut } from "@/lib/use-session";

const NAV = [{ href: "/staff/leads", key: "navLeads", icon: Inbox }] as const;

/** Navigation + language + sign-out. Rendered in the desktop sidebar and the phone sheet. */
function StaffNav({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations("staff");
  const tc = useTranslations("common");
  const locale = useLocale();
  const pathname = usePathname();
  const signOut = useSignOut();

  return (
    <div className="flex h-full flex-col gap-8">
      <nav className="flex flex-col gap-1" aria-label={tc("appName")}>
        {NAV.map(({ href, key, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex h-11 items-center gap-3 rounded-lg px-3 text-[0.9375rem] font-medium",
                active ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white",
              )}
            >
              {active ? <span aria-hidden className="absolute inset-y-2 left-0 w-1 rounded-full bg-gold" /> : null}
              <Icon className="size-4" aria-hidden />
              {t(key)}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto flex flex-col items-start gap-1 border-t border-white/10 pt-4">
        <LanguageSwitcher
          side="top"
          align="start"
          className="text-white/70 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white"
        />
        <Button
          variant="ghost"
          className="h-11 px-3 text-white/70 hover:bg-white/10 hover:text-white"
          onClick={() => signOut(locale)}
        >
          {tc("signOut")}
        </Button>
      </div>
    </div>
  );
}

export default function StaffLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("staff");
  const tc = useTranslations("common");
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden bg-night lg:sticky lg:top-0 lg:flex lg:h-dvh lg:w-64 lg:shrink-0 lg:flex-col lg:gap-10 lg:px-5 lg:py-7">
        <Link href="/staff/leads" aria-label={tc("appName")} className="rounded-md">
          <Logo tone="dark" />
          <span className="mt-2 block text-sm text-gold-soft">{t("workspace")}</span>
        </Link>
        <StaffNav />
      </aside>

      {/* Phone / tablet top bar with a menu sheet */}
      <header className="flex h-16 items-center justify-between bg-night px-4 lg:hidden">
        <Link href="/staff/leads" aria-label={tc("appName")} className="rounded-md">
          <Logo tone="dark" />
        </Link>
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="size-11 text-white hover:bg-white/10 hover:text-white"
              aria-label={tc("menu")}
            >
              <Menu className="size-5" aria-hidden />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 border-none bg-night px-5 py-7 text-white [&>button]:text-white">
            <SheetTitle className="mb-8">
              <Logo tone="dark" />
              <span className="mt-2 block text-sm font-normal text-gold-soft">{t("workspace")}</span>
            </SheetTitle>
            <StaffNav onNavigate={() => setMenuOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>

      <main className="flex-1 bg-surface px-4 py-8 sm:px-8 lg:py-12">
        <div className="mx-auto max-w-6xl">
          <RequireSession>
            {(user) =>
              user.role === "homeowner" ? (
                <div className="max-w-md space-y-4">
                  <Lock className="size-6 text-ink-2" aria-hidden />
                  <h1 className="text-2xl font-semibold text-ink">{t("forbiddenTitle")}</h1>
                  <p className="text-ink-2">{t("forbiddenBody")}</p>
                  <Button asChild className="h-11">
                    <Link href="/my">{t("forbiddenAction")}</Link>
                  </Button>
                </div>
              ) : (
                children
              )
            }
          </RequireSession>
        </div>
      </main>
    </div>
  );
}
