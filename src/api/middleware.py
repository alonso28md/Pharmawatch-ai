"""Cross-cutting pure-ASGI middleware: body-size limit, security headers, observability.

Contract with the routes (explicit, typed): ObservabilityMiddleware creates a
`RequestLog` for every business request and exposes it at `request.state.request_log`;
routes obtain it through the `get_request_log` dependency and fill in outcome fields;
exception handlers set `error`. The middleware itself measures latency and records
the final HTTP status in a try/finally, so failures are always logged.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from starlette.requests import Request

logger = logging.getLogger(__name__)

# Only these endpoints are operational traffic worth logging (not /health, /docs, static...).
BUSINESS_PATHS = ("/ask", "/report", "/report/stream", "/evaluate")


@dataclass
class RequestLog:
    """Typed record a business request fills in; persisted by the observability sink."""

    endpoint: str
    method: str
    status_code: int | None = None
    latency_ms: float | None = None
    input_text: str | None = None
    output_summary: str | None = None
    severity: str | None = None
    device_class: str | None = None
    reportable: bool | None = None
    confidence: float | None = None
    escalated: bool = False
    escalation_level: str | None = None
    error: str | None = None


RequestLogSink = Callable[[RequestLog], None]


def get_request_log(request: Request) -> RequestLog:
    """FastAPI dependency: the request's RequestLog (a detached one if not instrumented)."""
    log = getattr(request.state, "request_log", None)
    return log if log is not None else RequestLog(endpoint=request.url.path, method=request.method)


def _json_response_messages(status: int, payload: dict) -> list[dict]:
    body = json.dumps(payload).encode()
    return [
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        },
        {"type": "http.response.body", "body": body},
    ]


class ObservabilityMiddleware:
    """Times every request, adds X-Process-Time-Ms, and logs business requests (B-05/B-06/B-20)."""

    def __init__(self, app, sink: RequestLogSink):
        self.app = app
        self._sink = sink

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        tracked = scope.get("method") == "POST" and path in BUSINESS_PATHS
        log = RequestLog(endpoint=path, method=scope.get("method", ""))
        if tracked:
            scope.setdefault("state", {})["request_log"] = log

        start = time.perf_counter()
        response_started = False

        async def instrumented_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                log.status_code = message["status"]
                elapsed = (time.perf_counter() - start) * 1000
                headers = list(message.get("headers", []))
                headers.append((b"x-process-time-ms", f"{elapsed:.1f}".encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, instrumented_send)
        except Exception:
            logger.exception("Unhandled exception on %s", path)
            log.error = log.error or "internal_error"
            log.status_code = 500
            if not response_started:
                for message in _json_response_messages(
                    500,
                    {"code": "internal_error", "message": "Internal server error", "details": None},
                ):
                    await send(message)
        finally:
            log.latency_ms = round((time.perf_counter() - start) * 1000, 1)
            if tracked:
                if log.status_code and log.status_code >= 400 and not log.error:
                    log.error = f"http_{log.status_code}"
                try:
                    self._sink(log)
                except Exception:  # logging must never break a response
                    logger.exception("Failed to persist request log for %s", path)


def db_request_log_sink(
    repository_provider: Callable, store_input_text: Callable[[], bool] = lambda: False
) -> RequestLogSink:
    """Sink that writes RequestLog records to the SQLite query log.

    Unless STORE_INPUT_TEXT is enabled, the submitted text is replaced by its length and
    SHA-256 before it reaches the database.
    """

    def sink(log: RequestLog) -> None:
        record = asdict(log)
        text = record.pop("input_text")
        record["input_text"] = text if store_input_text() else None
        if text is not None:
            record["input_length"] = len(text)
            record["input_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        repository_provider().log_query(**record)

    return sink


class SecurityHeadersMiddleware:
    """Adds standard security headers to every response (including middleware-generated 500s).

    The interactive API docs load Swagger UI / ReDoc from a CDN with an inline bootstrap
    script, so those two pages get a CSP that allows exactly that; everything else keeps
    the strict `default-src 'self'`.
    """

    STRICT_CSP = "default-src 'self'"
    DOCS_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
        "worker-src 'self' blob:"
    )
    DOCS_PATHS = ("/docs", "/redoc")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        csp = self.DOCS_CSP if scope.get("path") in self.DOCS_PATHS else self.STRICT_CSP

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"content-security-policy", b"x-frame-options"}
                ]
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", csp.encode()),
                    (b"x-xss-protection", b"0"),
                ]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


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
            await self._reject(scope, send, limit)
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
                await self._reject(scope, send, limit)
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
    async def _reject(scope, send, limit: int) -> None:
        log = scope.get("state", {}).get("request_log")
        if log is not None:
            log.error = "payload_too_large"
        for message in _json_response_messages(
            413,
            {
                "code": "payload_too_large",
                "message": f"Request body exceeds {limit} bytes",
                "details": None,
            },
        ):
            await send(message)
