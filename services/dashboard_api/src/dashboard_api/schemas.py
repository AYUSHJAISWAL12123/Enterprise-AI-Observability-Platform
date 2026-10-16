"""API Response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MetricSummary(BaseModel):
    """Aggregated stats over a time window."""

    total_events: int
    evaluated_events: int
    safety_violations: int
    avg_groundedness: float
    avg_relevance: float
    avg_latency_ms: float


class TraceSummary(BaseModel):
    """High-level summary of a single interaction for list views."""

    trace_id: str
    event_id: str
    application_name: str
    model_name: str
    latency_ms: float
    groundedness_score: int | None
    relevance_score: int | None
    safety_flag: bool | None
    embedding_distance: float | None
    timestamp: str


class TraceDetail(TraceSummary):
    """Detailed view including messages and judge rationale."""

    messages: list[dict[str, Any]] = Field(description="Parsed JSON messages")
    judge_rationale: str | None
    attributes: dict[str, str] = Field(description="Custom event attributes")
