"""Loader for golden evaluation datasets (v1 and v2 formats)."""

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
    split: str = "test"
    language: str = "en"
    tags: list[str] = field(default_factory=list)
    label_source: str = "unspecified"
    needs_expert_review: bool = False


@dataclass
class GoldenDataset:
    cases: list[GoldenCase]
    version: str
    excluded_for_review: list[str]


def load_dataset(
    path: Path | str,
    categories: list[str] | None = None,
    split: str | None = None,
    include_unreviewed: bool = False,
) -> GoldenDataset:
    """Load cases, optionally filtered by category and split.

    Cases flagged `needs_expert_review` are excluded unless `include_unreviewed` is set:
    their labels are not trusted until a human validates them.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    cases = [
        GoldenCase(
            id=c["id"],
            category=c["category"],
            subcategory=c.get("subcategory", ""),
            input=c.get("input", {}),
            expected=c.get("expected", {}),
            split=c.get("split", "test"),
            language=c.get("language", "en"),
            tags=c.get("tags", []),
            label_source=c.get("label_source", "unspecified"),
            needs_expert_review=bool(c.get("needs_expert_review", False)),
        )
        for c in raw["cases"]
    ]
    if categories:
        cases = [c for c in cases if c.category in categories]
    if split and split != "all":
        cases = [c for c in cases if c.split == split]
    excluded = [] if include_unreviewed else [c.id for c in cases if c.needs_expert_review]
    cases = [c for c in cases if c.id not in excluded]

    logger.info("Loaded %d case(s) from %s (%d excluded pending expert review)", len(cases), path, len(excluded))
    return GoldenDataset(cases=cases, version=str(raw.get("version", "1")), excluded_for_review=excluded)


def load_golden_dataset(path: Path | str, categories: list[str] | None = None) -> list[GoldenCase]:
    """Backward-compatible helper: all reviewed cases, all splits."""
    return load_dataset(path, categories=categories).cases
