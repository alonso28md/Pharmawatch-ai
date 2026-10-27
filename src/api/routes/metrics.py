"""GET /metrics — operational metrics aggregated from the real query log."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from src.api.deps import get_repository
from src.api.schemas import OperationalMetricsResponse
from src.db.metrics import compute_operational_metrics

logger = logging.getLogger(__name__)
router = APIRouter()


def _collect(include_demo: bool) -> tuple[dict, int]:
    repository = get_repository()
    rows = repository.list_queries(limit=None, include_demo=include_demo)
    last_24h = repository.list_queries(
        limit=None, include_demo=include_demo, since=datetime.now(UTC) - timedelta(days=1)
    )
    return compute_operational_metrics(rows), len(last_24h)


@router.get("/metrics", response_model=OperationalMetricsResponse, tags=["observability"])
async def operational_metrics(
    include_demo: bool = Query(False, description="Include synthetic rows written by scripts/seed_db.py"),
) -> OperationalMetricsResponse:
    """Aggregate business-request metrics (/ask, /report, /evaluate) from the SQLite query log."""
    aggregates, queries_last_24h = await asyncio.to_thread(_collect, include_demo)
    return OperationalMetricsResponse(
        queries_last_24h=queries_last_24h, include_demo=include_demo, **aggregates
    )
