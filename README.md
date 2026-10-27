# PharmaWatch AI

**AI-powered pharmacovigilance assistant for medical device adverse event
classification and regulatory reporting**

> Built as a portfolio project demonstrating RAG, agentic AI (LangGraph),
> evaluation frameworks, and production-ready Python services.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-47%20passing-brightgreen)

## Problem

Hospitals and healthcare professionals in the EU are legally required to
report serious incidents involving medical devices to the competent
authority within strict deadlines (2, 10, or 15 days depending on severity,
under MDR 2017/745 Article 87). In practice, deciding *whether* an event is
a "serious incident" under Article 2(65), *which* MDR Annex VIII class a
device falls under, and *who* to notify requires navigating hundreds of
pages of regulation under time pressure - a task that is manual,
inconsistent across staff, and error-prone.

PharmaWatch AI combines a retrieval-augmented question-answering system
over the real MDR/AEMPS regulatory text with an agentic incident classifier
that drafts the reporting determination (severity, deadline, recipients) and
escalates to a human specialist whenever it isn't confident enough to decide
safely on its own.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full diagram and
data-flow walkthrough. In short:

```
Client → FastAPI (CORS, rate limiting, security headers, auth)
            ├─► RAG pipeline (ChromaDB + sentence-transformers + Claude)
            └─► LangGraph incident-classification agent (reuses the RAG
                 retriever as a tool) → SQLite (query log + eval history)
```

## Features

- **RAG over real regulatory text** - MDR 2017/745 Articles 87-92
  (vigilance, deadlines, FSCA, EUDAMED), the full Annex VIII classification
  rules (all 22 rules), and AEMPS's Spanish vigilance guide, chunked and
  indexed into ChromaDB. Every answer cites its source document and section.
- **Incident classification agent** - a LangGraph state machine that
  extracts structured facts from a free-text description, classifies the
  device under Annex VIII, assesses MDR Article 2(65) seriousness, and
  determines the reporting deadline and recipients - or escalates to a
  human when it can't safely decide.
- **Evaluation harness** - a 30-case golden dataset run against the real
  system (real Claude API calls, not mocked), scored on 8 metrics with
  published thresholds. See the real results below.
- **REST API** - FastAPI with rate limiting, optional API-key auth,
  security headers, input sanitization against basic prompt injection, and
  a `/config` capability endpoint so a future frontend can configure itself.
- **Operational metrics** - every `/ask` and `/report` call is logged to
  SQLite and aggregated into `/metrics` (latency percentiles, severity
  distribution, escalation rate, error rate).
- **Containerized** - a `Dockerfile` that bakes in the ingested vector store
  at build time, plus `docker-compose.yml` for local orchestration.

## Quick Start

### Without Docker

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

python scripts/ingest_documents.py   # builds the vector store (data/chroma_db/)
uvicorn src.api.main:app --reload
```

Open `http://localhost:8000` for the demo page, or `http://localhost:8000/docs`
for the interactive API docs.

### With Docker

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

docker compose up --build
```

The image runs `scripts/ingest_documents.py` at build time, so the vector
store ships pre-populated - no separate ingestion step needed.

### Running the test suite

```bash
pytest tests/ -v          # live-API tests auto-skip without ANTHROPIC_API_KEY
ruff check src/ tests/ scripts/
python scripts/run_evaluation.py   # full 30-case evaluation (real API calls, ~2 min)
```

## Evaluation Results

**Real results from the last full run against the live Claude API and the
real system** (not simulated, not hand-picked) - see
[docs/evaluation_report.md](docs/evaluation_report.md) for the full report
including the failed-case breakdown.

| Metric | Score | Threshold | Status |
|---|---|---|---|
| Retrieval Accuracy | 100.0% | >= 85% | ✅ PASS |
| Answer Faithfulness | 84.1% | >= 90% | ❌ FAIL |
| Hallucination Rate | 0.0% | <= 10% | ✅ PASS |
| Classification Accuracy | 90.0% | >= 80% | ✅ PASS |
| Reportability Accuracy | 90.0% | >= 85% | ✅ PASS |
| Escalation Appropriateness | 100.0% | >= 75% | ✅ PASS |
| Latency p50 | 7686 ms | < 5000 ms | ❌ FAIL |
| Latency p95 | 13967 ms | < 15000 ms | ✅ PASS |
| Source Citation Rate | 100.0% | >= 95% | ✅ PASS |

**29/30 cases pass (96.7%).** The one failure is a genuinely ambiguous burn
injury case where the agent's own confidence (just under 0.7) correctly
triggers escalation to a human instead of guessing - arguably the *safer*
outcome even though it doesn't match the golden label.

**Honesty over polish**: `answer_faithfulness` and `latency_p50` are left
failing, not hidden or adjusted. They're real, reproducible measurements:
- `answer_faithfulness` uses a free, embedding-based claim-support
  heuristic (no second LLM judge, to keep the harness cheap) - see
  `src/evaluation/metrics.py` for the calibration methodology and its
  limitations.
- Latency reflects real multi-call chains: the classification agent makes
  up to 4 sequential Claude calls per incident (extract → classify →
  assess → draft), and the RAG retriever itself takes several seconds per
  call on `claude-sonnet-5-5`. A production deployment would want these
  calls parallelized where independent, and/or a faster model for the
  lower-stakes extraction step.

## API Reference

Full reference with request/response examples:
[docs/api_reference.md](docs/api_reference.md).

```bash
# Ask a regulatory question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the reporting deadline for a serious incident?"}'

# Classify an adverse event
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{"description": "A ventilator stopped delivering breaths and the patient died.", "device_class": "III"}'

# Operational metrics
curl http://localhost:8000/metrics
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service healthcheck |
| `/ask` | POST | Regulatory Q&A with citations (RAG) |
| `/report` | POST | Incident classification + reporting determination (agent) |
| `/evaluate` | POST | Run the evaluation harness, refresh the report |
| `/metrics` | GET | Real operational metrics from logged traffic |
| `/config` | GET | Non-secret capability metadata |

## Project Structure

```
pharmawatch-ai/
├── src/
│   ├── config.py              # pydantic-settings configuration
│   ├── rag/                   # Module 1: ingestion, embeddings, ChromaDB, retriever
│   ├── agent/                 # Module 3: LangGraph state/tools/nodes/guardrails/graph
│   ├── evaluation/             # Module 2: golden dataset, metrics, harness, reporter
│   ├── api/                   # Module 4: FastAPI schemas/middleware/routes/main
│   └── db/                     # Module 5: SQLAlchemy models/repository/metrics
├── data/
│   ├── regulations/            # Real MDR/AEMPS source text
│   ├── golden_dataset.json     # 30-case evaluation dataset
│   └── classification_rules.json
├── tests/                      # pytest suite (47 tests)
├── scripts/                    # ingest_documents.py, run_evaluation.py, seed_db.py
├── static/                     # Minimal demo page
├── docs/                       # architecture, api_reference, security, evaluation_report
├── Dockerfile / docker-compose.yml
└── .github/workflows/ci.yml
```

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Claude (Anthropic API), `claude-sonnet-5-5` |
| RAG | ChromaDB 1.5 + sentence-transformers 6.2 (all-MiniLM-L6-v2) |
| Agent | LangGraph 1.2 + langchain-anthropic 1.7 |
| API | FastAPI 0.162 + slowapi 0.1 (rate limiting) |
| Database | SQLite + SQLAlchemy 2.1 |
| Validation | Pydantic 2.14 |
| CI/CD | GitHub Actions |
| Container | Docker (python:3.11-slim) |

## Security

See [docs/security.md](docs/security.md) for the full writeup: input
sanitization and basic prompt-injection screening, security response
headers (CSP, X-Frame-Options, etc.), rate limiting, optional API-key auth,
secrets handling, and the known limitations this portfolio project
deliberately doesn't address (no per-user auth, no PII scrubbing, no
encryption at rest).

## Roadmap

- [ ] Parallelize independent agent-node Claude calls to bring p50 latency
      under the 5s threshold.
- [ ] Add an optional LLM-judge mode for `answer_faithfulness` (more
      accurate, higher cost) alongside the current free embedding heuristic.
- [ ] `pip-audit`/`safety` dependency scanning in CI.
- [ ] WebSocket streaming for `/ask` and `/report` (the REST response
      shapes and CORS setup are already structured to allow this without a
      breaking change).
- [ ] PII/PHI scrubbing step for `/report` descriptions before they reach
      the LLM, for any deployment handling real (non-synthetic) incident
      narratives.
- [ ] Expand the golden dataset beyond 30 cases for tighter confidence
      intervals on the evaluation metrics.

## License

MIT - see [LICENSE](LICENSE).
