import { setRequestLocale } from "next-intl/server";

import { BillCheckScreen } from "./bill-check-screen";

export default async function BillCheckPage({ params }: PageProps<"/[locale]/my/bill/[id]">) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <BillCheckScreen id={id} />;
}
