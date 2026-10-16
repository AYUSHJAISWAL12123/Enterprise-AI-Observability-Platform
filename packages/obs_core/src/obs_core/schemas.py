"""Core Pydantic schemas for GenAI telemetry events.

These schemas follow the OpenTelemetry Semantic Conventions for Generative AI
(gen_ai.*) so the SDK can emit standard OTLP spans and the gateway can
deserialise them into strongly-typed objects without an impedance mismatch.

Design decisions:
- ``trace_id`` / ``event_id`` are the idempotency keys used throughout the
  pipeline; BigQuery MERGE operations key on them to make writes idempotent.
- ``prompt_tokens`` / ``completion_tokens`` map directly to the OTel
  ``gen_ai.usage.*_tokens`` attributes.
- All timestamps are stored as UTC-aware datetimes; the SDK normalises
  timezone before sending so the gateway never has to guess.
- ``GenAIMessage.content`` is ``str | None`` because streaming responses
  may emit a final span before the full content is assembled.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ModelInfo(BaseModel):
    """Identifies the model that produced the response."""

    provider: str = Field(..., description="e.g. 'google', 'openai'")
    name: str = Field(..., description="e.g. 'gemini-2.0-flash-001'")
    version: str | None = Field(None, description="Model version string if available")


class TokenUsage(BaseModel):
    """Token consumption for a single inference call."""

    prompt_tokens: Annotated[int, Field(ge=0)]
    completion_tokens: Annotated[int, Field(ge=0)]

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class GenAIMessage(BaseModel):
    """A single turn in the conversation (input or output)."""

    role: MessageRole
    content: str | None = Field(
        None,
        description="Message text. None only for streaming-incomplete spans.",
    )
    tool_call_id: str | None = None

    @field_validator("content")
    @classmethod
    def content_not_empty_string(cls, v: str | None) -> str | None:
        """Treat empty strings as missing; callers should pass None explicitly."""
        if v is not None and not v.strip():
            raise ValueError("content must be non-empty or None")
        return v


class GenAIEvent(BaseModel):
    """Top-level telemetry event emitted by an instrumented AI application.

    One ``GenAIEvent`` corresponds to one LLM inference call (a span in OTel
    terms).  The pipeline stores the raw event in BigQuery and downstream
    workers attach evaluation scores to it via ``event_id``.
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event identifier; used as idempotency key in BQ.",
    )
    trace_id: str = Field(
        ...,
        description="OTel trace ID; correlates all spans in one user request.",
    )
    span_id: str = Field(..., description="OTel span ID for this LLM call.")
    parent_span_id: str | None = Field(
        None, description="Parent span ID for nested LLM calls."
    )

    model: ModelInfo
    messages: list[GenAIMessage] = Field(
        ..., min_length=1, description="Conversation turns including the response."
    )
    token_usage: TokenUsage | None = None

    # Application metadata
    application_name: str = Field(..., description="Name of the instrumented app.")
    application_version: str | None = None
    environment: str = Field("production")

    # Timing
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC)
    )
    ended_at: datetime | None = None

    # Pass-through bag for non-standard attributes
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ended_after_started(self) -> GenAIEvent:
        """Catch clock-skew bugs from the instrumented application."""
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be before started_at")
        return self

    @property
    def latency_ms(self) -> float | None:
        """Wall-clock latency in milliseconds, or None if end is unknown."""
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds() * 1000

    @property
    def last_assistant_message(self) -> GenAIMessage | None:
        """Return the final assistant turn, if present."""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.ASSISTANT:
                return msg
        return None
