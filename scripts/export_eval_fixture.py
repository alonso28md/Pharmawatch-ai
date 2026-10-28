#!/usr/bin/env python
"""Write the latest stored evaluation (as served by GET /evaluations/latest) to the
frontend mock fixtures, so mock mode shows real stored results. No model calls.

Usage: python scripts/export_eval_fixture.py [dataset_label]   (default: v2)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api.routes.evaluations import _load  # noqa: E402


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "v2"
    latest = _load(label)
    if latest is None:
        sys.exit(f"No stored evaluation for dataset '{label}' in ARTIFACTS_DIR/evaluations")
    target = ROOT / "frontend" / "src" / "mocks" / "evaluation.fixture.json"
    target.write_text(json.dumps(latest.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {target.relative_to(ROOT)} from {latest.file}")


if __name__ == "__main__":
    main()
