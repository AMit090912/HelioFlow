"use client";

import { useTranslations } from "next-intl";
import { useEffect, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { getServerState, subscribeServerState, waitForServer } from "@/lib/server-status";

const ok = () => "ok" as const;

/** The free Render tier sleeps when idle; waking takes ~30–60 s (§16). This checks the API on
 * page load and shows a calm "waking up" notice while it boots. Reads made meanwhile wait for the
 * same wake-up (lib/api.ts), so the page fills in by itself once the API answers. */
export function ServerWaking() {
  const t = useTranslations("server");
  const tc = useTranslations("common");
  const state = useSyncExternalStore(subscribeServerState, getServerState, ok);

  useEffect(() => {
    void waitForServer({ quiet: true });
  }, []);

  if (state === "ok") return null;

  return (
    <div role="status" aria-live="polite" className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm sm:px-6">
        {state === "waking" ? (
          <>
            <span className="relative h-1 w-16 overflow-hidden rounded-full bg-teal-wash" aria-hidden>
              <span className="absolute inset-y-0 left-0 w-1/3 animate-[hf-slide_1.4s_ease-in-out_infinite] rounded-full bg-teal" />
            </span>
            <span className="font-medium text-ink">{t("waking")}</span>
            <span className="text-ink-2">{t("wakingHint")}</span>
          </>
        ) : (
          <>
            <span className="font-medium text-destructive">{t("unreachable")}</span>
            <Button size="sm" variant="outline" className="h-9" onClick={() => location.reload()}>
              {tc("retry")}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
