"""GET /reports/{incident_id} — fetch a previously classified incident."""

import asyncio

from fastapi import APIRouter, Depends, Path

from src.api.deps import get_repository, verify_api_key
from src.api.errors import ApiError
from src.api.schemas import ReportResponse

router = APIRouter()


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
