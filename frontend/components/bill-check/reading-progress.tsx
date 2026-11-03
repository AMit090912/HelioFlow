"use client";

import { Check, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { READING_GIVE_UP_MS } from "@/lib/leads";
import { cn } from "@/lib/utils";

const SLOW_AFTER_MS = 40_000;

/**
 * An honest "reading" state (Review Focus 3). The first two steps are facts the server already
 * reported (the file arrived; the photo passed its quality check), the third is what is running
 * now. Nothing pretends to advance on a timer. The server gives the AI 75 s and turns an orphaned
 * read into manual entry after 2 minutes, so polling ends; if it somehow doesn't, we stop
 * waiting at READING_GIVE_UP_MS and offer a retry instead of spinning forever.
 */
export function ReadingProgress({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("billCheck.processing");
  // Timed from when this screen first saw the read running, not from the server's created_at:
  // a phone clock that is off, or a retried upload with an old created_at, must not show "stuck".
  // By READING_GIVE_UP_MS the server (which sweeps at 2 min) has always finished or given up.
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(started);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const elapsed = Math.max(0, now - started);
  const stuck = elapsed > READING_GIVE_UP_MS;
  const slow = !stuck && elapsed > SLOW_AFTER_MS;

  const steps: { label: string; state: "done" | "active" | "todo" }[] = [
    { label: t("uploaded"), state: "done" },
    // A PDF with a text layer has no photo to check; it still counts as passed.
    { label: t("photo"), state: "done" },
    { label: t("reading"), state: stuck ? "todo" : "active" },
    { label: t("values"), state: "todo" },
  ];

  if (stuck) {
    return (
      <div role="alert" className="space-y-3">
        <h2 className="font-display text-xl font-semibold text-ink">{t("stuckTitle")}</h2>
        <p className="text-ink-2">{t("stuckBody")}</p>
        {/* Refetching lets the server turn the abandoned read into manual entry. */}
        <Button className="h-11" onClick={onRetry}>
          {t("typeInstead")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-[1.5rem] font-semibold text-ink">{t("title")}</h2>
        <p className="mt-1 text-ink-2">{t("subtitle")}</p>
      </div>
      <ol className="relative space-y-5" aria-live="polite">
        {steps.map((step, i) => (
          <li key={step.label} className="relative flex items-center gap-4">
            {i < steps.length - 1 ? (
              <span
                aria-hidden
                className={cn(
                  "absolute left-[0.9375rem] top-8 h-5 w-0.5",
                  step.state === "done" ? "bg-teal" : "bg-border",
                )}
              />
            ) : null}
            <span
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-full",
                step.state === "done" && "bg-teal text-white",
                step.state === "active" && "bg-gold/25 text-night",
                step.state === "todo" && "border-2 border-border bg-background",
              )}
            >
              {step.state === "done" ? <Check className="size-4" aria-hidden /> : null}
              {step.state === "active" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            </span>
            <span className={cn(step.state === "todo" ? "text-ink-2" : "font-medium text-ink")}>{step.label}</span>
          </li>
        ))}
      </ol>
      {/* A thin bar that moves only to show the page is alive, never to fake a percentage. */}
      <div className="h-1 overflow-hidden rounded-full bg-teal-wash" aria-hidden>
        <div className="h-full w-1/3 rounded-full bg-teal/70 [animation:hf-slide_1.6s_ease-in-out_infinite]" />
      </div>
      {slow ? (
        <p role="status" className="rounded-xl bg-attention-bg px-3.5 py-3 text-sm text-attention">
          {t("slow")}
        </p>
      ) : null}
    </div>
  );
}
