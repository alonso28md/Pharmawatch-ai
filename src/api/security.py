"""Input sanitization and basic prompt-injection screening for user-supplied text."""

import logging
import re

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 4000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ROLE_MARKER_LINE = re.compile(r"(?im)^\s*(system|assistant|user)\s*:\s*")

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (all|the)?\s*(previous|above|prior)\s*instructions",
        r"disregard (all|the)?\s*(previous|above|prior)\s*instructions",
        r"reveal (your|the)\s*(system prompt|instructions)",
        r"you are now\s+\w+",
        r"act as (an?|the)\s+\w+\s+(with no|without)\s+restrictions",
        r"</?(system|assistant)>",
    ]
]


def sanitize_user_text(text: str, field_name: str = "input") -> str:
    """Strip control characters, neutralize role markers, and screen for prompt injection.

    Raises HTTP 422 if the text is too long or matches a known prompt-injection
    pattern strongly enough to be rejected outright, rather than passed to the LLM.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} exceeds maximum length of {MAX_INPUT_LENGTH} characters",
        )

    cleaned = _CONTROL_CHARS.sub("", text)
    cleaned = _ROLE_MARKER_LINE.sub("", cleaned)
    cleaned = cleaned.strip()

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            logger.warning("Rejected %s: matched prompt-injection pattern %r", field_name, pattern.pattern)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field_name} contains disallowed content",
            )

    return cleaned
