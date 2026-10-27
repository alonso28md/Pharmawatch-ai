"""POST /ask — regulatory question answering via the RAG pipeline."""

import asyncio
import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_retriever, limiter, verify_api_key
from src.api.middleware import RequestLog, get_request_log
from src.api.schemas import AskRequest, AskResponse, Source
from src.api.security import sanitize_user_text
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ask", response_model=AskResponse, tags=["rag"], dependencies=[Depends(verify_api_key)])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def ask(
    request: Request,
    payload: AskRequest,
    request_log: Annotated[RequestLog, Depends(get_request_log)],
) -> AskResponse:
    """Answer a regulatory question with citations from the indexed documents."""
    question = sanitize_user_text(payload.question, field_name="question").text
    request_log.input_text = question[:500]

    start = time.perf_counter()
    # The retriever does blocking I/O (embedding + model call): run it off the event loop.
    result = await asyncio.to_thread(get_retriever().answer, question, language=payload.language)
    processing_time_ms = int((time.perf_counter() - start) * 1000)

    request_log.confidence = result.retrieval_score
    request_log.output_summary = result.answer[:500]

    return AskResponse(
        answer=result.answer,
        sources=[
            Source(
                document=s.document, section=s.section, text=s.text,
                relevance_score=s.relevance_score, chunk_id=s.chunk_id or None,
            )
            for s in result.sources
        ],
        retrieval_score=result.retrieval_score,
        processing_time_ms=processing_time_ms,
    )
