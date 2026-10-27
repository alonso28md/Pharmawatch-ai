# API Reference

Base URL (local): `http://localhost:8000`. Interactive OpenAPI docs are
served at `/docs` (Swagger UI) and `/redoc`.

All endpoints return JSON. `/ask`, `/report`, and `/evaluate` are rate
limited (`RATE_LIMIT_PER_MINUTE`, default 30/min per client IP) and, if
`API_KEY` is configured, require an `X-API-Key` header.

---

## `GET /health`

Service healthcheck: vector store connectivity, DB connectivity, configured
model, uptime.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "vectorstore": "connected",
  "vectorstore_documents": 87,
  "database": "connected",
  "model": "claude-sonnet-5-5",
  "uptime_seconds": 42.1
}
```

---

## `POST /ask`

Answer a regulatory question with citations from the indexed MDR/AEMPS
documents.

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the reporting deadline for a serious incident?"}'
```

```json
{
  "answer": "The deadline depends on the type of serious incident...",
  "sources": [
    {
      "document": "MDR 2017/745 (Articles 87-92, Vigilance)",
      "section": "Article 87 - Reporting of serious incidents and field safety corrective actions",
      "text": "Manufacturers shall report any serious incident...",
      "relevance_score": 0.85
    }
  ],
  "confidence": 0.82,
  "processing_time_ms": 6200
}
```

| Field | Type | Notes |
|---|---|---|
| `question` | string, required, min 10 chars | |
| `language` | string, optional | Currently informational; answer language is auto-detected from the question text. |

---

## `POST /report`

Classify a medical device adverse event and determine reporting
requirements.

```bash
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "description": "During a routine MRI scan, the contrast injector malfunctioned and delivered 3x the programmed dose of gadolinium. The patient experienced nausea and was kept for observation for 24 hours.",
    "device_name": "GadoFlow 3000 Contrast Injector",
    "device_class": "IIb"
  }'
```

```json
{
  "incident_id": "INC-2026-A1B2C3",
  "severity": "serious",
  "severity_confidence": 0.89,
  "severity_reasoning": "The overdose led to patient symptoms requiring extended observation...",
  "reportable": true,
  "report_to": ["competent_authority", "manufacturer"],
  "deadline_days": 15,
  "device_class": "IIb",
  "classification_rule": "Provided by caller / extracted directly from description",
  "escalated_to_human": false,
  "escalation_reason": null,
  "rag_sources": [
    {"document": "MDR 2017/745 (Articles 87-92, Vigilance)", "section": "Article 87 - ...", "text": "..."}
  ],
  "draft_notification": {
    "incident_date": null,
    "reporter_type": "healthcare_professional",
    "device_identification": "GadoFlow 3000 Contrast Injector",
    "event_description": "Contrast media overdose (3x programmed dose)...",
    "patient_outcome": "Nausea, 24h observation",
    "corrective_action": "Pending investigation"
  },
  "processing_time_ms": 14300
}
```

| Field | Type | Notes |
|---|---|---|
| `description` | string, required, min 20 chars | |
| `device_name` | string, optional | |
| `device_class` | `"I" \| "IIa" \| "IIb" \| "III"`, optional | Skips the Annex VIII keyword-classification step if provided. |

When the agent can't safely auto-determine the outcome (low confidence,
contradictory description, or missing critical information), `reportable`,
`report_to`, and `deadline_days` are `null` and `escalated_to_human` is
`true` with a human-readable `escalation_reason`.

**422** is returned for a too-short description or one matching a basic
prompt-injection pattern.

---

## `POST /evaluate`

Run the golden-dataset evaluation harness (real Claude API calls - this can
take several minutes) and refresh `docs/evaluation_report.{md,json}`.

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"dataset": "default", "verbose": false}'
```

```json
{
  "summary": {"total_cases": 30, "passed": 29, "failed": 1, "pass_rate": 0.9667},
  "metrics": {
    "retrieval_accuracy": 1.0,
    "answer_faithfulness": 0.841,
    "hallucination_rate": 0.0,
    "classification_accuracy": 0.9,
    "reportability_accuracy": 0.9,
    "escalation_appropriateness": 1.0,
    "latency_p50_ms": 7686.0,
    "latency_p95_ms": 13967.0,
    "source_citation_rate": 1.0
  },
  "failed_cases": [{"case_id": "case_018", "reason": "expected severity='serious', got 'non-serious'; expected reportable=True, got None"}],
  "report_path": "docs/evaluation_report.md",
  "timestamp": "2026-10-27T12:36:03Z"
}
```

---

## `GET /metrics`

Operational metrics aggregated from the real SQLite-backed query log
(`src/db`) - not the evaluation harness. Reflects actual API traffic.

```bash
curl http://localhost:8000/metrics
```

```json
{
  "total_queries": 142,
  "queries_last_24h": 23,
  "avg_latency_ms": 7776.3,
  "p95_latency_ms": 13440.0,
  "classification_distribution": {"serious": 38, "non-serious": 89, "escalated": 15},
  "escalation_rate": 0.106,
  "top_device_classes": {"IIb": 52, "IIa": 41, "III": 28, "I": 21},
  "avg_confidence": 0.83,
  "error_rate": 0.014
}
```

---

## `GET /config`

Non-secret capability metadata for a future client to configure itself
against.

```bash
curl http://localhost:8000/config
```

```json
{
  "model": "claude-sonnet-5-5",
  "rate_limit_per_minute": 30,
  "retrieval_top_k": 5,
  "supported_languages": ["en", "es"],
  "endpoints": ["/health", "/ask", "/report", "/evaluate", "/metrics", "/config"]
}
```

---

## Error responses

| Status | When |
|---|---|
| 422 | Validation failure (field too short/long) or a prompt-injection pattern match |
| 429 | Rate limit exceeded - `{"detail": "Rate limit exceeded. Please slow down."}` |
| 401 | Missing/invalid `X-API-Key` (only when `API_KEY` is configured) |
| 500 | Unhandled server error - generic message only, no stack trace, full detail logged server-side |
