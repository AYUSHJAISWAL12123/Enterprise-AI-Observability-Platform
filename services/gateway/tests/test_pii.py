"""Tests for gateway._pii (PII redaction)."""

import pytest
from gateway._pii import redact_event, redact_text
from obs_core.schemas import GenAIEvent, GenAIMessage, MessageRole, ModelInfo


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Emails
        ("Contact me at alice@example.com please", "Contact me at [EMAIL] please"),
        # Phone numbers
        ("Call 555-867-5309 now", "Call [PHONE] now"),
        ("Phone: (800) 555-1234", "Phone: [PHONE]"),
        # SSN
        ("SSN is 123-45-6789", "SSN is [SSN]"),
        # IPv4
        ("Server at 192.168.1.100", "Server at [IP_ADDRESS]"),
        # Clean text is unchanged
        ("Hello world", "Hello world"),
        # Multiple PIIs in one string
        (
            "Email alice@example.com or call 555-867-5309",
            "Email [EMAIL] or call [PHONE]",
        ),
    ],
)
def test_redact_text(text: str, expected: str) -> None:
    assert redact_text(text) == expected


def test_redact_event_cleans_all_messages() -> None:
    event = GenAIEvent(
        trace_id="t-1",
        span_id="s-1",
        model=ModelInfo(provider="google", name="gemini-2.0-flash-001"),
        messages=[
            GenAIMessage(role=MessageRole.USER, content="My email is bob@test.org"),
            GenAIMessage(role=MessageRole.ASSISTANT, content="Got it!"),
        ],
        application_name="test-app",
    )
    clean = redact_event(event)

    assert clean.messages[0].content == "My email is [EMAIL]"
    assert clean.messages[1].content == "Got it!"
    # Original is untouched (immutable copy)
    assert event.messages[0].content == "My email is bob@test.org"


def test_redact_event_preserves_event_id() -> None:
    event = GenAIEvent(
        trace_id="t-2",
        span_id="s-2",
        model=ModelInfo(provider="google", name="gemini-2.0-flash-001"),
        messages=[GenAIMessage(role=MessageRole.USER, content="hello")],
        application_name="test-app",
    )
    clean = redact_event(event)
    assert clean.event_id == event.event_id


def test_redact_message_with_none_content_is_noop() -> None:
    from gateway._pii import redact_message

    msg = GenAIMessage(role=MessageRole.ASSISTANT, content=None)
    result = redact_message(msg)
    assert result.content is None
