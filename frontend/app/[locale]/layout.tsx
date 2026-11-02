import type { Metadata } from "next";
import { Anek_Devanagari, Mukta } from "next/font/google";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Providers } from "@/components/providers";
import { ServerWaking } from "@/components/server-waking";
import { routing } from "@/i18n/routing";

import "../globals.css";

// Both families are Indian designs drawn for Latin and Devanagari together, so English,
// Hindi and Marathi share one voice (ARCHITECTURE §20). Mukta for reading, Anek (variable
// width) for display headlines.
const mukta = Mukta({
  subsets: ["latin", "devanagari"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mukta",
  display: "swap",
});
const anek = Anek_Devanagari({
  subsets: ["latin", "devanagari"],
  axes: ["wdth"],
  variable: "--font-anek",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "common" });
  return { title: `${t("appName")} | ${t("tagline")}`, description: t("footer") };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  return (
    <html lang={locale} className={`${mukta.variable} ${anek.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <NextIntlClientProvider>
          <Providers>
            <ServerWaking />
            {children}
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
