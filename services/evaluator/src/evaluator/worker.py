"""Evaluation worker orchestration loop.

The worker pulls a batch of unevaluated events, fans out requests to
Vertex AI (Judge + Embeddings) concurrently, and writes the results back
to BigQuery.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from evaluator._bq import ReaderProtocol, WriterProtocol
from evaluator._vertex import VertexProtocol
from evaluator.schemas import EvalResult, UnevaluatedEvent

logger = structlog.get_logger(__name__)


async def _evaluate_single(
    event: UnevaluatedEvent,
    vertex: VertexProtocol,
) -> EvalResult:
    """Evaluate one event using both LLM judge and drift computation concurrently."""
    # Fan out to Vertex AI
    scorecard, drift = await asyncio.gather(
        vertex.evaluate_judge(event.messages_json),
        vertex.compute_drift(event.messages_json),
    )

    return EvalResult(
        event_id=event.event_id,
        trace_id=event.trace_id,
        groundedness_score=scorecard.groundedness,
        relevance_score=scorecard.relevance,
        safety_flag=scorecard.safety_flag,
        judge_rationale=scorecard.rationale,
        embedding_distance=drift,
        evaluated_at=datetime.now(tz=UTC).isoformat(),
    )


async def run_batch(
    *,
    reader: ReaderProtocol,
    writer: WriterProtocol,
    vertex: VertexProtocol,
    batch_size: int,
) -> int:
    """Run one batch evaluation cycle.

    Returns the number of events evaluated and saved.
    """
    logger.info("evaluator starting batch", batch_size=batch_size)

    events = await reader.fetch_unevaluated(limit=batch_size)
    if not events:
        logger.info("evaluator no pending events")
        return 0

    logger.debug("evaluator fetched events", count=len(events))

    # Concurrently evaluate all events in the batch.
    # In production, you might want to use a bounded semaphore to avoid
    # hitting Vertex AI rate limits (429s).
    results: list[EvalResult] = await asyncio.gather(
        *[_evaluate_single(e, vertex) for e in events]
    )

    written: int = await writer.write_results(results)
    logger.info("evaluator batch complete", evaluated=written)
    return written
