"use client";

import { Check, Loader2, MessageSquareText } from "lucide-react";
import { useState } from "react";

import { projectError, STAGE_LABEL, when } from "@/components/staff/copy";
import { StatusLinkBox } from "@/components/staff/status-link-box";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { formatDay, formatRupees } from "@/lib/format";

/** YYYY-MM-DD in India, for the date picker's minimum (the server checks the same way). */
function todayInIndia(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}
import { STAGES, useMoveStage, useProject, type ProjectDetail } from "@/lib/projects";
import { cn } from "@/lib/utils";

const LANGUAGE = { en: "English", hi: "Hindi", mr: "Marathi" } as Record<string, string>;

/** Screen 8 detail: stage stepper, forward/back moves, status link, history, simulated messages. */
export function ProjectPanel({
  project,
  freshToken,
  homeownerLocale,
}: {
  project: ProjectDetail;
  freshToken?: string | null;
  homeownerLocale: string;
}) {
  const move = useMoveStage(project.id);
  const index = STAGES.indexOf(project.stage);
  const next = STAGES[index + 1];
  const previous = index > 0 ? STAGES[index - 1] : undefined;
  const [date, setDate] = useState("");
  const [correcting, setCorrecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const run = async (body: Parameters<typeof move.mutateAsync>[0]) => {
    setError(null);
    try {
      await move.mutateAsync(body);
      setDate("");
      setReason("");
      setCorrecting(false);
    } catch (err) {
      setError(err instanceof ApiError ? projectError(err.code, err.message) : "Couldn't save. Try again.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-ink-2 tabular">
            {project.code} · {project.selected_kw} kW
          </p>
          <h2 className="font-display text-2xl font-semibold text-ink">{project.homeowner_name}</h2>
          <p className="text-sm text-ink-2 tabular">
            Advance {formatRupees(project.advance_amount, "en")} · {project.advance_reference}
          </p>
        </div>
        <Link href={`/staff/leads/${project.lead_id}`} className="inline-flex min-h-11 items-center text-sm font-medium text-teal hover:underline">
          Open lead
        </Link>
      </div>

      <ol className="space-y-0">
        {project.stages.map((s, i) => {
          const done = i < index;
          const current = i === index;
          return (
            <li key={s.stage} className="relative flex gap-3 pb-4 last:pb-0">
              {i < project.stages.length - 1 ? (
                <span aria-hidden className={cn("absolute left-[0.6875rem] top-6 h-full w-0.5", done || current ? "bg-teal" : "bg-border")} />
              ) : null}
              <span
                aria-hidden
                className={cn(
                  "relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full",
                  done && "bg-teal text-white",
                  current && "bg-gold ring-4 ring-gold/25",
                  !done && !current && "border-2 border-border bg-background",
                )}
              >
                {done ? <Check className="size-3.5" /> : null}
              </span>
              <div aria-current={current ? "step" : undefined}>
                <p className={cn("text-[0.9375rem]", current ? "font-semibold text-ink" : done ? "text-ink" : "text-ink-2")}>
                  {STAGE_LABEL[s.stage]}
                </p>
                {s.done_at ? <p className="text-[0.8125rem] text-ink-2">{when(s.done_at)}</p> : null}
                {s.stage === "installation_scheduled" && project.scheduled_for && i <= index ? (
                  <p className="text-[0.8125rem] text-ink">Installation on {formatDay(project.scheduled_for, "en")}</p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="space-y-3 rounded-2xl border border-border bg-surface/50 p-4">
        {next ? (
          <div className="flex flex-wrap items-end gap-3">
            {next === "installation_scheduled" ? (
              <label className="space-y-1 text-sm text-ink">
                <span className="block font-medium">Installation date (optional)</span>
                <Input
                  type="date"
                  min={todayInIndia()}
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="h-10 w-44"
                />
              </label>
            ) : null}
            <Button
              className="h-10"
              disabled={move.isPending}
              onClick={() => run({ to: next, scheduled_for: date || null })}
            >
              {move.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Move to {STAGE_LABEL[next]}
            </Button>
          </div>
        ) : (
          <p className="text-sm font-medium text-teal">All stages complete.</p>
        )}
        {previous ? (
          correcting ? (
            <div className="space-y-2">
              <label htmlFor="correct-reason" className="text-sm font-medium text-ink">
                Why go back to &ldquo;{STAGE_LABEL[previous]}&rdquo;?
              </label>
              <Input id="correct-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="h-10" />
              <div className="flex gap-2">
                <Button variant="outline" className="h-10" disabled={move.isPending} onClick={() => run({ to: previous, note: reason })}>
                  Correct stage
                </Button>
                <Button variant="ghost" className="h-10" onClick={() => setCorrecting(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <button type="button" className="min-h-11 text-sm text-ink-2 underline-offset-4 hover:underline" onClick={() => setCorrecting(true)}>
              Correct a mistake: go back to {STAGE_LABEL[previous]}
            </button>
          )
        ) : null}
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        <p className="sr-only" aria-live="polite">
          {STAGE_LABEL[project.stage]}
        </p>
      </div>

      <section>
        <h3 className="mb-2 font-semibold text-ink">Status link</h3>
        <p className="mb-3 text-sm text-ink-2">
          Shows the stages and dates only: no phone, address or money. Opens in {LANGUAGE[homeownerLocale] ?? "English"}.
        </p>
        <StatusLinkBox project={project} freshToken={freshToken} locale={homeownerLocale} />
      </section>

      <section>
        <h3 className="mb-2 font-semibold text-ink">Messages to the homeowner</h3>
        {project.notifications.length ? (
          <ul className="space-y-2">
            {project.notifications.map((n) => (
              <li key={n.id} className="rounded-xl border border-border bg-background p-3 text-sm">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-[0.8125rem] text-ink-2">
                  <MessageSquareText className="size-3.5" aria-hidden />
                  <span>{n.channel === "whatsapp" ? "WhatsApp" : "SMS"}</span> to {n.recipient_masked} · {LANGUAGE[n.locale]} · {when(n.created_at)}
                  <span className="rounded-full bg-surface px-2 py-0.5 text-[0.75rem] font-medium text-ink-2">Simulated, not sent</span>
                </div>
                <p className="text-ink" lang={n.locale}>
                  {n.message}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-2">No messages yet.</p>
        )}
      </section>

      <section>
        <h3 className="mb-2 font-semibold text-ink">History</h3>
        <ol className="space-y-2 text-sm">
          {project.events.map((e) => (
            <li key={e.id}>
              <span className="font-medium text-ink">
                {e.from_stage ? `${STAGE_LABEL[e.from_stage]} → ` : ""}
                {STAGE_LABEL[e.to_stage]}
              </span>
              <span className="text-ink-2">
                {" "}
                · {e.actor_name ?? "System"} · {when(e.created_at)}
              </span>
              {e.note ? <p className="text-ink">{e.note}</p> : null}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

/** The panel bound to live data, so every move re-renders from the server's answer. */
export function LiveProjectPanel({
  id,
  freshToken,
  homeownerLocale,
}: {
  id: string;
  freshToken?: string | null;
  homeownerLocale: string;
}) {
  const { data, error } = useProject(id);
  if (error && !data) return <p role="alert" className="text-sm text-destructive">Couldn&apos;t load this project.</p>;
  if (!data) return <Loader2 className="size-5 animate-spin text-ink-2" aria-label="Loading" />;
  return <ProjectPanel project={data} freshToken={freshToken} homeownerLocale={homeownerLocale} />;
}
