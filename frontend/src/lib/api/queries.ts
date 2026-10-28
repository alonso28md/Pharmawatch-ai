import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, call } from "./client";
import type { components } from "./schema";

export type IncidentSummary = components["schemas"]["IncidentSummary"];
export type IncidentPage = components["schemas"]["IncidentPage"];
export type EvaluationLatest = components["schemas"]["EvaluationLatest"];

export interface ReportFilters {
  limit?: number;
  offset?: number;
  severity?: "serious" | "non-serious";
  escalation?: "none" | "advisory" | "blocking" | "escalated";
  date_from?: string;
  date_to?: string;
}

export const queryKeys = {
  health: ["health"] as const,
  config: ["config"] as const,
  metrics: (includeDemo: boolean) => ["metrics", includeDemo] as const,
  reports: (filters: ReportFilters) => ["reports", filters] as const,
  report: (id: string) => ["report", id] as const,
  evaluation: ["evaluation", "latest"] as const,
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

export function useMetrics(includeDemo = false) {
  return useQuery({
    queryKey: queryKeys.metrics(includeDemo),
    queryFn: () => call(() => api.GET("/metrics", { params: { query: { include_demo: includeDemo } } })),
    refetchInterval: 60_000,
  });
}

export function useReports(filters: ReportFilters) {
  return useQuery({
    queryKey: queryKeys.reports(filters),
    queryFn: () => call(() => api.GET("/reports", { params: { query: filters } })),
    placeholderData: keepPreviousData,
  });
}

export function useReport(id: string) {
  return useQuery({
    queryKey: queryKeys.report(id),
    queryFn: () => call(() => api.GET("/reports/{incident_id}", { params: { path: { incident_id: id } } })),
    retry: false,
  });
}

export function useLatestEvaluation() {
  return useQuery({
    queryKey: queryKeys.evaluation,
    queryFn: () => call(() => api.GET("/evaluations/latest", { params: { query: { dataset: "v2" } } })),
    retry: false,
  });
}
