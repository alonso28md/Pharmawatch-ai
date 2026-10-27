"""Cross-cutting ASGI middleware: timing, security headers, and query logging."""

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

QueryLogSink = Callable[[dict], None]


def _default_log_sink(record: dict) -> None:
    """Fallback sink (used only if no DB-backed sink is injected): logs via `logging`."""
    logger.info(
        "query endpoint=%s status=%s latency_ms=%s",
        record["endpoint"],
        record["status_code"],
        record["latency_ms"],
    )


class TimingMiddleware(BaseHTTPMiddleware):
    """Measures request latency and attaches it as an `X-Process-Time-Ms` header."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{latency_ms:.1f}"
        request.state.latency_ms = latency_ms
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security response headers to every response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-XSS-Protection"] = "0"
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request/response to a pluggable sink (a real DB-backed repository by default)."""

    def __init__(self, app, sink: QueryLogSink | None = None):
        super().__init__(app)
        self._sink = sink or _default_log_sink

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception while processing %s", request.url.path)
            raise

        latency_ms = getattr(request.state, "latency_ms", None)
        self._sink(
            {
                "timestamp": time.time(),
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "input_text": getattr(request.state, "input_text", None),
                "output_summary": getattr(request.state, "output_summary", None),
                "severity": getattr(request.state, "severity", None),
                "reportable": getattr(request.state, "reportable", None),
                "escalated": getattr(request.state, "escalated", False),
                "device_class": getattr(request.state, "device_class", None),
                "confidence": getattr(request.state, "confidence", None),
                "error": getattr(request.state, "error", None),
            }
        )
        return response
