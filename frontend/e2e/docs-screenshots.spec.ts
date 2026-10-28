import { expect, test } from "@playwright/test";

/**
 * README screenshots (English UI, mock mode: scenario data, no model calls).
 * Only runs when DOCS_SCREENSHOTS is set to the output folder, e.g.
 *   DOCS_SCREENSHOTS=../docs/screenshots npx playwright test e2e/docs-screenshots.spec.ts
 */
const OUT = process.env.DOCS_SCREENSHOTS;
test.skip(!OUT, "set DOCS_SCREENSHOTS to regenerate the README screenshots");
test.use({ locale: "en-GB" });

const DESKTOP = { width: 1440, height: 900 };

test("dashboard", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("./");
  await expect(page.getByRole("table", { name: "Latest incidents" })).toBeVisible();
  await page.screenshot({ path: `${OUT}/dashboard.png` });
});

test("triage with streamed steps and determination", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("triage");
  await page.getByLabel("What happened?").fill(
    "An infusion pump delivered an overdose of heparin because of a software fault; the patient had a major bleed and was admitted to the ICU.",
  );
  await page.getByRole("button", { name: "Classify Incident" }).click();
  await expect(page.getByRole("heading", { name: "Reporting deadline" })).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${OUT}/triage.png`, fullPage: true });
});

test("blocking escalation on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("triage");
  await page.getByLabel("What happened?").fill("Someone mentioned a possible problem with a monitor; the outcome for the patient is unknown.");
  await page.getByRole("button", { name: "Classify Incident" }).click();
  await expect(page.getByRole("heading", { name: "Human decision required" })).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${OUT}/triage-escalated-phone.png`, fullPage: true });
});

test("regulatory Q&A with citation", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("ask");
  await page.getByLabel("Regulatory question").fill("What is the deadline for reporting a serious incident that resulted in death?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.getByRole("button", { name: /C1: MDR 2017\/745/ }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.screenshot({ path: `${OUT}/ask.png` });
});

test("review queue", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("review");
  await expect(page.getByRole("table", { name: "Review queue" })).toBeVisible();
  await page.screenshot({ path: `${OUT}/review.png` });
});

test("evaluation", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("evaluation");
  await expect(page.getByRole("rowheader", { name: "over_escalation_rate" })).toBeVisible();
  await page.screenshot({ path: `${OUT}/evaluation.png`, fullPage: true });
});

test("operations", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await page.goto("operations");
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await page.screenshot({ path: `${OUT}/operations.png` });
});

test.describe("dark", () => {
  test.use({ colorScheme: "dark" });
  test("settings in dark mode", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto("settings");
    await expect(page.getByLabel("Server API key")).toBeVisible();
    await page.screenshot({ path: `${OUT}/settings-dark.png` });
  });
});
