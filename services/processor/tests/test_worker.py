"""Tests for processor.worker (process_batch and run_worker)."""

from __future__ import annotations

import asyncio

import pytest
from obs_core.schemas import GenAIEvent, GenAIMessage, MessageRole, ModelInfo
from processor._message import PubSubMessage
from processor._subscriber import SubscriberProtocol
from processor._writer import BigQueryWriteError, WriterProtocol
from processor.worker import process_batch, run_worker

MODEL = ModelInfo(provider="google", name="gemini-2.0-flash-001")


def _make_event(trace_id: str = "t-1") -> GenAIEvent:
    return GenAIEvent(
        trace_id=trace_id,
        span_id="s-1",
        model=MODEL,
        messages=[GenAIMessage(role=MessageRole.USER, content="hi")],
        application_name="test",
    )


def _encode(event: GenAIEvent) -> bytes:
    return event.model_dump_json().encode()


class FakeSubscriber:
    """Controllable test double for SubscriberProtocol."""

    def __init__(self, batches: list[list[PubSubMessage]]) -> None:
        self._batches = list(batches)
        self.acked: list[str] = []
        self.nacked: list[str] = []

    async def pull(self, *, max_messages: int) -> list[PubSubMessage]:
        if not self._batches:
            return []
        return self._batches.pop(0)

    async def ack(self, ack_ids: list[str]) -> None:
        self.acked.extend(ack_ids)

    async def nack(self, ack_ids: list[str]) -> None:
        self.nacked.extend(ack_ids)


assert isinstance(FakeSubscriber([]), SubscriberProtocol)


class FakeWriter:
    def __init__(self, *, fail: bool = False) -> None:
        self.written: list[GenAIEvent] = []
        self._fail = fail

    async def write_events(self, events: list[GenAIEvent]) -> int:
        if self._fail:
            raise BigQueryWriteError("BQ down")
        self.written.extend(events)
        return len(events)


assert isinstance(FakeWriter(), WriterProtocol)


def _msg(ack_id: str, event: GenAIEvent) -> PubSubMessage:
    return PubSubMessage(ack_id=ack_id, data=_encode(event), message_id=ack_id)


# ── process_batch tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_batch_empty_subscription_returns_zero() -> None:
    sub = FakeSubscriber([])
    writer = FakeWriter()
    result = await process_batch(subscriber=sub, writer=writer)
    assert result == 0
    assert writer.written == []


@pytest.mark.asyncio
async def test_process_batch_writes_and_acks_valid_events() -> None:
    e = _make_event()
    sub = FakeSubscriber([[_msg("ack-1", e)]])
    writer = FakeWriter()

    result = await process_batch(subscriber=sub, writer=writer)

    assert result == 1
    assert len(writer.written) == 1
    assert writer.written[0].event_id == e.event_id
    assert sub.acked == ["ack-1"]
    assert sub.nacked == []


@pytest.mark.asyncio
async def test_process_batch_nacks_invalid_json() -> None:
    bad_msg = PubSubMessage(ack_id="bad-1", data=b"not-json", message_id="m1")
    sub = FakeSubscriber([[bad_msg]])
    writer = FakeWriter()

    result = await process_batch(subscriber=sub, writer=writer)

    assert result == 0
    assert writer.written == []
    assert "bad-1" in sub.nacked
    assert "bad-1" not in sub.acked


@pytest.mark.asyncio
async def test_process_batch_nacks_on_bq_failure() -> None:
    e = _make_event()
    sub = FakeSubscriber([[_msg("ack-2", e)]])
    writer = FakeWriter(fail=True)

    result = await process_batch(subscriber=sub, writer=writer)

    assert result == 0
    assert sub.nacked == ["ack-2"]
    assert sub.acked == []


@pytest.mark.asyncio
async def test_process_batch_mixed_valid_and_invalid() -> None:
    good_event = _make_event("t-good")
    bad_msg = PubSubMessage(ack_id="bad", data=b"garbage", message_id="m-bad")
    good_msg = _msg("good", good_event)

    sub = FakeSubscriber([[bad_msg, good_msg]])
    writer = FakeWriter()

    result = await process_batch(subscriber=sub, writer=writer)

    assert result == 1
    assert sub.nacked == ["bad"]
    assert sub.acked == ["good"]


# ── run_worker tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_worker_stops_on_event() -> None:
    e = _make_event()
    sub = FakeSubscriber([[_msg("a1", e)], [_msg("a2", e)]])
    writer = FakeWriter()
    stop = asyncio.Event()

    # Let one cycle run then signal stop.
    async def _stopper() -> None:
        await asyncio.sleep(0.05)
        stop.set()

    await asyncio.gather(
        run_worker(
            subscriber=sub,
            writer=writer,
            idle_sleep_seconds=0.01,
            stop_event=stop,
        ),
        _stopper(),
    )
    # At least one event was processed.
    assert len(writer.written) >= 1
