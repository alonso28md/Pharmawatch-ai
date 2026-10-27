"""Optional independent reviewer node (REVIEWER_ENABLED).

Runs after determine_reporting. It sees the sanitized description (as data), the
principal agent's decision and the retrieved MDR fragments - but NOT the principal's
self-reported confidence, to avoid anchoring. It cannot change the decision: `agree`
lets it through; `disagree` or `uncertain` (or an unusable review) escalates to a human
with the reviewer's issues and evidence, and the principal decision is kept in `review`
for the specialist to see.
"""

import logging
import time

from src.agent.llm import LLMOutputError
from src.agent.nodes import (
    DATA_HANDLING_RULE,
    INCIDENT_CATEGORIES,
    AgentDeps,
    _context_block,
    _description_block,
    _nullable,
    _object,
    _steps,
)
from src.agent.state import IncidentState

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = _object(
    {
        "verdict": {"type": "string", "enum": ["agree", "disagree", "uncertain"]},
        "issues": {"type": "array", "items": {"type": "string"}},
        "suggested_category": _nullable({"type": "string", "enum": list(INCIDENT_CATEGORIES)}),
        "suggested_deadline_days": _nullable({"type": "integer"}),
        "evidence": {
            "type": "array",
            "items": _object({"chunk_id": {"type": "string"}, "quote": {"type": "string"}}),
        },
    }
)

REVIEWER_SYSTEM = (
    "You are an independent second reviewer of medical device vigilance decisions. Another "
    "analyst has classified an incident and determined its reporting obligation. Check that "
    "decision strictly against the MDR text provided and the facts in the description.\n"
    f"{DATA_HANDLING_RULE}\n"
    "Return verdict 'agree' only if the category, seriousness, deadline and recipients all "
    "follow from the facts and the cited MDR text. Return 'disagree' if any of them is wrong, "
    "with a suggested category/deadline. Return 'uncertain' if the facts do not allow a firm "
    "conclusion. List concrete issues, and support every issue with evidence: the chunk_id of "
    "the MDR fragment and a short verbatim quote from it. Do not invent facts or regulation."
)


def _decision(state: IncidentState) -> dict:
    return {
        "category": state.get("incident_category"),
        "severity": state.get("severity"),
        "reportable": state.get("reportable"),
        "deadline_days": state.get("deadline_days"),
        "report_to": state.get("report_to"),
        "reasoning": state.get("severity_reasoning"),
    }


def review(state: IncidentState, deps: AgentDeps) -> dict:
    """Second-opinion check; escalates (never overrides) on disagreement or uncertainty."""
    llm = deps.reviewer_llm or deps.llm
    context = deps.regulatory_context()
    decision = _decision(state)
    user = (
        f"{_description_block(state)}\n\n"
        f"DECISION UNDER REVIEW (JSON): {decision}\n\n"
        f"MDR FRAGMENTS:\n{_context_block(context)}"
    )

    errors = list(state.get("errors", []))
    start = time.perf_counter()
    try:
        result = llm.complete_json(REVIEWER_SYSTEM, user, REVIEW_SCHEMA)
        verdict = result.get("verdict") if result.get("verdict") in ("agree", "disagree", "uncertain") else "uncertain"
    except LLMOutputError as exc:
        errors.append(f"review: model output could not be parsed ({exc})")
        result, verdict = {}, "uncertain"
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    valid_ids = {c["chunk_id"] for c in context}
    evidence = [e for e in result.get("evidence", []) if isinstance(e, dict) and e.get("chunk_id") in valid_ids]
    record = {
        "verdict": verdict,
        "issues": [str(i) for i in result.get("issues", [])],
        "suggested_category": result.get("suggested_category"),
        "suggested_deadline_days": result.get("suggested_deadline_days"),
        "evidence": evidence,
        "principal_decision": decision,
        "latency_ms": latency_ms,
        "usage": llm.last_usage(),
        "model": getattr(llm, "model", None),
    }

    blocking = list(state.get("blocking_reasons", []))
    if verdict != "agree":
        issues = "; ".join(record["issues"]) or "no details given"
        blocking.append(
            f"Independent review {verdict}: {issues}. The proposed determination is withheld "
            "for a specialist (see review)."
        )
    return {"review": record, "blocking_reasons": blocking, "errors": errors,
            "processing_steps": _steps(state, "review")}
