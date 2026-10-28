# API reference

Base URL in local development: `http://localhost:8000`. The interactive schema is at
`/docs` (Swagger UI) and `/openapi.json`; `frontend/openapi.json` is a committed copy used to
generate the typed client (`python scripts/export_openapi.py`, then `npm run gen:api`).

## Authentication

Send the key in the `X-API-Key` header. Behaviour depends on two settings:

| `API_KEY` | `DEMO_MODE` | `/ask`, `/report`, `/report/stream`, `/reports` | `/evaluate` |
|---|---|---|---|
| set | any | key required (401 if missing or wrong) | key required |
| empty | `true` | open | 403 `endpoint_disabled` |
| empty | `false` (default) | 403 `endpoint_disabled` | 403 `endpoint_disabled` |

`/health`, `/config`, `/metrics` and `/evaluations/latest` are public and read-only. Keys are
compared in constant time.

## Errors

Every error has the same envelope:

```json
{ "code": "unauthorized", "message": "Invalid or missing API key", "details": null }
```

| Status | `code` | When |
|---|---|---|
| 401 | `unauthorized` | `API_KEY` is set and the header is missing or wrong. |
| 403 | `endpoint_disabled` | The endpoint is disabled by configuration (see the table above). |
| 404 | `not_found` | Unknown incident id, no stored evaluation, unknown route. |
| 409 | `evaluation_in_progress` | `POST /evaluate` while another evaluation runs in this process. |
| 413 | `payload_too_large` | Request body over `MAX_REQUEST_BYTES` (default 64 000), rejected before parsing. |
| 422 | `validation_error` / `unknown_dataset` | Invalid body or query (text too short or long, wrong enum, unknown dataset). Details never echo the submitted text. |
| 429 | `rate_limited` | More than `RATE_LIMIT_PER_MINUTE` requests per minute from one client on a cost-bearing endpoint. |
| 500 | `internal_error` | Unhandled error; logged server-side, no details returned. |
| 503 | `llm_unavailable` / `llm_bad_output` | The model provider failed or returned an unusable response. |

## Endpoints

| Method | Path | Auth | Model calls |
|---|---|---|---|
| GET | `/health` | public | no |
| GET | `/config` | public | no |
| POST | `/ask` | key / demo | yes |
| POST | `/report` | key / demo | yes |
| POST | `/report/stream` | key / demo | yes |
| GET | `/reports` | key / demo | no |
| GET | `/reports/{incident_id}` | key / demo | no |
| GET | `/metrics` | public | no |
| GET | `/evaluations/latest` | public | no |
| POST | `/evaluate` | key always | yes (minutes, costly) |

Cost-bearing endpoints (`/ask`, `/report`, `/report/stream`, `/evaluate`) are rate-limited.

### `GET /health`

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "vectorstore": "connected",
  "vectorstore_documents": 93,
  "database": "connected",
  "model": "claude-sonnet-5-5",
  "uptime_seconds": 12.6
}
```

`status` is `degraded` when the vector store or the database is unavailable.

### `GET /config`

Non-secret capabilities: model id, rate limit, retrieval top-k, supported languages
(`en`, `es`) and the list of endpoints. Never returns keys.

### `POST /ask`

Regulatory question answered from the indexed corpus.

| Field | Type | Notes |
|---|---|---|
| `question` | string, 10–4000 chars | required |
| `language` | `"en"` \| `"es"` \| null | forces the answer language; omitted = detected from the question |

Response:

| Field | Notes |
|---|---|
| `answer` | Answer text with `[Cn]` citation labels. |
| `sources` | Retrieved fragments: `document`, `section`, `text`, `relevance_score`, `chunk_id`. |
| `context` | The fragments exactly as given to the model, each with its `label` (`C1`…). |
| `cited_labels` | Labels the answer cites. |
| `answered_from_context` | `true` when the answer cites at least one fragment; `false` usually means the model abstained because the corpus does not answer the question. |
| `retrieval_score` | Mean similarity of the retrieved fragments (not a confidence in the answer). |
| `processing_time_ms` | Server-side time. |

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"question": "What is the deadline to report a serious public health threat?"}'
```

### `POST /report`

Classifies an incident description and drafts the reporting determination.

| Field | Type | Notes |
|---|---|---|
| `description` | string, 20–4000 chars | required; do not include patient-identifying data |
| `device_name` | string, ≤ 200 chars | optional |
| `device_class` | `"I"` \| `"IIa"` \| `"IIb"` \| `"III"` | optional; otherwise extracted from the text or derived from Annex VIII keywords |

Response (`ReportResponse`):

| Field | Notes |
|---|---|
| `incident_id` | `INC-YYYY-XXXXXXXX`. |
| `incident_category` | `death`, `unanticipated_serious_deterioration`, `public_health_threat`, `other_serious`, `non_serious` or `unknown`. |
| `severity`, `severity_confidence`, `severity_reasoning` | Serious / non-serious, the model-reported confidence and its reasoning. |
| `reportable`, `deadline_days`, `deadline_rule`, `report_to` | From `data/classification_rules.json`; `null` when the determination is withheld. |
| `device_class`, `device_class_source`, `classification_rule` | Class, where it came from (`caller`, `extracted`, `rule`) and the Annex VIII rule applied. |
| `escalation_level` | `none`, `advisory` (determination kept, flagged) or `blocking` (determination withheld; a human must decide). |
| `escalated_to_human`, `escalation_reason` | `escalation_reason` is free English text (no stable codes yet). |
| `rag_sources` | Regulatory fragments consulted. |
| `draft_notification` | Editable notification fields when the incident is reportable. |

### `POST /report/stream`

Same body as `POST /report`, answered as Server-Sent Events:

| Event | Data |
|---|---|
| `step` | `{"node": "extract_info", "index": 1}` — one per graph node actually executed, in order |
| `result` | a `ReportResponse` |
| `error` | `{"code", "message"}` (e.g. `llm_unavailable`) |

Validation and authentication errors are normal HTTP errors returned before the stream starts.

### `GET /reports`

Stored incident results, newest first. Query parameters: `limit` (1–100, default 20),
`offset`, `severity` (`serious` | `non-serious`), `escalation` (`none` | `advisory` |
`blocking` | `escalated` = advisory or blocking), `date_from`, `date_to` (inclusive UTC
calendar days, `YYYY-MM-DD`). Response: `{"items": [...], "total", "limit", "offset"}`; each
item is a `ReportResponse` plus `created_at`.

### `GET /reports/{incident_id}`

One stored incident result, or 404.

### `GET /metrics`

Operational metrics from the request log: total and last-24 h requests, latency average /
p50 / p95 and sample count, 5xx and 4xx rates, escalation and blocking-escalation rates,
outcome distribution, device classes, average model-reported confidence. Demo rows are
excluded unless `?include_demo=true`.

### `GET /evaluations/latest`

The newest stored evaluation result in `ARTIFACTS_DIR/evaluations` (a re-scored file is
preferred to its original): provenance metadata, per-metric mean / min / max / threshold and
failed cases. Optional `dataset` label (e.g. `v2`); omitted = newest of any dataset. 404 when none is stored. Read-only: it never
starts an evaluation.

### `POST /evaluate`

Runs the evaluation harness with real model calls (minutes; costs money). Body:
`{"dataset": "v2", "categories": ["rag", "classification"]}`. Only names in the
`EVALUATION_DATASETS` whitelist are accepted; one run per process (409 while busy). Results are
written as JSON to `ARTIFACTS_DIR/evaluations`; the response includes the summary, metrics,
failed cases and the file name.
