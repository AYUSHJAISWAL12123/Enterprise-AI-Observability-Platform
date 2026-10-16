"""Protocol-boundary message type for the Pub/Sub subscriber.

Defining our own ``PubSubMessage`` dataclass rather than exposing
``google.cloud.pubsub_v1`` types at the protocol boundary means:
  - The ``SubscriberProtocol`` has no GCP dependency in its signature.
  - Fakes in tests need no google-cloud-pubsub installation.
  - Future migration to a different broker (e.g. Kafka) only touches
    the ``PubSubSubscriber`` implementation, not the worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PubSubMessage:
    """Immutable view of a single Pub/Sub message."""

    ack_id: str
    data: bytes
    message_id: str
    attributes: dict[str, str] = field(default_factory=dict)
