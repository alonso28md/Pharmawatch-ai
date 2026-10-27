"""Deterministic tools the incident-classification agent uses for grounded facts."""

import logging
import re

from src.agent.regulatory import load_rules

logger = logging.getLogger(__name__)


def _keyword_pattern(keyword: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)


def classification_rules_tool(device_text: str) -> dict:
    """Match a device name/type (NOT the whole incident narrative) against Annex VIII rules.

    Whole-word matching, so e.g. "paediatric" no longer matches the "AED" keyword.
    Named Annex VIII exceptions (breast implants, joint replacements, ...) take
    priority over a rule's default class. No match returns class None - the caller
    escalates instead of defaulting to class I.
    """
    text = device_text or ""
    rules = load_rules()

    for override in rules.get("classification_overrides", []):
        if any(_keyword_pattern(k).search(text) for k in override["keywords"]):
            return {
                "class": override["class"],
                "rule": override["rule"],
                "reasoning": override["reasoning"],
                "matched": True,
            }

    best_match, best_score = None, 0
    for rule in rules["classification_rules"]:
        score = sum(1 for k in rule["keywords"] if _keyword_pattern(k).search(text))
        if score > best_score:
            best_match, best_score = rule, score

    if best_match is None:
        return {
            "class": None,
            "rule": None,
            "reasoning": "No Annex VIII classification keyword matched the device name/type.",
            "matched": False,
        }
    return {
        "class": best_match["class"],
        "rule": f"{best_match['rule']} ({best_match['group']} devices)",
        "reasoning": best_match["criteria"],
        "matched": True,
    }
