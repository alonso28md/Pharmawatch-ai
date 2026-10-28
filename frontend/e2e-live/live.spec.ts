import { expect, type Page, test } from "@playwright/test";

const KEY = process.env.LIVE_API_KEY ?? "";
const SHOTS = process.env.SCREENSHOT_DIR;

/** Collects console errors and CSP violations for the whole test. */
function watch(page: Page) {
  const problems: string[] = [];
  page.on("console", (m) => m.type() === "error" && problems.push(m.text()));
  page.on("pageerror", (e) => problems.push(e.message));
  return problems;
}

test("served by FastAPI: shell, health and evaluation without errors or CSP violations", async ({ page }) => {
  const problems = watch(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1, name: "Panel general" })).toBeVisible();
  await expect(page.getByText(/Modo demostración/)).toHaveCount(0); // real mode, not mocks
  await expect(page.getByRole("button", { name: /Estado del sistema: Operativo/ }).first()).toBeVisible();
  await page.goto("evaluation");
  await expect(page.getByRole("rowheader", { name: "over_escalation_rate" })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/live-evaluation.png`, fullPage: true });
  await page.goto("operations");
  await expect(page.getByRole("heading", { name: "Latencia" })).toBeVisible();
  expect(problems.filter((p) => !/401|Unauthorized/.test(p))).toEqual([]);
});

test("protected endpoints: 401 without key, data with the key from Settings", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("review");
  await expect(page.getByText("Clave de API no válida")).toBeVisible();
  await page.goto("settings");
  await page.getByLabel("Clave de API del servidor").fill(KEY);
  await page.getByRole("button", { name: "Guardar clave" }).click();
  await page.getByRole("button", { name: "Comprobar" }).click();
  await expect(page.getByText("El servidor acepta la petición.")).toBeVisible();
  await page.getByRole("link", { name: "Cola de revisión" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Cola de revisión" })).toBeVisible();
  await expect(page.getByText("Clave de API no válida")).toHaveCount(0);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/live-review.png`, fullPage: true });
});

test("deep link reload keeps the client route", async ({ page }) => {
  await page.goto("review/INC-DOES-NOT-EXIST");
  await expect(page.getByRole("link", { name: "Volver a la cola" })).toBeVisible();
});
