import type { ConfigResponse, HealthResponse, MetricsResponse } from "@/lib/api/client";

/**
 * Mock-mode fixtures. Shapes come from the generated OpenAPI types; values mirror real
 * backend responses captured during the phase-6 live checks (no invented regulation).
 * Everything rendered in mock mode is flagged by the "Demo mode" banner.
 */
export const healthFixture: HealthResponse = {
  status: "healthy",
  version: "2.0.0",
  vectorstore: "connected",
  vectorstore_documents: 93,
  database: "connected",
  model: "claude-sonnet-5-5",
  uptime_seconds: 3725.4,
};

export const configFixture: ConfigResponse = {
  model: "claude-sonnet-5-5",
  rate_limit_per_minute: 30,
  retrieval_top_k: 5,
  supported_languages: ["en", "es"],
  endpoints: ["/health", "/ask", "/report", "/reports/{incident_id}", "/evaluate", "/metrics", "/config"],
};

export const metricsFixture: MetricsResponse = {
  total_queries: 15,
  queries_last_24h: 15,
  include_demo: false,
  avg_latency_ms: 4312.6,
  p50_latency_ms: 4083.0,
  p95_latency_ms: 7612.4,
  latency_samples: 15,
  classification_distribution: { serious: 3, "non-serious": 1, escalated: 4 },
  escalation_rate: 0.5714,
  blocking_escalation_rate: 0.4286,
  top_device_classes: { III: 2, IIb: 1 },
  avg_confidence: 0.86,
  error_rate: 0.0,
  client_error_rate: 0.0667,
};
