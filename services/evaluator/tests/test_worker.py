"""Tests for evaluator.worker."""

from __future__ import annotations

import pytest
from evaluator._bq import ReaderProtocol, WriterProtocol
from evaluator._vertex import VertexProtocol
from evaluator.schemas import EvalResult, EvalScoreCard, UnevaluatedEvent
from evaluator.worker import run_batch


class FakeReader:
    def __init__(self, events: list[UnevaluatedEvent]) -> None:
        self.events = events
        self.fetch_called = False

    async def fetch_unevaluated(self, limit: int) -> list[UnevaluatedEvent]:
        self.fetch_called = True
        return self.events[:limit]


class FakeWriter:
    def __init__(self) -> None:
        self.written: list[EvalResult] = []

    async def write_results(self, results: list[EvalResult]) -> int:
        self.written.extend(results)
        return len(results)


class FakeVertex:
    async def evaluate_judge(self, messages_json: str) -> EvalScoreCard:
        return EvalScoreCard(
            groundedness=4,
            relevance=5,
            safety_flag=False,
            rationale="Test",
        )

    async def compute_drift(self, messages_json: str) -> float:
        return 0.123


assert isinstance(FakeReader([]), ReaderProtocol)
assert isinstance(FakeWriter(), WriterProtocol)
assert isinstance(FakeVertex(), VertexProtocol)


@pytest.fixture
def dummy_event() -> UnevaluatedEvent:
    return UnevaluatedEvent(
        event_id="e-1",
        trace_id="t-1",
        messages_json="[]",
        raw_row={},
    )


@pytest.mark.asyncio
async def test_run_batch_empty() -> None:
    reader = FakeReader([])
    writer = FakeWriter()
    vertex = FakeVertex()

    written = await run_batch(
        reader=reader, writer=writer, vertex=vertex, batch_size=10
    )

    assert written == 0
    assert reader.fetch_called
    assert len(writer.written) == 0


@pytest.mark.asyncio
async def test_run_batch_processes_events(dummy_event: UnevaluatedEvent) -> None:
    reader = FakeReader([dummy_event])
    writer = FakeWriter()
    vertex = FakeVertex()

    written = await run_batch(
        reader=reader, writer=writer, vertex=vertex, batch_size=10
    )

    assert written == 1
    assert len(writer.written) == 1
    res = writer.written[0]
    assert res.event_id == "e-1"
    assert res.groundedness_score == 4
    assert res.embedding_distance == 0.123
