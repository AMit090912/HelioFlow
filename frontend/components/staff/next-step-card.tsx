"use client";

import { ArrowDown, Check, Clock, Phone } from "lucide-react";

import { JOURNEY, JOURNEY_LABEL, journeyIndex, SECTION_LABEL, type NextStep } from "@/components/staff/next-step";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Jump to a lead-page section and move focus there, so keyboard users land on it too. */
export function goToSection(id: string) {
  const el = document.getElementById(`section-${id}`);
  if (!el) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  el.focus({ preventScroll: true });
}

/** The lead's progress: done steps ticked, the current one in gold. */
function Journey({ step, dark }: { step: NextStep["step"]; dark: boolean }) {
  const at = journeyIndex(step);
  return (
    <ol className="grid grid-cols-6 gap-1.5" aria-label="Progress">
      {JOURNEY.map((s, i) => {
        const done = i < at;
        const now = i === at;
        return (
          <li key={s} className="min-w-0" aria-current={now ? "step" : undefined}>
            <span
              className={cn(
                "block h-1.5 rounded-full",
                done ? (dark ? "bg-teal-wash" : "bg-teal") : now ? "bg-gold" : dark ? "bg-white/15" : "bg-border",
              )}
            />
            <span
              className={cn(
                "mt-1.5 flex items-center gap-1 truncate text-[0.75rem]",
                now ? (dark ? "font-semibold text-white" : "font-semibold text-ink") : dark ? "text-white/60" : "text-ink-2",
              )}
            >
              {done ? <Check className="size-3 shrink-0" aria-hidden /> : null}
              {JOURNEY_LABEL[s]}
              <span className="sr-only">{done ? " (done)" : now ? " (now)" : ""}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** The one thing to do on this lead, whose move it is, and a jump to where it is done. */
export function NextStepCard({ next, phone }: { next: NextStep; phone: string | null }) {
  const yours = next.owner === "you";
  const section = next.section;
  return (
    <section
      aria-labelledby="next-step-title"
      className={cn(
        "rounded-2xl p-5 sm:p-6",
        yours ? "bg-night text-white shadow-[0_24px_50px_-34px_rgba(1,46,43,0.7)]" : "border border-border bg-background",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-2xl">
          <p className={cn("flex items-center gap-1.5 text-sm font-medium", yours ? "text-gold" : "text-ink-2")}>
            {yours ? null : next.owner === "homeowner" ? <Clock className="size-4" aria-hidden /> : <Check className="size-4" aria-hidden />}
            {yours ? "Your next step" : next.owner === "homeowner" ? "Waiting on the homeowner" : "No action needed"}
          </p>
          <h2 id="next-step-title" className={cn("font-display mt-1 text-[1.625rem] font-semibold leading-tight", yours ? "text-white" : "text-ink")}>
            {next.title}
          </h2>
          {next.detail ? <p className={cn("mt-1.5 text-[0.9375rem]", yours ? "text-white/75" : "text-ink-2")}>{next.detail}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {next.owner === "homeowner" && phone ? (
            <Button asChild variant="outline" className="h-11">
              <a href={`tel:+91${phone}`}>
                <Phone className="size-4" aria-hidden /> Call the homeowner
              </a>
            </Button>
          ) : null}
          {yours && section ? (
            <Button className="h-11 bg-gold text-night hover:bg-gold/90" onClick={() => goToSection(section)}>
              Go to {SECTION_LABEL[section]} <ArrowDown className="size-4" aria-hidden />
            </Button>
          ) : null}
        </div>
      </div>
      {next.step !== "closed" ? (
        <div className="mt-5">
          <Journey step={next.step} dark={yours} />
        </div>
      ) : null}
    </section>
  );
}
