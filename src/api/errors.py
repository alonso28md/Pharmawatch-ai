"""Uniform API error envelope: every error response is {"code", "message", "details"}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.agent.llm import LLMOutputError, LLMUnavailableError

logger = logging.getLogger(__name__)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


class ApiError(Exception):
    """An error raised by application code that maps directly onto the envelope."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_body(code: str, message: str, details: Any = None) -> dict:
    return {"code": code, "message": message, "details": details}


def error_response(
    request: Request | None, status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    """Build the envelope response and tell the request log which error occurred."""
    if request is not None:
        request_log = getattr(request.state, "request_log", None)
        if request_log is not None:
            request_log.error = code
    return JSONResponse(status_code=status_code, content=error_body(code, message, details))


def _validation_details(exc: RequestValidationError) -> list[dict]:
    # Drop the raw "input" echo: it can be large and may contain the rejected payload.
    return [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else code
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            request, 422, "validation_error", "Request validation failed", _validation_details(exc)
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return error_response(request, 429, "rate_limited", "Rate limit exceeded. Please slow down.")

    @app.exception_handler(LLMUnavailableError)
    async def _llm_unavailable(request: Request, exc: LLMUnavailableError) -> JSONResponse:
        logger.warning("LLM unavailable on %s: %s", request.url.path, exc)
        return error_response(
            request, 503, "llm_unavailable", "The language model is temporarily unavailable"
        )

    @app.exception_handler(LLMOutputError)
    async def _llm_bad_output(request: Request, exc: LLMOutputError) -> JSONResponse:
        logger.warning("Unusable LLM output on %s: %s", request.url.path, exc)
        return error_response(
            request, 503, "llm_bad_output", "The language model returned an unusable response"
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url.path)
        return error_response(request, 500, "internal_error", "Internal server error")
