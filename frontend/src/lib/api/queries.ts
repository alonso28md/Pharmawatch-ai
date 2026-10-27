import { useQuery } from "@tanstack/react-query";
import { api, call } from "./client";

export const queryKeys = {
  health: ["health"] as const,
  config: ["config"] as const,
  metrics: ["metrics"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => call(() => api.GET("/health")),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useConfig() {
  return useQuery({ queryKey: queryKeys.config, queryFn: () => call(() => api.GET("/config")) });
}

export function useMetrics() {
  return useQuery({
    queryKey: queryKeys.metrics,
    queryFn: () => call(() => api.GET("/metrics", { params: { query: { include_demo: false } } })),
    refetchInterval: 60_000,
  });
}
