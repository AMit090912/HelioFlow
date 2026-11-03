import { setRequestLocale } from "next-intl/server";

import { QuoteScreen } from "./quote-screen";

export default async function QuotePage({ params }: PageProps<"/[locale]/my/quote/[id]">) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <QuoteScreen id={id} />;
}
