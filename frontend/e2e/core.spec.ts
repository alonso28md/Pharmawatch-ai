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

test("dashboard, review queue and incident detail", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("./");
  await expect(page.getByRole("table", { name: "Últimos incidentes" })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/dashboard-desktop.png`, fullPage: true });
  await page.goto("review");
  const queue = page.getByRole("table", { name: "Cola de revisión" });
  await expect(queue).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/review-desktop.png`, fullPage: true });
  await queue.getByRole("link").first().click();
  await expect(page.getByRole("link", { name: "Volver a la cola" })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/review-detail-desktop.png`, fullPage: true });
});

test("evaluation and operations", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("evaluation");
  await expect(page.getByText("Etiquetas borrador (IA), pendientes de validación experta")).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "over_escalation_rate" })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/evaluation-desktop.png`, fullPage: true });
  await page.goto("operations");
  await expect(page.getByRole("heading", { name: "Clases de dispositivo" })).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/operations-desktop.png`, fullPage: true });
});

test("review queue and dashboard on a phone: no horizontal page scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  await expect(page.getByRole("table", { name: "Últimos incidentes" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.goto("review");
  await expect(page.getByRole("table", { name: "Cola de revisión" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/review-phone.png`, fullPage: true });
});
