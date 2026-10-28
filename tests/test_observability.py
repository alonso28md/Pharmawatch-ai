"""Phase 3: non-blocking routes, request logging, /metrics, incident persistence, migration."""

import asyncio
import sqlite3
import time

import pytest

from src.api.deps import get_classification_fn, get_repository, limiter
from src.config import get_settings
from src.db.repository import Repository
from src.rag.retriever import RagAnswer, Source
from tests.fakes import ScriptedLLM, assessment, deps_for, extraction

REPORT = {"description": "The infusion pump over-infused; the patient was admitted to the ICU."}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def stub_ask(monkeypatch):
    class Stub:
        def answer(self, question, **kwargs):
            return RagAnswer("ok", [Source("D", "S", "t", 0.8, "c1")], 0.8, 1)

    monkeypatch.setattr("src.api.routes.ask.get_retriever", lambda: Stub())


@pytest.fixture
def override_classify():
    from src.api.main import app

    def install(fn):
        app.dependency_overrides[get_classification_fn] = lambda: fn

    yield install
    app.dependency_overrides.pop(get_classification_fn, None)


def _graph_classifier(category="other_serious", delay=0.0):
    from src.agent.graph import run_incident_classification

    def classify(description, **kwargs):
        llm = ScriptedLLM(
            extract=extraction(device_class="IIb"), assess=assessment(category), delay=delay
        )
        return run_incident_classification(description, deps=deps_for(llm), **kwargs)

    return classify


def _rows(endpoint=None):
    return [
        r for r in get_repository().list_queries() if endpoint is None or r.endpoint == endpoint
    ]


# --- B-04: the event loop stays free --------------------------------------------------------


async def test_health_answers_fast_while_a_report_is_running(api_client, override_classify):
    override_classify(_graph_classifier(delay=0.75))  # extract + assess + draft = ~2.25 s
    report_task = asyncio.create_task(api_client.post("/report", json=REPORT))
    await asyncio.sleep(0.3)  # the report is now inside a blocking model call

    start = time.perf_counter()
    health = await api_client.get("/health")
    health_ms = (time.perf_counter() - start) * 1000

    assert health.status_code == 200
    assert not report_task.done()
    assert health_ms < 200, f"/health took {health_ms:.0f} ms while /report was running"
    assert (await report_task).status_code == 200


# --- B-05 / B-06 / B-20: what gets logged ---------------------------------------------------


async def test_successful_request_logs_latency_status_and_outcome(api_client, override_classify):
    override_classify(_graph_classifier("unanticipated_serious_deterioration"))
    assert (await api_client.post("/report", json=REPORT)).status_code == 200
    (row,) = _rows("/report")
    assert row.status_code == 200
    assert row.latency_ms is not None and row.latency_ms > 0
    assert row.error is None
    assert row.escalation_level == "none" and row.source == "live"


@pytest.mark.parametrize(
    ("body", "status", "error"),
    [
        ({"description": "short"}, 422, "validation_error"),
        ({"description": " " * 30}, 422, "validation_error"),
    ],
)
async def test_client_errors_are_logged_with_status_and_code(api_client, body, status, error):
    response = await api_client.post("/report", json=body)
    assert response.status_code == status
    (row,) = _rows("/report")
    assert row.status_code == status and row.error == error
    assert row.latency_ms is not None


async def test_413_and_429_are_logged(api_client, monkeypatch, stub_ask):
    monkeypatch.setenv("MAX_REQUEST_BYTES", "200")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    await api_client.post("/ask", json={"question": "q" * 300})
    await api_client.post("/ask", json={"question": "What is the deadline?"})
    await api_client.post("/ask", json={"question": "What is the deadline?"})
    statuses = sorted((r.status_code, r.error) for r in _rows("/ask"))
    assert statuses == [(200, None), (413, "payload_too_large"), (429, "rate_limited")]


async def test_unhandled_exception_is_a_logged_uniform_500(api_client, override_classify):
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    override_classify(boom)
    response = await api_client.post("/report", json=REPORT)
    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "details": None,
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    (row,) = _rows("/report")
    assert row.status_code == 500 and row.error == "internal_error"


async def test_non_business_routes_are_not_logged(api_client):
    for path in ("/health", "/config", "/metrics", "/", "/static/app.js", "/openapi.json"):
        await api_client.get(path)
    assert _rows() == []


async def test_process_time_header_is_set_everywhere(api_client):
    response = await api_client.get("/config")
    assert float(response.headers["x-process-time-ms"]) >= 0


# --- /metrics ---------------------------------------------------------------------------------


async def test_metrics_report_real_latency_and_errors_and_exclude_demo(
    api_client, override_classify
):
    repo = get_repository()
    for _ in range(5):
        repo.log_query(
            endpoint="/report",
            severity="serious",
            latency_ms=99999.0,
            status_code=200,
            source="demo",
            escalated=True,
        )
    override_classify(_graph_classifier())
    await api_client.post("/report", json=REPORT)
    await api_client.post("/report", json={"description": "short"})

    live = (await api_client.get("/metrics")).json()
    assert live["total_queries"] == 2
    assert live["include_demo"] is False
    assert 0 < live["avg_latency_ms"] < 99999.0
    assert live["latency_samples"] == 2
    assert live["client_error_rate"] == 0.5
    assert live["error_rate"] == 0.0

    with_demo = (await api_client.get("/metrics", params={"include_demo": "true"})).json()
    assert with_demo["total_queries"] == 7
    assert with_demo["classification_distribution"]["escalated"] == 5


def test_seed_db_rows_are_marked_demo(tmp_path, monkeypatch):
    import scripts.seed_db as seed_db

    monkeypatch.setenv("DB_PATH", str(tmp_path / "seed.db"))
    get_settings.cache_clear()
    seed_db.main(num_records=10)
    rows = Repository(tmp_path / "seed.db").list_queries()
    assert len(rows) == 10 and {r.source for r in rows} == {"demo"}
    assert Repository(tmp_path / "seed.db").list_queries(include_demo=False) == []


# --- incident persistence ---------------------------------------------------------------------


async def test_report_is_persisted_without_the_description(api_client, override_classify):
    override_classify(_graph_classifier("unanticipated_serious_deterioration"))
    created = (await api_client.post("/report", json=REPORT)).json()

    fetched = await api_client.get(f"/reports/{created['incident_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created
    with sqlite3.connect(get_settings().db_path_absolute) as conn:
        incident_rows = conn.execute("SELECT * FROM incidents").fetchall()
    assert len(incident_rows) == 1
    assert "over-infused" not in repr(incident_rows)


async def test_unknown_and_malformed_incident_ids(api_client):
    assert (await api_client.get("/reports/INC-2026-ABCDEF12")).status_code == 404
    assert (await api_client.get("/reports/..%2F..%2Fetc")).status_code in (404, 422)
    assert (await api_client.get("/reports/not-an-id")).status_code == 422


# --- migration of an existing (pre-v2) database -------------------------------------------------


OLD_QUERIES_DDL = """
CREATE TABLE queries (
    id INTEGER NOT NULL PRIMARY KEY, timestamp DATETIME NOT NULL, endpoint VARCHAR(64) NOT NULL,
    input_text TEXT, output_summary TEXT, severity VARCHAR(16), device_class VARCHAR(8),
    reportable BOOLEAN, confidence FLOAT, escalated BOOLEAN NOT NULL, latency_ms FLOAT, error TEXT
)
"""


def test_existing_database_is_migrated_additively(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(OLD_QUERIES_DDL)
        conn.execute(
            "INSERT INTO queries (timestamp, endpoint, escalated, latency_ms) "
            "VALUES ('2026-10-27 11:50:47', '/ask', 0, NULL)"  # pre-v2 real traffic never had a latency (B-05)
        )

    repo = Repository(path)
    (old,) = repo.list_queries()
    assert old.latency_ms is None and old.source == "live" and old.status_code is None
    repo.log_query(endpoint="/ask", status_code=200, latency_ms=1.0)
    assert len(repo.list_queries()) == 2
    Repository(path)  # idempotent: a second start does not try to re-add columns


# --- B-15 / B-19 / R-04 -------------------------------------------------------------------------


async def test_ask_exposes_retrieval_score_not_confidence(api_client, stub_ask):
    body = (await api_client.post("/ask", json={"question": "What is the deadline?"})).json()
    assert body["retrieval_score"] == 0.8
    assert "confidence" not in body
    assert body["sources"][0]["chunk_id"] == "c1"


def test_regulatory_context_is_retrieved_once_and_cached(populated_vectorstore):
    from src.rag.retriever import RagRetriever

    retriever = RagRetriever(vectorstore=populated_vectorstore, llm=ScriptedLLM())
    calls = []
    original = retriever.retrieve
    retriever.retrieve = lambda q, top_k=None: calls.append(q) or original(q, top_k=top_k)

    first = retriever.regulatory_context()
    second = retriever.regulatory_context()
    assert first is second
    assert len(calls) == 2  # one retrieval per fixed query, only on the first call
    assert any("Article 87" in c["section"] for c in first)


def test_default_graph_is_compiled_once(monkeypatch):
    from src.agent import graph

    graph.reset_default_graph()
    monkeypatch.setattr(graph, "default_deps", lambda: deps_for(ScriptedLLM()))
    assert graph.get_default_graph() is graph.get_default_graph()
    graph.reset_default_graph()


def test_legacy_seed_rows_are_marked_demo_on_upgrade(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute(OLD_QUERIES_DDL)
        rows = [
            ("2026-10-27 11:50:47", "/ask", 0, 3100.0, "(demo) answer with citations"),  # seed_db
            ("2026-10-27 11:50:47", "/report", 1, 9000.0, "severity=serious"),  # seed_db
            ("2026-10-27 12:31:24", "/evaluate", 0, None, None),  # real (B-05: no latency)
            ("2026-10-27 12:54:16", "/", 0, None, None),  # real, non-business
        ]
        conn.executemany(
            "INSERT INTO queries (timestamp, endpoint, escalated, latency_ms, output_summary) VALUES (?,?,?,?,?)",
            rows,
        )

    repo = Repository(path)
    by_endpoint = {r.endpoint: r.source for r in repo.list_queries()}
    assert by_endpoint == {"/ask": "demo", "/report": "demo", "/evaluate": "live", "/": "live"}

    repo.log_query(endpoint="/ask", latency_ms=5.0)  # a new row without status must stay live
    Repository(path)  # restart: the one-off update does not re-run
    assert [r.source for r in Repository(path).list_queries() if r.latency_ms == 5.0] == ["live"]


async def test_metrics_ignore_non_business_legacy_rows(api_client):
    repo = get_repository()
    repo.log_query(endpoint="/docs", status_code=200, latency_ms=1.0)
    repo.log_query(endpoint="/ask", status_code=200, latency_ms=2.0)
    body = (await api_client.get("/metrics")).json()
    assert body["total_queries"] == 1 and body["queries_last_24h"] == 1


async def test_input_text_is_not_stored_by_default(api_client, override_classify):
    import hashlib

    override_classify(_graph_classifier())
    await api_client.post("/report", json=REPORT)
    (row,) = _rows("/report")
    assert row.input_text is None
    assert row.input_length == len(REPORT["description"])
    assert row.input_sha256 == hashlib.sha256(REPORT["description"].encode()).hexdigest()


async def test_input_text_is_stored_only_when_enabled(api_client, override_classify, monkeypatch):
    monkeypatch.setenv("STORE_INPUT_TEXT", "true")
    get_settings.cache_clear()
    override_classify(_graph_classifier())
    await api_client.post("/report", json=REPORT)
    (row,) = _rows("/report")
    assert row.input_text == REPORT["description"]
