"""GET /health — service healthcheck."""

import logging

from fastapi import APIRouter

from src.api.deps import get_repository, get_retriever, uptime_seconds
from src.api.schemas import HealthResponse
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Report service status, vector store connectivity, and configured model.

    A plain `def`: FastAPI runs it in the threadpool, so the (blocking) vector-store and
    DB checks never stall the event loop.
    """
    settings = get_settings()
    try:
        document_count = get_retriever().count_indexed_chunks()
        vectorstore_status = "connected"
    except Exception:
        logger.exception("Vector store health check failed")
        document_count = 0
        vectorstore_status = "unavailable"

    try:
        get_repository().list_queries(limit=1)
        database_status = "connected"
    except Exception:
        logger.exception("Database health check failed")
        database_status = "unavailable"

    healthy = vectorstore_status == "connected" and database_status == "connected"
    return HealthResponse(
        status="healthy" if healthy else "degraded",
        version="1.0.0",
        vectorstore=vectorstore_status,
        vectorstore_documents=document_count,
        database=database_status,
        model=settings.anthropic_model,
        uptime_seconds=uptime_seconds(),
    )
