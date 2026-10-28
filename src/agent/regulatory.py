"""Single source of truth for incident categories, reporting deadlines and keyword signals.

Deadlines and recipients come from data/classification_rules.json (MDR Article 87),
never from code. The keyword lists here are an AUXILIARY signal only (used to detect
contradictions and as a cross-check); the category itself comes from the model's
structured judgement, and any doubt escalates to a human.
"""

import json
import re
from functools import lru_cache
from typing import Literal

from src.config import PROJECT_ROOT

RULES_PATH = PROJECT_ROOT / "data" / "classification_rules.json"

IncidentCategory = Literal[
    "death",
    "unanticipated_serious_deterioration",
    "public_health_threat",
    "other_serious",
    "non_serious",
    "unknown",
]
INCIDENT_CATEGORIES: tuple[str, ...] = (
    "death",
    "unanticipated_serious_deterioration",
    "public_health_threat",
    "other_serious",
    "non_serious",
    "unknown",
)
SERIOUS_CATEGORIES = frozenset(
    {"death", "unanticipated_serious_deterioration", "public_health_threat", "other_serious"}
)

# Category -> trigger key of a rule in classification_rules.json["reporting_deadlines"].
# The corpus (mdr_vigilance_articles.txt, Article 87 summary) states:
#   serious public health threat -> 2 days; death or unanticipated serious deterioration
#   -> 10 days; any other serious incident -> 15 days.
# REGULATORY-REVIEW: what makes a deterioration "unanticipated" (vs. an anticipated one,
# which falls under "other serious incident") is not defined in the corpus; the model
# decides it and must flag doubt via `alternative_category`, which escalates.
CATEGORY_TRIGGERS: dict[str, str] = {
    "public_health_threat": "serious_public_health_threat",
    "death": "death_or_unanticipated_serious_deterioration",
    "unanticipated_serious_deterioration": "death_or_unanticipated_serious_deterioration",
    "other_serious": "other_serious_incident",
}


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def reporting_for_category(category: str) -> dict:
    """Return {reportable, report_to, deadline_days, deadline_rule} for a category.

    `unknown` is not a decision: callers must escalate before asking for it.
    """
    if category not in INCIDENT_CATEGORIES:
        raise ValueError(f"Unknown incident category: {category!r}")
    if category == "unknown":
        raise ValueError("No reporting determination exists for an unknown category")
    if category == "non_serious":
        # REGULATORY-REVIEW: non-serious incidents may still feed Article 88 trend
        # reporting (the 30-day "non_serious_trend" rule); that is a manufacturer-side
        # statistical process and is not determined per incident here.
        return {"reportable": False, "report_to": [], "deadline_days": None, "deadline_rule": None}

    trigger = CATEGORY_TRIGGERS[category]
    rule = next(r for r in load_rules()["reporting_deadlines"]["rules"] if r["trigger"] == trigger)
    # REGULATORY-REVIEW: report_to lists come verbatim from classification_rules.json;
    # who notifies whom (healthcare centre vs. manufacturer under Article 87 and the
    # Spanish AEMPS procedure) needs confirmation by a vigilance specialist.
    return {
        "reportable": True,
        "report_to": list(rule["report_to"]),
        "deadline_days": rule["deadline_days"],
        "deadline_rule": trigger,
    }


def same_determination(category_a: str, category_b: str) -> bool:
    """True when two categories lead to the same reporting outcome (so doubt between them is harmless)."""
    if "unknown" in (category_a, category_b):
        return False
    return reporting_for_category(category_a) == reporting_for_category(category_b)


# --- auxiliary keyword signal -------------------------------------------------------

DEATH_TERMS = (
    "death",
    "died",
    "dies",
    "dead",
    "fatal",
    "deceased",
    "passed away",
    "fallecido",
    "fallecida",
    "falleció",
    "muerte",
    "murió",
)
LIFE_THREATENING_TERMS = (
    "life-threatening",
    "life threatening",
    "cardiac arrest",
    "respiratory arrest",
    "resuscitated",
    "resuscitation",
    "parada cardiaca",
    "parada cardíaca",
    "parada respiratoria",
)
PUBLIC_HEALTH_TERMS = (
    "public health threat",
    "outbreak",
    "widespread risk",
    "multiple patients across",
    "amenaza para la salud pública",
    "brote",
)
DETERIORATION_TERMS = (
    "hospitalized",
    "hospitalised",
    "hospitalization",
    "hospitalisation",
    "admitted",
    "icu",
    "intensive care",
    "surgical intervention",
    "emergency surgery",
    "required surgery",
    "reoperation",
    "permanent",
    "disability",
    "serious deterioration",
    "prolonged hospital",
    "injury",
    "injured",
    "burn",
    "burns",
    "required treatment",
    "medical intervention",
    "overdose",
    "anaphylaxis",
    "anaphylactic",
    "hospitalizado",
    "hospitalizada",
    "ingreso",
    "uci",
    "cirugía de urgencia",
    "intervención quirúrgica",
    "lesión",
    "quemadura",
    "sobredosis",
    # Device-fragment retrieval / removal procedures (e.g. "catheter ... required retrieval").
    "required retrieval",
    "retrieval by interventional radiology",
    "interventional radiology",
    "endovascular retrieval",
    "required removal",
    "surgical removal",
    "emergency removal",
    "needed surgery",
    "needed an operation",
    "extracción urgente",
    "extracción de urgencia",
    "requirió extracción",
    "fue necesario extraer",
    "radiología intervencionista",
)
NON_SERIOUS_TERMS = (
    "no harm",
    "not harmed",
    "unharmed",
    "no injury",
    "not injured",
    "uninjured",
    "unaffected",
    "no clinical impact",
    "no clinical effect",
    "near miss",
    "near-miss",
    "resolved before use",
    "no patient involved",
    "no patient was involved",
    "no patient contact",
    "no patient was harmed",
    "no one was harmed",
    "nobody was harmed",
    "expected side effect",
    "sin daño",
    "sin lesiones",
    "ningún paciente",
    "sin impacto clínico",
)


def _pattern(terms: tuple[str, ...]) -> re.Pattern:
    alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


_DEATH = _pattern(DEATH_TERMS)
_LIFE = _pattern(LIFE_THREATENING_TERMS)
_PUBLIC = _pattern(PUBLIC_HEALTH_TERMS)
_DETERIORATION = _pattern(DETERIORATION_TERMS)
_NON_SERIOUS = _pattern(NON_SERIOUS_TERMS)

# Sentences describing what *could* have happened (Art. 2(65) "might have led to") are
# not evidence of actual harm, so they are excluded from the serious-term scan.
_HYPOTHETICAL = re.compile(
    r"\b(could have|might have|would have|may have led|potentially|risk of|"
    r"podría haber|pudo haber|habría)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+")


def _actual_events(text: str) -> str:
    """Drop hypothetical sentences and explicit negations, keeping statements of fact."""
    kept = [s for s in _SENTENCE_SPLIT.split(text or "") if not _HYPOTHETICAL.search(s)]
    return _NON_SERIOUS.sub(" ", " ".join(kept))


def mentions_death(text: str) -> bool:
    return bool(_DEATH.search(_actual_events(text)))


def mentions_death_or_life_threat(text: str) -> bool:
    cleaned = _actual_events(text)
    return bool(_DEATH.search(cleaned) or _LIFE.search(cleaned))


def severity_signal(description: str, patient_outcome: str | None = None) -> dict:
    """Keyword cross-check of MDR Art. 2(65) criteria (auxiliary signal, not a decision).

    Whole-word matching only; explicit negations ("no injury", "not harmed") and
    hypothetical sentences ("could have died") are removed before the serious-term scan.
    """
    text = f"{description} {patient_outcome or ''}"
    has_non_serious = bool(_NON_SERIOUS.search(text))
    cleaned = _actual_events(text)

    criteria = []
    if _DEATH.search(cleaned):
        criteria.append("death")
    if _PUBLIC.search(cleaned):
        criteria.append("public_health_threat")
    if _LIFE.search(cleaned) or _DETERIORATION.search(cleaned):
        criteria.append("serious_deterioration")

    return {
        "criteria_met": criteria,
        "non_serious_signal": has_non_serious,
        "contradictory_signals": bool(criteria) and has_non_serious,
    }
