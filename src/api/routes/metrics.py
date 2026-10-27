"""GET /metrics — operational metrics aggregated from the real query log."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from src.api.deps import get_repository
from src.api.schemas import OperationalMetricsResponse
from src.db.metrics import compute_operational_metrics

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics", response_model=OperationalMetricsResponse, tags=["observability"])
async def operational_metrics() -> OperationalMetricsResponse:
    """Aggregate operational metrics from the SQLite-backed query log (src/db)."""
    queries = get_repository().list_queries(limit=10000)
    aggregates = compute_operational_metrics(queries)

    cutoff = datetime.now(UTC) - timedelta(days=1)
    queries_last_24h = sum(
        1 for q in queries if q.timestamp and q.timestamp.replace(tzinfo=UTC) >= cutoff
    )

    return OperationalMetricsResponse(
        total_queries=aggregates["total_queries"],
        queries_last_24h=queries_last_24h,
        avg_latency_ms=aggregates["avg_latency_ms"],
        p95_latency_ms=aggregates["p95_latency_ms"],
        classification_distribution=aggregates["classification_distribution"],
        escalation_rate=aggregates["escalation_rate"],
        top_device_classes=aggregates["top_device_classes"],
        avg_confidence=aggregates["avg_confidence"],
        error_rate=aggregates["error_rate"],
    )
