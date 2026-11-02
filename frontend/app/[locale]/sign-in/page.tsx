import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { SignInForm } from "./sign-in-form";

export default async function SignInPage({ params }: PageProps<"/[locale]/sign-in">) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <Suspense>
      <SignInForm />
    </Suspense>
  );
}
