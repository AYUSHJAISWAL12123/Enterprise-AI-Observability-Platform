"""Tests for Dashboard API routes."""

from __future__ import annotations

import pytest
from dashboard_api.app import create_app
from dashboard_api.schemas import MetricSummary, TraceDetail, TraceSummary
from fastapi.testclient import TestClient


class FakeReader:
    def __init__(self) -> None:
        self.summary = MetricSummary(
            total_events=10,
            evaluated_events=10,
            safety_violations=0,
            avg_groundedness=4.5,
            avg_relevance=4.8,
            avg_latency_ms=300.0,
        )
        self.traces = [
            TraceSummary(
                trace_id="t-1",
                event_id="e-1",
                application_name="test-app",
                model_name="m-1",
                latency_ms=100.0,
                groundedness_score=5,
                relevance_score=5,
                safety_flag=False,
                embedding_distance=0.1,
                timestamp="2025-01-01T00:00:00Z",
            )
        ]

    async def get_summary(self, hours: int) -> MetricSummary:
        return self.summary

    async def list_traces(self, limit: int, offset: int) -> list[TraceSummary]:
        return self.traces

    async def get_trace(self, trace_id: str) -> TraceDetail | None:
        if trace_id == "not-found":
            return None
        return TraceDetail(
            **self.traces[0].model_dump(),
            messages=[{"role": "user", "content": "hi"}],
            judge_rationale="Looks good",
            attributes={"k": "v"},
        )


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.state.reader = FakeReader()
    return TestClient(app)


def test_get_metrics(client: TestClient) -> None:
    resp = client.get("/api/v1/metrics?hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 10
    assert data["avg_groundedness"] == 4.5


def test_list_traces(client: TestClient) -> None:
    resp = client.get("/api/v1/traces?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["trace_id"] == "t-1"


def test_get_trace_success(client: TestClient) -> None:
    resp = client.get("/api/v1/traces/t-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == "t-1"
    assert len(data["messages"]) == 1
    assert data["judge_rationale"] == "Looks good"


def test_get_trace_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/traces/not-found")
    assert resp.status_code == 404
