"""Escalation and output-validation guardrails for the incident-classification agent.

Escalation is driven by explicit criteria first (unknown outcome, contradiction,
category doubt, missing critical data, unparseable model output); the model's
self-reported confidence is only one additional criterion (B-11).
"""

import logging

from src.agent.regulatory import (
    INCIDENT_CATEGORIES,
    SERIOUS_CATEGORIES,
    mentions_death,
    mentions_death_or_life_threat,
    same_determination,
)
from src.agent.state import IncidentState

logger = logging.getLogger(__name__)

CONFIDENCE_ESCALATION_THRESHOLD = 0.7
VALID_SEVERITIES = {"serious", "non-serious"}
VALID_DEADLINES = {2, 10, 15}

REASON_UNKNOWN_OUTCOME = (
    "The patient outcome is unknown or not documented; requesting more information "
    "instead of guessing."
)
REASON_MISSING_DEVICE = "The device involved could not be identified from the description."
REASON_CONTRADICTION = (
    "The description contains contradictory severity signals (serious wording alongside a "
    "no-harm statement); escalating instead of guessing."
)
REASON_UNKNOWN_CATEGORY = "The incident category could not be determined."
REASON_LOW_CONFIDENCE = (
    "Severity assessment confidence is below 0.7; recommend review by a vigilance specialist."
)
REASON_DEATH_CONFLICT = (
    "The description mentions a death but the assessed category is not death-related; "
    "escalating the conflict."
)
REASON_PARSE_FAILURE = "A model response could not be parsed into the required structure."
ADVISORY_DEATH = (
    "Death or life-threatening outcome detected: flagged for immediate specialist review in "
    "addition to the automated determination."
)
ADVISORY_DEVICE_CLASS = (
    "The device's MDR class could not be determined (not stated and no Annex VIII rule "
    "matched); the reporting deadline does not depend on it, but the class needs manual review."
)


def is_low_confidence(confidence: float | None) -> bool:
    return confidence is None or confidence < CONFIDENCE_ESCALATION_THRESHOLD


def blocking_reasons(state: IncidentState) -> list[str]:
    """Reasons that withhold the automated reporting determination entirely."""
    reasons: list[str] = []
    category = state.get("incident_category")
    alternative = state.get("alternative_category")
    signal = state.get("severity_signal") or {}

    if any("parse" in e for e in state.get("errors", [])):
        reasons.append(REASON_PARSE_FAILURE)
    if not state.get("outcome_known") or not (state.get("patient_outcome") or "").strip():
        reasons.append(REASON_UNKNOWN_OUTCOME)
    if not (state.get("device_name") or "").strip():
        reasons.append(REASON_MISSING_DEVICE)
    if category in (None, "unknown"):
        reasons.append(REASON_UNKNOWN_CATEGORY)
    elif alternative and alternative != category and not same_determination(category, alternative):
        reasons.append(
            f"The incident could be '{category}' or '{alternative}', which lead to different "
            "reporting obligations; escalating the category doubt."
        )
    if signal.get("contradictory_signals"):
        reasons.append(REASON_CONTRADICTION)
    # Only the extracted *actual* outcome is checked: the narrative may legitimately say
    # "could have died" for a potential (other_serious) incident.
    if category not in (None, "unknown", "death", "public_health_threat") and mentions_death(
        state.get("patient_outcome") or ""
    ):
        reasons.append(REASON_DEATH_CONFLICT)
    if is_low_confidence(state.get("severity_confidence")):
        reasons.append(REASON_LOW_CONFIDENCE)
    return reasons


def advisory_reasons(state: IncidentState) -> list[str]:
    """Reasons that keep the determination but flag it for specialist review."""
    reasons: list[str] = []
    text = f"{state.get('event_type') or ''} {state.get('patient_outcome') or ''}"
    if state.get("incident_category") == "death" or mentions_death_or_life_threat(text):
        reasons.append(ADVISORY_DEATH)
    if not state.get("device_class"):
        reasons.append(ADVISORY_DEVICE_CLASS)
    return reasons


def validate_output(state: IncidentState) -> list[str]:
    """Guardrail 5: internal-consistency checks on the final state before it is returned."""
    errors: list[str] = []
    severity = state.get("severity")
    category = state.get("incident_category")
    blocking = state.get("escalation_level") == "blocking"

    if severity is not None and severity not in VALID_SEVERITIES:
        errors.append(f"Invalid severity value: {severity!r}")
    if category is not None and category not in INCIDENT_CATEGORIES:
        errors.append(f"Invalid incident category: {category!r}")
    if severity is not None and category not in (None, "unknown"):
        expected = "serious" if category in SERIOUS_CATEGORIES else "non-serious"
        if severity != expected:
            errors.append(f"severity {severity!r} is inconsistent with category {category!r}")

    if blocking:
        if state.get("reportable") is not None or state.get("deadline_days") is not None:
            errors.append("a blocked (escalated) case must not carry a reporting determination")
        return errors

    deadline_days = state.get("deadline_days")
    if deadline_days is not None and deadline_days not in VALID_DEADLINES:
        errors.append(f"Invalid deadline_days value: {deadline_days!r}")
    if state.get("reportable") is None:
        errors.append("reportable is missing on a non-escalated case")
    if state.get("reportable") and (not state.get("report_to") or deadline_days is None):
        errors.append("reportable=True but report_to or deadline_days is empty")
    if state.get("reportable") is False and deadline_days is not None:
        errors.append("reportable=False but a deadline is set")
    if not state.get("severity_reasoning"):
        errors.append("severity_reasoning is empty")
    return errors
