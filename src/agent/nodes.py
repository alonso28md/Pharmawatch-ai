"""LangGraph node implementations for the incident-classification agent."""

import logging

from src.agent.guardrails import determine_escalation, is_death_or_life_threatening
from src.agent.llm import call_claude_json
from src.agent.state import IncidentState
from src.agent.tools import (
    classification_rules_tool,
    rag_query_tool,
    reporting_requirements_tool,
    severity_criteria_tool,
)

logger = logging.getLogger(__name__)

VALID_DEVICE_CLASSES = {"I", "IIa", "IIb", "III"}


def extract_info(state: IncidentState) -> dict:
    """Extract device name, device class, event type and patient outcome from free text."""
    system = (
        "You extract structured facts from a medical device adverse event description. "
        "Respond with ONLY a JSON object, no prose, with exactly these keys: "
        '"device_name" (string or null), '
        '"device_class" (one of "I", "IIa", "IIb", "III", or null if not stated), '
        '"event_type" (short phrase, e.g. "malfunction", "injury", "death", "near-miss", '
        '"overdose", "incorrect dose"), '
        '"patient_outcome" (a short phrase - ALWAYS fill this with your best summary of the '
        "patient impact. If the description explicitly states no patient was involved or no "
        'harm occurred, write that explicitly (e.g. "no patient involved, no clinical '
        'impact") - do NOT return null in that case, since "no impact" is a known outcome, '
        "not missing information. Only return null if the description truly gives no "
        "indication either way of what happened to any patient.)"
    )
    user = f"INCIDENT DESCRIPTION:\n{state['description']}"

    extracted = call_claude_json(system, user)

    device_name = state.get("device_name_hint") or extracted.get("device_name")
    device_class = state.get("device_class_hint") or extracted.get("device_class")
    if device_class not in VALID_DEVICE_CLASSES:
        device_class = None

    processing_steps = [*state.get("processing_steps", []), "extract_info"]
    errors = list(state.get("errors", []))
    if not extracted:
        errors.append("extract_info: Claude response could not be parsed as JSON")

    return {
        "device_name": device_name,
        "device_class": device_class,
        "event_type": extracted.get("event_type"),
        "patient_outcome": extracted.get("patient_outcome"),
        "processing_steps": processing_steps,
        "errors": errors,
    }


def classify_device(state: IncidentState) -> dict:
    """Determine the MDR Annex VIII risk class for the device."""
    processing_steps = [*state.get("processing_steps", []), "classify_device"]

    if state.get("device_class"):
        return {
            "device_class": state["device_class"],
            "classification_rule": "Provided by caller / extracted directly from description",
            "processing_steps": processing_steps,
        }

    result = classification_rules_tool(state["description"])
    return {
        "device_class": result["class"],
        "classification_rule": f"{result['rule']}: {result['reasoning']}",
        "processing_steps": processing_steps,
    }


def assess_severity(state: IncidentState) -> dict:
    """Assess whether the incident is a 'serious incident' under MDR Art. 2(65)."""
    processing_steps = [*state.get("processing_steps", []), "assess_severity"]

    severity_tool_result = severity_criteria_tool(
        state["description"], state.get("patient_outcome") or ""
    )
    rag_result = rag_query_tool(
        "What qualifies as a serious incident under MDR Article 2(65), and what are the "
        "reporting deadlines?"
    )

    system = (
        "You are a pharmacovigilance specialist assessing whether a medical device "
        "adverse event is a 'serious incident' under MDR Article 2(65). "
        "You are given a rule-based signal and regulatory context; weigh them against "
        "the incident description and produce your own judgement. "
        "Respond with ONLY a JSON object with exactly these keys: "
        '"severity" ("serious" or "non-serious"), '
        '"confidence" (float 0.0-1.0), '
        '"reasoning" (1-3 sentences citing the relevant MDR criterion).'
    )
    user = (
        f"INCIDENT DESCRIPTION:\n{state['description']}\n\n"
        f"PATIENT OUTCOME: {state.get('patient_outcome')}\n\n"
        f"RULE-BASED SIGNAL: {severity_tool_result}\n\n"
        f"REGULATORY CONTEXT:\n{rag_result['answer']}"
    )

    assessment = call_claude_json(system, user)

    severity = assessment.get("severity")
    if severity not in {"serious", "non-serious"}:
        severity = "serious" if severity_tool_result["serious"] else "non-serious"

    try:
        confidence = float(assessment.get("confidence"))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError
    except (TypeError, ValueError):
        confidence = severity_tool_result["confidence"]

    reasoning = assessment.get("reasoning") or (
        f"Rule-based assessment: criteria met = {severity_tool_result['criteria_met']}."
    )

    return {
        "severity": severity,
        "severity_confidence": round(confidence, 4),
        "severity_reasoning": reasoning,
        "rag_sources": rag_result["sources"],
        "processing_steps": processing_steps,
        "_severity_tool_result": severity_tool_result,  # consumed by the graph's router
    }


def determine_reporting(state: IncidentState) -> dict:
    """Determine report recipients, deadline, and whether the incident is reportable."""
    processing_steps = [*state.get("processing_steps", []), "determine_reporting"]

    result = reporting_requirements_tool(
        severity=state.get("severity"),
        event_type=state.get("event_type"),
        device_class=state.get("device_class"),
        patient_outcome=state.get("patient_outcome"),
    )

    escalated = state.get("escalated_to_human", False)
    escalation_reason = state.get("escalation_reason")
    if is_death_or_life_threatening(state.get("event_type"), state.get("patient_outcome")):
        escalated = True
        note = (
            "Death or life-threatening outcome detected: flagged for immediate "
            "specialist review in addition to the automated determination."
        )
        escalation_reason = f"{escalation_reason} {note}".strip() if escalation_reason else note

    return {
        "reportable": result["reportable"],
        "report_to": result["report_to"],
        "deadline_days": result["deadline_days"],
        "escalated_to_human": escalated,
        "escalation_reason": escalation_reason,
        "processing_steps": processing_steps,
    }


def generate_report(state: IncidentState) -> dict:
    """Draft the notification fields for a reportable incident."""
    processing_steps = [*state.get("processing_steps", []), "generate_report"]

    if not state.get("reportable"):
        return {"draft_notification": None, "processing_steps": processing_steps}

    system = (
        "You draft a medical device incident notification for submission to a "
        "competent authority. Respond with ONLY a JSON object with exactly these keys: "
        '"incident_date" (null - unknown, to be filled by the reporter), '
        '"reporter_type" (e.g. "healthcare_professional"), '
        '"device_identification" (string), '
        '"event_description" (1-2 sentence summary), '
        '"patient_outcome" (short phrase), '
        '"corrective_action" (short phrase, or "Pending investigation" if unknown).'
    )
    user = (
        f"INCIDENT DESCRIPTION:\n{state['description']}\n\n"
        f"DEVICE NAME: {state.get('device_name')}\n"
        f"DEVICE CLASS: {state.get('device_class')}\n"
        f"SEVERITY: {state.get('severity')}\n"
        f"PATIENT OUTCOME: {state.get('patient_outcome')}"
    )

    draft = call_claude_json(system, user)
    if not draft:
        draft = {
            "incident_date": None,
            "reporter_type": "healthcare_professional",
            "device_identification": state.get("device_name") or "Unknown device",
            "event_description": state["description"][:300],
            "patient_outcome": state.get("patient_outcome"),
            "corrective_action": "Pending investigation",
        }

    return {"draft_notification": draft, "processing_steps": processing_steps}


def escalate(state: IncidentState) -> dict:
    """Terminal node for cases that cannot be safely auto-determined."""
    processing_steps = [*state.get("processing_steps", []), "escalate"]
    severity_tool_result = state.get("_severity_tool_result", {})

    escalated, reason = determine_escalation(state, severity_tool_result)

    return {
        "escalated_to_human": True,
        "escalation_reason": reason or "Escalated for human review.",
        "reportable": None,
        "report_to": None,
        "deadline_days": None,
        "draft_notification": None,
        "processing_steps": processing_steps,
    }
