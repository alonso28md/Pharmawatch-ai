import { expect, test } from "@playwright/test";

const SHOTS = process.env.SCREENSHOT_DIR;

test("triage: real steps stream in, then the determination", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("triage");
  await page.getByLabel("¿Qué ha pasado?").fill(
    "Una bomba de infusión administró heparina en exceso por un fallo de software; el paciente sufrió una hemorragia importante e ingresó en la UCI.",
  );
  await page.getByRole("button", { name: "Clasificar incidente" }).click();
  await expect(page.getByText("Extracción de datos del texto")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Plazo de notificación" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Deterioro grave no anticipado").first()).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/triage-desktop.png`, fullPage: true });
});

test("triage: blocking escalation on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("triage");
  await page.getByLabel("¿Qué ha pasado?").fill("Alguien comentó un posible problema con un monitor; no consta el resultado para el paciente.");
  await page.getByRole("button", { name: "Clasificar incidente" }).click();
  await expect(page.getByRole("heading", { name: "Decisión humana necesaria" })).toBeVisible({ timeout: 10_000 });
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/triage-blocked-phone.png`, fullPage: true });
});

test("ask: citation opens the exact fragment", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("ask");
  await page.getByLabel("Pregunta normativa").fill("¿Cuál es el plazo para notificar un incidente grave con resultado de muerte?");
  await page.getByRole("button", { name: "Preguntar", exact: true }).click();
  await page.getByRole("button", { name: /C1: MDR 2017\/745/ }).first().click();
  await expect(page.getByRole("dialog")).toContainText("not later than 10 days");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/ask-desktop.png` });
});
