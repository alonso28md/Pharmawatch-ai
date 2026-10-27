import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** WCAG contrast check of the design tokens declared in styles/index.css (DESIGN.md §9). */
const css = readFileSync(path.resolve(import.meta.dirname, "../styles/index.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--pw-([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1]!, m[2]!]));
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

const light = block(":root {");
const dark = { ...light, ...block(':root[data-theme="dark"]') };

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme contrast", (_name, t) => {
  it.each(["canvas", "surface", "surface-raised", "surface-sunken"])("text tiers on %s are >= 4.5:1", (bg) => {
    expect(contrast(t.text!, t[bg]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t["text-muted"]!, t[bg]!)).toBeGreaterThanOrEqual(4.5);
  });

  it("accent works as link text and as a button fill", () => {
    expect(contrast(t.accent!, t.surface!)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t["accent-contrast"]!, t.accent!)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(["ok", "serious", "critical", "escalation", "info"])("%s status text on its tint is >= 4.5:1", (role) => {
    expect(contrast(t[`${role}-fg`]!, t[`${role}-bg`]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t[`${role}-fg`]!, t.surface!)).toBeGreaterThanOrEqual(4.5);
  });

  it("strong borders are visible against surfaces (>= 1.4:1 decorative, inputs use border-strong)", () => {
    expect(contrast(t["border-strong"]!, t.surface!)).toBeGreaterThanOrEqual(1.4);
  });
});
