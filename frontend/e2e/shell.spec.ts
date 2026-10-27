import { expect, test } from "@playwright/test";

const SHOTS = process.env.SCREENSHOT_DIR;
const WIDTHS = [
  { name: "phone", width: 390, height: 844 },
  { name: "tablet", width: 820, height: 1180 },
  { name: "desktop", width: 1440, height: 900 },
];

test.describe("app shell (mock mode)", () => {
  for (const vp of WIDTHS) {
    test(`renders navigation, status and disclaimer at ${vp.name} width`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText(/Requiere revisión humana/)).toBeVisible();
      await expect(page.getByText(/Modo demostración/)).toBeVisible();
      if (vp.width < 1024) {
        await page.getByRole("button", { name: "Menú" }).click();
      }
      await expect(page.getByRole("link", { name: "Triaje de incidentes" }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: /Estado del sistema: Operativo/ }).first()).toBeVisible();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/shell-${vp.name}.png`, fullPage: true });
    });
  }
});
