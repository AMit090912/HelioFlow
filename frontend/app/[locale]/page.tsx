import { Check } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { RooftopSunrise } from "@/components/illustrations/rooftop-sunrise";
import { SpotBill, SpotHome, SpotQuote } from "@/components/illustrations/spot";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";

const FACTS = ["bill", "subsidy", "visit"] as const;
const STEPS = [
  { key: "home", Spot: SpotHome },
  { key: "bill", Spot: SpotBill },
  { key: "quote", Spot: SpotQuote },
] as const;

export default async function LandingPage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("landing");
  const tc = await getTranslations("common");

  return (
    <>
      <SiteHeader tone="dark" />
      <main className="flex-1">
        {/* Hero: dusk over a Vidarbha rooftop */}
        <section className="overflow-hidden bg-night text-white">
          <div className="mx-auto grid max-w-6xl items-end gap-8 px-4 pt-8 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:gap-12 lg:pt-14">
            <div className="pb-4 lg:pb-20">
              <p className="text-[0.9375rem] font-medium text-gold-soft">{t("kicker")}</p>
              <h1 className="font-display mt-4 text-[2.5rem] font-semibold leading-[1.05] sm:text-[3.5rem]">
                {t("title")}
              </h1>
              <p className="mt-6 max-w-[54ch] text-lg text-white/75">{t("lede")}</p>
              <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                {/* M1: leads to sign-in; re-pointed to the lead form in M4. */}
                <Button
                  asChild
                  size="lg"
                  className="h-13 rounded-xl bg-gold px-7 text-base font-semibold text-night hover:bg-gold-soft"
                >
                  <Link href="/get-solar">{t("cta")}</Link>
                </Button>
                <Button
                  asChild
                  variant="ghost"
                  size="lg"
                  className="h-13 px-4 text-base text-white/80 hover:bg-white/10 hover:text-white"
                >
                  <Link href="/sign-in">{t("haveAccount")}</Link>
                </Button>
              </div>
              <ul className="mt-10 grid gap-3 text-[0.9375rem] text-white/80">
                {FACTS.map((fact) => (
                  <li key={fact} className="flex items-start gap-2.5">
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-gold/20 text-gold">
                      <Check className="size-3.5" strokeWidth={3} aria-hidden />
                    </span>
                    {t(`facts.${fact}`)}
                  </li>
                ))}
              </ul>
            </div>
            <RooftopSunrise className="-mb-px w-full" />
          </div>
        </section>

        {/* The quote as a story: size → cost after subsidy → payback (brief, Design) */}
        <section className="border-b border-border/70">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
            <div className="max-w-2xl">
              <h2 className="font-display text-3xl font-semibold text-ink sm:text-[2.25rem]">{t("example.title")}</h2>
              <p className="mt-3 text-lg text-ink-2">{t("example.body")}</p>
            </div>
            <dl className="mt-10 grid overflow-hidden rounded-3xl border border-border bg-surface sm:grid-cols-3">
              <div className="border-b border-border p-7 sm:border-b-0 sm:border-r">
                <dt className="text-sm font-medium text-ink-2">{t("example.size")}</dt>
                <dd className="font-display tabular mt-2 text-4xl font-semibold text-ink">{t("example.sizeValue")}</dd>
              </div>
              <div className="border-b border-border p-7 sm:border-b-0 sm:border-r">
                <dt className="text-sm font-medium text-ink-2">{t("example.net")}</dt>
                <dd className="font-display tabular mt-2 text-4xl font-semibold text-teal">{t("example.netValue")}</dd>
                <dd className="mt-1 text-sm text-ink-2">{t("example.netNote")}</dd>
              </div>
              <div className="bg-night p-7 text-white">
                <dt className="text-sm font-medium text-white/70">{t("example.payback")}</dt>
                <dd className="font-display mt-2 text-4xl font-semibold text-gold">{t("example.paybackValue")}</dd>
              </div>
            </dl>
            <p className="mt-4 text-sm text-ink-2">{t("example.note")}</p>
          </div>
        </section>

        {/* How it works — a real sequence, so it is numbered */}
        <section className="bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
            <h2 className="font-display text-3xl font-semibold text-ink sm:text-[2.25rem]">{t("stepsTitle")}</h2>
            <ol className="relative mt-10 grid gap-10 sm:grid-cols-3 sm:gap-8">
              <span
                aria-hidden
                className="absolute left-[12%] right-[12%] top-10 hidden border-t-2 border-dashed border-gold/70 sm:block"
              />
              {STEPS.map(({ key, Spot }, index) => (
                <li key={key} className="relative flex gap-5 sm:flex-col sm:gap-4">
                  <span className="grid size-20 shrink-0 place-items-center rounded-2xl border border-border bg-background">
                    <Spot className="w-14" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-teal tabular">
                      {index + 1} / {STEPS.length}
                    </p>
                    <h3 className="font-display mt-1 text-xl font-semibold text-ink">{t(`steps.${key}.title`)}</h3>
                    <p className="mt-1.5 max-w-[40ch] text-ink-2">{t(`steps.${key}.body`)}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </main>

      <footer className="bg-night text-white/70">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>{tc("footer")}</p>
          <Link href="/sign-in" className="font-medium text-gold-soft underline-offset-4 hover:underline">
            {t("staffLink")}
          </Link>
        </div>
      </footer>
    </>
  );
}
