import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { renderApp } from "./render";

describe("app shell", () => {
  it("renders the navigation with all seven screens, a skip link and the disclaimer", async () => {
    renderApp("/");
    const nav = screen.getAllByRole("navigation", { name: /navegación principal|main navigation/i })[0]!;
    expect(within(nav).getAllByRole("link")).toHaveLength(7);
    expect(screen.getByRole("link", { name: /saltar al contenido|skip to content/i })).toHaveAttribute("href", "#main");
    expect(screen.getByText(/requiere revisión humana|requires human review/i)).toBeInTheDocument();
  });

  it("navigates between screens and marks the active link", async () => {
    const user = userEvent.setup();
    renderApp("/");
    const nav = screen.getAllByRole("navigation", { name: /navegación principal|main navigation/i })[0]!;
    await user.click(within(nav).getByRole("link", { name: /triaje|triage/i }));
    expect(await screen.findByRole("heading", { level: 1, name: /triaje|triage/i })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /triaje|triage/i })).toHaveAttribute("aria-current", "page");
  });

  it("shows real system status from /health", async () => {
    renderApp("/");
    expect((await screen.findAllByRole("button", { name: /operativo|operational/i })).length).toBeGreaterThan(0);
  });

  it("reports the backend as unreachable when /health fails", async () => {
    server.use(http.get("*/api/health", () => HttpResponse.error()));
    renderApp("/");
    expect((await screen.findAllByRole("button", { name: /sin conexión|unreachable/i }, { timeout: 4000 })).length).toBeGreaterThan(0);
  });
});
