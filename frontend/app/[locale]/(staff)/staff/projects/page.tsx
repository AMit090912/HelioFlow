"use client";

import { ArrowUpDown } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { SpotEmptyInbox } from "@/components/illustrations/spot";
import { STAGE_LABEL } from "@/components/staff/copy";
import { nextStageOf } from "@/components/staff/next-step";
import { LiveProjectPanel } from "@/components/staff/project-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjects, useProject, type ProjectRow } from "@/lib/projects";
import { cn } from "@/lib/utils";

const STUCK_AFTER_DAYS = 14;

export default function ProjectsPage() {
  return (
    <Suspense>
      <Projects />
    </Suspense>
  );
}

function Projects() {
  const { data: projects, error, refetch } = useProjects();
  const leadParam = useSearchParams().get("lead");
  const [picked, setPicked] = useState<string | null>(null);
  const [longestFirst, setLongestFirst] = useState(true);

  const sorted = useMemo(
    () => [...(projects ?? [])].sort((a, b) => (longestFirst ? b.days_in_stage - a.days_in_stage : a.days_in_stage - b.days_in_stage)),
    [projects, longestFirst],
  );
  const selected = picked ?? projects?.find((p) => p.lead_id === leadParam)?.id ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[2.25rem] font-semibold text-ink">Projects</h1>
        <p className="mt-1 text-ink-2">From advance to subsidy credited. Move one stage at a time.</p>
      </div>

      {error && !projects ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-ink">Couldn&apos;t load projects.</p>
          <Button variant="outline" className="h-11" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      ) : !projects ? (
        <Skeleton className="h-48 w-full rounded-2xl" />
      ) : projects.length === 0 ? (
        <EmptyState
          illustration={<SpotEmptyInbox className="w-full" />}
          title="No projects yet"
          message="A project starts when you record the advance on an accepted quote."
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="overflow-hidden rounded-2xl border border-border bg-background self-start">
            <table className="w-full text-left text-[0.9375rem]">
              <thead className="border-b border-border bg-surface/70 text-[0.8125rem] text-ink-2">
                <tr>
                  <th className="px-4 py-3 font-medium">Project</th>
                  <th className="hidden px-4 py-3 font-medium sm:table-cell">Stage</th>
                  <th className="px-4 py-3 font-medium" aria-sort={longestFirst ? "descending" : "ascending"}>
                    <button type="button" className="inline-flex min-h-8 items-center gap-1" onClick={() => setLongestFirst((v) => !v)}>
                      Days in stage <ArrowUpDown className="size-3.5" aria-hidden />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sorted.map((p) => (
                  <Row key={p.id} project={p} active={p.id === selected} onPick={() => setPicked(p.id)} />
                ))}
              </tbody>
            </table>
          </div>
          <section aria-label="Project detail" className="rounded-2xl border border-border bg-background p-5 sm:p-6">
            {selected ? <SelectedProject id={selected} /> : <p className="text-ink-2">Choose a project to see its stages and messages.</p>}
          </section>
        </div>
      )}
    </div>
  );
}

function Row({ project, active, onPick }: { project: ProjectRow; active: boolean; onPick: () => void }) {
  const stuck = project.days_in_stage >= STUCK_AFTER_DAYS && project.stage !== "subsidy_credited";
  return (
    <tr className={cn("relative cursor-pointer align-top hover:bg-surface/50", active && "bg-teal-wash/50")}>
      <td className="px-4 py-3">
        <button type="button" onClick={onPick} aria-pressed={active} className="text-left font-semibold text-ink after:absolute after:inset-0">
          {project.homeowner_name}
        </button>
        <p className="text-[0.8125rem] text-ink-2 tabular">
          {project.code} · {project.selected_kw} kW
        </p>
        <p className="text-[0.8125rem] text-ink sm:hidden">{STAGE_LABEL[project.stage]}</p>
        <div className="sm:hidden">
          <NextMove project={project} />
        </div>
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">
        <p className="text-ink">{STAGE_LABEL[project.stage]}</p>
        <NextMove project={project} />
      </td>
      <td className="px-4 py-3 tabular">
        <span className={cn(stuck ? "rounded-md bg-attention-bg px-2 py-0.5 text-attention" : "text-ink")}>
          {project.days_in_stage} {project.days_in_stage === 1 ? "day" : "days"}
        </span>
      </td>
    </tr>
  );
}

function SelectedProject({ id }: { id: string }) {
  const { data: project } = useProject(id);
  if (!project) return <Skeleton className="h-64 w-full rounded-xl" />;
  return <LiveProjectPanel key={id} id={id} homeownerLocale={project.homeowner_locale} />;
}

/** What to do next on the project, in the same words as the lead page. */
function NextMove({ project }: { project: ProjectRow }) {
  const next = nextStageOf(project.stage);
  return next ? (
    <p className="text-[0.8125rem] font-semibold text-teal">Next: move to {STAGE_LABEL[next]}</p>
  ) : (
    <p className="text-[0.8125rem] text-ink-2">All done</p>
  );
}
