"""Tests for the SQLAlchemy models, repository CRUD, and operational metrics."""

from src.db.metrics import compute_operational_metrics
from src.db.repository import Repository


def _repo(tmp_path) -> Repository:
    return Repository(tmp_path / "test.db")


def test_log_and_list_queries_roundtrip(tmp_path):
    repository = _repo(tmp_path)

    query_id = repository.log_query(
        endpoint="/ask",
        input_text="What is the deadline?",
        output_summary="15 days",
        confidence=0.9,
        latency_ms=1200.5,
    )
    assert query_id > 0

    rows = repository.list_queries()
    assert len(rows) == 1
    assert rows[0].endpoint == "/ask"
    assert rows[0].input_text == "What is the deadline?"
    assert rows[0].confidence == 0.9


def test_list_queries_orders_newest_first(tmp_path):
    repository = _repo(tmp_path)
    for i in range(3):
        repository.log_query(endpoint="/ask", input_text=f"q{i}")

    rows = repository.list_queries()
    assert [r.input_text for r in rows] == ["q2", "q1", "q0"]


def test_log_and_list_evaluation_runs(tmp_path):
    repository = _repo(tmp_path)
    run_id = repository.log_evaluation_run(
        total_cases=30,
        passed=29,
        failed=1,
        metrics_json='{"retrieval_accuracy": 1.0}',
        report_path="docs/x.md",
    )
    assert run_id > 0

    runs = repository.list_evaluation_runs()
    assert len(runs) == 1
    assert runs[0].total_cases == 30
    assert runs[0].passed == 29


def test_compute_operational_metrics_aggregates_correctly(tmp_path):
    repository = _repo(tmp_path)
    repository.log_query(
        endpoint="/report",
        severity="serious",
        device_class="IIb",
        reportable=True,
        confidence=0.9,
        escalated=False,
        latency_ms=1000,
    )
    repository.log_query(
        endpoint="/report",
        severity="non-serious",
        device_class="I",
        reportable=False,
        confidence=0.95,
        escalated=False,
        latency_ms=2000,
    )
    repository.log_query(endpoint="/report", escalated=True, latency_ms=3000)
    repository.log_query(endpoint="/ask", error="boom", latency_ms=500)

    rows = repository.list_queries()
    metrics = compute_operational_metrics(rows)

    assert metrics["total_queries"] == 4
    assert metrics["avg_latency_ms"] == 1625.0
    assert metrics["classification_distribution"] == {
        "serious": 1,
        "non-serious": 1,
        "escalated": 1,
    }
    assert metrics["escalation_rate"] == round(1 / 3, 4)
    assert metrics["top_device_classes"] == {"IIb": 1, "I": 1}
    assert metrics["error_rate"] == 0.25


def test_compute_operational_metrics_handles_empty_list():
    metrics = compute_operational_metrics([])
    assert metrics["total_queries"] == 0
    assert metrics["avg_latency_ms"] == 0.0
    assert metrics["escalation_rate"] == 0.0
    assert metrics["error_rate"] == 0.0
