"""POST /report — classify a medical device adverse event and determine reporting."""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_classification_fn, get_repository, limiter, verify_api_key
from src.api.middleware import RequestLog, get_request_log
from src.api.schemas import ReportRequest, ReportResponse, Source
from src.api.security import INJECTION_ADVISORY, sanitize_user_text
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate_incident_id() -> str:
    year = datetime.now(UTC).year
    return f"INC-{year}-{uuid.uuid4().hex[:8].upper()}"


def build_report_response(incident_id: str, final_state: dict, processing_time_ms: int) -> ReportResponse:
    return ReportResponse(
        incident_id=incident_id,
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
            Source(document=s["document"], section=s["section"], text=s["text"], chunk_id=s.get("chunk_id"))
            for s in (final_state.get("rag_sources") or [])
        ],
        draft_notification=final_state.get("draft_notification"),
        processing_time_ms=processing_time_ms,
    )


def _flag_possible_injection(final_state: dict) -> dict:
    """Surface a suspected injection as an advisory escalation (never a silent change)."""
    reason = " ".join(filter(None, [final_state.get("escalation_reason"), INJECTION_ADVISORY]))
    level = final_state.get("escalation_level", "none")
    return {
        **final_state,
        "escalated_to_human": True,
        "escalation_level": "blocking" if level == "blocking" else "advisory",
        "escalation_reason": reason,
    }


@router.post("/report", response_model=ReportResponse, tags=["agent"], dependencies=[Depends(verify_api_key)])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def report(
    request: Request,
    payload: ReportRequest,
    classify: Annotated[Callable, Depends(get_classification_fn)],
    request_log: Annotated[RequestLog, Depends(get_request_log)],
) -> ReportResponse:
    """Classify an adverse event description and determine its reporting requirements.

    Every classified incident is persisted (without its free-text description) and can
    be fetched again with GET /reports/{incident_id}.
    """
    sanitized = sanitize_user_text(payload.description, field_name="description")
    device = sanitize_user_text(payload.device_name, field_name="device_name") if payload.device_name else None
    description, device_name = sanitized.text, device.text if device else None
    request_log.input_text = description[:500]

    start = time.perf_counter()
    # The agent makes blocking model calls: run it off the event loop (B-04).
    final_state = await asyncio.to_thread(
        classify, description, device_name_hint=device_name or None, device_class_hint=payload.device_class
    )
    processing_time_ms = int((time.perf_counter() - start) * 1000)
    if sanitized.injection_suspected or (device and device.injection_suspected):
        final_state = _flag_possible_injection(final_state)

    request_log.severity = final_state.get("severity")
    request_log.reportable = final_state.get("reportable")
    request_log.escalated = bool(final_state.get("escalated_to_human"))
    request_log.escalation_level = final_state.get("escalation_level")
    request_log.device_class = final_state.get("device_class")
    request_log.confidence = final_state.get("severity_confidence")
    request_log.output_summary = (
        f"category={final_state.get('incident_category')}, reportable={final_state.get('reportable')}, "
        f"deadline_days={final_state.get('deadline_days')}, escalation={final_state.get('escalation_level')}"
    )

    response = build_report_response(_generate_incident_id(), final_state, processing_time_ms)
    await asyncio.to_thread(get_repository().save_incident, response.incident_id, response.model_dump())
    return response
