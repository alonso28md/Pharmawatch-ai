"""Shared FastAPI dependencies: singletons, auth, and rate limiting."""

import time
from functools import lru_cache

from fastapi import Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.agent.graph import run_incident_classification
from src.config import get_settings
from src.rag.retriever import RagRetriever

limiter = Limiter(key_func=get_remote_address)

APP_START_TIME = time.monotonic()


class InMemoryQueryLog:
    """Process-lifetime query log backing /metrics until Phase 5 wires a real DB.

    This is the Phase-4 mock/noop sink referenced in the project's build plan:
    it reflects real requests made during this process's lifetime, but nothing
    is persisted across restarts. Phase 5 replaces it with a SQLite-backed
    repository without changing LoggingMiddleware's public interface.
    """

    def __init__(self, max_records: int = 2000):
        self._records: list[dict] = []
        self._max_records = max_records

    def add(self, record: dict) -> None:
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)

    def all(self) -> list[dict]:
        return list(self._records)


_query_log = InMemoryQueryLog()


def get_query_log() -> InMemoryQueryLog:
    return _query_log


@lru_cache(maxsize=1)
def get_retriever() -> RagRetriever:
    """Process-wide cached RagRetriever (holds the vector store connection)."""
    return RagRetriever()


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
