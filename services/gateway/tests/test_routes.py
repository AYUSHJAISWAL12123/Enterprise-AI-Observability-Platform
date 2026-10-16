"""Tests for gateway routes (POST /v1/events, GET /health, GET /ready).

Uses FastAPI's TestClient (httpx) with dependency overrides to avoid any
real Pub/Sub or environment variable dependencies.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from gateway._auth import verify_token
from gateway._publisher import PublisherProtocol
from gateway.app import create_app
from obs_core.schemas import GenAIEvent

API_KEY = "test-secret-key"


class FakePublisher:
    """Test double that captures published events."""

    def __init__(self) -> None:
        self.published: list[GenAIEvent] = []

    async def publish_event(self, event: GenAIEvent) -> str:
        self.published.append(event)
        return "fake-msg-id"


assert isinstance(FakePublisher(), PublisherProtocol)


def _make_app(publisher: FakePublisher) -> FastAPI:
    """Build a test app with auth and publisher overridden."""
    app = create_app()
    app.state.api_keys = frozenset({API_KEY})
    app.state.publisher = publisher
    # Override auth dependency so it always passes in tests.
    app.dependency_overrides[verify_token] = lambda: None
    return app


def _valid_payload() -> dict:  # type: ignore[type-arg]
    return {
        "trace_id": "trace-abc",
        "span_id": "span-001",
        "model": {"provider": "google", "name": "gemini-2.0-flash-001"},
        "messages": [{"role": "user", "content": "What is 2+2?"}],
        "application_name": "test-app",
    }


class TestIngestEvent:
    def setup_method(self) -> None:
        self.publisher = FakePublisher()
        self.client = TestClient(_make_app(self.publisher))

    def test_valid_event_returns_202(self) -> None:
        resp = self.client.post("/v1/events", json=_valid_payload())
        assert resp.status_code == 202

    def test_response_contains_event_id_and_message_id(self) -> None:
        resp = self.client.post("/v1/events", json=_valid_payload())
        body = resp.json()
        assert "event_id" in body
        assert body["message_id"] == "fake-msg-id"

    def test_event_is_published(self) -> None:
        self.client.post("/v1/events", json=_valid_payload())
        assert len(self.publisher.published) == 1

    def test_pii_is_redacted_before_publish(self) -> None:
        payload = _valid_payload()
        payload["messages"] = [{"role": "user", "content": "email me at bob@test.com"}]
        self.client.post("/v1/events", json=payload)
        published = self.publisher.published[0]
        assert published.messages[0].content == "email me at [EMAIL]"

    def test_invalid_payload_returns_422(self) -> None:
        resp = self.client.post("/v1/events", json={"bad": "payload"})
        assert resp.status_code == 422

    def test_empty_messages_returns_422(self) -> None:
        payload = _valid_payload()
        payload["messages"] = []
        resp = self.client.post("/v1/events", json=payload)
        assert resp.status_code == 422


class TestAuth:
    """Auth tests using the real verify_token dependency."""

    def setup_method(self) -> None:
        publisher = FakePublisher()
        # Create app WITHOUT overriding verify_token
        app = create_app()
        app.state.api_keys = frozenset({API_KEY})
        app.state.publisher = publisher
        self.client = TestClient(app)

    def test_missing_token_returns_401(self) -> None:
        resp = self.client.post("/v1/events", json=_valid_payload())
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self) -> None:
        resp = self.client.post(
            "/v1/events",
            json=_valid_payload(),
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    def test_correct_token_accepted(self) -> None:
        resp = self.client.post(
            "/v1/events",
            json=_valid_payload(),
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 202


class TestProbes:
    def setup_method(self) -> None:
        publisher = FakePublisher()
        self.client = TestClient(_make_app(publisher))

    def test_health_returns_200(self) -> None:
        assert self.client.get("/health").status_code == 200

    def test_ready_returns_200_when_publisher_set(self) -> None:
        assert self.client.get("/ready").status_code == 200

    def test_ready_returns_503_when_no_publisher(self) -> None:
        app = create_app()
        app.state.api_keys = frozenset({API_KEY})
        # Do NOT set app.state.publisher
        client = TestClient(app)
        assert client.get("/ready").status_code == 503
