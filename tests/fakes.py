"""Test doubles: a scripted LLMClient and agent dependencies that never touch the network."""

from src.agent.llm import Usage
from src.agent.nodes import ASSESSMENT_SYSTEM, DRAFT_SYSTEM, EXTRACTION_SYSTEM, AgentDeps
from src.agent.reviewer import REVIEWER_SYSTEM

REGULATORY_CHUNK = {
    "chunk_id": "mdr_vigilance_articles.txt::Article 87::0",
    "document": "MDR 2017/745 (Articles 87-92, Vigilance)",
    "section": "Article 87",
    "text": "... not later than 15 days ... not later than 10 days ... not later than 2 days ...",
}


class ScriptedLLM:
    """LLMClient whose JSON answers are scripted per agent stage.

    Each stage value is a dict (returned), an Exception (raised), or a list of those
    (consumed in order). Every call is recorded in `calls` as (stage, system, user).
    """

    def __init__(self, extract=None, assess=None, draft=None, review=None, text="stub answer", delay=0.0):
        self.responses = {"extract": extract, "assess": assess, "review": review, "draft": draft or {
            "incident_date": None, "reporter_type": "healthcare_professional",
            "device_identification": "device", "event_description": "summary",
            "patient_outcome": "outcome", "corrective_action": "Pending investigation",
        }}
        self.text = text
        self.delay = delay
        self.calls: list[tuple[str, str, str]] = []
        self.usage = Usage()

    @staticmethod
    def _stage(system: str) -> str:
        if system == EXTRACTION_SYSTEM:
            return "extract"
        if system == ASSESSMENT_SYSTEM:
            return "assess"
        if system == DRAFT_SYSTEM:
            return "draft"
        if system == REVIEWER_SYSTEM:
            return "review"
        return "other"

    def _next(self, stage: str):
        value = self.responses.get(stage)
        if isinstance(value, list):
            value = value.pop(0)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise AssertionError(f"ScriptedLLM has no response for stage {stage!r}")
        return dict(value)

    def complete_json(self, system: str, user: str, schema: dict, max_tokens: int = 4096) -> dict:
        if self.delay:
            import time

            time.sleep(self.delay)
        stage = self._stage(system)
        self.calls.append((stage, system, user))
        self.usage.add(10, 5)
        return self._next(stage)

    def complete_text(self, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append(("text", system, user))
        self.usage.add(10, 5)
        return self.text

    def last_usage(self) -> dict[str, int]:
        return {"input_tokens": 10, "output_tokens": 5}

    def stages(self) -> list[str]:
        return [stage for stage, _, _ in self.calls]


def extraction(device="infusion pump", outcome="patient hospitalized", known=True,
               device_class=None, device_type=None, event="malfunction") -> dict:
    return {
        "device_name": device, "device_type": device_type, "device_class_stated": device_class,
        "event_type": event, "patient_outcome": outcome, "outcome_known": known,
    }


def assessment(category="other_serious", confidence=0.9, alternative=None,
               reasoning="Art. 2(65) applies.") -> dict:
    return {
        "category": category, "alternative_category": alternative,
        "confidence": confidence, "reasoning": reasoning,
    }


def review(verdict="agree", issues=(), category=None, deadline=None, evidence=()) -> dict:
    return {
        "verdict": verdict, "issues": list(issues), "suggested_category": category,
        "suggested_deadline_days": deadline, "evidence": list(evidence),
    }


def deps_for(llm: ScriptedLLM, reviewer: bool = False, reviewer_llm=None) -> AgentDeps:
    return AgentDeps(
        llm=llm, regulatory_context=lambda: [REGULATORY_CHUNK],
        reviewer_enabled=reviewer, reviewer_llm=reviewer_llm,
    )
