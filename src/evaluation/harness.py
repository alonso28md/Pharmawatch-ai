"""Evaluation harness: runs the golden dataset against the real system."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.agent.graph import run_incident_classification
from src.config import get_settings
from src.evaluation.dataset import GoldenCase, load_golden_dataset
from src.evaluation.metrics import (
    answer_faithfulness_and_hallucination,
    classification_accuracy,
    escalation_appropriateness,
    latency_percentiles,
    reportability_accuracy,
    retrieval_accuracy,
    source_citation_rate,
)
from src.rag.retriever import RagRetriever

logger = logging.getLogger(__name__)


@dataclass
class EvaluationRunResult:
    """The full output of one evaluation harness run."""

    total_cases: int
    passed: int
    failed: int
    metrics: dict[str, float]
    failed_cases: list[dict]
    rag_results: list[dict] = field(default_factory=list)
    classification_results: list[dict] = field(default_factory=list)
    model: str = ""


def _run_rag_case(retriever: RagRetriever, case: GoldenCase) -> dict:
    question = case.input["question"]
    start = time.perf_counter()
    answer = retriever.answer(question)
    latency_ms = (time.perf_counter() - start) * 1000

    answer_lower = answer.answer.lower()
    missing_phrases = [
        phrase
        for phrase in case.expected.get("answer_contains", [])
        if phrase.lower() not in answer_lower
    ]
    expected_doc = case.expected.get("source_document", "")
    retrieved_docs = [source.document for source in answer.sources]
    doc_found = any(expected_doc in doc or doc in expected_doc for doc in retrieved_docs)

    passed = not missing_phrases and doc_found
    reason = None
    if not passed:
        reasons = []
        if missing_phrases:
            reasons.append(f"answer missing expected phrase(s): {missing_phrases}")
        if not doc_found:
            reasons.append(f"expected source '{expected_doc}' not among retrieved: {retrieved_docs}")
        reason = "; ".join(reasons)

    return {
        "case_id": case.id,
        "question": question,
        "expected": case.expected,
        "answer": answer.answer,
        "sources": [
            {"document": s.document, "section": s.section, "text": s.text}
            for s in answer.sources
        ],
        "retrieval_score": answer.retrieval_score,
        "latency_ms": latency_ms,
        "passed": passed,
        "failure_reason": reason,
    }


def _run_classification_case(case: GoldenCase) -> dict:
    description = case.input["incident_description"]
    device_class_hint = case.input.get("device_class")

    start = time.perf_counter()
    final_state = run_incident_classification(description, device_class_hint=device_class_hint)
    latency_ms = (time.perf_counter() - start) * 1000

    expected = case.expected
    predicted_severity = final_state.get("severity")
    predicted_reportable = final_state.get("reportable")
    escalated = bool(final_state.get("escalated_to_human"))

    if "should_escalate" in expected:
        passed = escalated == expected["should_escalate"]
        reason = None if passed else f"expected escalation={expected['should_escalate']}, got {escalated}"
    else:
        severity_ok = predicted_severity == expected.get("severity")
        reportable_ok = predicted_reportable == expected.get("reportable")
        passed = severity_ok and reportable_ok
        reasons = []
        if not severity_ok:
            reasons.append(f"expected severity={expected.get('severity')!r}, got {predicted_severity!r}")
        if not reportable_ok:
            reasons.append(f"expected reportable={expected.get('reportable')!r}, got {predicted_reportable!r}")
        reason = "; ".join(reasons) if reasons else None

    return {
        "case_id": case.id,
        "description": description,
        "expected": expected,
        "predicted_severity": predicted_severity,
        "predicted_reportable": predicted_reportable,
        "predicted_deadline_days": final_state.get("deadline_days"),
        "predicted_report_to": final_state.get("report_to"),
        "escalated_to_human": escalated,
        "escalation_reason": final_state.get("escalation_reason"),
        "latency_ms": latency_ms,
        "passed": passed,
        "failure_reason": reason,
    }


class EvaluationHarness:
    """Runs the golden dataset against the real RAG + agent system and scores it."""

    def __init__(self, dataset_path: Path | str, retriever: RagRetriever | None = None):
        self._dataset_path = dataset_path
        self._retriever = retriever or RagRetriever()

    def run(self, categories: list[str] | None = None) -> EvaluationRunResult:
        """Run every (optionally category-filtered) case and compute all metrics."""
        settings = get_settings()
        cases = load_golden_dataset(self._dataset_path, categories=categories)

        rag_cases = [c for c in cases if c.category == "rag"]
        classification_cases = [c for c in cases if c.category == "classification"]

        rag_results = []
        for case in rag_cases:
            logger.info("Running RAG case %s", case.id)
            rag_results.append(_run_rag_case(self._retriever, case))

        classification_results = []
        for case in classification_cases:
            logger.info("Running classification case %s", case.id)
            classification_results.append(_run_classification_case(case))

        all_latencies = [r["latency_ms"] for r in rag_results] + [
            r["latency_ms"] for r in classification_results
        ]
        p50, p95 = latency_percentiles(all_latencies)
        faithfulness, hallucination_rate = answer_faithfulness_and_hallucination(rag_results)

        metrics = {
            "retrieval_accuracy": retrieval_accuracy(rag_results),
            "answer_faithfulness": faithfulness,
            "hallucination_rate": hallucination_rate,
            "classification_accuracy": classification_accuracy(classification_results),
            "reportability_accuracy": reportability_accuracy(classification_results),
            "escalation_appropriateness": escalation_appropriateness(classification_results),
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "source_citation_rate": source_citation_rate(rag_results),
        }

        all_results = rag_results + classification_results
        passed = sum(1 for r in all_results if r["passed"])
        failed_cases = [
            {"case_id": r["case_id"], "reason": r["failure_reason"]}
            for r in all_results
            if not r["passed"]
        ]

        return EvaluationRunResult(
            total_cases=len(all_results),
            passed=passed,
            failed=len(all_results) - passed,
            metrics=metrics,
            failed_cases=failed_cases,
            rag_results=rag_results,
            classification_results=classification_results,
            model=settings.anthropic_model,
        )
