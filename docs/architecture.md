# Architecture

PharmaWatch AI has five independent modules wired together by a thin FastAPI
layer. Each module can be tested and reasoned about on its own.

```
                              ┌─────────────────────────┐
                              │        Client            │
                              │  (static/index.html demo,│
                              │   curl, future frontend) │
                              └────────────┬─────────────┘
                                           │ HTTPS / JSON
                              ┌────────────▼─────────────┐
                              │        FastAPI            │
                              │  CORS, rate limiting,     │
                              │  security headers, auth   │
                              │  /ask /report /evaluate   │
                              │  /health /metrics /config │
                              └──────┬─────────────┬──────┘
                 ┌───────────────────┘             └───────────────────┐
                 │                                                     │
        ┌────────▼─────────┐                              ┌───────────▼──────────┐
        │   RAG Pipeline     │                              │  Incident-Classification│
        │  (src/rag)         │◄─────── rag_query tool ──────┤  Agent (src/agent,      │
        │                     │                              │  LangGraph)             │
        │ ingest → embeddings │                              │                         │
        │ → ChromaDB →        │                              │ extract_info →          │
        │ retriever (Claude)  │                              │ classify_device →       │
        └────────┬────────────┘                              │ assess_severity →       │
                 │                                            │ [escalate | determine_  │
                 │                                            │  reporting → generate_  │
                 │                                            │  report]                │
                 │                                            └───────────┬─────────────┘
                 │                                                         │
        ┌────────▼─────────────────────────────────────────────────────────▼────────┐
        │                        Claude API (Anthropic)                              │
        │           claude-sonnet-5-5 - used by both modules above                   │
        └───────────────────────────────────────────────────────────────────────────┘

        ┌─────────────────────────┐          ┌──────────────────────────────┐
        │  Evaluation Harness       │          │   SQLite persistence          │
        │  (src/evaluation)         │          │   (src/db)                    │
        │                            │          │                                │
        │  golden_dataset.json (30)  │          │  QueryLog (every /ask,/report)│
        │  → runs RAG + agent live   │          │  EvaluationRun (every eval)   │
        │  → 8 metrics vs thresholds │          │  → powers /metrics            │
        │  → evaluation_report.md    │          │                                │
        └─────────────────────────┘          └──────────────────────────────┘
```

## Data flow: `POST /report`

1. `src/api/security.py` sanitizes the free-text description (length limit,
   role-marker stripping, basic prompt-injection pattern rejection).
2. `src/agent/graph.py` runs the LangGraph state machine:
   - `extract_info` asks Claude to pull structured fields (device name/class,
     event type, patient outcome) out of the free text.
   - `classify_device` either trusts a caller-supplied device class or falls
     back to `src/agent/tools.py::classification_rules_tool`, a keyword
     matcher against `data/classification_rules.json` (MDR Annex VIII rules
     plus named exceptions like breast implants/joint replacements).
   - `assess_severity` combines a rule-based signal
     (`severity_criteria_tool`), live regulatory context
     (`rag_query_tool`, reusing the Phase 1 retriever), and a Claude judgement
     call into a final severity + confidence + reasoning.
   - A router inspects three guardrails (low confidence, contradictory
     signals, missing critical info) and either escalates to a human or
     continues to `determine_reporting` (deadline/report-to lookup from
     `data/classification_rules.json`) and `generate_report` (drafts the
     notification fields).
   - A fourth guardrail (death/life-threatening) doesn't block the automated
     determination but flags `escalated_to_human` for an *additional*
     specialist review alongside it.
3. The route sets `request.state.*` fields the `LoggingMiddleware` reads and
   persists via `src/db/repository.py`.

## Data flow: `POST /ask`

1. Sanitize the question.
2. `src/rag/retriever.py` embeds the question (all-MiniLM-L6-v2), queries the
   persisted ChromaDB collection for the top-k chunks, and builds a
   cited-sources prompt. An explicit `ANSWER LANGUAGE` instruction is derived
   from the question itself (see the Phase 3 bug writeup below) rather than
   trusting the model to infer it, since that was found to be unreliable.
3. Claude answers using only the retrieved context; the response is split
   back into an `answer` string plus a `sources` list with document/section/
   relevance score.

## Why these specific design choices

- **ChromaDB + sentence-transformers over a managed vector DB**: free, local,
  no extra infrastructure for a portfolio-scale corpus (87 chunks across 3
  documents).
- **LangGraph over a hand-rolled state machine**: the escalation branching is
  exactly the kind of conditional-routing problem LangGraph is built for, and
  it keeps the graph topology declarative and testable in isolation from the
  node logic.
- **Embedding-based faithfulness/hallucination metrics over an LLM judge**:
  avoids doubling the evaluation harness's API cost and latency. This is a
  real tradeoff - see `src/evaluation/metrics.py` and the evaluation report's
  notes for the calibration details and its limitations.
- **SQLite over Postgres**: this is a single-process portfolio deployment;
  SQLite needs no extra service and is trivial to inspect locally.
