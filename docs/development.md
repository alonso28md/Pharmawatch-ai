# Development

## Requirements

| Tool | Version used | Notes |
|---|---|---|
| Python | 3.14 | `requirements.lock` was resolved on Python 3.14 (Docker and CI use 3.14). |
| Node.js | 24 LTS | Only for the web interface. |
| Anthropic API key | — | Only for real model calls (`/ask`, `/report`, evaluation). Tests and mock mode do not need it. |

## Backend

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -c requirements.lock
cp .env.example .env                 # then fill in the values you need
python scripts/ingest_documents.py   # builds data/chroma_db (downloads the embedding model once)
uvicorn src.api.main:app --reload
```

`requirements.txt` lists direct runtime dependencies, `requirements-dev.txt` adds the tools,
and `requirements.lock` pins every package.

Optional: `python scripts/seed_db.py` adds synthetic demo rows to the request log (marked
`source='demo'`, hidden from `/metrics` unless `include_demo=true`).

### Configuration

All settings are environment variables (or `.env`); see `.env.example` for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | empty | Model API key. |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Model id. |
| `API_KEY` | empty | Key clients send in `X-API-Key`. |
| `DEMO_MODE` | `false` | With `API_KEY` empty, opens `/ask` and `/report` for local demos. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per-IP limit on cost-bearing endpoints. |
| `MAX_REQUEST_BYTES` | `64000` | Request body limit. |
| `STORE_INPUT_TEXT` | `false` | Store submitted text in the request log (default: length and hash only). |
| `DB_PATH` | `data/pharmawatch.db` | SQLite file. |
| `CHROMA_PERSIST_DIR` | `data/chroma_db` | Vector store directory. |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Changing it requires re-running the ingestion. |
| `RETRIEVAL_TOP_K` | `5` | Fragments retrieved per question. |
| `REVIEWER_ENABLED` / `REVIEWER_MODEL` | `false` / empty | Optional reviewer node. |
| `EVAL_JUDGE_MODEL` | empty | Judge model for the evaluation (empty = `ANTHROPIC_MODEL`). |
| `EVALUATION_DATASETS` | `default=…,v2=…` | Whitelist of dataset names for `/evaluate`. |
| `ARTIFACTS_DIR` | `artifacts` | Where evaluation results are written. |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Allowed browser origins. |

## Web interface

```bash
cd frontend
npm ci
npm run dev:mock     # http://localhost:5173 — mock data in the browser, no backend, no model calls
npm run dev          # http://localhost:5173 — proxies /api/* to the backend on :8000
npm run build        # frontend/dist, served by the backend at http://localhost:8000/app
```

After changing the API, regenerate the typed client:

```bash
python scripts/export_openapi.py
cd frontend && npm run gen:api
```

Design rules (tokens, typography, colour, motion, accessibility) are in
[frontend/DESIGN.md](../frontend/DESIGN.md).

## Tests

Nothing in the default test runs calls the model.

```bash
pytest                          # backend: scripted LLM, isolated temp DB and vector store
ruff check src tests scripts
ruff format --check src tests scripts

cd frontend
npm run typecheck && npm run lint
npm test                        # Vitest + Testing Library + Mock Service Worker
npx playwright install chromium # once
npm run test:e2e                # Playwright on the mock production build: 7 screens × 3 widths, axe, keyboard
```

| Suite | Count | What it covers |
|---|---|---|
| Backend (pytest) | 242 collected; 5 opt-in tests need `--live` and a key and are skipped by default | API contracts, auth, errors, agent graph with a scripted LLM, escalation, metrics, dataset invariants, streaming, listing, serving `/app`. |
| Frontend unit (Vitest) | 52 | Screens, API client, key storage, retry policy, design tokens (WCAG contrast). |
| End-to-end (Playwright) | 47 (39 by default; 8 regenerate the README screenshots on demand) | Smoke of the 7 screens at 390 / 820 / 1440 px, axe with no serious or critical violations, dark mode, keyboard flow, settings. |
| Live smoke | 3 | Production build served by a real backend; never submits `/ask` or `/report`. |

Live smoke against a running backend (no model calls):

```bash
# terminal 1 — empty ANTHROPIC_API_KEY so nothing can reach the model
ANTHROPIC_API_KEY= DEMO_MODE=true API_KEY=local-test-key uvicorn src.api.main:app --port 8000
# terminal 2
cd frontend && npm run build
LIVE_BASE_URL=http://127.0.0.1:8000 LIVE_API_KEY=local-test-key npm run test:live
```

Regenerate the README screenshots (mock data):

```bash
cd frontend && DOCS_SCREENSHOTS=../docs/screenshots npx playwright test e2e/docs-screenshots.spec.ts
```

## Documentation checks

```bash
python scripts/check_docs.py              # figures vs stored results, links, commands, secrets, claims
python scripts/check_docs.py --count-tests # also counts backend and frontend tests (slower, no cost)
```

## Evaluation (costs money)

See [evaluation.md](evaluation.md#reproducing). `scripts/run_evaluation.py` calls the model for
every case and repetition; the stored v2 run made 550 calls.

## Docker

```bash
docker compose up --build
```

The image builds the web interface, installs the locked dependencies, indexes the corpus and
runs as an unprivileged user. Pass `ANTHROPIC_API_KEY` and `API_KEY` (or `DEMO_MODE=true`)
through the environment. The Docker build has not been verified in this environment.

## Project conventions

- One commit per phase or fix; the commit message explains why.
- Regulatory interpretations that the corpus does not settle are marked `REGULATORY-REVIEW` in
  code and data and listed in [open_questions.md](open_questions.md).
- Never invent regulatory text or figures: documentation numbers are checked by
  `scripts/check_docs.py` against stored results.
