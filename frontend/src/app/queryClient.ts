import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

/** Retry only what can recover by itself (network, 5xx, 429); a 4xx answer will not change. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (!(error instanceof ApiError)) return true;
  return error.status === 0 || error.status === 429 || error.status >= 500;
}

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: shouldRetry } },
  });
}
