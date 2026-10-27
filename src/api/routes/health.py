"""GET /health — service healthcheck."""

import logging

from fastapi import APIRouter

from src.api.deps import get_retriever, uptime_seconds
from src.api.schemas import HealthResponse
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Report service status, vector store connectivity, and configured model."""
    settings = get_settings()
    try:
        document_count = get_retriever().count_indexed_chunks()
        vectorstore_status = "connected"
    except Exception:
        logger.exception("Vector store health check failed")
        document_count = 0
        vectorstore_status = "unavailable"

    return HealthResponse(
        status="healthy" if vectorstore_status == "connected" else "degraded",
        version="1.0.0",
        vectorstore=vectorstore_status,
        vectorstore_documents=document_count,
        database="connected",
        model=settings.anthropic_model,
        uptime_seconds=uptime_seconds(),
    )
