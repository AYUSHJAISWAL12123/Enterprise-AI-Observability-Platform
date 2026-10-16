"""Tests for obs_sdk._client (HttpGatewayClient)."""

import httpx
import pytest
import respx
from obs_core.schemas import GenAIEvent, GenAIMessage, MessageRole, ModelInfo
from obs_sdk._client import GatewayClientProtocol, GatewayError, HttpGatewayClient

GATEWAY = "http://gateway.test"


def _make_event() -> GenAIEvent:
    return GenAIEvent(
        trace_id="trace-1",
        span_id="span-1",
        model=ModelInfo(provider="google", name="gemini-2.0-flash-001"),
        messages=[GenAIMessage(role=MessageRole.USER, content="Hello")],
        application_name="test-app",
    )


class FakeGatewayClient:
    """Minimal fake that satisfies GatewayClientProtocol."""

    def __init__(self) -> None:
        self.sent: list[GenAIEvent] = []

    async def send_event(self, event: GenAIEvent) -> None:
        self.sent.append(event)


def test_fake_satisfies_protocol() -> None:
    assert isinstance(FakeGatewayClient(), GatewayClientProtocol)


@pytest.mark.asyncio
@respx.mock
async def test_send_event_success() -> None:
    respx.post(f"{GATEWAY}/v1/events").mock(return_value=httpx.Response(200))

    async with HttpGatewayClient(gateway_url=GATEWAY, api_key="key") as client:
        await client.send_event(_make_event())

    assert respx.calls.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_send_event_4xx_raises_immediately() -> None:
    """4xx errors must not be retried (caller bug, not transient)."""
    respx.post(f"{GATEWAY}/v1/events").mock(return_value=httpx.Response(401))

    async with HttpGatewayClient(gateway_url=GATEWAY, api_key="bad") as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.send_event(_make_event())

    # Only 1 attempt — no retries on auth failure.
    assert respx.calls.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_send_event_5xx_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """5xx responses trigger retries up to max_attempts."""
    import asyncio

    async def _noop(_: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _noop)

    respx.post(f"{GATEWAY}/v1/events").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200),
        ]
    )

    async with HttpGatewayClient(
        gateway_url=GATEWAY, api_key="key", max_retries=3
    ) as client:
        await client.send_event(_make_event())

    assert respx.calls.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_send_event_exhausts_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    async def _noop(_: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _noop)

    respx.post(f"{GATEWAY}/v1/events").mock(return_value=httpx.Response(503))

    async with HttpGatewayClient(
        gateway_url=GATEWAY, api_key="key", max_retries=3
    ) as client:
        with pytest.raises(GatewayError):
            await client.send_event(_make_event())

    assert respx.calls.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_authorization_header_sent() -> None:
    route = respx.post(f"{GATEWAY}/v1/events").mock(return_value=httpx.Response(200))

    async with HttpGatewayClient(gateway_url=GATEWAY, api_key="my-secret") as client:
        await client.send_event(_make_event())

    assert route.calls[0].request.headers["authorization"] == "Bearer my-secret"
