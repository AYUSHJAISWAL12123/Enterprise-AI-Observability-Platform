"""Gateway HTTP client with a testable Protocol interface.

Using a Protocol instead of an abstract base class means any object with a
matching ``send_event`` signature can be used — test fakes need no
inheritance, satisfying the dependency-injection requirement.

The ``HttpGatewayClient`` is the production implementation.  It serialises
a ``GenAIEvent`` to JSON and POSTs it to the ingestion gateway.  Transient
network errors and HTTP 5xx responses trigger the retry decorator; 4xx
errors (bad payloads, auth failures) are raised immediately as they are not
transient.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import httpx
from obs_core.schemas import GenAIEvent

from obs_sdk._retry import async_retry

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Raised for transient gateway failures (5xx, 429, network errors)."""


_RETRYABLE = (httpx.TransportError, httpx.TimeoutException, GatewayError)


@runtime_checkable
class GatewayClientProtocol(Protocol):
    """Structural interface for sending events; fakes implement this."""

    async def send_event(self, event: GenAIEvent) -> None:
        """Send a single telemetry event to the ingestion gateway.

        Implementations must be idempotent: the gateway deduplicates on
        ``event.event_id`` so safe to retry on network failures.
        """
        ...


class HttpGatewayClient:
    """Production gateway client backed by httpx.

    Instantiate once per service and reuse; the underlying ``AsyncClient``
    maintains a connection pool which is released on ``aclose()``.

    Args:
        gateway_url: Base URL of the ingestion gateway (no trailing slash).
        api_key: Bearer token for gateway authentication.
        timeout: Per-request timeout in seconds.
        max_retries: Retry attempts for transient errors (exponential backoff).
    """

    def __init__(
        self,
        *,
        gateway_url: str,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = gateway_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "obs-sdk/0.1.0",
        }
        self._timeout = timeout
        self._max_retries = max_retries
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self._headers,
        )

    async def send_event(self, event: GenAIEvent) -> None:
        """Serialise and POST a GenAIEvent; retry on transient failures."""
        await self._post(event)

    @async_retry(max_attempts=3, base_delay=0.5, retryable_exceptions=_RETRYABLE)  # type: ignore[untyped-decorator]
    async def _post(self, event: GenAIEvent) -> None:
        payload = event.model_dump_json()
        response = await self._http.post(
            f"{self._base_url}/v1/events",
            content=payload,
        )
        if response.status_code == 429:
            # Rate limited — treat as transient so the retry decorator fires.
            raise GatewayError(f"Rate limited: {response.status_code}")
        if response.status_code >= 500:
            raise GatewayError(
                f"Gateway error: {response.status_code} {response.text[:200]}"
            )
        # 4xx are programming errors (bad schema, wrong auth); raise immediately.
        response.raise_for_status()
        logger.debug(
            "obs_sdk event sent",
            extra={"event_id": event.event_id, "trace_id": event.trace_id},
        )

    async def aclose(self) -> None:
        """Release the underlying connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> HttpGatewayClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
