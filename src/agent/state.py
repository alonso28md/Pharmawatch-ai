"""Shared state passed between LangGraph nodes of the incident-classification agent."""

from typing import Literal, TypedDict


class IncidentState(TypedDict):
    """State object threaded through the incident-classification graph."""

    # Input
    description: str

    # Optional input hints
    device_name_hint: str | None
    device_class_hint: Literal["I", "IIa", "IIb", "III"] | None

    # Extracted info
    device_name: str | None
    device_class: Literal["I", "IIa", "IIb", "III"] | None
    event_type: str | None
    patient_outcome: str | None

    # Assessment
    severity: Literal["serious", "non-serious"] | None
    severity_confidence: float | None
    severity_reasoning: str | None

    # Reporting decision
    reportable: bool | None
    report_to: list[str] | None
    deadline_days: int | None
    classification_rule: str | None

    # Draft notification (generate_report)
    draft_notification: dict | None

    # Guardrails
    escalated_to_human: bool
    escalation_reason: str | None

    # RAG context used
    rag_sources: list[dict] | None

    # Metadata
    processing_steps: list[str]
    errors: list[str]
