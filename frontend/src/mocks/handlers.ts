import { delay, http, HttpResponse } from "msw";
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
        controller.enqueue(encoder.encode(`event: result\ndata: ${JSON.stringify(result)}\n\n`));
        controller.close();
      },
    });
    return new HttpResponse(stream, { headers: { "Content-Type": "text/event-stream" } });
  }),
];
