/**
 * The whole product in one run (ARCHITECTURE §15.4), through the screens only:
 * homeowner signs up through the lead form → uploads the sample bill → confirms the values →
 * sales sees the lead → verifies the roof → sends a quote → homeowner accepts →
 * sales records the advance → moves a stage → the public status page shows the new stage.
 */
import { expect, test, type Browser, type Page } from "@playwright/test";

import { HOMEOWNER_STATE, SAMPLE_BILL, signIn, STAFF_PASSWORD, uniquePhone } from "./helpers";

test.describe.configure({ mode: "serial" });

let leadId = "";
let leadCode = "";
let statusLink = "";
let oldestQuoteId = "";
let newestQuoteId = "";

async function homeowner(browser: Browser): Promise<Page> {
  return (await browser.newContext({ storageState: HOMEOWNER_STATE })).newPage();
}

test("homeowner: lead form, bill upload and confirmation", async ({ page }) => {
  await page.goto("/en/get-solar");
  await page.locator("label:has(input[value=owner])").click();
  await page.locator("label:has(input[value=home])").click();
  await page.locator("label:has(input[value=rcc_flat])").click();
  await page.fill("#roof_area_sqft", "450");
  await page.fill("#monthly_bill", "3200");
  await page.fill("#pincode", "440010");
  await page.getByRole("button", { name: "Continue" }).click();

  await page.fill("#full_name", "Sunita Bawane");
  await page.fill("#phone", uniquePhone());
  await page.fill("#password", "sunrise-roof-42");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account and continue" }).click();

  await expect(page.getByRole("heading", { name: "Upload your electricity bill" })).toBeVisible();
  leadCode = (await page.getByText(/LD-\d{6}/).first().innerText()).match(/LD-\d{6}/)![0];
  await page.setInputFiles('input[type=file][accept*="pdf"]', SAMPLE_BILL);
  await page.getByRole("button", { name: "Upload and read my bill" }).click();

  // Demo mode reads the synthetic sample deterministically; the values are editable.
  await expect(page.locator("#avg_monthly_units")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("#avg_monthly_units")).not.toHaveValue("");
  await page.getByRole("button", { name: "Confirm these values" }).click();
  await page.waitForURL("**/en/my");
  await expect(page.getByRole("heading", { name: "My solar" })).toBeVisible();

  const mine = await page.evaluate(() => fetch("/api/leads/mine").then((r) => r.json()));
  leadId = mine[0].id;
  expect(mine[0].next_action).not.toBeNull(); // scored and qualified
  await page.context().storageState({ path: HOMEOWNER_STATE });
});

test("sales: finds the lead, verifies the roof and sends a quote", async ({ page }) => {
  await signIn(page, "sales@helioflow.example", STAFF_PASSWORD);
  // A fresh High lead is the team's move, so it is on the default tab.
  await expect(page.getByRole("group", { name: "Whose move" }).getByRole("button", { name: /Your move/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  const row = page.getByRole("row", { name: new RegExp(leadCode) });
  await expect(row.getByText("Visit the roof")).toBeVisible();
  await row.getByRole("link", { name: "Sunita Bawane" }).click();
  await expect(page.getByText(leadCode).first()).toBeVisible();

  // The next step leads the page and points at the right section.
  await expect(page.getByRole("heading", { name: "Visit the roof" })).toBeVisible();
  await page.getByRole("button", { name: "Go to Roof and load" }).click();
  await page.fill("#v-roof", "450");
  await page.fill("#v-load", "5");
  await page.getByRole("button", { name: "Save verification" }).click();

  await expect(page.getByRole("heading", { name: "Build and send the quote" })).toBeVisible();
  const send = page.getByRole("button", { name: "Send quote" });
  await expect(send).toBeEnabled();
  await send.click();
  await expect(page.getByText(/Sent HF-Q-/)).toBeVisible();

  // A revision: the homeowner must always land on the newest quote.
  await page.getByRole("button", { name: "Send revised quote" }).click();
  await expect(page.getByText(/Sent HF-Q-/)).toBeVisible();
  const detail = await (await page.request.get(`/api/staff/leads/${leadId}`)).json();
  const sentQuotes = [...detail.quotes].sort((a, b) => a.sent_at.localeCompare(b.sent_at));
  expect(sentQuotes).toHaveLength(2);
  oldestQuoteId = sentQuotes[0].id;
  newestQuoteId = sentQuotes[1].id;
  await expect(page.getByRole("heading", { name: "Homeowner to accept the quote" })).toBeVisible();
});

test("homeowner: opens the quote, downloads the PDF and accepts 3 kW", async ({ browser }) => {
  const page = await homeowner(browser);

  // An old link (e.g. from an earlier message) opens the newest quote in one step.
  await page.goto(`/en/my/quote/${oldestQuoteId}`);
  await page.waitForURL(`**/en/my/quote/${newestQuoteId}**`);
  await expect(page.getByText("Your quote was updated")).toBeVisible();

  await page.goto("/en/my");
  await page.getByRole("link", { name: "See your quote" }).first().click();
  await page.waitForURL("**/en/my/quote/**");

  const quoteId = page.url().split("/").pop()!.split("?")[0];
  expect(quoteId).toBe(newestQuoteId);
  const pdf = await page.request.get(`/api/quotes/${quoteId}/pdf?lang=en`);
  expect(pdf.status()).toBe(200);
  expect(pdf.headers()["content-type"]).toBe("application/pdf");

  await page.locator("label:has(input[value='3'])").click();
  await page.getByRole("button", { name: "Accept the 3 kW system" }).click();
  await page.getByRole("button", { name: "Yes, accept" }).click();
  await expect(page.getByText("You accepted the 3 kW system")).toBeVisible();
});

test("sales: records the advance, gets the status link and moves a stage", async ({ page }) => {
  await signIn(page, "sales@helioflow.example", STAFF_PASSWORD);
  await page.goto(`/en/staff/leads/${leadId}`);
  await expect(page.getByRole("heading", { name: "Record the advance" })).toBeVisible();
  await page.locator("#section-project input[inputmode=decimal]").fill("25000");
  await page.getByRole("button", { name: "Record advance and start project" }).click();

  const link = page.getByLabel("Status link");
  await expect(link).toBeVisible();
  statusLink = await link.inputValue();
  expect(statusLink).toContain("/en/s/");

  await page.getByRole("button", { name: "Move to Installation scheduled" }).click();
  await expect(page.getByRole("button", { name: "Move to Installation completed" })).toBeVisible();
});

test("public status page shows the new stage, signed out, with nothing private", async ({ browser }) => {
  const page = await (await browser.newContext()).newPage();
  const path = statusLink.replace(/^https?:\/\/[^/]+/, "");
  const response = await page.goto(path);
  expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
  await expect(page.getByText("Installation scheduled").first()).toBeVisible();
  // §12: first name, project code and stages only. No surname, money or phone number.
  const text = await page.locator("main").innerText();
  expect(text).toContain("Sunita");
  expect(text).not.toMatch(/₹|25,000|Bawane|\d{10}/);
});

test("homeowner dashboard follows the project", async ({ browser }) => {
  const page = await homeowner(browser);
  await page.goto("/en/my");
  await expect(page.getByRole("heading", { name: "Installation scheduled" })).toBeVisible();
  await expect(page.getByText("Accepted")).toBeVisible();
});
