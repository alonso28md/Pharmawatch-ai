"""Invariants of the v2 golden dataset (structure, coverage, label consistency, no leakage)."""

import json
from collections import Counter

import pytest

from src.agent.regulatory import reporting_for_category
from src.evaluation.dataset import load_dataset
from src.evaluation.metrics import _normalize, expected_facts
from tests.conftest import PROJECT_ROOT

PATH = PROJECT_ROOT / "data" / "golden_dataset_v2.json"
RAW = json.loads(PATH.read_text(encoding="utf-8"))
CASES = RAW["cases"]
REVIEWED = [c for c in CASES if not c["needs_expert_review"]]
CLASSIFICATION = [c for c in REVIEWED if c["category"] == "classification"]
RAG = [c for c in REVIEWED if c["category"] == "rag"]


def test_size_ids_and_metadata():
    assert len(CASES) >= 150
    assert len({c["id"] for c in CASES}) == len(CASES)
    for c in CASES:
        assert c["split"] in {"dev", "test"}
        assert c["language"] in {"en", "es"}
        assert c["label_source"] == "draft-ai"
        assert isinstance(c["needs_expert_review"], bool)
        if c["needs_expert_review"]:
            assert c.get("review_note")


@pytest.mark.parametrize(
    "category",
    ["public_health_threat", "death", "unanticipated_serious_deterioration", "other_serious"],
)
def test_each_deadline_trigger_has_at_least_ten_reviewed_cases(category):
    assert sum(1 for c in CLASSIFICATION if c["expected"].get("category") == category) >= 10


def test_coverage_of_required_scenarios():
    tags = Counter(t for c in REVIEWED for t in c["tags"])
    assert sum(1 for c in CASES if c["language"] == "es") / len(CASES) >= 0.25
    assert sum(1 for c in RAG if c["expected"].get("abstain")) >= 5
    assert tags["injection"] >= 5
    assert tags["typo"] + tags["noisy"] + tags["long"] >= 4
    assert sum(1 for c in CLASSIFICATION if "device_class" not in c["input"]) >= 50
    assert sum(1 for c in CLASSIFICATION if c["expected"].get("escalate")) >= 10
    assert {c["subcategory"] for c in CLASSIFICATION} >= {
        "unknown_outcome",
        "contradictory",
        "injection",
    }


def test_both_splits_cover_every_classification_label():
    for split in ("dev", "test"):
        labels = {
            c["expected"].get("category", "escalate") for c in CLASSIFICATION if c["split"] == split
        }
        assert labels == {
            "public_health_threat",
            "death",
            "unanticipated_serious_deterioration",
            "other_serious",
            "non_serious",
            "escalate",
        }


def test_no_expected_answer_appears_literally_in_the_question():
    for c in RAG:
        question = _normalize(c["input"]["question"])
        for fact in expected_facts(c["expected"]):
            leaked = [v for v in fact if _normalize(v).strip() in question]
            assert not leaked, f"{c['id']}: {leaked} appears in the question"


def test_classification_labels_match_the_rules_table():
    for c in CLASSIFICATION:
        exp = c["expected"]
        if exp.get("escalate"):
            assert "deadline_days" not in exp and "reportable" not in exp
            continue
        table = reporting_for_category(exp["category"])
        assert exp["reportable"] == table["reportable"], c["id"]
        if table["reportable"]:
            assert exp["deadline_days"] == table["deadline_days"], c["id"]
            assert exp["report_to"] == table["report_to"], c["id"]


def test_loader_filters_split_and_excludes_unreviewed():
    test_only = load_dataset(PATH, split="test")
    assert {c.split for c in test_only.cases} == {"test"}
    assert not any(c.needs_expert_review for c in test_only.cases)
    everything = load_dataset(PATH, split="all", include_unreviewed=True)
    assert len(everything.cases) == len(CASES)
    assert len(load_dataset(PATH).excluded_for_review) == sum(
        c["needs_expert_review"] for c in CASES
    )
