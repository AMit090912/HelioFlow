import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { GetSolarFlow } from "./get-solar-flow";

export default async function GetSolarPage({ params }: PageProps<"/[locale]/get-solar">) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <Suspense>
      <GetSolarFlow />
    </Suspense>
  );
}
