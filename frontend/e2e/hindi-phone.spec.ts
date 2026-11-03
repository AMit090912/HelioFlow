/**
 * The homeowner journey must work in Hindi on a phone (§2 Languages; the M4 done-when):
 * the lead form at 390 px in हिन्दी, through account creation, to the bill step.
 */
import { expect, test } from "@playwright/test";

import { uniquePhone } from "./helpers";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("lead form in Hindi at phone width reaches the bill step", async ({ page }) => {
  await page.goto("/hi/get-solar");
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");

  // Empty submit shows errors in Hindi, not English.
  await page.locator("form button[type=submit]").click();
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.locator("form")).not.toContainText("Please");

  await page.locator("label:has(input[value=owner])").click();
  await page.locator("label:has(input[value=home])").click();
  await page.locator("label:has(input[value=rcc_flat])").click();
  await page.fill("#roof_area_sqft", "450");
  await page.fill("#monthly_bill", "3,200");
  await page.fill("#pincode", "440010");
  await page.locator("form button[type=submit]").click();

  await expect(page.getByRole("heading", { name: "अपना खाता बनाएँ" })).toBeVisible();
  await page.fill("#full_name", "सुनीता बावणे");
  await page.fill("#phone", uniquePhone());
  await page.fill("#password", "sunrise-roof-42");
  await page.getByRole("checkbox").check();
  await page.locator("form button[type=submit]").click();

  await expect(page.getByRole("heading", { name: "अपना बिजली बिल अपलोड करें" })).toBeVisible();
  await expect(page.getByText(/LD-\d{6}/).first()).toBeVisible();

  // Nothing overflows sideways at phone width.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
