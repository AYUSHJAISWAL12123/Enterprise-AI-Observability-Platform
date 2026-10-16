"""Pub/Sub subscriber — synchronous pull wrapped in an executor.

Synchronous pull is chosen over streaming pull because:
- It gives the worker explicit control over concurrency (pull only when
  ready to write, avoiding unbounded in-memory buffering).
- It is easier to reason about backpressure in a single-threaded worker.
- The streaming pull callback model is harder to test deterministically.

The GCP client is created lazily to avoid network calls at import time.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

from google.api_core import exceptions

from processor._message import PubSubMessage

logger = logging.getLogger(__name__)


@runtime_checkable
class SubscriberProtocol(Protocol):
    """Structural interface for pulling and acknowledging messages."""

    async def pull(self, *, max_messages: int) -> list[PubSubMessage]:
        """Pull up to ``max_messages`` from the subscription."""
        ...

    async def ack(self, ack_ids: list[str]) -> None:
        """Acknowledge successfully processed messages."""
        ...

    async def nack(self, ack_ids: list[str]) -> None:
        """Negatively acknowledge messages for redelivery."""
        ...


class PubSubSubscriber:
    """Pulls messages from a Google Cloud Pub/Sub subscription.

    Args:
        project_id: GCP project owning the subscription.
        subscription_id: Pub/Sub subscription ID (not the full path).
    """

    def __init__(self, *, project_id: str, subscription_id: str) -> None:
        self._project_id = project_id
        self._subscription_id = subscription_id
        self._client: Any = None  # lazy init; typed Any (no py.typed in pubsub)
        self._subscription_path: str | None = None

    def _ensure_client(self) -> tuple[Any, str]:
        if self._client is None:
            from google.cloud import pubsub_v1  # type: ignore[attr-defined]

            self._client = pubsub_v1.SubscriberClient()
            self._subscription_path = self._client.subscription_path(
                self._project_id, self._subscription_id
            )
        assert self._subscription_path is not None  # noqa: S101
        return self._client, self._subscription_path

    async def pull(self, *, max_messages: int) -> list[PubSubMessage]:
        """Pull a batch; returns an empty list when the subscription is idle."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._pull_sync, max_messages)

    def _pull_sync(self, max_messages: int) -> list[PubSubMessage]:
        client, path = self._ensure_client()
        try:
            response = client.pull(
                request={"subscription": path, "max_messages": max_messages},
                timeout=5.0,
            )
        except (exceptions.DeadlineExceeded, exceptions.RetryError):
            logger.debug("processor pull timed out (subscription idle)")
            return []
        messages = []
        for msg in response.received_messages:
            messages.append(
                PubSubMessage(
                    ack_id=msg.ack_id,
                    data=msg.message.data,
                    message_id=msg.message.message_id,
                    attributes=dict(msg.message.attributes),
                )
            )
        logger.debug("processor pulled %d messages", len(messages))
        return messages

    async def ack(self, ack_ids: list[str]) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._ack_sync, ack_ids)

    def _ack_sync(self, ack_ids: list[str]) -> None:
        if not ack_ids:
            return
        client, path = self._ensure_client()
        client.acknowledge(request={"subscription": path, "ack_ids": ack_ids})

    async def nack(self, ack_ids: list[str]) -> None:
        """Nack by setting ack deadline to 0, causing immediate redelivery."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._nack_sync, ack_ids)

    def _nack_sync(self, ack_ids: list[str]) -> None:
        if not ack_ids:
            return
        client, path = self._ensure_client()
        client.modify_ack_deadline(
            request={"subscription": path, "ack_ids": ack_ids, "ack_deadline_seconds": 0}
        )
