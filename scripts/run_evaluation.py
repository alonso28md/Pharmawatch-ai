#!/usr/bin/env python
"""Run a golden-dataset evaluation against the real system.

Makes real (paid) model calls: roughly 2 per RAG case (answer + judge) and 3 per
classification case (extract, assess, draft) per repetition. Results are written as JSON
to ARTIFACTS_DIR/evaluations/; nothing is written under docs/ or to the query DB.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.evaluation.dataset import load_dataset  # noqa: E402
from src.evaluation.harness import EvaluationHarness  # noqa: E402
from src.evaluation.reporter import render_markdown, write_json_report  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def estimate_calls(dataset_path: Path, split: str, categories, repetitions: int) -> dict:
    cases = load_dataset(dataset_path, categories=categories, split=split).cases
    rag = sum(1 for c in cases if c.category == "rag")
    cls = len(cases) - rag
    return {"rag_cases": rag, "classification_cases": cls,
            "max_calls": repetitions * (2 * rag + 3 * cls)}


def main() -> None:
    settings = get_settings()
    named = settings.evaluation_dataset_files
    parser = argparse.ArgumentParser(description="Run the PharmaWatch AI evaluation harness.")
    parser.add_argument("--dataset", default="v2", help=f"Dataset name ({', '.join(sorted(named))}) or JSON path")
    parser.add_argument("--split", default="test", choices=["dev", "test", "all"])
    parser.add_argument("--categories", nargs="*", default=None, help="Filter: rag and/or classification")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4, help="Concurrent cases (affects latency figures)")
    parser.add_argument("--reviewer", action="store_true", help="Enable the reviewer node")
    parser.add_argument("--estimate-only", action="store_true", help="Print the call estimate and exit")
    args = parser.parse_args()

    dataset_path = named.get(args.dataset) or Path(args.dataset)
    label = args.dataset if args.dataset in named else dataset_path.stem
    estimate = estimate_calls(dataset_path, args.split, args.categories, args.repetitions)
    logger.info("Planned run: %s", estimate)
    if args.estimate_only:
        return

    harness = EvaluationHarness(
        dataset_path, split=args.split, repetitions=args.repetitions,
        max_workers=args.workers, reviewer_enabled=args.reviewer,
    )
    result = harness.run(categories=args.categories)
    print(render_markdown(result, result.metadata["timestamp"], label))
    path = write_json_report(result, settings.artifacts_dir_absolute, label + ("_reviewer" if args.reviewer else ""))
    logger.info("Usage: %s", result.metadata["usage"])
    logger.info("Wrote %s", path)


if __name__ == "__main__":
    main()
