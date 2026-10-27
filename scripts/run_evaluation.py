#!/usr/bin/env python
"""Run the golden-dataset evaluation harness against the real system and write reports."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT  # noqa: E402
from src.evaluation.harness import EvaluationHarness  # noqa: E402
from src.evaluation.reporter import write_reports  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PharmaWatch AI evaluation harness.")
    parser.add_argument(
        "--dataset", default=str(PROJECT_ROOT / "data" / "golden_dataset.json"), help="Path to golden_dataset.json"
    )
    parser.add_argument("--categories", nargs="*", default=None, help="Filter to specific categories")
    args = parser.parse_args()

    harness = EvaluationHarness(args.dataset)
    result = harness.run(categories=args.categories)

    logger.info(
        "Evaluation complete: %d/%d passed (%.1f%%)",
        result.passed,
        result.total_cases,
        (result.passed / result.total_cases * 100) if result.total_cases else 0.0,
    )
    for metric_name, value in result.metrics.items():
        logger.info("  %s = %s", metric_name, value)

    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    write_reports(
        result,
        markdown_path=docs_dir / "evaluation_report.md",
        json_path=docs_dir / "evaluation_report.json",
        dataset_label=Path(args.dataset).name,
    )


if __name__ == "__main__":
    main()
