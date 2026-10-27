"""Shared state passed between LangGraph nodes of the incident-classification agent.

Every key a node returns MUST be declared here: LangGraph silently drops undeclared
keys from node updates (that is how the contradiction guardrail was lost - B-01).
"""

from typing import Literal, TypedDict

DeviceClass = Literal["I", "IIa", "IIb", "III"]
DeviceClassSource = Literal["caller", "extracted", "rule"]
EscalationLevel = Literal["none", "advisory", "blocking"]


class IncidentState(TypedDict):
    """State object threaded through the incident-classification graph."""

    # Input (already sanitized by the API layer)
    description: str
    device_name_hint: str | None
    device_class_hint: DeviceClass | None

    # Extraction
    device_name: str | None
    device_type: str | None
    device_class: DeviceClass | None
    device_class_source: DeviceClassSource | None
    classification_rule: str | None
    event_type: str | None
    patient_outcome: str | None
    outcome_known: bool | None

    # Assessment
    severity_signal: dict | None  # auxiliary keyword cross-check (regulatory.severity_signal)
    incident_category: str | None
    alternative_category: str | None
    severity: Literal["serious", "non-serious"] | None
    severity_confidence: float | None
    severity_reasoning: str | None
    rag_sources: list[dict] | None

    # Reporting decision
    reportable: bool | None
    report_to: list[str] | None
    deadline_days: int | None
    deadline_rule: str | None

    # Independent review (optional reviewer node)
    review: dict | None

    # Draft notification
    draft_notification: dict | None

    # Escalation. "blocking" withholds the reporting determination; "advisory" keeps it
    # but flags it for specialist review (e.g. death, undetermined device class).
    blocking_reasons: list[str]
    advisory_reasons: list[str]
    escalated_to_human: bool
    escalation_level: EscalationLevel
    escalation_reason: str | None

    # Metadata
    processing_steps: list[str]
    errors: list[str]
