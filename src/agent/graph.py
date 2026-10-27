"""LangGraph definition for the incident-classification agent.

Topology: extract_info -> classify_device -> assess_severity ->
  [escalate if confidence < 0.7 / contradictory / missing info] -> END
  [determine_reporting -> generate_report] -> END
"""

import logging

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.guardrails import determine_escalation
from src.agent.nodes import (
    assess_severity,
    classify_device,
    determine_reporting,
    escalate,
    extract_info,
    generate_report,
)
from src.agent.state import IncidentState

logger = logging.getLogger(__name__)


def _route_after_severity(state: IncidentState) -> str:
    """Guardrails 1, 3, 4: decide whether to escalate instead of auto-determining."""
    severity_tool_result = state.get("_severity_tool_result", {})
    needs_escalation, _ = determine_escalation(state, severity_tool_result)
    return "escalate" if needs_escalation else "determine_reporting"


def build_graph() -> CompiledStateGraph:
    """Build and compile the incident-classification StateGraph."""
    graph = StateGraph(IncidentState)

    graph.add_node("extract_info", extract_info)
    graph.add_node("classify_device", classify_device)
    graph.add_node("assess_severity", assess_severity)
    graph.add_node("determine_reporting", determine_reporting)
    graph.add_node("generate_report", generate_report)
    graph.add_node("escalate", escalate)

    graph.set_entry_point("extract_info")
    graph.add_edge("extract_info", "classify_device")
    graph.add_edge("classify_device", "assess_severity")

    graph.add_conditional_edges(
        "assess_severity",
        _route_after_severity,
        {"escalate": "escalate", "determine_reporting": "determine_reporting"},
    )

    graph.add_edge("determine_reporting", "generate_report")
    graph.add_edge("generate_report", END)
    graph.add_edge("escalate", END)

    return graph.compile()


def build_initial_state(
    description: str,
    device_name_hint: str | None = None,
    device_class_hint: str | None = None,
) -> IncidentState:
    """Construct the initial IncidentState for a new incident description."""
    return IncidentState(
        description=description,
        device_name_hint=device_name_hint,
        device_class_hint=device_class_hint,
        device_name=None,
        device_class=None,
        event_type=None,
        patient_outcome=None,
        severity=None,
        severity_confidence=None,
        severity_reasoning=None,
        reportable=None,
        report_to=None,
        deadline_days=None,
        classification_rule=None,
        draft_notification=None,
        escalated_to_human=False,
        escalation_reason=None,
        rag_sources=None,
        processing_steps=[],
        errors=[],
    )


def run_incident_classification(
    description: str,
    device_name_hint: str | None = None,
    device_class_hint: str | None = None,
) -> IncidentState:
    """Build the graph, run it on `description`, and return the final state."""
    graph = build_graph()
    initial_state = build_initial_state(description, device_name_hint, device_class_hint)
    final_state = graph.invoke(initial_state)
    logger.info(
        "Incident classification complete: severity=%s escalated=%s",
        final_state.get("severity"),
        final_state.get("escalated_to_human"),
    )
    return final_state
