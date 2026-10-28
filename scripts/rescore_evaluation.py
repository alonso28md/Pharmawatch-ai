#!/usr/bin/env python
"""Re-score a saved evaluation JSON with the current metric code. No model calls.

Every saved result keeps what scoring needs (answer, citations, sources, judge verdict,
numeric check, expected labels, final agent state), so metric definitions can evolve
without paying for a new run. Old reports that predate the stored context labels get
them reconstructed: labels are assigned C1..Cn in retrieval order, i.e. one per source.

Usage: python scripts/rescore_evaluation.py artifacts/evaluations/eval_v2_<ts>.json
Writes <same name>_rescored.json next to the input.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.metrics import (  # noqa: E402
    aggregate_repetitions,
    classification_metrics,
    latency_metrics,
    load_thresholds,
    meets_threshold,
    rag_metrics,
    score_classification_case,
    score_rag_case,
)


def _rescore(result: dict) -> dict:
    result = {k: v for k, v in result.items() if k not in ("scores", "passed", "failure_reason")}
    if "answer" in result:
        if not result.get("context"):
            result["context"] = [
                {"label": f"C{i}"} for i in range(1, len(result.get("sources", [])) + 1)
            ]
        return score_rag_case(result)
    return score_classification_case(result)


def rescore(report: dict) -> dict:
    scored = [_rescore(r) for r in report["results"] if "error" not in r]
    reps = sorted({r["repetition"] for r in scored})
    per_rep = []
    for rep in reps:
        rows = [r for r in scored if r["repetition"] == rep]
        rag = [r for r in rows if "answer" in r]
        cls = [r for r in rows if "final_state" in r]
        metrics = {}
        if rag:
            metrics.update(rag_metrics(rag))
        if cls:
            metrics.update(classification_metrics(cls))
        metrics.update(latency_metrics(rag, cls))
        per_rep.append(metrics)
    summary = aggregate_repetitions(per_rep)
    thresholds = load_thresholds()

    outcomes: dict[str, list[bool]] = {}
    for r in scored:
        outcomes.setdefault(r["case_id"], []).append(r["passed"])
    return {
        **report,
        "rescored_from": report.get("timestamp"),
        "summary": {
            **report["summary"],
            "passed": sum(1 for v in outcomes.values() if all(v)),
            "failed": sum(1 for v in outcomes.values() if not all(v)),
            "flaky_cases": sorted(c for c, v in outcomes.items() if any(v) and not all(v)),
        },
        "metrics": {name: s["mean"] for name, s in summary.items()},
        "metric_summary": {
            name: {
                **s,
                "threshold": thresholds.get(name),
                "meets_threshold": meets_threshold(name, s["mean"]),
            }
            for name, s in summary.items()
        },
        "results": scored,
    }


def main() -> None:
    source = Path(sys.argv[1])
    report = json.loads(source.read_text(encoding="utf-8"))
    out = rescore(report)
    target = source.with_name(source.stem + "_rescored.json")
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Wrote {target}")
    for name, s in out["metric_summary"].items():
        print(f"{name:34} mean={s['mean']!s:8} min={s['min']!s:8} max={s['max']!s:8}")


if __name__ == "__main__":
    main()
