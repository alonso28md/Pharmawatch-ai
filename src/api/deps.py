"""Shared FastAPI dependencies: singletons, auth, and rate limiting."""

import time
from functools import lru_cache

from fastapi import Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.agent.graph import run_incident_classification
from src.config import get_settings
from src.db.repository import Repository
from src.rag.retriever import RagRetriever

limiter = Limiter(key_func=get_remote_address)

APP_START_TIME = time.monotonic()


@lru_cache(maxsize=1)
def get_retriever() -> RagRetriever:
    """Process-wide cached RagRetriever (holds the vector store connection)."""
    return RagRetriever()


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    """Process-wide cached Repository (holds the SQLite engine/session factory)."""
    settings = get_settings()
    return Repository(settings.db_path_absolute)


def log_query_record(record: dict) -> None:
    """Adapter from LoggingMiddleware's raw record shape to Repository.log_query."""
    get_repository().log_query(
        endpoint=record["endpoint"],
        input_text=record.get("input_text"),
        output_summary=record.get("output_summary"),
        severity=record.get("severity"),
        device_class=record.get("device_class"),
        reportable=record.get("reportable"),
        confidence=record.get("confidence"),
        escalated=bool(record.get("escalated")),
        latency_ms=record.get("latency_ms"),
        error=record.get("error"),
    )


def get_classification_fn():
    """Return the incident-classification entrypoint (seam for test overrides)."""
    return run_incident_classification


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional API-key gate: enforced only when API_KEY is configured."""
    settings = get_settings()
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def uptime_seconds() -> float:
    return round(time.monotonic() - APP_START_TIME, 1)
