"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type State = "idle" | "slow" | "down";

const SLOW_AFTER_MS = 2500;
const GIVE_UP_AFTER_MS = 60_000;

/** The free Render tier sleeps when idle; the first request can take ~30–60 s (§16).
 * Shows a calm notice only when the health check is actually slow. */
export function ServerWaking() {
  const t = useTranslations("server");
  const tc = useTranslations("common");
  const [state, setState] = useState<State>("idle");
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setState("idle");
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let unmounted = false;
    const controller = new AbortController();
    const slow = setTimeout(() => setState("slow"), SLOW_AFTER_MS);
    const giveUp = setTimeout(() => controller.abort(), GIVE_UP_AFTER_MS);
    fetch("/api/health", { signal: controller.signal, cache: "no-store" })
      .then((res) => !unmounted && setState(res.ok ? "idle" : "down"))
      .catch(() => !unmounted && setState("down")) // network error or 60 s give-up
      .finally(() => {
        clearTimeout(slow);
        clearTimeout(giveUp);
      });
    return () => {
      unmounted = true;
      clearTimeout(slow);
      clearTimeout(giveUp);
      controller.abort();
    };
  }, [attempt]);

  if (state === "idle") return null;

  return (
    <div role="status" aria-live="polite" className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm sm:px-6">
        {state === "slow" ? (
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
            <Button size="sm" variant="outline" className="h-9" onClick={retry}>
              {tc("retry")}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
