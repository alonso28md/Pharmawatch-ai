import createClient, { type Middleware } from "openapi-fetch";
import { getApiKey } from "./keyStore";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type ReportResponse = Schemas["ReportResponse"];
export type AskResponse = Schemas["AskResponse"];
export type HealthResponse = Schemas["HealthResponse"];
export type MetricsResponse = Schemas["OperationalMetricsResponse"];
export type ConfigResponse = Schemas["ConfigResponse"];

/** Uniform backend error envelope: {code, message, details}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** 403 endpoint_disabled: backend has neither API_KEY nor DEMO_MODE configured. */
  get isEndpointDisabled(): boolean {
    return this.status === 403 && this.code === "endpoint_disabled";
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const key = getApiKey();
    if (key) request.headers.set("X-API-Key", key);
    return request;
  },
};

/** Absolute API base on the current origin ("/api" in dev/mock, "" when served by FastAPI). */
export function apiBase(): string {
  const base = import.meta.env.VITE_API_BASE ?? "";
  return new URL(base || "/", window.location.origin).href.replace(/\/$/, "");
}

// Resolve fetch at call time (not import time) so request interceptors such as MSW apply.
export const api = createClient<paths>({ baseUrl: apiBase(), fetch: (request) => globalThis.fetch(request) });
api.use(authMiddleware);

/** Unwrap an openapi-fetch result, throwing ApiError for any non-2xx answer. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok && result.data !== undefined) return result.data;
  const body = (result.error ?? {}) as { code?: string; message?: string; details?: unknown };
  throw new ApiError(
    result.response.status,
    body.code ?? `http_${result.response.status}`,
    body.message ?? result.response.statusText,
    body.details,
  );
}

/** Network failures (backend down) surface as a uniform ApiError too. */
export async function call<T>(fn: () => Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  try {
    return unwrap(await fn());
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, "network_error", error instanceof Error ? error.message : "Network error");
  }
}
