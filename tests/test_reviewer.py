"""Phase 7: the optional independent reviewer node (scripted LLMs, no network)."""

import pytest

from src.agent.graph import run_incident_classification
from src.agent.llm import LLMOutputError
from tests.fakes import REGULATORY_CHUNK, ScriptedLLM, assessment, deps_for, extraction, review

TEXT = "The pacemaker stopped pacing; the patient had a cardiac arrest and was admitted to the ICU."


def _llm(review_response, category="unanticipated_serious_deterioration", confidence=0.93):
    return ScriptedLLM(
        extract=extraction(
            device="pacemaker", device_type="pacemaker", outcome="cardiac arrest, ICU"
        ),
        assess=assessment(category, confidence=confidence),
        review=review_response,
    )


def test_agree_keeps_the_determination():
    llm = _llm(review("agree"))
    final = run_incident_classification(TEXT, deps=deps_for(llm, reviewer=True))
    assert final["deadline_days"] == 10
    assert final["escalation_level"] != "blocking"
    assert final["review"]["verdict"] == "agree"
    assert llm.stages() == ["extract", "assess", "review", "draft"]


@pytest.mark.parametrize("verdict", ["disagree", "uncertain"])
def test_disagree_or_uncertain_escalates_without_overriding(verdict):
    evidence = [
        {"chunk_id": REGULATORY_CHUNK["chunk_id"], "quote": "not later than 10 days"},
        {"chunk_id": "invented::chunk", "quote": "made up"},
    ]
    llm = _llm(
        review(
            verdict,
            issues=["deadline should be 15"],
            category="other_serious",
            deadline=15,
            evidence=evidence,
        )
    )
    final = run_incident_classification(TEXT, deps=deps_for(llm, reviewer=True))

    assert final["escalation_level"] == "blocking"
    assert final["reportable"] is None and final["deadline_days"] is None
    assert f"Independent review {verdict}" in final["escalation_reason"]
    # The reviewer's suggestion is recorded, not applied; the principal decision is preserved.
    assert final["review"]["principal_decision"]["deadline_days"] == 10
    assert final["review"]["suggested_deadline_days"] == 15
    assert [e["chunk_id"] for e in final["review"]["evidence"]] == [REGULATORY_CHUNK["chunk_id"]]
    assert "draft" not in llm.stages()


def test_unparseable_review_escalates_and_is_recorded():
    llm = _llm(LLMOutputError("bad json"))
    final = run_incident_classification(TEXT, deps=deps_for(llm, reviewer=True))
    assert final["escalation_level"] == "blocking"
    assert final["review"]["verdict"] == "uncertain"
    assert any(e.startswith("review:") for e in final["errors"])


def test_reviewer_does_not_see_the_principal_confidence():
    llm = _llm(review("agree"), confidence=0.8731)
    run_incident_classification(TEXT, deps=deps_for(llm, reviewer=True))
    (_, _, user) = next(call for call in llm.calls if call[0] == "review")
    assert "0.8731" not in user and "confidence" not in user
    assert "<incident_description>" in user and REGULATORY_CHUNK["chunk_id"] in user


def test_reviewer_is_skipped_when_disabled_or_already_blocked():
    disabled = _llm(review("disagree"))
    run_incident_classification(TEXT, deps=deps_for(disabled, reviewer=False))
    assert "review" not in disabled.stages()

    blocked = _llm(review("agree"), category="unknown")
    final = run_incident_classification(TEXT, deps=deps_for(blocked, reviewer=True))
    assert "review" not in blocked.stages()
    assert final["review"] is None


def test_separate_reviewer_model_is_used_and_metered():
    principal = _llm(None)
    reviewer = ScriptedLLM(review=review("agree"))
    final = run_incident_classification(
        TEXT, deps=deps_for(principal, reviewer=True, reviewer_llm=reviewer)
    )
    assert "review" not in principal.stages() and reviewer.stages() == ["review"]
    assert final["review"]["usage"] == {"input_tokens": 10, "output_tokens": 5}
    assert final["review"]["latency_ms"] >= 0


@pytest.mark.parametrize(("flag", "has_review"), [("true", True), ("false", False)])
def test_reviewer_enabled_setting_controls_the_production_graph(monkeypatch, flag, has_review):
    from src.agent import graph
    from src.config import get_settings

    monkeypatch.setenv("REVIEWER_ENABLED", flag)
    monkeypatch.setattr(graph, "get_llm_client", lambda: ScriptedLLM())  # no global client created
    get_settings.cache_clear()
    try:
        deps = graph.default_deps()
        assert deps.reviewer_enabled is has_review
        assert ("review" in graph.build_graph(deps).get_graph().nodes) is has_review
    finally:
        get_settings.cache_clear()
