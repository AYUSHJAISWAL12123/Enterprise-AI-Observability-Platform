"""Core processing loop: pull → parse → write → ack.

This module contains the pure logic of one processing cycle and the
long-running loop that drives it.  Both are async so they compose cleanly
with any async entrypoint (main, tests).

Error handling strategy:
- ``ValidationError`` (malformed message): nack immediately — the message
  is unprocessable and should go to a dead-letter queue.
- ``BigQueryWriteError``: nack the entire batch — BQ errors are retryable
  and we must not ack data we failed to persist.
- Any other unexpected exception: nack + log + continue — don't crash the
  worker on one bad batch.
"""

from __future__ import annotations

import asyncio

import structlog
from obs_core.schemas import GenAIEvent
from pydantic import ValidationError

from processor._message import PubSubMessage
from processor._subscriber import SubscriberProtocol
from processor._writer import BigQueryWriteError, WriterProtocol

logger = structlog.get_logger(__name__)


async def process_batch(
    *,
    subscriber: SubscriberProtocol,
    writer: WriterProtocol,
    max_messages: int = 100,
) -> int:
    """Execute one pull-parse-write-ack cycle.

    Returns the number of events successfully written.  Callers can use
    this to implement adaptive sleep (slow down when idle, speed up when
    backlogged).
    """
    messages: list[PubSubMessage] = await subscriber.pull(max_messages=max_messages)
    if not messages:
        return 0

    valid_events: list[GenAIEvent] = []
    valid_ack_ids: list[str] = []
    invalid_ack_ids: list[str] = []

    for msg in messages:
        try:
            event = GenAIEvent.model_validate_json(msg.data)
            valid_events.append(event)
            valid_ack_ids.append(msg.ack_id)
        except ValidationError as exc:
            # Poison pill — nack so it goes to the dead-letter topic.
            logger.warning(
                "processor invalid message",
                message_id=msg.message_id,
                error=str(exc),
            )
            invalid_ack_ids.append(msg.ack_id)

    # Nack unparseable messages before attempting the write so a BQ failure
    # doesn't accidentally ack the bad messages too.
    if invalid_ack_ids:
        await subscriber.nack(invalid_ack_ids)

    if not valid_events:
        return 0

    try:
        written: int = await writer.write_events(valid_events)
        await subscriber.ack(valid_ack_ids)
        logger.info("processor batch complete", written=written)
        return written
    except BigQueryWriteError as exc:
        logger.error(
            "processor BQ write failed — nacking batch",
            batch_size=len(valid_events),
            error=str(exc),
        )
        await subscriber.nack(valid_ack_ids)
        return 0
    except Exception as exc:
        logger.error(
            "processor unexpected error — nacking batch",
            error=str(exc),
            exc_info=True,
        )
        await subscriber.nack(valid_ack_ids)
        return 0


async def run_worker(
    *,
    subscriber: SubscriberProtocol,
    writer: WriterProtocol,
    max_messages: int = 100,
    idle_sleep_seconds: float = 2.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run the processing loop until ``stop_event`` is set (or forever).

    ``stop_event`` is used in tests to terminate the loop after N cycles.
    In production it is ``None`` and the loop runs until the process exits.

    Args:
        subscriber: Message source (Pub/Sub or fake).
        writer: Data sink (BigQuery or fake).
        max_messages: Max messages per pull cycle.
        idle_sleep_seconds: Pause when no messages are available.
        stop_event: Optional signal to terminate the loop gracefully.
    """
    logger.info("processor worker started")
    while stop_event is None or not stop_event.is_set():
        written = await process_batch(
            subscriber=subscriber,
            writer=writer,
            max_messages=max_messages,
        )
        if written == 0:
            # Back off when subscription is idle to avoid hammering PubSub.
            await asyncio.sleep(idle_sleep_seconds)
