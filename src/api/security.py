"""Input sanitization and prompt-injection *signalling* for user-supplied text.

The pattern screen is a signal, not a defence: it is trivially bypassed (paraphrase,
other languages, invisible characters) and it produced false positives on legitimate
questions, so it no longer rejects requests. Matches are logged and, for /report,
raised as an advisory escalation. The actual defences live elsewhere: user text is
delimited as untrusted data in every prompt, model output is schema-constrained, and
deadlines/recipients come from the rules table, not from model text.
"""

import logging
import re
from dataclasses import dataclass

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 4000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Zero-width characters are used to split trigger words: replace them with a space.
_INVISIBLE_CHARS = re.compile(r"[​-‏⁠﻿]")
_ROLE_MARKER_LINE = re.compile(r"(?im)^\s*(system|assistant|user)\s*:\s*")

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|above|prior|earlier|all)\b.{0,20}\b(instructions?|rules|context)\b",
        r"\b(ignora|olvida)\b.{0,30}\b(instrucciones|reglas|contexto)\b",
        r"\b(reveal|print|show|repeat)\b.{0,20}\b(system prompt|hidden rules|instructions)\b",
        r"\b(muestra|revela)\b.{0,20}\b(prompt|instrucciones)\b",
        r"\byou are now (in|an?|the)\b.{0,20}\b(mode|assistant|ai|model)\b",
        r"\bact as\b.{0,30}\b(with no|without)\s+restrictions\b",
        r"</?\s*(system|assistant|context|incident_description)\s*>",
        r"\b(note|instruction)s? (to|for) (the )?(ai|assistant|model)\b",
        r"\bnota para el asistente\b",
    ]
]


@dataclass
class SanitizedText:
    text: str
    injection_suspected: bool


def sanitize_user_text(text: str, field_name: str = "input") -> SanitizedText:
    """Strip control/invisible characters and role markers; flag likely prompt injection.

    Raises HTTP 422 only for structural problems (too long, empty after cleaning).
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} exceeds maximum length of {MAX_INPUT_LENGTH} characters",
        )

    cleaned = _CONTROL_CHARS.sub("", _INVISIBLE_CHARS.sub(" ", text))
    cleaned = _ROLE_MARKER_LINE.sub("", cleaned).strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{field_name} is empty"
        )

    suspected = any(p.search(cleaned) for p in _INJECTION_PATTERNS)
    if suspected:
        logger.warning("Possible prompt injection in %s (request not rejected)", field_name)
    return SanitizedText(text=cleaned, injection_suspected=suspected)


INJECTION_ADVISORY = (
    "The input contains text that looks like instructions to the AI (possible prompt "
    "injection); the determination was made treating it as data, but please verify it."
)
