"""Tools the incident-classification agent's nodes call for grounded facts."""

import json
import logging

from src.config import PROJECT_ROOT
from src.rag.retriever import RagRetriever

logger = logging.getLogger(__name__)

_RULES_PATH = PROJECT_ROOT / "data" / "classification_rules.json"
_rules_cache: dict | None = None


def get_rules() -> dict:
    """Load (and cache) data/classification_rules.json."""
    global _rules_cache
    if _rules_cache is None:
        with open(_RULES_PATH, encoding="utf-8") as f:
            _rules_cache = json.load(f)
    return _rules_cache


def classification_rules_tool(device_description: str) -> dict:
    """Tool 1: match a free-text device description against MDR Annex VIII rules."""
    description_lower = device_description.lower()

    # Named Annex VIII exceptions (e.g. breast implants, joint replacements) take
    # priority over the general per-rule default class, since a plain keyword count
    # would otherwise return the rule's unqualified default (e.g. Rule 8 -> IIb).
    for override in get_rules().get("classification_overrides", []):
        if any(keyword.lower() in description_lower for keyword in override["keywords"]):
            return {
                "class": override["class"],
                "rule": override["rule"],
                "reasoning": override["reasoning"],
                "matched": True,
                "match_score": 1,
            }

    rules = get_rules()["classification_rules"]
    best_match = None
    best_score = 0
    for rule in rules:
        score = sum(1 for keyword in rule["keywords"] if keyword.lower() in description_lower)
        if score > best_score:
            best_score = score
            best_match = rule

    if best_match is None:
        return {
            "class": "I",
            "rule": "Rule 1 (default, no keyword match)",
            "reasoning": (
                "No Annex VIII classification keywords matched the device description; "
                "defaulting to class I per Rule 1. Manual review recommended."
            ),
            "matched": False,
        }

    return {
        "class": best_match["class"],
        "rule": f"{best_match['rule']} ({best_match['group']} devices)",
        "reasoning": best_match["criteria"],
        "matched": True,
        "match_score": best_score,
    }


def severity_criteria_tool(event_description: str, patient_outcome: str) -> dict:
    """Tool 2: evaluate MDR Art. 2(65) seriousness criteria against event/outcome text."""
    text = f"{event_description} {patient_outcome or ''}".lower()

    death_terms = ["death", "died", "fatal", "deceased"]
    threat_terms = ["public health threat", "outbreak", "widespread risk"]
    deterioration_terms = [
        "hospitaliz",
        "surgical intervention",
        "surgery",
        "permanent",
        "disability",
        "life-threatening",
        "life threatening",
        "serious deterioration",
        "prolonged",
        "injury",
        "burn",
        "required treatment",
        "medical intervention",
        "overdose",
    ]
    non_serious_terms = [
        "no harm",
        "no injury",
        "near miss",
        "near-miss",
        "resolved before use",
        "no clinical",
        "expected side effect",
        "no patient contact",
        "no impact",
    ]

    has_non_serious_signal = any(term in text for term in non_serious_terms)

    # Strip explicit negations (e.g. "no injury", "no harm") before scanning for
    # deterioration terms, so a naive substring match on "injury" doesn't fire on
    # "no injury" - a real false positive caught in testing.
    cleaned_text = text
    for term in non_serious_terms:
        cleaned_text = cleaned_text.replace(term, " ")

    criteria_met = []
    if any(term in cleaned_text for term in death_terms):
        criteria_met.append("death")
    if any(term in cleaned_text for term in threat_terms):
        criteria_met.append("public_health_threat")
    if any(term in cleaned_text for term in deterioration_terms):
        criteria_met.append("serious_deterioration")

    if criteria_met and not has_non_serious_signal:
        serious = True
        confidence = min(0.95, 0.6 + 0.15 * len(criteria_met))
    elif criteria_met and has_non_serious_signal:
        # Contradictory signal: serious wording alongside a "no harm" style disclaimer.
        serious = True
        confidence = 0.5
    elif has_non_serious_signal:
        serious = False
        confidence = 0.85
    else:
        # No clear signal either way: likely missing information.
        serious = False
        confidence = 0.4

    return {
        "serious": serious,
        "criteria_met": criteria_met,
        "confidence": round(confidence, 2),
        "contradictory_signals": bool(criteria_met) and has_non_serious_signal,
    }


def rag_query_tool(query: str) -> dict:
    """Tool 3: query the RAG system (Phase 1) for regulatory context."""
    retriever = RagRetriever()
    result = retriever.answer(query)
    return {
        "answer": result.answer,
        "sources": [
            {"document": s.document, "section": s.section, "text": s.text}
            for s in result.sources
        ],
    }


def reporting_requirements_tool(
    severity: str, event_type: str, device_class: str, patient_outcome: str = ""
) -> dict:
    """Tool 4: determine who to report to, the deadline, and required report fields."""
    deadline_rules = get_rules()["reporting_deadlines"]["rules"]

    if severity != "serious":
        return {"report_to": [], "deadline_days": None, "required_fields": [], "reportable": False}

    # Check both event_type and patient_outcome: the death/life-threatening signal often
    # only shows up in the outcome text (e.g. event_type="malfunction", outcome="...died").
    combined_lower = f"{event_type or ''} {patient_outcome or ''}".lower()
    if "public health" in combined_lower or "widespread" in combined_lower:
        trigger = "serious_public_health_threat"
    elif any(
        term in combined_lower
        for term in ("death", "died", "fatal", "life-threatening", "life threatening")
    ):
        trigger = "death_or_unanticipated_serious_deterioration"
    else:
        trigger = "other_serious_incident"

    rule = next(r for r in deadline_rules if r["trigger"] == trigger)

    required_fields = [
        "incident_date",
        "reporter_type",
        "device_identification",
        "device_class",
        "event_description",
        "patient_outcome",
        "corrective_action",
    ]

    return {
        "report_to": rule["report_to"],
        "deadline_days": rule["deadline_days"],
        "required_fields": required_fields,
        "reportable": True,
        "deadline_rule": trigger,
    }
