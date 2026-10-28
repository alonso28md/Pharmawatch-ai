import { ApiError, apiBase, type ReportResponse } from "./client";
import { getApiKey } from "./keyStore";
import type { components } from "./schema";

export type ReportRequest = components["schemas"]["ReportRequest"];
export interface StepEvent {
  node: string;
  index: number;
}

/** Parse complete SSE blocks from a buffer; returns the parsed events and the remainder. */
export function parseSseBuffer(buffer: string): { events: { event: string; data: unknown }[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events = blocks
    .filter((block) => block.trim())
    .map((block) => {
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      return { event, data: JSON.parse(data.join("\n")) as unknown };
    });
  return { events, rest };
}

/**
 * POST /report/stream. Calls `onStep` for every real LangGraph node event and resolves
 * with the final ReportResponse. Errors (HTTP or `error` events) reject with ApiError.
 */
export async function streamReport(
  body: ReportRequest,
  onStep: (step: StepEvent) => void,
  signal?: AbortSignal,
): Promise<ReportResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "text/event-stream" };
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;

  let response: Response;
  try {
    response = await fetch(`${apiBase()}/report/stream`, { method: "POST", headers, body: JSON.stringify(body), signal });
  } catch (error) {
    throw new ApiError(0, "network_error", error instanceof Error ? error.message : "Network error");
  }
  if (!response.ok || !response.body) {
    const envelope = (await response.json().catch(() => ({}))) as { code?: string; message?: string; details?: unknown };
    throw new ApiError(response.status, envelope.code ?? `http_${response.status}`, envelope.message ?? response.statusText, envelope.details);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const { events, rest } = parseSseBuffer(done ? `${buffer}\n\n` : buffer);
    buffer = rest;
    for (const { event, data } of events) {
      if (event === "step") onStep(data as StepEvent);
      else if (event === "result") return data as ReportResponse;
      else if (event === "error") {
        const err = data as { code: string; message: string };
        throw new ApiError(503, err.code, err.message);
      }
    }
    if (done) break;
  }
  throw new ApiError(0, "stream_incomplete", "The stream ended without a result");
}
