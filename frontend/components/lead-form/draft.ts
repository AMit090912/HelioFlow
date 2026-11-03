/**
 * The form's memory across reloads (Review Focus 1). Step-1 answers and, once created, the lead
 * id live in sessionStorage: a reload resumes where the person was and never creates a second
 * lead. sessionStorage can throw (private mode, blocked storage), so every access is guarded.
 */

import type { Ownership, PropertyType, RoofType } from "@/lib/leads";

export type HomeDraft = {
  ownership: Ownership;
  property_type: PropertyType;
  roof_type: RoofType;
  roof_area_sqft: string;
  monthly_bill: string;
  pincode: string;
};

const HOME_KEY = "hf.leadForm.home.v1";
const LEAD_KEY = "hf.leadForm.leadId.v1";
const PHASE_KEY = "hf.leadForm.phase.v1";

function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the form still works, it just won't survive a reload */
  }
}

export function loadHome(): Partial<HomeDraft> | null {
  const raw = read(HOME_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Partial<HomeDraft>) : null;
  } catch {
    return null;
  }
}

export const saveHome = (home: Partial<HomeDraft>) => write(HOME_KEY, JSON.stringify(home));
export const loadLeadId = () => read(LEAD_KEY);
export const saveLeadId = (id: string) => write(LEAD_KEY, id);

/** Whether step 1 was finished, so a reload or language switch in step 2 stays in step 2. */
export const loadHomeDone = () => read(PHASE_KEY) === "account";
export const saveHomeDone = (done: boolean) => write(PHASE_KEY, done ? "account" : null);

export function clearDraft(): void {
  write(HOME_KEY, null);
  write(LEAD_KEY, null);
  write(PHASE_KEY, null);
}
