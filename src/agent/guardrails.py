"""Escalation and output-validation guardrails for the incident-classification agent."""

import logging

from src.agent.state import IncidentState

logger = logging.getLogger(__name__)

CONFIDENCE_ESCALATION_THRESHOLD = 0.7
VALID_SEVERITIES = {"serious", "non-serious"}
VALID_DEADLINES = {2, 10, 15, 30}

DEATH_LIFE_THREATENING_TERMS = ("death", "died", "fatal", "life-threatening", "life threatening")


def is_low_confidence(severity_confidence: float | None) -> bool:
    """Guardrail 1: escalate when the severity assessment is not clear enough."""
    return severity_confidence is None or severity_confidence < CONFIDENCE_ESCALATION_THRESHOLD


def is_death_or_life_threatening(event_type: str | None, patient_outcome: str | None) -> bool:
    """Guardrail 2: death/life-threatening cases always get flagged for human review."""
    text = f"{event_type or ''} {patient_outcome or ''}".lower()
    return any(term in text for term in DEATH_LIFE_THREATENING_TERMS)


def has_contradictory_info(severity_tool_result: dict) -> bool:
    """Guardrail 3: escalate when the description mixes serious and non-serious signals."""
    return bool(severity_tool_result.get("contradictory_signals"))


def has_missing_critical_info(device_name: str | None, patient_outcome: str | None) -> bool:
    """Guardrail 4: escalate when essential fields could not be extracted."""
    return not device_name or not patient_outcome


def determine_escalation(state: IncidentState, severity_tool_result: dict) -> tuple[bool, str | None]:
    """Combine guardrails 1, 3 and 4 into a single escalate/continue decision.

    Guardrail 2 (death/life-threatening) is handled separately: it does not block
    the normal reporting determination (the incident must still get a deadline and
    a report_to list), but it does flag `escalated_to_human` for an additional,
    immediate specialist review alongside the automated determination.
    """
    reasons = []

    if is_low_confidence(state.get("severity_confidence")):
        reasons.append(
            "Severity classification confidence is below 0.7; recommend review by a "
            "pharmacovigilance specialist."
        )

    if has_contradictory_info(severity_tool_result):
        reasons.append(
            "The incident description contains contradictory severity signals; "
            "escalating instead of guessing."
        )

    if has_missing_critical_info(state.get("device_name"), state.get("patient_outcome")):
        reasons.append(
            "Essential information (device type and/or patient outcome) could not be "
            "extracted from the description; requesting more information instead of "
            "guessing."
        )

    if reasons:
        return True, " ".join(reasons)
    return False, None


def validate_output(state: IncidentState) -> list[str]:
    """Guardrail 5: validate the final state before returning it to the caller."""
    errors: list[str] = []

    severity = state.get("severity")
    if severity is not None and severity not in VALID_SEVERITIES:
        errors.append(f"Invalid severity value: {severity!r}")

    deadline_days = state.get("deadline_days")
    if deadline_days is not None and deadline_days not in VALID_DEADLINES:
        errors.append(f"Invalid deadline_days value: {deadline_days!r}")

    if state.get("reportable") and not state.get("report_to"):
        errors.append("reportable=True but report_to is empty")

    if not state.get("escalated_to_human") and severity is not None:
        if not state.get("severity_reasoning"):
            errors.append("severity_reasoning is empty")

    return errors
