"""Loader for the golden evaluation dataset."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GoldenCase:
    """A single golden-dataset test case."""

    id: str
    category: str
    subcategory: str
    input: dict = field(default_factory=dict)
    expected: dict = field(default_factory=dict)


def load_golden_dataset(path: Path | str, categories: list[str] | None = None) -> list[GoldenCase]:
    """Load golden-dataset cases from `path`, optionally filtered by category."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    cases = [
        GoldenCase(
            id=case["id"],
            category=case["category"],
            subcategory=case.get("subcategory", ""),
            input=case.get("input", {}),
            expected=case.get("expected", {}),
        )
        for case in raw["cases"]
    ]

    if categories:
        cases = [case for case in cases if case.category in categories]

    logger.info("Loaded %d golden case(s) from %s", len(cases), path)
    return cases
