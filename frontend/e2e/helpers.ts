import path from "node:path";

import { expect, type Page } from "@playwright/test";

/** The synthetic sample bill that demo mode recognises (backend/app/services/ai/samples). */
export const SAMPLE_BILL = path.resolve(__dirname, "../../backend/app/services/ai/samples/sample-bill.jpg");

/** Seeded staff password: SEED_DEMO_PASSWORD when the database was seeded. */
export const STAFF_PASSWORD = process.env.SEED_DEMO_PASSWORD ?? "HelioDemo#2026";

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
