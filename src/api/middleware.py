"""Cross-cutting ASGI middleware: timing, security headers, and query logging."""

import json
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


class BodySizeLimitMiddleware:
    """Reject request bodies over `max_bytes` with 413, before the app parses them (S-02).

    Checks Content-Length up front and also counts streamed (chunked) bodies.
    """

    def __init__(self, app, max_bytes_provider: Callable[[], int]):
        self.app = app
        self._max_bytes = max_bytes_provider

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._max_bytes()
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._reject(send, limit)
            return

        # Buffer the (small, bounded) body up front: raising from inside `receive` would be
        # swallowed by FastAPI's body parser and turned into a 400.
        chunks: list[bytes] = []
        received = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            received += len(body)
            if received > limit:
                await self._reject(send, limit)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(send, limit: int) -> None:
        body = json.dumps(
            {"code": "payload_too_large", "message": f"Request body exceeds {limit} bytes", "details": None}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})


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
