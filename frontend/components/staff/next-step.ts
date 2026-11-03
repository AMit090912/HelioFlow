/**
 * What the sales team should do next on a lead, worked out from its status (and, once it is a
 * project, the project's stage). One source for the inbox, the lead page and the projects list,
 * so they always agree. `next_action` (survey visit or call) is only the score's suggestion for
 * HOW to check the roof; it is not the next step once the roof is checked.
 */

import { STAGE_LABEL } from "@/components/staff/copy";
import { STAGES, type Stage } from "@/lib/projects";

/** The lead's journey, as the sales team sees it. */
export const JOURNEY = ["bill", "check", "quote", "accept", "advance", "project"] as const;
export type JourneyStep = (typeof JOURNEY)[number];

export const JOURNEY_LABEL: Record<JourneyStep, string> = {
  bill: "Bill",
  check: "Roof check",
  quote: "Quote",
  accept: "Acceptance",
  advance: "Advance",
  project: "Project",
};

/** The lead-page section where each step is done. */
export type SectionId = "bill" | "roof" | "quote" | "project";
export const SECTION_LABEL: Record<SectionId, string> = {
  bill: "Bill",
  roof: "Roof and load",
  quote: "Quote builder",
  project: "Project",
};

export type Owner = "you" | "homeowner" | "none";

export type NextStep = {
  step: JourneyStep | "done" | "closed";
  owner: Owner;
  /** Short, starts with a verb when it is the team's move. */
  title: string;
  detail: string;
  section?: SectionId;
};

type LeadLike = { status: string; next_action: "survey_visit" | "call" | null };

export function nextStageOf(stage: Stage): Stage | undefined {
  return STAGES[STAGES.indexOf(stage) + 1];
}

export function nextStep(lead: LeadLike, stage?: Stage | null): NextStep {
  switch (lead.status) {
    case "draft":
    case "bill_processing":
    case "bill_review":
      return {
        step: "bill",
        owner: "homeowner",
        title: "Homeowner to confirm their bill",
        detail: "Nothing to do yet. The lead is scored once they confirm the values read from their bill.",
        section: "bill",
      };
    case "qualified":
    case "survey_pending":
      return {
        step: "check",
        owner: "you",
        title: "Visit the roof",
        detail: "Measure the open roof area and note the sanctioned load, then save them in Roof and load.",
        section: "roof",
      };
    case "call_pending":
      return {
        step: "check",
        owner: "you",
        title: "Call to check the roof",
        detail:
          "Confirm the open roof area and sanctioned load on the phone and save them. If a visit is worth it, upgrade to a survey visit.",
        section: "roof",
      };
    case "surveyed":
      return {
        step: "quote",
        owner: "you",
        title: "Build and send the quote",
        detail: "The roof is checked. Review the options and send the quote to the homeowner.",
        section: "quote",
      };
    case "quoted":
      return {
        step: "accept",
        owner: "homeowner",
        title: "Homeowner to accept the quote",
        detail: "They choose a size and accept it online. You can call to answer questions, or send a revised quote.",
        section: "quote",
      };
    case "accepted":
      return {
        step: "advance",
        owner: "you",
        title: "Record the advance",
        detail: "Collect the advance and record it. That starts the project and sends the homeowner their status link.",
        section: "project",
      };
    case "converted": {
      if (stage === "subsidy_credited") {
        return {
          step: "done",
          owner: "none",
          title: "All done",
          detail: "The subsidy is credited. Nothing more to do on this lead.",
          section: "project",
        };
      }
      const next = stage ? nextStageOf(stage) : undefined;
      return {
        step: "project",
        owner: "you",
        title: next ? `Move to ${STAGE_LABEL[next]}` : "Move the project forward",
        detail: stage
          ? `Now at ${STAGE_LABEL[stage]}. Move it on when that step has happened; the homeowner is told each time.`
          : "Move the project one stage at a time; the homeowner is told each time.",
        section: "project",
      };
    }
    case "closed_lost":
      return { step: "closed", owner: "none", title: "Closed", detail: "This lead is closed. Nothing to do." };
    default:
      return { step: "bill", owner: "none", title: lead.status, detail: "" };
  }
}

/** How far along the journey the lead is: index into JOURNEY; JOURNEY.length when done. */
export function journeyIndex(step: NextStep["step"]): number {
  if (step === "done") return JOURNEY.length;
  if (step === "closed") return -1;
  return JOURNEY.indexOf(step);
}
