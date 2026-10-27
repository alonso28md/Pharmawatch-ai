"""Evaluation harness: runs a golden dataset against the real system, N times per case.

Each (case, repetition) is scored independently; metrics are computed per repetition and
reported as mean/min/max across repetitions, because model outputs are not deterministic
(sampling parameters such as temperature can no longer be set on the API). A run records
the model, judge model, git commit, dataset version/split and token usage.
"""

import logging
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.agent.graph import build_graph, build_initial_state
from src.agent.llm import AnthropicLLMClient, LLMClient, LLMOutputError, LLMUnavailableError
from src.agent.nodes import AgentDeps
from src.config import PROJECT_ROOT, get_settings
from src.evaluation.dataset import GoldenCase, load_dataset
from src.evaluation.judge import LLMJudge, verify_numeric_claims
from src.evaluation.metrics import (
    aggregate_repetitions,
    classification_metrics,
    latency_metrics,
    rag_metrics,
    score_classification_case,
    score_rag_case,
)
from src.rag.retriever import RagRetriever

logger = logging.getLogger(__name__)


@dataclass
class EvaluationRunResult:
    """The full output of one evaluation harness run."""

    total_cases: int
    passed: int  # cases that passed in every repetition
    failed: int
    metrics: dict[str, float | None]  # mean across repetitions
    failed_cases: list[dict]
    rag_results: list[dict] = field(default_factory=list)
    classification_results: list[dict] = field(default_factory=list)
    model: str = ""
    metric_summary: dict[str, dict] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    flaky_cases: list[str] = field(default_factory=list)


def _git_commit() -> str | None:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return f"{commit}{'-dirty' if dirty else ''}" or None
    except (OSError, subprocess.SubprocessError):
        return None


class EvaluationHarness:
    """Runs a golden dataset against the real RAG + agent system and scores it."""

    def __init__(
        self,
        dataset_path: Path | str,
        *,
        split: str | None = None,
        repetitions: int = 1,
        max_workers: int = 1,
        system_llm: LLMClient | None = None,
        judge_llm: LLMClient | None = None,
        retriever: RagRetriever | None = None,
        reviewer_enabled: bool = False,
        include_unreviewed: bool = False,
    ):
        settings = get_settings()
        self._dataset_path = Path(dataset_path)
        self._split = split
        self._repetitions = max(1, repetitions)
        self._max_workers = max(1, max_workers)
        self._include_unreviewed = include_unreviewed
        self.system_llm = system_llm or AnthropicLLMClient()
        self.judge_llm = judge_llm or AnthropicLLMClient(model=settings.eval_judge_model or None)
        self._retriever = retriever or RagRetriever(llm=self.system_llm)
        self._judge = LLMJudge(self.judge_llm)
        self._reviewer_enabled = reviewer_enabled
        self._graph = build_graph(
            AgentDeps(
                llm=self.system_llm,
                regulatory_context=self._retriever.regulatory_context,
                reviewer_enabled=reviewer_enabled,
            )
        )

    # --- single cases ------------------------------------------------------------------

    def _base(self, case: GoldenCase, repetition: int) -> dict:
        return {
            "case_id": case.id, "repetition": repetition, "split": case.split,
            "language": case.language, "subcategory": case.subcategory, "tags": case.tags,
            "expected": case.expected,
        }

    def _run_rag_case(self, case: GoldenCase, repetition: int) -> dict:
        question = case.input["question"]
        start = time.perf_counter()
        answer = self._retriever.answer(question, language=case.input.get("language"))
        latency_ms = (time.perf_counter() - start) * 1000

        # Exactly what the model saw, headers included (document - section), so a correct
        # "Article 87" taken from a chunk header is not flagged as unsupported.
        context_texts = [f"{c['document']} - {c['section']}\n{c['text']}" for c in answer.context]
        judge = None
        judge_error = None
        try:
            verdict = self._judge.judge(question, answer.answer, context_texts)
            judge = {"abstained": verdict.abstained, "claims": verdict.claims}
        except (LLMOutputError, LLMUnavailableError) as exc:
            judge_error = f"judge failed: {exc}"

        result = {
            **self._base(case, repetition),
            "question": question,
            "answer": answer.answer,
            "sources": [{"document": s.document, "section": s.section, "chunk_id": s.chunk_id} for s in answer.sources],
            "context": answer.context,
            "cited_labels": answer.cited_labels,
            "retrieval_score": answer.retrieval_score,
            "judge": judge,
            "numeric": verify_numeric_claims(answer.answer, context_texts),
            "latency_ms": latency_ms,
        }
        scored = score_rag_case(result)
        if judge_error:
            scored["passed"] = False
            scored["failure_reason"] = "; ".join(filter(None, [scored["failure_reason"], judge_error]))
        return scored

    def _run_classification_case(self, case: GoldenCase, repetition: int) -> dict:
        start = time.perf_counter()
        final_state = self._graph.invoke(
            build_initial_state(
                case.input["incident_description"],
                device_name_hint=case.input.get("device_name"),
                device_class_hint=case.input.get("device_class"),
            )
        )
        latency_ms = (time.perf_counter() - start) * 1000
        kept = (
            "incident_category", "alternative_category", "severity", "severity_confidence",
            "severity_reasoning", "reportable", "report_to", "deadline_days", "deadline_rule",
            "device_name", "device_class", "device_class_source", "patient_outcome", "outcome_known",
            "escalation_level", "escalation_reason", "review", "errors", "processing_steps",
        )
        result = {
            **self._base(case, repetition),
            "description": case.input["incident_description"],
            "final_state": {k: final_state.get(k) for k in kept},
            "latency_ms": latency_ms,
        }
        return score_classification_case(result)

    def _run_one(self, case: GoldenCase, repetition: int) -> dict:
        try:
            if case.category == "rag":
                return self._run_rag_case(case, repetition)
            return self._run_classification_case(case, repetition)
        except LLMUnavailableError as exc:
            # One failed API call should not abort a long run; the case counts as failed.
            logger.warning("Case %s rep %d: LLM unavailable (%s)", case.id, repetition, exc)
            return {**self._base(case, repetition), "category": case.category, "error": str(exc),
                    "passed": False, "failure_reason": f"llm_unavailable: {exc}", "latency_ms": None}

    # --- whole run ---------------------------------------------------------------------

    def run(self, categories: list[str] | None = None) -> EvaluationRunResult:
        settings = get_settings()
        dataset = load_dataset(
            self._dataset_path, categories=categories, split=self._split,
            include_unreviewed=self._include_unreviewed,
        )
        tasks = [(case, rep) for rep in range(self._repetitions) for case in dataset.cases]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            results = list(pool.map(lambda t: self._run_one(*t), tasks))
        wall_seconds = round(time.perf_counter() - started, 1)

        by_category = {c.id: c.category for c in dataset.cases}
        per_rep_metrics = []
        for rep in range(self._repetitions):
            rep_results = [r for r in results if r["repetition"] == rep and "scores" in r]
            rag = [r for r in rep_results if by_category[r["case_id"]] == "rag"]
            cls = [r for r in rep_results if by_category[r["case_id"]] == "classification"]
            metrics = {}
            if rag:
                metrics.update(rag_metrics(rag))
            if cls:
                metrics.update(classification_metrics(cls))
            metrics.update(latency_metrics(rag, cls))
            per_rep_metrics.append(metrics)
        summary = aggregate_repetitions(per_rep_metrics)

        outcomes: dict[str, list[bool]] = defaultdict(list)
        reasons: dict[str, list[str]] = defaultdict(list)
        for r in results:
            outcomes[r["case_id"]].append(r["passed"])
            if not r["passed"] and r.get("failure_reason"):
                reasons[r["case_id"]].append(r["failure_reason"])
        passed = sum(1 for v in outcomes.values() if all(v))
        flaky = sorted(cid for cid, v in outcomes.items() if any(v) and not all(v))
        failed_cases = [
            {"case_id": cid, "reason": f"failed {v.count(False)}/{len(v)} repetitions: {reasons[cid][0]}"}
            for cid, v in outcomes.items() if not all(v)
        ]

        metadata = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": _git_commit(),
            "model": getattr(self.system_llm, "model", settings.anthropic_model),
            "judge_model": getattr(self.judge_llm, "model", None),
            "dataset": self._dataset_path.name,
            "dataset_version": dataset.version,
            "split": self._split or "all",
            "repetitions": self._repetitions,
            "max_workers": self._max_workers,
            "reviewer_enabled": self._reviewer_enabled,
            "cases": {"rag": sum(1 for c in dataset.cases if c.category == "rag"),
                      "classification": sum(1 for c in dataset.cases if c.category == "classification")},
            "excluded_pending_expert_review": dataset.excluded_for_review,
            "usage": {"system": self.system_llm.usage.snapshot(), "judge": self.judge_llm.usage.snapshot()},
            "wall_seconds": wall_seconds,
            # Runs where the model API failed: counted as failed cases, absent from metrics.
            "errored_runs": [f"{r['case_id']}#{r['repetition']}" for r in results if "error" in r],
        }
        rag_results = [r for r in results if by_category[r["case_id"]] == "rag"]
        classification_results = [r for r in results if by_category[r["case_id"]] == "classification"]
        return EvaluationRunResult(
            total_cases=len(outcomes),
            passed=passed,
            failed=len(outcomes) - passed,
            metrics={name: s["mean"] for name, s in summary.items()},
            failed_cases=failed_cases,
            rag_results=rag_results,
            classification_results=classification_results,
            model=metadata["model"],
            metric_summary=summary,
            metadata=metadata,
            flaky_cases=flaky,
        )
