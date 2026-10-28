import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import fixture from "@/mocks/evaluation.fixture.json";
import { metricsFixture } from "@/mocks/fixtures";
import { server } from "@/mocks/server";
import { renderApp } from "./render";

describe("dashboard", () => {
  it("shows real activity figures and the most recent incidents", async () => {
    renderApp("/");
    expect(await screen.findByText("15")).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: /latest incidents/i });
    expect(within(table).getAllByRole("row").length).toBeGreaterThan(1);
  });

  it("says there is no traffic instead of showing zeros as figures", async () => {
    server.use(
      http.get("*/api/metrics", () =>
        HttpResponse.json({ ...metricsFixture, total_queries: 0, queries_last_24h: 0, latency_samples: 0 }),
      ),
    );
    renderApp("/");
    expect(await screen.findByText(/no traffic recorded yet/i)).toBeInTheDocument();
  });
});

describe("review queue", () => {
  it("lists only escalated incidents by default and opens one read-only", async () => {
    const user = userEvent.setup();
    renderApp("/review");
    const table = await screen.findByRole("table", { name: /review queue/i });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.length).toBeGreaterThan(0);
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();

    await user.click(within(rows[0]!).getByRole("link"));
    expect(await screen.findByRole("link", { name: /back to queue/i })).toBeInTheDocument();
  });

  it("keeps filters in the URL and shows an empty state", async () => {
    const user = userEvent.setup();
    renderApp("/review?severity=non-serious&escalation=blocking");
    expect(await screen.findByText(/no escalated incidents/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /clear filters/i }));
    expect(await screen.findByRole("table", { name: /review queue/i })).toBeInTheDocument();
  });

  it("reports a missing incident", async () => {
    renderApp("/review/INC-DOESNOTEXIST");
    expect(await screen.findByText(/does not exist/i)).toBeInTheDocument();
  });
});

describe("evaluation", () => {
  it("shows provenance, the draft-label and proposed-threshold warnings and every metric", async () => {
    renderApp("/evaluation");
    expect(await screen.findByText(fixture.file)).toBeInTheDocument();
    expect(screen.getByText(/draft labels \(ai\)/i)).toBeInTheDocument();
    expect(screen.getByText(/proposed thresholds/i)).toBeInTheDocument();
    for (const key of Object.keys(fixture.metric_summary)) {
      expect(screen.getByRole("rowheader", { name: key })).toBeInTheDocument();
    }
    // Weak metrics are shown as failing, not hidden.
    const failing = Object.values(fixture.metric_summary).filter((s) => s.meets_threshold === false).length;
    expect(screen.getAllByText(/^misses$/i)).toHaveLength(failing);
  });

  it("explains how each metric is computed", async () => {
    renderApp("/evaluation");
    expect(await screen.findByRole("button", { name: /^how it is computed: rag cases with the expected document/i })).toBeInTheDocument();
  });

  it("says so when no evaluation has been stored", async () => {
    server.use(http.get("*/api/evaluations/latest", () => HttpResponse.json({ detail: "none" }, { status: 404 })));
    renderApp("/evaluation");
    expect(await screen.findByText(/no stored evaluation/i)).toBeInTheDocument();
  });
});

describe("operations", () => {
  it("shows latency, error rates and charts with a table twin", async () => {
    renderApp("/operations");
    expect(await screen.findByText("4.08 s")).toBeInTheDocument();
    expect(screen.getByText(/client errors/i)).toBeInTheDocument();
    expect(screen.getAllByText(/show data as a table/i)).toHaveLength(2);
    expect(screen.getByRole("table", { name: /device classes/i })).toBeInTheDocument();
  });

  it("asks the backend for demo rows only when the toggle is on", async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    server.use(
      http.get("*/api/metrics", ({ request }) => {
        seen.push(new URL(request.url).searchParams.get("include_demo") ?? "");
        return HttpResponse.json(metricsFixture);
      }),
    );
    renderApp("/operations");
    await screen.findByText("4.08 s");
    await user.click(screen.getByRole("checkbox", { name: /include demo rows/i }));
    await vi.waitFor(() => expect(seen).toContain("true"));
    expect(seen[0]).toBe("false");
  });
});
