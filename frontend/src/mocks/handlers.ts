import { delay, http, HttpResponse } from "msw";
import type { ReportResponse } from "@/lib/api/client";
import type { IncidentSummary } from "@/lib/api/queries";
// The versioned summary of the reported run (scripts/export_eval_fixture.py).
import evaluationSnapshot from "../../../docs/results/evaluation_latest.json";
import { configFixture, healthFixture, metricsFixture } from "./fixtures";
import { askAnswer, pickScenario, triageScenarios } from "./scenarios";

const API = "*/api";
/** Simulated network/model latency in mock mode (0 under test). */
const STEP_MS = import.meta.env.MODE === "test" ? 0 : 350;

let counter = 0;
function incidentId(): string {
  counter += 1;
  return `INC-${new Date().getFullYear()}-${(0xa1b2c300 + counter).toString(16).toUpperCase()}`;
}

/** In-memory incident store: seeded with the scenario results, plus incidents triaged in this session. */
const HOUR = 3_600_000;
const store: IncidentSummary[] = (
  [
    ["unknown", 2],
    ["death", 5],
    ["nonSerious", 26],
    ["serious", 49],
  ] as const
).map(([key, hoursAgo]) => ({
  ...triageScenarios[key].result,
  incident_id: incidentId(),
  processing_time_ms: 6100,
  created_at: new Date(Date.now() - hoursAgo * HOUR).toISOString(),
}));

function remember(result: ReportResponse) {
  store.unshift({ ...result, created_at: new Date().toISOString() });
}

function invalid(field: string, msg: string) {
  return HttpResponse.json(
    { code: "validation_error", message: "Request validation failed", details: [{ loc: ["body", field], msg, type: "value_error" }] },
    { status: 422 },
  );
}

export const handlers = [
  http.get(`${API}/health`, () => HttpResponse.json(healthFixture)),
  http.get(`${API}/config`, () => HttpResponse.json(configFixture)),
  http.get(`${API}/metrics`, () => HttpResponse.json(metricsFixture)),
  http.get(`${API}/evaluations/latest`, () => HttpResponse.json({ ...evaluationSnapshot, source: "snapshot" })),

  http.get(`${API}/reports`, ({ request }) => {
    const q = new URL(request.url).searchParams;
    const limit = Number(q.get("limit") ?? 20);
    const offset = Number(q.get("offset") ?? 0);
    const severity = q.get("severity");
    const escalation = q.get("escalation");
    const from = q.get("date_from");
    const to = q.get("date_to");
    const matches = store.filter((i) => {
      if (severity && i.severity !== severity) return false;
      if (escalation === "escalated" && i.escalation_level === "none") return false;
      if (escalation && escalation !== "escalated" && i.escalation_level !== escalation) return false;
      const day = i.created_at.slice(0, 10);
      if (from && day < from) return false;
      if (to && day > to) return false;
      return true;
    });
    return HttpResponse.json({ items: matches.slice(offset, offset + limit), total: matches.length, limit, offset });
  }),

  http.get(`${API}/reports/:id`, ({ params }) => {
    const found = store.find((i) => i.incident_id === params.id);
    return found
      ? HttpResponse.json(found)
      : HttpResponse.json({ code: "not_found", message: "Incident not found", details: null }, { status: 404 });
  }),

  http.post(`${API}/ask`, async ({ request }) => {
    const body = (await request.json()) as { question?: string };
    const question = (body.question ?? "").trim();
    if (question.length < 10) return invalid("question", "String should have at least 10 characters");
    await delay(STEP_MS * 3);
    return HttpResponse.json({ ...askAnswer(question), processing_time_ms: 2400 });
  }),

  http.post(`${API}/report/stream`, async ({ request }) => {
    const body = (await request.json()) as { description?: string };
    const description = (body.description ?? "").trim();
    if (description.length < 20) return invalid("description", "String should have at least 20 characters");
    const scenario = triageScenarios[pickScenario(description)];
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        for (const [i, node] of scenario.steps.entries()) {
          await delay(STEP_MS);
          controller.enqueue(encoder.encode(`event: step\ndata: ${JSON.stringify({ node, index: i + 1 })}\n\n`));
        }
        const result = { ...scenario.result, incident_id: incidentId(), processing_time_ms: STEP_MS * scenario.steps.length + 4100 };
        remember(result as ReportResponse);
        controller.enqueue(encoder.encode(`event: result\ndata: ${JSON.stringify(result)}\n\n`));
        controller.close();
      },
    });
    return new HttpResponse(stream, { headers: { "Content-Type": "text/event-stream" } });
  }),
];
