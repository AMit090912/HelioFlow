import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import { StatusView } from "./status-view";

// The link itself is the secret: keep it out of search engines and referrers (§12).
export const metadata: Metadata = {
  title: "HelioFlow",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function StatusPage({ params }: PageProps<"/[locale]/s/[token]">) {
  const { locale, token } = await params;
  setRequestLocale(locale);
  return <StatusView token={token} />;
}
