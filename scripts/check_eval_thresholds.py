#!/usr/bin/env python
"""Check an evaluation JSON report against config/eval_thresholds.json (used by CI).

Exit code 1 if any gating metric misses its threshold or is missing (N/A). Non-gating
metrics (latency) are printed but never fail the check.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.metrics import load_thresholds, meets_threshold  # noqa: E402


def check(report: dict) -> list[str]:
    failures = []
    for name, rule in load_thresholds().items():
        value = report["metrics"].get(name)
        ok = meets_threshold(name, value)
        status = "N/A" if ok is None else ("PASS" if ok else "FAIL")
        print(f"{status:4}  {name:36} {value!s:>10}  ({rule['op']} {rule['value']}{'' if rule['gate'] else ', info'})")
        if rule["gate"] and ok is not True:
            failures.append(name)
    return failures


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else max(
        Path("artifacts/evaluations").glob("*.json"), key=lambda p: p.stat().st_mtime
    )
    failures = check(json.loads(path.read_text(encoding="utf-8")))
    if failures:
        print(f"\nThresholds missed: {', '.join(failures)}")
        sys.exit(1)
    print("\nAll gating thresholds met.")


if __name__ == "__main__":
    main()
