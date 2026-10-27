#!/usr/bin/env python
"""Run the golden-dataset evaluation harness against the real system.

Makes real (paid) model calls. Results are written as JSON to ARTIFACTS_DIR/evaluations/;
nothing is written under docs/ and nothing is logged to the operational query DB.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.evaluation.harness import EvaluationHarness  # noqa: E402
from src.evaluation.reporter import write_json_report  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the PharmaWatch AI evaluation harness.")
    parser.add_argument(
        "--dataset",
        default="default",
        help=f"Dataset name ({', '.join(sorted(settings.evaluation_dataset_files))}) or a JSON file path",
    )
    parser.add_argument("--categories", nargs="*", default=None, help="Filter to specific categories")
    args = parser.parse_args()

    named = settings.evaluation_dataset_files
    dataset_path = named.get(args.dataset) or Path(args.dataset)
    label = args.dataset if args.dataset in named else dataset_path.stem

    result = EvaluationHarness(dataset_path).run(categories=args.categories)

    logger.info("Evaluation complete: %d/%d passed", result.passed, result.total_cases)
    for metric_name, value in result.metrics.items():
        logger.info("  %s = %s", metric_name, value)

    path = write_json_report(result, settings.artifacts_dir_absolute, label)
    logger.info("Wrote %s", path)


if __name__ == "__main__":
    main()
