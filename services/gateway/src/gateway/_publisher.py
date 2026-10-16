"""Pub/Sub publisher with a Protocol interface for dependency injection.

``PubSubPublisher`` wraps the synchronous google-cloud-pubsub client in an
executor so it does not block the FastAPI event loop.  The synchronous
client is used (over the async gRPC stub) because it handles credentials,
retry, and flow control out of the box and is the recommended path for
server-side publishing.

The ``PublisherProtocol`` lets tests inject a ``FakePublisher`` without
touching any GCP APIs, satisfying the no-hidden-globals requirement.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

from obs_core.schemas import GenAIEvent

logger = logging.getLogger(__name__)


@runtime_checkable
class PublisherProtocol(Protocol):
    """Structural interface for publishing a GenAIEvent to the message bus."""

    async def publish_event(self, event: GenAIEvent) -> str:
        """Publish the event; return the broker-assigned message ID.

        Implementations must be idempotent with respect to ``event.event_id``
        — the downstream processor will deduplicate on that key.
        """
        ...


class PubSubPublisher:
    """Publishes GenAIEvents to a Google Cloud Pub/Sub topic.

    Uses Workload Identity for authentication — no service account keys.
    The underlying client is created lazily on first publish so the object
    can be constructed during FastAPI lifespan setup without network calls.

    Args:
        project_id: GCP project that owns the topic.
        topic_id: Pub/Sub topic ID (not the full resource path).\
    """

    def __init__(self, *, project_id: str, topic_id: str) -> None:
        self._topic_path: str | None = None
        self._project_id = project_id
        self._topic_id = topic_id
        # Typed as Any because google-cloud-pubsub has no py.typed marker.
        self._client: Any = None  # lazy init

    def _ensure_client(self) -> tuple[Any, str]:
        """Create the publisher client on first use (avoids import-time I/O)."""
        if self._client is None:
            # Import inside method so the module can be imported in tests
            # without google-cloud-pubsub credentials available.
            from google.cloud import pubsub_v1

            self._client = pubsub_v1.PublisherClient()
            self._topic_path = self._client.topic_path(
                self._project_id, self._topic_id
            )
        assert self._topic_path is not None  # noqa: S101 — guaranteed by above
        return self._client, self._topic_path

    async def publish_event(self, event: GenAIEvent) -> str:
        """Serialise the event to JSON and publish; return message ID."""
        loop = asyncio.get_running_loop()
        message_id: str = await loop.run_in_executor(
            None, self._publish_sync, event
        )
        logger.debug(
            "gateway pubsub published",
            extra={"event_id": event.event_id, "message_id": message_id},
        )
        return message_id

    def _publish_sync(self, event: GenAIEvent) -> str:
        """Blocking publish call; runs in a thread pool executor."""
        client, topic_path = self._ensure_client()
        data = event.model_dump_json().encode("utf-8")
        attributes = {
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "application_name": event.application_name,
            "environment": event.environment,
        }
        future = client.publish(topic_path, data=data, **attributes)
        return future.result()  # type: ignore[no-any-return]
