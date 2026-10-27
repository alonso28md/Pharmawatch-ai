"""Tests for the evaluation harness, metrics, and reporter."""

import json

from src.evaluation import metrics
from src.evaluation.dataset import load_golden_dataset
from src.evaluation.harness import EvaluationHarness
from src.evaluation.reporter import render_markdown, to_json_dict
from tests.conftest import PROJECT_ROOT, requires_api_key

GOLDEN_DATASET_PATH = PROJECT_ROOT / "data" / "golden_dataset.json"


# --- dataset loader ---------------------------------------------------------------


def test_load_golden_dataset_has_30_cases_split_evenly():
    cases = load_golden_dataset(GOLDEN_DATASET_PATH)
    assert len(cases) == 30

    rag_cases = [c for c in cases if c.category == "rag"]
    classification_cases = [c for c in cases if c.category == "classification"]
    assert len(rag_cases) == 15
    assert len(classification_cases) == 15

    for subcat in ("deadlines", "classification", "procedures"):
        assert sum(1 for c in rag_cases if c.subcategory == subcat) == 5
    for subcat in ("clearly_serious", "clearly_non_serious", "ambiguous"):
        assert sum(1 for c in classification_cases if c.subcategory == subcat) == 5


def test_load_golden_dataset_filters_by_category():
    cases = load_golden_dataset(GOLDEN_DATASET_PATH, categories=["rag"])
    assert all(c.category == "rag" for c in cases)
    assert len(cases) == 15


# --- metrics (pure functions, synthetic data) --------------------------------------


def test_retrieval_accuracy_counts_matching_source_documents():
    results = [
        {"expected": {"source_document": "MDR 2017/745"}, "sources": [{"document": "MDR 2017/745 Annex VIII"}]},
        {"expected": {"source_document": "AEMPS"}, "sources": [{"document": "MDR 2017/745"}]},
    ]
    assert metrics.retrieval_accuracy(results) == 0.5


def test_source_citation_rate():
    results = [{"sources": [{"document": "x"}]}, {"sources": []}]
    assert metrics.source_citation_rate(results) == 0.5


def test_classification_accuracy_only_counts_graded_cases():
    results = [
        {"expected": {"severity": "serious"}, "predicted_severity": "serious"},
        {"expected": {"severity": "non-serious"}, "predicted_severity": "serious"},
        {"expected": {"should_escalate": True}, "predicted_severity": None},
    ]
    assert metrics.classification_accuracy(results) == 0.5


def test_reportability_accuracy():
    results = [
        {"expected": {"reportable": True}, "predicted_reportable": True},
        {"expected": {"reportable": False}, "predicted_reportable": True},
    ]
    assert metrics.reportability_accuracy(results) == 0.5


def test_escalation_appropriateness():
    results = [
        {"expected": {"should_escalate": True}, "escalated_to_human": True},
        {"expected": {"should_escalate": True}, "escalated_to_human": False},
        {"expected": {"severity": "serious"}, "escalated_to_human": False},
    ]
    assert metrics.escalation_appropriateness(results) == 0.5


def test_latency_percentiles():
    p50, p95 = metrics.latency_percentiles([100, 200, 300, 400, 500])
    assert p50 == 300
    assert p95 == 480


def test_meets_threshold():
    assert metrics.meets_threshold("retrieval_accuracy", 0.9) is True
    assert metrics.meets_threshold("retrieval_accuracy", 0.5) is False
    assert metrics.meets_threshold("hallucination_rate", 0.05) is True
    assert metrics.meets_threshold("latency_p50_ms", 3000) is True


# --- reporter -----------------------------------------------------------------------


def test_render_markdown_and_json_report(tmp_path):
    from src.evaluation.harness import EvaluationRunResult

    result = EvaluationRunResult(
        total_cases=2,
        passed=1,
        failed=1,
        metrics={"retrieval_accuracy": 0.9, "hallucination_rate": 0.05, "latency_p50_ms": 3000},
        failed_cases=[{"case_id": "case_999", "reason": "example failure"}],
        model="claude-sonnet-5-5",
    )

    markdown = render_markdown(result, "2026-01-01T00:00:00Z", "golden_dataset.json")
    assert "PharmaWatch AI" in markdown
    assert "case_999" in markdown
    assert "90.0%" in markdown

    payload = to_json_dict(result, "2026-01-01T00:00:00Z", "golden_dataset.json")
    assert payload["summary"]["total_cases"] == 2
    assert payload["metrics"]["retrieval_accuracy"] == 0.9
    json.dumps(payload)  # must be JSON-serializable


# --- full harness integration (requires ANTHROPIC_API_KEY) -------------------------


@requires_api_key
def test_harness_runs_small_live_slice(tmp_path):
    tiny_dataset = {
        "cases": [
            {
                "id": "t_rag_1",
                "category": "rag",
                "subcategory": "deadlines",
                "input": {"question": "What is the reporting deadline for a serious incident under the MDR?"},
                "expected": {
                    "answer_contains": ["15 days"],
                    "source_document": "MDR 2017/745 (Articles 87-92, Vigilance)",
                    "source_section": "Article 87",
                },
            },
            {
                "id": "t_cls_1",
                "category": "classification",
                "subcategory": "clearly_non_serious",
                "input": {
                    "incident_description": (
                        "A nurse noticed that a disposable syringe plunger was slightly stiff "
                        "to push during a routine injection. No incorrect dose was delivered, "
                        "the patient experienced no harm, and the syringe was discarded with "
                        "no clinical impact."
                    )
                },
                "expected": {"severity": "non-serious", "reportable": False},
            },
        ]
    }
    dataset_path = tmp_path / "tiny_dataset.json"
    dataset_path.write_text(json.dumps(tiny_dataset), encoding="utf-8")

    harness = EvaluationHarness(dataset_path)
    result = harness.run()

    assert result.total_cases == 2
    assert "retrieval_accuracy" in result.metrics
    assert "classification_accuracy" in result.metrics
    assert result.metrics["latency_p50_ms"] >= 0
