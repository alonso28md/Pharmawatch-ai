import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { ApiError, api, call } from "@/lib/api/client";
import { getApiKey, isKeyInSession, setApiKey } from "@/lib/api/keyStore";
import { server } from "@/mocks/server";

afterEach(() => setApiKey(null));

describe("API client", () => {
  it("sends the API key header when one is set", async () => {
    let seen: string | null = null;
    server.use(
      http.get("*/api/config", ({ request }) => {
        seen = request.headers.get("x-api-key");
        return HttpResponse.json({});
      }),
    );
    setApiKey("test-key");
    await call(() => api.GET("/config"));
    expect(seen).toBe("test-key");
  });

  it("keeps the key in memory only unless asked to remember it for the session", () => {
    setApiKey("memory-only");
    expect(getApiKey()).toBe("memory-only");
    expect(isKeyInSession()).toBe(false);
    setApiKey("session-key", { rememberForSession: true });
    expect(window.sessionStorage.getItem("pharmawatch.apiKey")).toBe("session-key");
    expect(Object.values(window.localStorage).join()).not.toContain("session-key");
  });

  it("turns the uniform error envelope into an ApiError", async () => {
    server.use(
      http.get("*/api/config", () =>
        HttpResponse.json(
          { code: "endpoint_disabled", message: "This endpoint is disabled", details: null },
          { status: 403 },
        ),
      ),
    );
    const error = await call(() => api.GET("/config")).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isEndpointDisabled).toBe(true);
  });

  it("maps network failures to a network_error ApiError", async () => {
    server.use(http.get("*/api/config", () => HttpResponse.error()));
    const error = (await call(() => api.GET("/config")).catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("network_error");
    expect(error.status).toBe(0);
  });
});

describe("query retry policy", () => {
  it("does not retry 4xx answers but retries network errors and 5xx", async () => {
    const { shouldRetry } = await import("@/app/queryClient");
    const { ApiError } = await import("@/lib/api/client");
    expect(shouldRetry(0, new ApiError(401, "unauthorized", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(404, "not_found", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(0, "network_error", "x"))).toBe(true);
    expect(shouldRetry(0, new ApiError(503, "llm_unavailable", "x"))).toBe(true);
    expect(shouldRetry(2, new ApiError(503, "llm_unavailable", "x"))).toBe(false);
  });
});
