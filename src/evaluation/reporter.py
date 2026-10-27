"""Markdown + JSON report generation for an evaluation run."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.harness import EvaluationRunResult
from src.evaluation.metrics import METRIC_THRESHOLDS, meets_threshold

logger = logging.getLogger(__name__)

METRIC_LABELS = {
    "retrieval_accuracy": "Retrieval Accuracy",
    "answer_faithfulness": "Answer Faithfulness",
    "hallucination_rate": "Hallucination Rate",
    "classification_accuracy": "Classification Accuracy",
    "reportability_accuracy": "Reportability Accuracy",
    "escalation_appropriateness": "Escalation Appropriateness",
    "latency_p50_ms": "Latency p50",
    "latency_p95_ms": "Latency p95",
    "source_citation_rate": "Source Citation Rate",
}


def _format_value(metric_name: str, value: float) -> str:
    if metric_name.endswith("_ms"):
        return f"{value:.0f} ms"
    return f"{value * 100:.1f}%"


def _format_threshold(metric_name: str) -> str:
    operator, threshold = METRIC_THRESHOLDS[metric_name]
    if metric_name.endswith("_ms"):
        return f"{operator} {threshold:.0f} ms"
    return f"{operator} {threshold * 100:.0f}%"


def to_json_dict(result: EvaluationRunResult, timestamp: str, dataset_label: str) -> dict:
    """Build the JSON payload (consumed by CI's threshold check)."""
    return {
        "timestamp": timestamp,
        "model": result.model,
        "dataset": dataset_label,
        "summary": {
            "total_cases": result.total_cases,
            "passed": result.passed,
            "failed": result.failed,
            "pass_rate": round(result.passed / result.total_cases, 4) if result.total_cases else 0.0,
        },
        "metrics": result.metrics,
        "failed_cases": result.failed_cases,
    }


def render_markdown(result: EvaluationRunResult, timestamp: str, dataset_label: str) -> str:
    """Render the full Markdown evaluation report."""
    lines = [
        "# PharmaWatch AI — Evaluation Report",
        "",
        f"Generated: {timestamp}",
        f"Model: {result.model}",
        f"Dataset: {dataset_label} ({result.total_cases} cases)",
        "",
        "## Summary",
        "",
        f"- Total cases: {result.total_cases}",
        f"- Passed: {result.passed}",
        f"- Failed: {result.failed}",
        f"- Pass rate: {result.passed / result.total_cases * 100:.1f}%" if result.total_cases else "- Pass rate: N/A",
        "",
        "## Metrics",
        "",
        "| Metric | Score | Threshold | Status |",
        "|---|---|---|---|",
    ]

    for metric_name, value in result.metrics.items():
        label = METRIC_LABELS.get(metric_name, metric_name)
        status = "PASS" if meets_threshold(metric_name, value) else "FAIL"
        lines.append(
            f"| {label} | {_format_value(metric_name, value)} | "
            f"{_format_threshold(metric_name)} | {status} |"
        )

    lines += ["", "## Failed Cases", ""]
    if result.failed_cases:
        for failed in result.failed_cases:
            lines.append(f"- **{failed['case_id']}**: {failed['reason']}")
    else:
        lines.append("None - all cases passed.")

    lines += ["", "## Notes", ""]
    lines.append(
        "- `hallucination_rate` and `answer_faithfulness` are computed with an "
        "embedding-based claim-support heuristic (sentence-transformers cosine "
        "similarity against retrieved chunks, calibrated threshold - see "
        "`CLAIM_SUPPORT_SIMILARITY_THRESHOLD` in `src/evaluation/metrics.py`), "
        "not a second LLM judge."
    )
    lines.append(
        "- `escalation_appropriateness` is measured only over the dataset's "
        "`ambiguous` classification subcategory (cases with missing critical "
        "information, which must be escalated rather than guessed)."
    )
    lines.append(
        "- Any metric below its threshold is reported as-is below, not hidden or "
        "adjusted - see the project README for the honesty-over-polish rationale."
    )

    return "\n".join(lines) + "\n"


def write_reports(
    result: EvaluationRunResult,
    markdown_path: Path | str,
    json_path: Path | str,
    dataset_label: str = "default",
) -> None:
    """Write both the Markdown report and its JSON sibling (used by CI)."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    markdown = render_markdown(result, timestamp, dataset_label)
    Path(markdown_path).write_text(markdown, encoding="utf-8")
    logger.info("Wrote evaluation report to %s", markdown_path)

    payload = to_json_dict(result, timestamp, dataset_label)
    Path(json_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote evaluation JSON to %s", json_path)
