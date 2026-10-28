"""LangGraph definition for the incident-classification agent.

Topology:
  extract_info -> classify_device -> assess_severity -> gate
    gate --(any blocking reason)--> escalate -> finalize -> END
    gate --(clear)--> determine_reporting -> generate_report -> finalize -> END
  With REVIEWER_ENABLED, determine_reporting -> review, and a non-"agree" review routes
  to escalate instead of generate_report.

`gate` records the blocking reasons in state (conditional-edge functions cannot write
state); `finalize` adds advisory reasons and runs the output-validation guardrail.
"""

import logging
import threading
from collections.abc import Callable

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent import guardrails
from src.agent.llm import AnthropicLLMClient, get_llm_client
from src.agent.nodes import (
    AgentDeps,
    assess_severity,
    classify_device,
    determine_reporting,
    escalate,
    extract_info,
    finalize,
    generate_report,
)
from src.agent.reviewer import review
from src.agent.state import IncidentState
from src.config import get_settings

logger = logging.getLogger(__name__)


def gate(state: IncidentState, deps: AgentDeps) -> dict:
    return {
        "blocking_reasons": guardrails.blocking_reasons(state),
        "processing_steps": [*state.get("processing_steps", []), "gate"],
    }


def _route_after_gate(state: IncidentState) -> str:
    return "escalate" if state.get("blocking_reasons") else "determine_reporting"


def _route_after_review(state: IncidentState) -> str:
    return "escalate" if state.get("blocking_reasons") else "generate_report"


def _bind(node: Callable[[IncidentState, AgentDeps], dict], deps: AgentDeps):
    def bound(state: IncidentState) -> dict:
        return node(state, deps)

    bound.__name__ = node.__name__
    return bound


def build_graph(deps: AgentDeps) -> CompiledStateGraph:
    """Build and compile the incident-classification StateGraph around `deps`."""
    graph = StateGraph(IncidentState)
    for node in (extract_info, classify_device, assess_severity, gate, determine_reporting,
                 generate_report, escalate, finalize):
        graph.add_node(node.__name__, _bind(node, deps))

    graph.set_entry_point("extract_info")
    graph.add_edge("extract_info", "classify_device")
    graph.add_edge("classify_device", "assess_severity")
    graph.add_edge("assess_severity", "gate")
    graph.add_conditional_edges(
        "gate", _route_after_gate,
        {"escalate": "escalate", "determine_reporting": "determine_reporting"},
    )
    if deps.reviewer_enabled:
        graph.add_node("review", _bind(review, deps))
        graph.add_edge("determine_reporting", "review")
        graph.add_conditional_edges(
            "review", _route_after_review,
            {"escalate": "escalate", "generate_report": "generate_report"},
        )
    else:
        graph.add_edge("determine_reporting", "generate_report")
    graph.add_edge("generate_report", "finalize")
    graph.add_edge("escalate", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def default_deps() -> AgentDeps:
    """Production collaborators: the shared LLM client and the cached MDR context."""
    from src.rag.retriever import get_retriever

    settings = get_settings()
    reviewer_llm = (
        AnthropicLLMClient(model=settings.reviewer_model)
        if settings.reviewer_enabled and settings.reviewer_model else None
    )
    return AgentDeps(
        llm=get_llm_client(),
        regulatory_context=get_retriever().regulatory_context,
        reviewer_enabled=settings.reviewer_enabled,
        reviewer_llm=reviewer_llm,
    )


_default_graph: CompiledStateGraph | None = None
_default_graph_lock = threading.Lock()


def get_default_graph() -> CompiledStateGraph:
    """The production graph, compiled once per process (R-04)."""
    global _default_graph
    with _default_graph_lock:
        if _default_graph is None:
            _default_graph = build_graph(default_deps())
        return _default_graph


def reset_default_graph() -> None:
    global _default_graph
    with _default_graph_lock:
        _default_graph = None


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
        device_type=None,
        device_class=None,
        device_class_source=None,
        classification_rule=None,
        event_type=None,
        patient_outcome=None,
        outcome_known=None,
        severity_signal=None,
        incident_category=None,
        alternative_category=None,
        severity=None,
        severity_confidence=None,
        severity_reasoning=None,
        rag_sources=None,
        reportable=None,
        report_to=None,
        deadline_days=None,
        deadline_rule=None,
        review=None,
        draft_notification=None,
        blocking_reasons=[],
        advisory_reasons=[],
        escalated_to_human=False,
        escalation_level="none",
        escalation_reason=None,
        processing_steps=[],
        errors=[],
    )


def stream_incident_classification(
    description: str,
    device_name_hint: str | None = None,
    device_class_hint: str | None = None,
    deps: AgentDeps | None = None,
):
    """Run the graph and yield its real progress.

    Yields ("step", node_name) each time a LangGraph node finishes, in execution order,
    then ("result", final_state). Nothing is synthesised: the steps are the graph's own
    update events.
    """
    graph = build_graph(deps) if deps is not None else get_default_graph()
    final_state: dict = {}
    for mode, chunk in graph.stream(
        build_initial_state(description, device_name_hint, device_class_hint),
        stream_mode=["updates", "values"],
    ):
        if mode == "updates":
            for node in chunk:
                yield "step", node
        else:
            final_state = chunk
    yield "result", final_state


def run_incident_classification(
    description: str,
    device_name_hint: str | None = None,
    device_class_hint: str | None = None,
    deps: AgentDeps | None = None,
) -> IncidentState:
    """Run the graph on `description` and return the final state.

    With `deps`, a dedicated graph is built around them (tests, evaluation variants);
    otherwise the process-wide compiled graph is reused.
    """
    graph = build_graph(deps) if deps is not None else get_default_graph()
    final_state = graph.invoke(build_initial_state(description, device_name_hint, device_class_hint))
    logger.info(
        "Incident classification complete: category=%s escalation=%s",
        final_state.get("incident_category"),
        final_state.get("escalation_level"),
    )
    return final_state
