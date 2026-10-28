"""The single, injectable LLM client used by the agent, the RAG retriever and the evaluator.

All JSON-producing calls use structured outputs (`output_config.format` with a JSON
schema), so the response is schema-valid JSON or the call is reported as a failure -
it never silently degrades to a regex guess. Forced `tool_choice` is not used because
current models reject it, and sampling parameters (`temperature`) are not sent because
the API no longer accepts them.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Protocol

import anthropic

from src.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """The model API could not produce a response (network, timeout, 5xx, auth, refusal)."""


class LLMOutputError(ValueError):
    """The model answered, but not with output matching the requested schema."""


@dataclass
class Usage:
    """Running token/call counters (shared by every call made through one client)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "calls": self.calls,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            }


class LLMClient(Protocol):
    """What the rest of the system needs from a language model."""

    usage: Usage

    def complete_text(self, system: str, user: str, max_tokens: int = 4096) -> str: ...

    def complete_json(
        self, system: str, user: str, schema: dict, max_tokens: int = 4096
    ) -> dict: ...

    def last_usage(self) -> dict[str, int]:
        """Tokens of the most recent call made by the current thread."""
        ...


def _status_error_detail(exc: anthropic.APIStatusError) -> str:
    error = (exc.body or {}).get("error", {}) if isinstance(exc.body, dict) else {}
    message = str(error.get("message") or "")[:200]
    return f"{type(exc).__name__} {exc.status_code} {error.get('type', '')}: {message}".strip()


class AnthropicLLMClient:
    """LLMClient backed by the Anthropic Messages API."""

    def __init__(self, model: str | None = None, client: anthropic.Anthropic | None = None):
        settings = get_settings()
        self.model = model or settings.anthropic_model
        self._client = client or anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self.usage = Usage()
        self._local = threading.local()

    def last_usage(self) -> dict[str, int]:
        return getattr(self._local, "last", {"input_tokens": 0, "output_tokens": 0})

    def _create(self, system: str, user: str, max_tokens: int, **extra):
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                **extra,
            )
        except anthropic.APIStatusError as exc:
            # 4xx/5xx after the SDK's retries. Keep the provider's status and message (no
            # secrets) - e.g. an exhausted credit balance arrives as a 400 and must be visible.
            detail = _status_error_detail(exc)
            logger.warning("LLM call failed: %s", detail)
            raise LLMUnavailableError(detail) from exc
        except anthropic.APIConnectionError as exc:  # includes APITimeoutError
            logger.warning("LLM call failed: %s", type(exc).__name__)
            raise LLMUnavailableError(type(exc).__name__) from exc

        self.usage.add(response.usage.input_tokens, response.usage.output_tokens)
        self._local.last = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        if response.stop_reason == "refusal":
            raise LLMUnavailableError("model declined the request")
        if response.stop_reason == "max_tokens":
            raise LLMOutputError("response truncated at max_tokens")
        return response

    @staticmethod
    def _text(response) -> str:
        return "".join(block.text for block in response.content if block.type == "text")

    def complete_text(self, system: str, user: str, max_tokens: int = 4096) -> str:
        return self._text(self._create(system, user, max_tokens))

    def complete_json(self, system: str, user: str, schema: dict, max_tokens: int = 4096) -> dict:
        response = self._create(
            system,
            user,
            max_tokens,
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = self._text(response)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMOutputError("response is not valid JSON") from exc
        if not isinstance(data, dict):
            raise LLMOutputError("response JSON is not an object")
        return data


_default_client: LLMClient | None = None
_default_lock = threading.Lock()


def get_llm_client() -> LLMClient:
    """Return the process-wide LLM client (constructed lazily)."""
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = AnthropicLLMClient()
        return _default_client


def set_llm_client(client: LLMClient | None) -> None:
    """Replace (or with None, reset) the process-wide client - used by tests and tools."""
    global _default_client
    with _default_lock:
        _default_client = client
