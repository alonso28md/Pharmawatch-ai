"""Shared FastAPI dependencies: singletons, auth, and rate limiting."""

import hmac
import time
from functools import lru_cache

from fastapi import Header
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.agent.graph import run_incident_classification
from src.api.errors import ApiError
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


def _key_matches(provided: str | None, expected: str) -> bool:
    return provided is not None and hmac.compare_digest(provided.encode(), expected.encode())


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Gate for the cost-bearing endpoints (/ask, /report).

    API_KEY set   -> the X-API-Key header must match it.
    API_KEY empty -> the endpoints are disabled unless DEMO_MODE=true is set explicitly.
    """
    settings = get_settings()
    if settings.api_key:
        if not _key_matches(x_api_key, settings.api_key):
            raise ApiError(401, "unauthorized", "Invalid or missing API key")
        return
    if not settings.demo_mode:
        raise ApiError(
            403, "endpoint_disabled", "This endpoint is disabled: configure API_KEY or DEMO_MODE"
        )


async def verify_api_key_strict(x_api_key: str | None = Header(default=None)) -> None:
    """Gate for /evaluate: always requires a configured API_KEY, even in demo mode."""
    settings = get_settings()
    if not settings.api_key:
        raise ApiError(403, "endpoint_disabled", "This endpoint requires API_KEY to be configured")
    if not _key_matches(x_api_key, settings.api_key):
        raise ApiError(401, "unauthorized", "Invalid or missing API key")


def uptime_seconds() -> float:
    return round(time.monotonic() - APP_START_TIME, 1)
