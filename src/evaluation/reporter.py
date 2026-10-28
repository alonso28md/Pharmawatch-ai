"""JSON (and optional Markdown text) rendering for an evaluation run."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.harness import EvaluationRunResult
from src.evaluation.metrics import load_thresholds, meets_threshold

logger = logging.getLogger(__name__)


def _compact_result(r: dict) -> dict:
    keep = (
        "case_id",
        "repetition",
        "split",
        "language",
        "subcategory",
        "tags",
        "passed",
        "failure_reason",
        "latency_ms",
        "scores",
        "expected",
        "error",
    )
    out = {k: r[k] for k in keep if k in r}
    if "answer" in r:
        out.update(
            question=r["question"],
            answer=r["answer"],
            cited_labels=r["cited_labels"],
            context=[
                {"label": c["label"], "chunk_id": c["chunk_id"]} for c in r.get("context", [])
            ],
            sources=r["sources"],
            judge=r["judge"],
            numeric=r["numeric"],
        )
    if "final_state" in r:
        out.update(description=r["description"], final_state=r["final_state"])
    return out


def to_json_dict(result: EvaluationRunResult, timestamp: str, dataset_label: str) -> dict:
    """Full machine-readable payload (consumed by CI's threshold check)."""
    thresholds = load_thresholds()
    return {
        "timestamp": timestamp,
        "model": result.model,
        "dataset": dataset_label,
        "metadata": result.metadata,
        "summary": {
            "total_cases": result.total_cases,
            "passed": result.passed,
            "failed": result.failed,
            "pass_rate": round(result.passed / result.total_cases, 4)
            if result.total_cases
            else None,
            "flaky_cases": result.flaky_cases,
        },
        "metrics": result.metrics,
        "metric_summary": {
            name: {
                **stats,
                "threshold": thresholds.get(name),
                "meets_threshold": meets_threshold(name, stats["mean"]),
            }
            for name, stats in result.metric_summary.items()
        },
        "failed_cases": result.failed_cases,
        "results": [_compact_result(r) for r in result.rag_results + result.classification_results],
    }


def render_markdown(result: EvaluationRunResult, timestamp: str, dataset_label: str) -> str:
    """Human-readable summary (printed to the console; not written to the repository)."""
    lines = [
        "# PharmaWatch AI — Evaluation Report",
        "",
        f"Generated: {timestamp}",
        f"Model: {result.model}",
        f"Dataset: {dataset_label} ({result.total_cases} cases)",
        "",
        "## Summary",
        "",
        f"- Passed (every repetition): {result.passed}/{result.total_cases}",
        "",
        "## Metrics",
        "",
        "| Metric | Mean | Min | Max | Threshold | Status |",
        "|---|---|---|---|---|---|",
    ]
    thresholds = load_thresholds()
    for name, value in result.metrics.items():
        stats = result.metric_summary.get(name, {"min": value, "max": value})
        rule = thresholds.get(name)
        ok = meets_threshold(name, value)
        status = "N/A" if ok is None else ("PASS" if ok else "FAIL")
        fmt = (
            (lambda v: "N/A" if v is None else f"{v:.0f} ms")
            if name.endswith("_ms")
            else (lambda v: "N/A" if v is None else f"{v * 100:.1f}%")
        )
        threshold = f"{rule['op']} {rule['value']}" if rule else "-"
        lines.append(
            f"| {name} | {fmt(value)} | {fmt(stats['min'])} | {fmt(stats['max'])} | {threshold} | {status} |"
        )

    lines += ["", "## Failed Cases", ""]
    lines += [f"- **{f['case_id']}**: {f['reason']}" for f in result.failed_cases] or ["None."]
    return "\n".join(lines) + "\n"


def write_json_report(
    result: EvaluationRunResult, artifacts_dir: Path | str, dataset_label: str
) -> Path:
    """Write the run's JSON payload to <artifacts_dir>/evaluations/ and return its path.

    Evaluation output is data, not documentation: it never goes under docs/.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(artifacts_dir) / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"eval_{dataset_label}_{timestamp}.json"
    payload = to_json_dict(result, timestamp, dataset_label)
    path.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote evaluation JSON to %s", path)
    return path
