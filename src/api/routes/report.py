"""POST /report — classify a medical device adverse event and determine reporting."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from src.agent.llm import LLMOutputError, LLMUnavailableError
from src.api.deps import (
    get_classification_fn,
    get_classification_stream_fn,
    get_repository,
    limiter,
    verify_api_key,
)
from src.api.middleware import RequestLog, get_request_log
from src.api.schemas import ReportRequest, ReportResponse, Source
from src.api.security import INJECTION_ADVISORY, sanitize_user_text
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate_incident_id() -> str:
    year = datetime.now(UTC).year
    return f"INC-{year}-{uuid.uuid4().hex[:8].upper()}"


def build_report_response(
    incident_id: str, final_state: dict, processing_time_ms: int
) -> ReportResponse:
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
            Source(
                document=s["document"],
                section=s["section"],
                text=s["text"],
                chunk_id=s.get("chunk_id"),
            )
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


def _prepare(payload: ReportRequest, request_log: RequestLog) -> tuple[str, str | None, bool]:
    """Sanitize inputs; returns (description, device_name, injection_suspected)."""
    sanitized = sanitize_user_text(payload.description, field_name="description")
    device = (
        sanitize_user_text(payload.device_name, field_name="device_name")
        if payload.device_name
        else None
    )
    request_log.input_text = sanitized.text[:500]
    suspected = sanitized.injection_suspected or bool(device and device.injection_suspected)
    return sanitized.text, (device.text if device else None) or None, suspected


async def _finish(
    final_state: dict, injection_suspected: bool, processing_time_ms: int, request_log: RequestLog
) -> ReportResponse:
    """Flag suspected injection, fill the request log and persist the incident."""
    if injection_suspected:
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
    await asyncio.to_thread(
        get_repository().save_incident, response.incident_id, response.model_dump()
    )
    return response


@router.post(
    "/report", response_model=ReportResponse, tags=["agent"], dependencies=[Depends(verify_api_key)]
)
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
    description, device_name, suspected = _prepare(payload, request_log)
    start = time.perf_counter()
    # The agent makes blocking model calls: run it off the event loop (B-04).
    final_state = await asyncio.to_thread(
        classify, description, device_name_hint=device_name, device_class_hint=payload.device_class
    )
    return await _finish(
        final_state, suspected, int((time.perf_counter() - start) * 1000), request_log
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


@router.post(
    "/report/stream",
    tags=["agent"],
    dependencies=[Depends(verify_api_key)],
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-sent events"}},
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def report_stream(
    request: Request,
    payload: ReportRequest,
    stream_classify: Annotated[Callable, Depends(get_classification_stream_fn)],
    request_log: Annotated[RequestLog, Depends(get_request_log)],
) -> StreamingResponse:
    """Same as POST /report, streamed as server-sent events.

    Events: `step` {"node", "index"} each time a LangGraph node finishes (the graph's own
    update events, in order); then `result` (a ReportResponse) or `error`
    {"code", "message"}. Validation and auth errors are returned before the stream starts.
    """
    description, device_name, suspected = _prepare(payload, request_log)

    async def events():
        start = time.perf_counter()
        index = 0
        try:
            async for kind, value in iterate_in_threadpool(
                stream_classify(
                    description,
                    device_name_hint=device_name,
                    device_class_hint=payload.device_class,
                )
            ):
                if kind == "step":
                    index += 1
                    yield _sse("step", {"node": value, "index": index})
                else:
                    response = await _finish(
                        value, suspected, int((time.perf_counter() - start) * 1000), request_log
                    )
                    yield _sse("result", response.model_dump())
        except (LLMUnavailableError, LLMOutputError) as exc:
            code = "llm_unavailable" if isinstance(exc, LLMUnavailableError) else "llm_bad_output"
            logger.warning("Streamed /report failed: %s", exc)
            request_log.error = code
            yield _sse(
                "error", {"code": code, "message": "The language model is temporarily unavailable"}
            )
        except Exception:
            logger.exception("Streamed /report failed")
            request_log.error = "internal_error"
            yield _sse("error", {"code": "internal_error", "message": "Internal server error"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
