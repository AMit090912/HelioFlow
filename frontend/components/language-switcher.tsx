"use client";

import { Check, Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing, type Locale } from "@/i18n/routing";
import { cn } from "@/lib/utils";

/** Keeps the current page, switches the locale prefix. Persisting the choice to the
 * user's profile arrives with the PATCH endpoint in M4. */
type Placement = { side?: "top" | "bottom"; align?: "start" | "end" };

/** `side`/`align` let the narrow staff sidebar open the menu upwards from its own left edge. */
export function LanguageSwitcher({
  className,
  side = "bottom",
  align = "end",
}: { className?: string } & Placement) {
  const t = useTranslations("common");
  const locale = useLocale() as Locale;
  const pathname = usePathname();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const choose = (next: Locale) => {
    if (next === locale) return;
    const query = typeof window !== "undefined" ? window.location.search : "";
    startTransition(() => router.replace(`${pathname}${query}`, { locale: next }));
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className={cn("h-11 gap-2 px-3 text-ink-2", className)} disabled={pending}>
          <Languages className="size-4" aria-hidden />
          <span className="sr-only">{t("languageLabel")}: </span>
          <span lang={locale}>{t(`languages.${locale}`)}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side={side} align={align} sideOffset={8} collisionPadding={12} className="min-w-44">
        {routing.locales.map((code) => (
          <DropdownMenuItem key={code} onSelect={() => choose(code)} className="h-11 justify-between">
            <span lang={code}>{t(`languages.${code}`)}</span>
            {code === locale ? <Check className="size-4 text-teal" aria-hidden /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
