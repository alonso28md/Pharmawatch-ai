import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { daysRemaining } from "@/lib/deadline";
import { parseSseBuffer } from "@/lib/api/stream";
import { server } from "@/mocks/server";
import { renderApp } from "./render";

const SERIOUS = "The infusion pump over-infused heparin and the patient had a major bleed and was admitted to the ICU.";

async function submit(text: string) {
  const user = userEvent.setup();
  renderApp("/triage");
  await user.type(await screen.findByLabelText(/¿Qué ha pasado\?|What happened\?/), text);
  await user.click(screen.getByRole("button", { name: /clasificar incidente|classify incident/i }));
  return user;
}

describe("triage", () => {
  it("validates the description inline before calling the API", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(http.post("*/api/report/stream", () => { called = true; return HttpResponse.json({}); }));
    renderApp("/triage");
    await user.click(await screen.findByRole("button", { name: /clasificar incidente|classify incident/i }));
    const textarea = screen.getByLabelText(/¿Qué ha pasado\?|What happened\?/);
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(textarea).toHaveFocus();
    expect(screen.getByText(/al menos 20 caracteres|at least 20 characters/)).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("shows the real agent steps and then the determination with its deadline", async () => {
    await submit(SERIOUS);
    expect(await screen.findByText(/Plazo y destinatarios|Deadline and recipients/)).toBeInTheDocument();
    const result = await screen.findByRole("heading", { name: /plazo de notificación|reporting deadline/i });
    const summary = result.closest("section")!;
    expect(within(summary).getByText(/Deterioro grave no anticipado|Unanticipated serious deterioration/)).toBeInTheDocument();
    expect(within(summary).getByText("10")).toBeInTheDocument();
    expect(within(summary).getByText(/Autoridad competente|Competent authority/)).toBeInTheDocument();
    expect(screen.getByText(/Regla del Anexo VIII|Annex VIII rule/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /borrador de notificación|notification draft/i })).toBeInTheDocument();
  });

  it("presents a blocking escalation without a deadline", async () => {
    await submit("Something seemed off with a monitor; the outcome is unknown and not documented.");
    const notice = await screen.findByRole("region", { name: /decisión humana necesaria|human decision required/i });
    expect(within(notice).getByText(/resultado|outcome/i)).toBeInTheDocument();
    expect(screen.getByText(/Retenido hasta la decisión|Withheld until a specialist/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /borrador|draft/i })).not.toBeInTheDocument();
  });

  it("explains a 403 from a backend without API_KEY or DEMO_MODE", async () => {
    server.use(
      http.post("*/api/report/stream", () =>
        HttpResponse.json({ code: "endpoint_disabled", message: "disabled", details: null }, { status: 403 }),
      ),
    );
    await submit(SERIOUS);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/DEMO_MODE/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: /ajustes|settings/i })).toHaveAttribute("href", "/settings");
  });
});

describe("helpers", () => {
  it("parses SSE blocks incrementally", () => {
    const { events, rest } = parseSseBuffer('event: step\ndata: {"node":"gate","index":4}\n\nevent: res');
    expect(events).toEqual([{ event: "step", data: { node: "gate", index: 4 } }]);
    expect(rest).toBe("event: res");
  });

  it("counts deadline days from the date of awareness", () => {
    const today = new Date(2026, 9, 28);
    expect(daysRemaining("2026-10-28", 10, today)).toBe(10);
    expect(daysRemaining("2026-10-20", 10, today)).toBe(2);
    expect(daysRemaining("2026-10-10", 10, today)).toBe(-8);
  });
});
