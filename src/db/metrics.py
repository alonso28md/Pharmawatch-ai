"""Aggregate operational metrics computed from logged queries."""

from collections import Counter

from src.db.models import QueryLog
from src.evaluation.metrics import latency_percentiles


def compute_operational_metrics(queries: list[QueryLog]) -> dict:
    """Aggregate avg/p95 latency, severity distribution, escalation and error rates."""
    total_queries = len(queries)

    latencies = [q.latency_ms for q in queries if q.latency_ms is not None]
    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    _, p95_latency_ms = latency_percentiles(latencies)

    severities = [q.severity for q in queries if q.severity]
    classification_distribution = dict(Counter(severities))
    escalated_count = sum(1 for q in queries if q.escalated)
    classification_distribution["escalated"] = escalated_count

    device_classes = [q.device_class for q in queries if q.device_class]
    top_device_classes = dict(Counter(device_classes))

    confidences = [q.confidence for q in queries if q.confidence is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    error_count = sum(1 for q in queries if q.error)
    error_rate = round(error_count / total_queries, 4) if total_queries else 0.0

    classifiable_total = len(severities) + escalated_count
    escalation_rate = round(escalated_count / classifiable_total, 4) if classifiable_total else 0.0

    return {
        "total_queries": total_queries,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "classification_distribution": classification_distribution,
        "escalation_rate": escalation_rate,
        "top_device_classes": top_device_classes,
        "avg_confidence": avg_confidence,
        "error_rate": error_rate,
    }
