#!/usr/bin/env python
"""Write the latest stored evaluation (as served by GET /evaluations/latest) to the versioned
snapshot docs/results/evaluation_latest.json. No model calls.

The snapshot is what the documentation quotes (checked by scripts/check_docs.py), what mock
mode shows, and what the API serves when ARTIFACTS_DIR has no results of its own.

Usage: python scripts/export_eval_fixture.py [dataset_label]   (default: v2)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api.routes.evaluations import SNAPSHOT, _pick_latest  # noqa: E402
from src.api.routes.evaluations import _load as load_latest  # noqa: E402
from src.config import get_settings  # noqa: E402


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "v2"
    directory = get_settings().artifacts_dir_absolute / "evaluations"
    if not directory.is_dir() or _pick_latest(directory, label) is None:
        sys.exit(f"No stored evaluation for dataset '{label}' in ARTIFACTS_DIR/evaluations")
    latest = load_latest(label)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    payload = latest.model_dump(exclude={"source"})
    SNAPSHOT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {SNAPSHOT.relative_to(ROOT)} from {latest.file}")


if __name__ == "__main__":
    main()
