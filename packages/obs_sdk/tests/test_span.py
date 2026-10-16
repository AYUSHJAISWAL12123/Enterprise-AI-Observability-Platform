"""Tests for obs_sdk._span (Span context manager)."""

import pytest
from obs_core.schemas import GenAIEvent, GenAIMessage, MessageRole, ModelInfo, TokenUsage
from obs_sdk._span import Span


class CapturingClient:
    """Test double that captures sent events and can simulate failures."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[GenAIEvent] = []
        self._fail = fail

    async def send_event(self, event: GenAIEvent) -> None:
        if self._fail:
            raise RuntimeError("gateway down")
        self.sent.append(event)


MODEL = ModelInfo(provider="google", name="gemini-2.0-flash-001")
USER_MSG = GenAIMessage(role=MessageRole.USER, content="What is 2+2?")
ASST_MSG = GenAIMessage(role=MessageRole.ASSISTANT, content="4.")


def _make_span(client: CapturingClient, **kw: object) -> Span:
    return Span(
        client=client,
        trace_id="trace-abc",
        model=MODEL,
        application_name="test-app",
        **kw,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_span_sends_event_on_exit() -> None:
    client = CapturingClient()
    async with _make_span(client) as span:
        span.add_message(USER_MSG)
        span.add_message(ASST_MSG)

    assert len(client.sent) == 1
    event = client.sent[0]
    assert event.trace_id == "trace-abc"
    assert len(event.messages) == 2


@pytest.mark.asyncio
async def test_span_records_token_usage() -> None:
    client = CapturingClient()
    async with _make_span(client) as span:
        span.add_message(USER_MSG)
        span.set_token_usage(TokenUsage(prompt_tokens=10, completion_tokens=5))

    assert client.sent[0].token_usage == TokenUsage(prompt_tokens=10, completion_tokens=5)


@pytest.mark.asyncio
async def test_span_records_latency() -> None:
    client = CapturingClient()
    async with _make_span(client) as span:
        span.add_message(USER_MSG)

    event = client.sent[0]
    assert event.latency_ms is not None
    assert event.latency_ms >= 0


@pytest.mark.asyncio
async def test_span_extra_attributes() -> None:
    client = CapturingClient()
    async with _make_span(client, extra_attributes={"rag_k": 5}) as span:
        span.add_message(USER_MSG)
        span.set_attribute("session_id", "s-99")

    assert client.sent[0].attributes == {"rag_k": 5, "session_id": "s-99"}


@pytest.mark.asyncio
async def test_span_no_messages_skips_send() -> None:
    """An empty span must not crash and must not send a malformed event."""
    client = CapturingClient()
    async with _make_span(client):
        pass  # no messages added

    assert client.sent == []


@pytest.mark.asyncio
async def test_span_send_failure_silent_by_default() -> None:
    """Gateway errors must never propagate to the instrumented app."""
    client = CapturingClient(fail=True)
    async with _make_span(client) as span:
        span.add_message(USER_MSG)
    # No exception raised — span exited cleanly.


@pytest.mark.asyncio
async def test_span_send_failure_raises_when_requested() -> None:
    client = CapturingClient(fail=True)
    with pytest.raises(RuntimeError, match="gateway down"):
        async with _make_span(client, raise_on_error=True) as span:
            span.add_message(USER_MSG)


@pytest.mark.asyncio
async def test_span_id_auto_generated_when_not_provided() -> None:
    client = CapturingClient()
    async with _make_span(client) as span:
        span.add_message(USER_MSG)

    assert len(client.sent[0].span_id) == 36  # UUID4


@pytest.mark.asyncio
async def test_span_custom_span_id() -> None:
    client = CapturingClient()
    async with _make_span(client, span_id="my-span-id") as span:
        span.add_message(USER_MSG)

    assert client.sent[0].span_id == "my-span-id"
