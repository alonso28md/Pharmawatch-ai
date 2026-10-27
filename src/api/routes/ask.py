"""POST /ask — regulatory question answering via the RAG pipeline."""

import logging
import time

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_retriever, limiter, verify_api_key
from src.api.schemas import AskRequest, AskResponse, Source
from src.api.security import sanitize_user_text
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ask", response_model=AskResponse, tags=["rag"], dependencies=[Depends(verify_api_key)])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def ask(request: Request, payload: AskRequest) -> AskResponse:
    """Answer a regulatory question with citations from the indexed documents."""
    question = sanitize_user_text(payload.question, field_name="question")

    start = time.perf_counter()
    result = get_retriever().answer(question)
    processing_time_ms = int((time.perf_counter() - start) * 1000)
    request.state.confidence = result.confidence
    request.state.input_text = question[:500]
    request.state.output_summary = result.answer[:500]

    return AskResponse(
        answer=result.answer,
        sources=[
            Source(
                document=s.document, section=s.section, text=s.text, relevance_score=s.relevance_score
            )
            for s in result.sources
        ],
        confidence=result.confidence,
        processing_time_ms=processing_time_ms,
    )
