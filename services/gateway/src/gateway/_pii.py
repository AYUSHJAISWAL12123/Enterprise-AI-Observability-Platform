"""PII redaction applied to GenAIEvent message content before storage.

We redact rather than drop messages so downstream evaluators can still
judge coherence and relevance.  The placeholder tokens (e.g. ``[EMAIL]``)
are stable so regex-based metrics won't break on redacted spans.

Patterns are intentionally conservative — false positives (redacting a
non-PII string that looks like an email) are preferable to false negatives
(leaking real PII into BigQuery).

This module is pure-function / stateless so it is trivial to unit test and
to swap for a more sophisticated scanning library (e.g. Google Cloud DLP)
without changing callers.
"""

from __future__ import annotations

import re

from obs_core.schemas import GenAIEvent, GenAIMessage

# ── Compiled patterns (compiled once at import, not per-call) ─────────────────

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email addresses
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
        "[EMAIL]",
    ),
    # US/international phone numbers (various separators)
    (
        re.compile(
            r"""
            (?<!\d)                     # not preceded by a digit
            (\+?1[\s\-.]?)?             # optional country code
            \(?\d{3}\)?[\s\-.]?         # area code
            \d{3}[\s\-.]?\d{4}          # local number
            (?!\d)                      # not followed by a digit
            """,
            re.VERBOSE,
        ),
        "[PHONE]",
    ),
    # Credit card numbers (Luhn-like: 13-16 digits with separators)
    (
        re.compile(r"\b(?:\d[ \-]?){13,16}\b"),
        "[CREDIT_CARD]",
    ),
    # US Social Security Numbers
    (
        re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"),
        "[SSN]",
    ),
    # IPv4 addresses
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        "[IP_ADDRESS]",
    ),
]


def redact_text(text: str) -> str:
    """Apply all PII patterns to a string; return redacted copy.

    Each pattern is applied in sequence so overlapping matches (e.g. a phone
    number embedded in a credit-card-like string) are handled predictably.
    """
    for pattern, placeholder in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def redact_message(message: GenAIMessage) -> GenAIMessage:
    """Return a new GenAIMessage with PII removed from content."""
    if message.content is None:
        return message
    redacted = redact_text(message.content)
    # model_copy avoids re-validation of fields we haven't touched.
    return message.model_copy(update={"content": redacted})


def redact_event(event: GenAIEvent) -> GenAIEvent:
    """Return a new GenAIEvent with PII redacted from all message contents.

    We never mutate the original; callers can hold onto the raw event for
    logging purposes (e.g. audit trail) before publishing the clean copy.
    """
    redacted_messages = [redact_message(m) for m in event.messages]
    return event.model_copy(update={"messages": redacted_messages})
