"""GET /metrics — operational metrics aggregated from recent requests."""

import logging
import time
from collections import Counter

from fastapi import APIRouter

from src.api.deps import get_query_log
from src.api.schemas import OperationalMetricsResponse
from src.evaluation.metrics import latency_percentiles

logger = logging.getLogger(__name__)
router = APIRouter()

_SECONDS_PER_DAY = 86400


@router.get("/metrics", response_model=OperationalMetricsResponse, tags=["observability"])
async def operational_metrics() -> OperationalMetricsResponse:
    """Aggregate operational metrics over requests seen during this process's lifetime.

    Backed by the in-memory query log (see src/api/deps.py); Phase 5 adds a
    SQLite-backed repository with the same aggregation shape for durability
    across restarts.
    """
    records = get_query_log().all()

    total_queries = len(records)
    now = time.time()
    queries_last_24h = sum(
        1 for r in records if r.get("timestamp") and now - r["timestamp"] <= _SECONDS_PER_DAY
    )

    latencies = [r["latency_ms"] for r in records if r.get("latency_ms") is not None]
    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    _, p95_latency_ms = latency_percentiles(latencies)

    severities = [r["severity"] for r in records if r.get("severity")]
    classification_distribution = dict(Counter(severities))
    escalated_count = sum(1 for r in records if r.get("escalated"))
    classification_distribution["escalated"] = escalated_count

    device_classes = [r["device_class"] for r in records if r.get("device_class")]
    top_device_classes = dict(Counter(device_classes))

    confidences = [r["confidence"] for r in records if r.get("confidence") is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    error_count = sum(1 for r in records if r.get("status_code", 200) >= 500 or r.get("error"))
    error_rate = round(error_count / total_queries, 4) if total_queries else 0.0

    classifiable_total = len(severities) + escalated_count
    escalation_rate = round(escalated_count / classifiable_total, 4) if classifiable_total else 0.0

    return OperationalMetricsResponse(
        total_queries=total_queries,
        queries_last_24h=queries_last_24h,
        avg_latency_ms=avg_latency_ms,
        p95_latency_ms=p95_latency_ms,
        classification_distribution=classification_distribution,
        escalation_rate=escalation_rate,
        top_device_classes=top_device_classes,
        avg_confidence=avg_confidence,
        error_rate=error_rate,
    )
