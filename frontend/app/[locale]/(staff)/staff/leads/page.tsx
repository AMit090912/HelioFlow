"use client";

import { useTranslations } from "next-intl";

import { EmptyState } from "@/components/empty-state";
import { SpotEmptyInbox } from "@/components/illustrations/spot";

export default function LeadsInboxPage() {
  const t = useTranslations("staff");
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[2.25rem] font-semibold text-ink">{t("leadsTitle")}</h1>
        <p className="mt-1 text-ink-2">{t("leadsSubtitle")}</p>
      </div>
      <EmptyState
        illustration={<SpotEmptyInbox className="w-full" />}
        title={t("leadsEmptyTitle")}
        message={t("leadsEmpty")}
      />
    </div>
  );
}
