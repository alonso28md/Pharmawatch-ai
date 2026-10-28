"""B-F2 backend: POST /report/stream (real LangGraph node events) and /ask citation context."""

import json

import pytest

from src.agent.graph import run_incident_classification, stream_incident_classification
from src.agent.llm import LLMUnavailableError
from src.api.deps import get_classification_stream_fn, get_repository, limiter
from src.rag.retriever import RagAnswer, Source
from tests.fakes import ScriptedLLM, assessment, deps_for, extraction

TEXT = "The infusion pump over-infused; the patient was admitted to the ICU."


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


def _llm(category="unanticipated_serious_deterioration", **extract):
    return ScriptedLLM(
        extract=extraction(device_class="IIb", **extract), assess=assessment(category)
    )


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def stream_with(api_client):
    from src.api.main import app

    def install(llm_or_fn):
        fn = llm_or_fn
        if isinstance(llm_or_fn, ScriptedLLM):

            def fn(description, **kw):
                return stream_incident_classification(description, deps=deps_for(llm_or_fn), **kw)

        app.dependency_overrides[get_classification_stream_fn] = lambda: fn

    yield install
    app.dependency_overrides.pop(get_classification_stream_fn, None)


def test_stream_yields_the_graph_nodes_in_order_and_the_same_final_state():
    steps, final = [], None
    for kind, value in stream_incident_classification(TEXT, deps=deps_for(_llm())):
        if kind == "step":
            steps.append(value)
        else:
            final = value
    assert steps == [
        "extract_info",
        "classify_device",
        "assess_severity",
        "gate",
        "determine_reporting",
        "generate_report",
        "finalize",
    ]
    reference = run_incident_classification(TEXT, deps=deps_for(_llm()))
    assert {
        k: final[k]
        for k in ("deadline_days", "incident_category", "escalation_level", "processing_steps")
    } == {
        k: reference[k]
        for k in ("deadline_days", "incident_category", "escalation_level", "processing_steps")
    }


async def test_report_stream_emits_real_steps_then_the_result(api_client, stream_with):
    stream_with(_llm())
    response = await api_client.post("/report/stream", json={"description": TEXT})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    kinds = [e for e, _ in events]
    assert kinds[-1] == "result" and kinds[:-1] == ["step"] * (len(kinds) - 1)
    nodes = [d["node"] for e, d in events if e == "step"]
    assert nodes[0] == "extract_info" and nodes[-1] == "finalize"
    assert [d["index"] for e, d in events if e == "step"] == list(range(1, len(nodes) + 1))
    result = events[-1][1]
    assert result["deadline_days"] == 10
    # The streamed result is persisted and logged exactly like POST /report.
    assert get_repository().get_incident(result["incident_id"])["deadline_days"] == 10
    (row,) = [q for q in get_repository().list_queries() if q.endpoint == "/report/stream"]
    assert row.status_code == 200 and row.latency_ms is not None and row.escalation_level == "none"


async def test_escalated_stream_shows_the_escalate_node(api_client, stream_with):
    stream_with(_llm(outcome="unknown", known=False))
    events = _parse_sse((await api_client.post("/report/stream", json={"description": TEXT})).text)
    nodes = [d["node"] for e, d in events if e == "step"]
    assert "escalate" in nodes and "generate_report" not in nodes
    assert events[-1][1]["escalation_level"] == "blocking"


async def test_validation_errors_are_returned_before_streaming(api_client, stream_with):
    stream_with(_llm())
    response = await api_client.post("/report/stream", json={"description": "short"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_model_outage_mid_stream_becomes_an_error_event(api_client, stream_with):
    def failing(description, **kwargs):
        yield "step", "extract_info"
        raise LLMUnavailableError("APITimeoutError")

    stream_with(failing)
    events = _parse_sse((await api_client.post("/report/stream", json={"description": TEXT})).text)
    assert events == [
        ("step", {"node": "extract_info", "index": 1}),
        (
            "error",
            {"code": "llm_unavailable", "message": "The language model is temporarily unavailable"},
        ),
    ]


async def test_ask_returns_labelled_context_and_citation_signal(api_client, monkeypatch):
    context = [
        {
            "label": "C1",
            "chunk_id": "c1",
            "document": "MDR",
            "section": "Article 87",
            "text": "not later than 15 days",
        }
    ]

    class Stub:
        def __init__(self, cited):
            self.cited = cited

        def answer(self, question, **kwargs):
            return RagAnswer(
                "15 days [C1]" if self.cited else "Not in the context.",
                [Source("MDR", "Article 87", "t", 0.8, "c1")],
                0.8,
                1,
                context=context,
                cited_labels=self.cited,
            )

    monkeypatch.setattr("src.api.routes.ask.get_retriever", lambda: Stub(["C1"]))
    body = (await api_client.post("/ask", json={"question": "What is the deadline?"})).json()
    assert body["context"][0]["text"] == "not later than 15 days"
    assert body["cited_labels"] == ["C1"] and body["answered_from_context"] is True

    monkeypatch.setattr("src.api.routes.ask.get_retriever", lambda: Stub([]))
    body = (await api_client.post("/ask", json={"question": "Paracetamol daily dose?"})).json()
    assert body["answered_from_context"] is False


async def test_failed_stream_counts_as_server_error_in_metrics(api_client, stream_with):
    def failing(description, **kwargs):
        raise LLMUnavailableError("down")
        yield  # pragma: no cover

    stream_with(failing)
    await api_client.post("/report/stream", json={"description": TEXT})
    metrics = (await api_client.get("/metrics")).json()
    assert metrics["total_queries"] == 1 and metrics["error_rate"] == 1.0
