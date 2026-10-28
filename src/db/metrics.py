"""Aggregate operational metrics computed from logged business requests."""

from collections import Counter

from src.db.models import QueryLog
from src.evaluation.metrics import latency_percentiles


def compute_operational_metrics(queries: list[QueryLog]) -> dict:
    """Latency, outcome distribution, escalation and error rates over the given rows.

    Error rates count HTTP status: 5xx (or a row with an error and no status) as server
    errors, 4xx as client errors. Classification figures use successful /report rows only.
    """
    total = len(queries)

    latencies = [q.latency_ms for q in queries if q.latency_ms is not None]
    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    p50_latency_ms, p95_latency_ms = latency_percentiles(latencies)

    def is_server_error(q: QueryLog) -> bool:
        # 5xx, or an error recorded on a non-4xx row (a stream that failed after its 200).
        status = q.status_code or 0
        return status >= 500 or (bool(q.error) and not 400 <= status < 500)

    server_errors = sum(1 for q in queries if is_server_error(q))
    client_errors = sum(1 for q in queries if q.status_code is not None and 400 <= q.status_code < 500)

    reports = [
        q for q in queries if q.endpoint in ("/report", "/report/stream") and (q.status_code or 200) < 400
    ]
    escalated = [q for q in reports if q.escalated]
    blocking = [q for q in reports if q.escalation_level == "blocking"]
    distribution = dict(Counter(q.severity for q in reports if q.severity))
    distribution["escalated"] = len(escalated)

    confidences = [q.confidence for q in reports if q.confidence is not None]

    return {
        "total_queries": total,
        "avg_latency_ms": avg_latency_ms,
        "p50_latency_ms": p50_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "latency_samples": len(latencies),
        "classification_distribution": distribution,
        "escalation_rate": round(len(escalated) / len(reports), 4) if reports else 0.0,
        "blocking_escalation_rate": round(len(blocking) / len(reports), 4) if reports else 0.0,
        "top_device_classes": dict(Counter(q.device_class for q in reports if q.device_class)),
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "error_rate": round(server_errors / total, 4) if total else 0.0,
        "client_error_rate": round(client_errors / total, 4) if total else 0.0,
    }
