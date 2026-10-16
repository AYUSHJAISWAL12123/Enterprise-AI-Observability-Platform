"""Tests for obs_core.schemas."""

from datetime import UTC, datetime, timedelta

import pytest
from obs_core.schemas import (
    GenAIEvent,
    GenAIMessage,
    MessageRole,
    ModelInfo,
    TokenUsage,
)
from pydantic import ValidationError

MODEL = ModelInfo(provider="google", name="gemini-2.0-flash-001")
MSG_USER = GenAIMessage(role=MessageRole.USER, content="What is the capital of France?")
MSG_ASST = GenAIMessage(role=MessageRole.ASSISTANT, content="Paris.")


def _event(**overrides: object) -> GenAIEvent:
    base: dict[str, object] = {
        "trace_id": "t-001",
        "span_id": "s-001",
        "model": MODEL,
        "messages": [MSG_USER, MSG_ASST],
        "application_name": "test-app",
    }
    base.update(overrides)
    return GenAIEvent(**base)  # type: ignore[arg-type]


class TestTokenUsage:
    def test_total_tokens(self) -> None:
        u = TokenUsage(prompt_tokens=10, completion_tokens=5)
        assert u.total_tokens == 15

    def test_negative_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TokenUsage(prompt_tokens=-1, completion_tokens=0)


class TestGenAIMessage:
    def test_empty_content_rejected(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            GenAIMessage(role=MessageRole.USER, content="   ")

    def test_none_content_allowed(self) -> None:
        msg = GenAIMessage(role=MessageRole.ASSISTANT, content=None)
        assert msg.content is None


class TestGenAIEvent:
    def test_event_id_auto_generated(self) -> None:
        e = _event()
        assert len(e.event_id) == 36  # UUID4

    def test_latency_ms(self) -> None:
        now = datetime.now(tz=UTC)
        e = _event(started_at=now, ended_at=now + timedelta(milliseconds=250))
        assert e.latency_ms == pytest.approx(250.0, rel=1e-3)

    def test_latency_ms_none_when_no_end(self) -> None:
        assert _event().latency_ms is None

    def test_ended_before_started_rejected(self) -> None:
        now = datetime.now(tz=UTC)
        with pytest.raises(ValidationError, match="ended_at"):
            _event(started_at=now, ended_at=now - timedelta(seconds=1))

    def test_last_assistant_message(self) -> None:
        e = _event()
        assert e.last_assistant_message == MSG_ASST

    def test_no_assistant_message(self) -> None:
        e = _event(messages=[MSG_USER])
        assert e.last_assistant_message is None

    def test_empty_messages_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _event(messages=[])
