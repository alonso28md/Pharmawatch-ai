import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const SHOTS = process.env.SCREENSHOT_DIR;
const WIDTHS = [
  { name: "phone", width: 390, height: 844 },
  { name: "tablet", width: 820, height: 1180 },
  { name: "desktop", width: 1440, height: 900 },
];
const SCREENS = [
  { path: "./", name: "dashboard", ready: (p: Page) => p.getByRole("table", { name: "Últimos incidentes" }) },
  { path: "triage", name: "triage", ready: (p: Page) => p.getByLabel("¿Qué ha pasado?") },
  { path: "ask", name: "ask", ready: (p: Page) => p.getByLabel("Pregunta normativa") },
  { path: "review", name: "review", ready: (p: Page) => p.getByRole("table", { name: "Cola de revisión" }) },
  { path: "evaluation", name: "evaluation", ready: (p: Page) => p.getByRole("rowheader", { name: "over_escalation_rate" }) },
  { path: "operations", name: "operations", ready: (p: Page) => p.getByRole("heading", { name: "Clases de dispositivo" }) },
  { path: "settings", name: "settings", ready: (p: Page) => p.getByLabel("Clave de API del servidor") },
];

async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
}

for (const vp of WIDTHS) {
  test.describe(`smoke at ${vp.name} width`, () => {
    for (const screen of SCREENS) {
      test(`${screen.name}: renders, no horizontal scroll, no serious axe violations`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(screen.path);
        await expect(screen.ready(page)).toBeVisible();
        await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(await seriousViolations(page)).toEqual([]);
        if (SHOTS) await page.screenshot({ path: `${SHOTS}/${screen.name}-${vp.name}.png`, fullPage: true });
      });
    }
  });
}

test.describe("dark theme", () => {
  test.use({ colorScheme: "dark" });
  for (const screen of SCREENS) {
    test(`${screen.name}: no serious axe violations in dark mode`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(screen.path);
      await expect(screen.ready(page)).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
      expect(await seriousViolations(page)).toEqual([]);
      if (SHOTS && ["dashboard", "evaluation", "triage"].includes(screen.name)) {
        await page.screenshot({ path: `${SHOTS}/${screen.name}-dark.png`, fullPage: true });
      }
    });
  }
});

test("keyboard: skip link, visible focus and classify without a mouse", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("triage");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Saltar al contenido" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
  await page.keyboard.press("Enter");
  await page.getByLabel("¿Qué ha pasado?").focus();
  // A visible focus indicator: outline or box-shadow on the focused control.
  const ring = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    const s = getComputedStyle(el);
    return s.outlineStyle !== "none" || s.boxShadow !== "none";
  });
  expect(ring).toBe(true);
  await page.keyboard.type("Un monitor mostró una lectura errónea; el paciente recibió tratamiento innecesario y se recuperó.");
  await page.getByRole("button", { name: "Clasificar incidente" }).focus();
  await page.keyboard.press("Enter");
  // Result arrives in a live region so screen readers announce it.
  await expect(page.locator("[aria-live]").filter({ hasText: /Plazo de notificación|Decisión humana necesaria|Revisión recomendada/ }).first()).toBeVisible({ timeout: 10_000 });
});

test("settings: language and theme switch the whole app, key stays out of localStorage", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("settings");
  await page.getByLabel("Clave de API del servidor").fill("test-key-123");
  await page.getByRole("button", { name: "Guardar clave" }).click();
  await expect(page.getByText("Clave guardada en memoria (se pierde al recargar).")).toBeVisible();
  await page.getByText("English", { exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  await page.getByText("Dark", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const stored = await page.evaluate(() => JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage }));
  expect(stored).not.toContain("test-key-123");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/settings-en-dark.png`, fullPage: true });
});
