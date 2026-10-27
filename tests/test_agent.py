"""Tests for the LangGraph incident-classification agent (live Claude calls)."""

from src.agent import guardrails
from src.agent.graph import run_incident_classification
from src.agent.tools import (
    classification_rules_tool,
    reporting_requirements_tool,
    severity_criteria_tool,
)
from tests.conftest import requires_api_key

# --- Pure-function tool/guardrail tests (no API key required) -------------------


def test_classification_rules_tool_matches_breast_implant():
    result = classification_rules_tool("silicone breast implant for reconstruction")
    assert result["class"] == "III"
    assert result["matched"]


def test_classification_rules_tool_defaults_to_class_i_when_unmatched():
    result = classification_rules_tool("a completely generic unspecified item")
    assert result["class"] == "I"
    assert result["matched"] is False


def test_severity_criteria_tool_flags_death():
    result = severity_criteria_tool("the patient died after device failure", "deceased")
    assert result["serious"] is True
    assert "death" in result["criteria_met"]


def test_severity_criteria_tool_flags_non_serious():
    result = severity_criteria_tool("minor cosmetic scratch, no harm, no injury", "no clinical impact")
    assert result["serious"] is False


def test_reporting_requirements_tool_death_gets_10_day_deadline():
    result = reporting_requirements_tool(
        severity="serious", event_type="malfunction", device_class="III", patient_outcome="patient died"
    )
    assert result["deadline_days"] == 10
    assert result["reportable"] is True


def test_reporting_requirements_tool_other_serious_gets_15_day_deadline():
    result = reporting_requirements_tool(
        severity="serious",
        event_type="injury",
        device_class="IIb",
        patient_outcome="hospitalized for observation",
    )
    assert result["deadline_days"] == 15


def test_reporting_requirements_tool_non_serious_not_reportable():
    result = reporting_requirements_tool(
        severity="non-serious", event_type="malfunction", device_class="I", patient_outcome="no harm"
    )
    assert result["reportable"] is False
    assert result["report_to"] == []


def test_guardrail_low_confidence_triggers_escalation():
    assert guardrails.is_low_confidence(0.5) is True
    assert guardrails.is_low_confidence(0.85) is False


def test_guardrail_missing_info_triggers_escalation():
    assert guardrails.has_missing_critical_info(None, None) is True
    assert guardrails.has_missing_critical_info("infusion pump", "nausea") is False


def test_guardrail_output_validation_catches_invalid_severity():
    bad_state = {"severity": "catastrophic", "escalated_to_human": False, "severity_reasoning": "x"}
    errors = guardrails.validate_output(bad_state)
    assert any("severity" in e for e in errors)


# --- Full graph tests (require ANTHROPIC_API_KEY) --------------------------------


@requires_api_key
def test_agent_clearly_serious_case_is_reportable_and_not_escalated():
    description = (
        "A patient required emergency surgical intervention after a hip joint "
        "replacement implant loosened and caused significant internal bleeding. "
        "The implant is a Class III device."
    )
    result = run_incident_classification(description)

    assert result["severity"] == "serious"
    assert result["reportable"] is True
    assert result["deadline_days"] in {10, 15}
    assert result["report_to"]
    assert result["severity_confidence"] >= 0.7
    assert "escalate" not in result["processing_steps"]


@requires_api_key
def test_agent_clearly_minor_case_is_non_serious_and_not_reportable():
    description = (
        "A nurse noticed that a disposable syringe plunger was slightly stiff to push "
        "during a routine injection. No incorrect dose was delivered, the patient "
        "experienced no harm, and the syringe was discarded with no clinical impact."
    )
    result = run_incident_classification(description)

    assert result["severity"] == "non-serious"
    assert result["reportable"] is False
    assert result["escalated_to_human"] is False


@requires_api_key
def test_agent_ambiguous_case_with_missing_info_escalates():
    description = (
        "A report was filed describing a possible issue with equipment used during a "
        "procedure, but no further details about the device or the patient outcome "
        "were provided."
    )
    result = run_incident_classification(description)

    assert result["escalated_to_human"] is True
    assert result["escalation_reason"]
    assert result["reportable"] is None
    assert "escalate" in result["processing_steps"]


@requires_api_key
def test_agent_output_passes_validation_guardrail():
    description = (
        "During a routine MRI scan, the contrast injector malfunctioned and delivered "
        "3x the programmed dose of gadolinium. The patient experienced nausea and was "
        "kept for observation for 24 hours."
    )
    result = run_incident_classification(description)
    errors = guardrails.validate_output(result)
    assert errors == []
