"""Characterization tests for the critical audit findings.

Each test asserts the CORRECT behaviour and is marked xfail(strict=True) while the
bug exists. When a fix lands the test starts passing, strict mode turns that into a
failure, and the marker must be removed - so a fix can't land silently untested.
"""

import json

from src.agent.graph import run_incident_classification
from tests.fakes import ScriptedLLM, assessment, deps_for, extraction


def test_b01_contradictory_description_escalates():
    llm = ScriptedLLM(
        extract=extraction(device="infusion pump", outcome="hospitalized", device_class="IIb"),
        assess=assessment("unanticipated_serious_deterioration", confidence=0.9),
    )
    final = run_incident_classification(
        "During surgery the pump caused an injury requiring hospitalization; "
        "the ward note says there was no harm to the patient.",
        deps=deps_for(llm),
    )
    assert final["escalated_to_human"] is True
    assert final["reportable"] is None
    assert "contradict" in (final["escalation_reason"] or "").lower()


def test_b02_pacemaker_cardiac_arrest_gets_10_days():
    llm = ScriptedLLM(
        extract=extraction(device="implanted cardiac pacemaker", device_type="pacemaker",
                           outcome="cardiac arrest, resuscitated, transferred to ICU"),
        assess=assessment("unanticipated_serious_deterioration", confidence=0.97),
    )
    final = run_incident_classification(
        "An implanted cardiac pacemaker unexpectedly stopped pacing; the patient suffered "
        "cardiac arrest, was resuscitated and transferred to the ICU.",
        deps=deps_for(llm),
    )
    assert final["deadline_days"] == 10
    assert final["reportable"] is True


def test_b02_deceased_outcome_gets_10_days():
    """A 'deceased' outcome must either get the 10-day deadline or be escalated - never 15 days."""
    for category in ("death", "other_serious"):
        llm = ScriptedLLM(
            extract=extraction(device="ventilator", outcome="patient deceased"),
            assess=assessment(category, confidence=0.95),
        )
        final = run_incident_classification(
            "The ventilator stopped delivering breaths; the patient was deceased when staff arrived.",
            deps=deps_for(llm),
        )
        assert final["deadline_days"] in (10, None)
        assert final["deadline_days"] == 10 or final["escalation_level"] == "blocking"


def test_b03_unknown_outcome_escalates_instead_of_not_reportable():
    llm = ScriptedLLM(
        extract=extraction(device="monitor", outcome="unknown; nurse unsure whether any patient was affected",
                           known=False, event="possible malfunction"),
        assess=assessment("non_serious", confidence=0.7),
    )
    final = run_incident_classification(
        "A nurse mentioned that something seemed off with a monitor during a shift, but was "
        "unsure whether it affected any reading or had any effect on the patient.",
        deps=deps_for(llm),
    )
    assert final["escalated_to_human"] is True
    assert final["reportable"] is None


class _StubRetriever:
    def answer(self, question, **kwargs):
        from src.rag.retriever import RagAnswer, Source

        return RagAnswer("stub", [Source("D", "S", "t", 0.9)], 0.9, 1)

    def count_indexed_chunks(self):
        return 1


async def test_b05_query_log_records_latency(api_client, monkeypatch):
    from src.api.deps import get_repository

    monkeypatch.setattr("src.api.routes.ask.get_retriever", lambda: _StubRetriever())
    response = await api_client.post("/ask", json={"question": "What is the reporting deadline?"})
    assert response.status_code == 200
    rows = [r for r in get_repository().list_queries() if r.endpoint == "/ask"]
    assert rows and rows[0].latency_ms is not None


async def test_b06_server_error_is_logged(api_client):
    from src.api.deps import get_classification_fn, get_repository
    from src.api.main import app

    def boom(*args, **kwargs):
        raise RuntimeError("simulated unexpected failure")

    app.dependency_overrides[get_classification_fn] = lambda: boom
    try:
        response = await api_client.post(
            "/report", json={"description": "A ventilator stopped and the patient died overnight."}
        )
    finally:
        app.dependency_overrides.pop(get_classification_fn, None)

    assert response.status_code >= 500
    rows = [r for r in get_repository().list_queries() if r.endpoint == "/report"]
    assert rows and rows[0].error


async def test_b07_evaluate_rejects_arbitrary_dataset_path(api_client, monkeypatch, tmp_path):
    from src.config import PROJECT_ROOT, get_settings

    # An authorized caller: the bug was that even a legitimate key could point
    # the harness at any file on disk and overwrite the tracked docs/ reports.
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    docs_before = {p: p.stat().st_mtime_ns for p in (PROJECT_ROOT / "docs").rglob("*") if p.is_file()}

    dataset = tmp_path / "outside.json"
    dataset.write_text(json.dumps({"cases": []}), encoding="utf-8")
    response = await api_client.post(
        "/evaluate", json={"dataset": str(dataset)}, headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 422
    assert {p: p.stat().st_mtime_ns for p in (PROJECT_ROOT / "docs").rglob("*") if p.is_file()} == docs_before
