"""Shared helper for structured (JSON) Claude calls used by the agent's nodes."""

import json
import logging
import re

import anthropic

from src.config import get_settings

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Return a lazily-constructed, process-wide Anthropic client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def call_claude_json(system: str, user: str, max_tokens: int = 1024) -> dict:
    """Call Claude and parse a JSON object out of its text response.

    Returns an empty dict (rather than raising) if the response contains no
    parseable JSON object, so callers can apply their own fallback/guardrail.
    """
    settings = get_settings()
    client = get_client()
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next((block.text for block in response.content if block.type == "text"), "")
    return _extract_json(text)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        logger.warning("No JSON object found in Claude response: %s", text[:200])
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from Claude response: %s", text[:200])
        return {}
