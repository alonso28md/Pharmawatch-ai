"""POST /report — classify a medical device adverse event and determine reporting."""

import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_classification_fn, limiter, verify_api_key
from src.api.schemas import ReportRequest, ReportResponse, Source
from src.api.security import sanitize_user_text
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate_incident_id() -> str:
    year = datetime.now(UTC).year
    return f"INC-{year}-{uuid.uuid4().hex[:8].upper()}"


@router.post("/report", response_model=ReportResponse, tags=["agent"], dependencies=[Depends(verify_api_key)])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def report(
    request: Request,
    payload: ReportRequest,
    classify: Annotated[Callable, Depends(get_classification_fn)],
) -> ReportResponse:
    """Classify an adverse event description and determine its reporting requirements."""
    description = sanitize_user_text(payload.description, field_name="description")
    device_name = (
        sanitize_user_text(payload.device_name, field_name="device_name") if payload.device_name else None
    )

    start = time.perf_counter()
    final_state = classify(
        description,
        device_name_hint=device_name or None,
        device_class_hint=payload.device_class,
    )
    processing_time_ms = int((time.perf_counter() - start) * 1000)

    request.state.severity = final_state.get("severity")
    request.state.reportable = final_state.get("reportable")
    request.state.escalated = final_state.get("escalated_to_human", False)
    request.state.device_class = final_state.get("device_class")
    request.state.confidence = final_state.get("severity_confidence")
    request.state.input_text = description[:500]
    request.state.output_summary = (
        f"category={final_state.get('incident_category')}, reportable={final_state.get('reportable')}, "
        f"deadline_days={final_state.get('deadline_days')}"
    )

    return ReportResponse(
        incident_id=_generate_incident_id(),
        severity=final_state.get("severity"),
        severity_confidence=final_state.get("severity_confidence"),
        severity_reasoning=final_state.get("severity_reasoning"),
        incident_category=final_state.get("incident_category"),
        reportable=final_state.get("reportable"),
        report_to=final_state.get("report_to"),
        deadline_days=final_state.get("deadline_days"),
        deadline_rule=final_state.get("deadline_rule"),
        device_class=final_state.get("device_class"),
        device_class_source=final_state.get("device_class_source"),
        classification_rule=final_state.get("classification_rule"),
        escalated_to_human=final_state.get("escalated_to_human", False),
        escalation_level=final_state.get("escalation_level", "none"),
        escalation_reason=final_state.get("escalation_reason"),
        rag_sources=[
            Source(document=s["document"], section=s["section"], text=s["text"])
            for s in (final_state.get("rag_sources") or [])
        ],
        draft_notification=final_state.get("draft_notification"),
        processing_time_ms=processing_time_ms,
    )
