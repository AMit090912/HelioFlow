import path from "node:path";

import { expect, type Page } from "@playwright/test";

/** The synthetic sample bill that demo mode recognises (backend/app/services/ai/samples). */
export const SAMPLE_BILL = path.resolve(__dirname, "../../backend/app/services/ai/samples/sample-bill.jpg");

/** Seeded staff password: the SEED_DEMO_PASSWORD the e2e database was seeded with. No default in
 *  the repo, so no real password is ever committed. */
export const STAFF_PASSWORD = process.env.SEED_DEMO_PASSWORD ?? "";
if (!STAFF_PASSWORD) throw new Error("Set SEED_DEMO_PASSWORD to the password the e2e database was seeded with.");

/** Signed-in homeowner session, shared between the journey's steps. */
export const HOMEOWNER_STATE = path.resolve(__dirname, ".state/homeowner.json");

/** A ten-digit Indian mobile number that is new on every run. */
export function uniquePhone(): string {
  return "9" + String(Date.now()).slice(-9);
}

export async function signIn(page: Page, identifier: string, password: string) {
  await page.goto("/en/sign-in");
  await page.fill("#identifier", identifier);
  await page.fill("#password", password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/staff\/leads|\/my/);
}
