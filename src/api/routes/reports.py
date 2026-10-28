"""Stored incidents: GET /reports (list) and GET /reports/{incident_id}."""

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from src.api.deps import get_repository, verify_api_key
from src.api.errors import ApiError
from src.api.schemas import IncidentPage, IncidentSummary, ReportResponse

router = APIRouter()


@router.get(
    "/reports", response_model=IncidentPage, tags=["agent"], dependencies=[Depends(verify_api_key)]
)
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    severity: Literal["serious", "non-serious"] | None = None,
    escalation: Literal["none", "advisory", "blocking", "escalated"] | None = None,
    date_from: Annotated[date | None, Query(description="Inclusive, UTC calendar day")] = None,
    date_to: Annotated[date | None, Query(description="Inclusive, UTC calendar day")] = None,
) -> IncidentPage:
    """Stored incident results, newest first, with optional filters."""
    since = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from else None
    # Exclusive upper bound: start of the day after date_to.
    until = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC) if date_to else None
    items, total = await asyncio.to_thread(
        get_repository().list_incidents,
        limit=limit,
        offset=offset,
        severity=severity,
        escalation=escalation,
        since=since,
        until=until,
    )
    return IncidentPage(
        items=[IncidentSummary(**i) for i in items], total=total, limit=limit, offset=offset
    )


@router.get(
    "/reports/{incident_id}",
    response_model=ReportResponse,
    tags=["agent"],
    dependencies=[Depends(verify_api_key)],
)
async def get_report(
    incident_id: str = Path(..., pattern=r"^INC-\d{4}-[0-9A-F]{6,8}$"),
) -> ReportResponse:
    """Return the stored classification result for `incident_id`."""
    stored = await asyncio.to_thread(get_repository().get_incident, incident_id)
    if stored is None:
        raise ApiError(404, "not_found", "Incident not found")
    return ReportResponse(**stored)
