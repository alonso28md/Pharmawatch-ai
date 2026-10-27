"""Characterization tests for the critical audit findings.

Each test asserts the CORRECT behaviour and is marked xfail(strict=True) while the
bug exists. When a fix lands the test starts passing, strict mode turns that into a
failure, and the marker must be removed - so a fix can't land silently untested.
"""

import json

import pytest

import src.agent.nodes as nodes
from src.agent.graph import run_incident_classification
from src.agent.tools import reporting_requirements_tool


def _scripted_llm(monkeypatch, responses: list[dict]) -> None:
    """Replace the agent's Claude calls with a fixed sequence of JSON responses."""
    queue = list(responses)
    monkeypatch.setattr(nodes, "call_claude_json", lambda *a, **k: queue.pop(0))
    monkeypatch.setattr(nodes, "rag_query_tool", lambda q: {"answer": "stub", "sources": []})


@pytest.mark.xfail(strict=True, reason="B-01: contradictory-signal guardrail is dropped by LangGraph")
def test_b01_contradictory_description_escalates(monkeypatch):
    _scripted_llm(
        monkeypatch,
        [
            {"device_name": "infusion pump", "device_class": "IIb", "event_type": "injury",
             "patient_outcome": "hospitalized"},
            {"severity": "serious", "confidence": 0.9, "reasoning": "hospitalization"},
            {},
        ],
    )
    final = run_incident_classification(
        "During surgery the pump caused an injury requiring hospitalization; "
        "the ward note says there was no harm to the patient."
    )
    assert final["escalated_to_human"] is True
    assert "contradict" in (final["escalation_reason"] or "").lower()


@pytest.mark.xfail(strict=True, reason="B-02: non-fatal unanticipated serious deterioration gets 15 days")
def test_b02_pacemaker_cardiac_arrest_gets_10_days(monkeypatch):
    _scripted_llm(
        monkeypatch,
        [
            {"device_name": "implanted pacemaker", "device_class": None, "event_type": "malfunction",
             "patient_outcome": "cardiac arrest, resuscitated, ICU admission - unanticipated "
                                "serious deterioration of health"},
            {"severity": "serious", "confidence": 0.97, "reasoning": "Art. 2(65)(b)"},
            {"incident_date": None},
        ],
    )
    final = run_incident_classification(
        "An implanted cardiac pacemaker unexpectedly stopped pacing; the patient suffered "
        "cardiac arrest, was resuscitated and transferred to the ICU."
    )
    assert final["deadline_days"] == 10


@pytest.mark.xfail(strict=True, reason="B-02: 'deceased' is missing from the 10-day trigger terms")
def test_b02_deceased_outcome_gets_10_days():
    result = reporting_requirements_tool("serious", "malfunction", "III", "patient deceased")
    assert result["deadline_days"] == 10


@pytest.mark.xfail(strict=True, reason="B-03: an 'unknown' outcome string bypasses the missing-info guardrail")
def test_b03_unknown_outcome_escalates_instead_of_not_reportable(monkeypatch):
    _scripted_llm(
        monkeypatch,
        [
            {"device_name": "monitor", "device_class": None, "event_type": "possible malfunction",
             "patient_outcome": "unknown; nurse unsure whether any patient was affected"},
            {"severity": "non-serious", "confidence": 0.7, "reasoning": "vague report"},
        ],
    )
    final = run_incident_classification(
        "A nurse mentioned that something seemed off with a monitor during a shift, but was "
        "unsure whether it affected any reading or had any effect on the patient."
    )
    assert final["escalated_to_human"] is True
    assert final["reportable"] is None


class _StubRetriever:
    def answer(self, question):
        from src.rag.retriever import RagAnswer, Source

        return RagAnswer("stub", [Source("D", "S", "t", 0.9)], 0.9, 1)

    def count_indexed_chunks(self):
        return 1


@pytest.mark.xfail(strict=True, reason="B-05: TimingMiddleware runs outside LoggingMiddleware")
async def test_b05_query_log_records_latency(api_client, monkeypatch):
    from src.api.deps import get_repository

    monkeypatch.setattr("src.api.routes.ask.get_retriever", lambda: _StubRetriever())
    response = await api_client.post("/ask", json={"question": "What is the reporting deadline?"})
    assert response.status_code == 200
    rows = [r for r in get_repository().list_queries() if r.endpoint == "/ask"]
    assert rows and rows[0].latency_ms is not None


@pytest.mark.xfail(strict=True, reason="B-06: failed requests are never written to the query log")
async def test_b06_server_error_is_logged(api_client, monkeypatch):
    from src.api.deps import get_repository

    def boom(*args, **kwargs):
        raise RuntimeError("simulated LLM outage")

    monkeypatch.setattr("src.api.routes.report.run_incident_classification", boom)
    response = await api_client.post(
        "/report", json={"description": "A ventilator stopped and the patient died overnight."}
    )
    assert response.status_code >= 500
    rows = [r for r in get_repository().list_queries() if r.endpoint == "/report"]
    assert rows and rows[0].error


@pytest.mark.xfail(strict=True, reason="B-07: /evaluate accepts arbitrary filesystem paths")
async def test_b07_evaluate_rejects_arbitrary_dataset_path(api_client, monkeypatch, tmp_path):
    import src.api.routes.evaluate as evaluate_route

    # Redirect any report write away from the real docs/ while the bug still exists.
    fake_root = tmp_path / "fake_root"
    (fake_root / "docs").mkdir(parents=True)
    monkeypatch.setattr(evaluate_route, "PROJECT_ROOT", fake_root)

    dataset = tmp_path / "outside.json"
    dataset.write_text(json.dumps({"cases": []}), encoding="utf-8")
    response = await api_client.post("/evaluate", json={"dataset": str(dataset)})

    assert response.status_code == 422
    assert not (fake_root / "docs" / "evaluation_report.md").exists()
