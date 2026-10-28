# Changelog

Bug ids (`B-`, security `S-`, robustness `R-`, evaluation `E-`, tests `T-`) come from the
technical audit of v1. Each entry names the commit where the fix landed.

## 2.0.0 — unreleased

### Web interface (branch `ui-v1`)

- New React + TypeScript web interface served by the backend at `/app`: Overview, Incident
  triage with the agent's real steps streamed over SSE, Regulatory Q&A with citations, Review
  queue (read-only), Evaluation, Operations, Settings. Spanish and English, light / dark /
  system theme, reduced motion, mock mode with no backend (`9cf87c0`, `d4b523d`, `fb61c14`,
  `e1456bb`).
- New read-only endpoints: `GET /reports` (paginated, filtered), `POST /report/stream` (SSE),
  `GET /evaluations/latest` (`d4b523d`, `fb61c14`).
- Accessibility: axe with no serious or critical violations on all screens at three widths and
  in dark mode; keyboard-only flow; charts with a table equivalent (`e1456bb`).
- The build no longer inlines `data:` assets, which the strict CSP blocked (`e1456bb`).
- Requests answered with a 4xx are no longer retried by the client (`e1456bb`).
- Conditional decision metrics (`deadline_accuracy_decided`, `recipients_accuracy_decided`,
  `decision_rate`, `escalation_rate`) and offline re-scoring of stored results (`e1c2104`).
- Infusion pumps and electrosurgical units classified IIb from the corpus (`REGULATORY-REVIEW`);
  legacy seed rows marked as demo; request log stores only length and hash of submitted text
  by default (`ff43443`).
- Re-scoring now rebuilds the failed-case list and pass rate (a case that passed after
  re-scoring stayed listed as failed).
- The summary of the reported evaluation is versioned in `docs/results/`; `GET
  /evaluations/latest` serves it, marked `"source": "snapshot"`, when an installation has no
  stored results (a fresh clone showed an empty Evaluation screen).
- `scripts/check_docs.py` checks the documentation figures, links, commands, secrets and claims.
- `ruff format` applied to the whole Python code base, format only (`e30463c`).

### Correctness and safety (branch `hardening-v2`)

| Id | Fix | Commit |
|---|---|---|
| B-01 | Every node output key is declared in the agent state; a `gate` node records blocking reasons so the router sees them. | `baf5483` |
| B-02 | Single source for incident categories and deadline lookup; the model returns a structured category, deadlines come from the rules table; doubt between categories escalates. | `baf5483` |
| B-03 | Extraction returns whether the outcome is known; an unknown outcome always escalates. | `baf5483` |
| B-04 | Blocking work runs off the event loop. | `90355c8` |
| B-05, B-06, B-20 | One observability middleware records latency, status and error for every business request, including 4xx, 413, 429 and 5xx. | `90355c8` |
| B-07 | `/evaluate` accepts only whitelisted dataset names; one run per process. | `dd2f2bb` |
| B-08 | Section labels parsed correctly ("5.4. Rule 8" → "Rule 8"). | `23191b1` |
| B-09, B-10 | Whole-word device matching; no match gives no class plus an advisory review (no default class I). | `baf5483` |
| B-11 | Escalation on explicit criteria plus low confidence; blocking and advisory levels. | `baf5483` |
| B-12, B-13 | Lengths validated after stripping; device name sanitized and capped. | `baf5483` |
| B-14 | Single injectable LLM client with structured outputs, timeouts and typed errors. | `baf5483` |
| B-15 | Severity assessment uses retrieval-only context (no extra model call). | `baf5483` |
| B-16 | Device class provenance: `caller`, `extracted` or `rule`. | `baf5483` |
| B-17 | Output validation runs on every path. | `baf5483` |
| B-19 | RAG "confidence" renamed `retrieval_score`; sources expose `chunk_id`. | `90355c8` |
| B-21 | Multilingual embeddings: Spanish questions now retrieve from every document; the vector store refuses a mismatched embedding model. | `0d2feea` |
| S-01 | Cost-bearing endpoints disabled without `API_KEY` unless `DEMO_MODE=true`; constant-time key comparison. | `dd2f2bb` |
| S-02 | Request body limit (413) enforced before parsing. | `baf5483` |
| R-01, R-04 | Single LLM client; production graph compiled once. | `baf5483` |
| E-01…E-09 | Evaluation rebuilt: dataset v2 (152 draft-AI cases, frozen split), scored deadlines and recipients, escalation precision and recall, real faithfulness judge with numeric grounding, repetitions with min/max. | `23191b1` |
| T-01…T-08 | Characterization tests first (xfail), then fixed; tests isolated from real data. | `04ade94` and later |

B-18 does not appear in the change history.

Also in `hardening-v2`:

- The prompt-injection pattern screen flags instead of rejecting (it was bypassable and
  rejected legitimate questions); quoted refusals are not scored as injection compliance
  (`fc89c99`).
- Packaging: direct dependencies only, separate dev requirements, full lockfile on Python 3.14,
  multi-stage Docker image running as a non-root user, single version source (`938b456`).
- Optional independent reviewer node, disabled by default; its ablation has not been run
  (`fe09d45`).
- Uniform error envelope `{code, message, details}` (`dd2f2bb`).

### Documentation

- README and `docs/` rewritten.
- The v1 evaluation report was removed (`docs/evaluation_report.md`, `docs/evaluation_report.json`):
  its 30-case metrics did not score deadlines or escalation and are not comparable with v2. See
  [evaluation.md](evaluation.md).

## 1.0.0

Initial portfolio version (branch `master`): FastAPI service, RAG over the MDR / AEMPS corpus,
LangGraph incident classifier, SQLite persistence, v1 golden dataset of 30 cases, static demo
page, Docker and CI configuration.
