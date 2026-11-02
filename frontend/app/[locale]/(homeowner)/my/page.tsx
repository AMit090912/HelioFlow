"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { EmptyState } from "@/components/empty-state";
import { SpotEmptyRoof } from "@/components/illustrations/spot";
import { RequireSession } from "@/components/require-session";
import { SiteHeader } from "@/components/site-header";
import { useRouter } from "@/i18n/navigation";

function StaffGoesToInbox() {
  const router = useRouter();
  useEffect(() => router.replace("/staff/leads"), [router]);
  return null;
}

export default function MySolarPage() {
  const t = useTranslations("home");

  return (
    <>
      <SiteHeader />
      <main className="flex-1 bg-surface">
        <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
          <RequireSession>
            {(user) =>
              user.role !== "homeowner" ? (
                <StaffGoesToInbox />
              ) : (
                <div className="space-y-8">
                  <div>
                    <p className="text-ink-2">{t("greeting", { name: user.full_name.split(" ")[0] })}</p>
                    <h1 className="font-display mt-1 text-[2.25rem] font-semibold text-ink">{t("title")}</h1>
                  </div>
                  <EmptyState
                    illustration={<SpotEmptyRoof className="w-full" />}
                    title={t("emptyTitle")}
                    message={t("empty")}
                  />
                </div>
              )
            }
          </RequireSession>
        </div>
      </main>
    </>
  );
}
