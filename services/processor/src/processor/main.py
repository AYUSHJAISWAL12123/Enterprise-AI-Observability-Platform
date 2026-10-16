"""Processor service entrypoint.

Sets up config, logging, and the worker loop.  Handles SIGTERM gracefully
so Kubernetes can drain in-flight messages before terminating the pod.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from obs_core.config import Settings
from obs_core.logging import configure_logging

from processor._subscriber import PubSubSubscriber
from processor._writer import BigQueryWriter
from processor.worker import run_worker


def _build_stop_event() -> asyncio.Event:
    """Return an Event that is set when SIGTERM or SIGINT is received."""
    stop = asyncio.Event()

    def _handle_signal(sig: int, _frame: object) -> None:
        logging.getLogger(__name__).info("processor received signal %d — stopping", sig)
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    return stop


async def _main() -> None:
    settings = Settings()
    configure_logging(
        log_level=settings.log_level.value,
        service_name=settings.service_name,
        environment=settings.environment.value,
    )

    subscriber = PubSubSubscriber(
        project_id=settings.gcp_project_id,
        subscription_id=settings.pubsub_subscription_raw_events,
    )
    writer = BigQueryWriter(
        project_id=settings.gcp_project_id,
        dataset_id=settings.bq_dataset_raw,
        table_id=settings.bq_table_events,
    )
    stop_event = _build_stop_event()

    await run_worker(
        subscriber=subscriber,
        writer=writer,
        stop_event=stop_event,
    )


if __name__ == "__main__":
    asyncio.run(_main())
