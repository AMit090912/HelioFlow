import { useTranslations } from "next-intl";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";

export default function NotFound() {
  const t = useTranslations("errors");
  const tc = useTranslations("common");
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-16 sm:px-6">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("NOT_FOUND")}</h1>
        <Button asChild className="mt-8 h-11">
          <Link href="/">{tc("appName")}</Link>
        </Button>
      </main>
    </>
  );
}
