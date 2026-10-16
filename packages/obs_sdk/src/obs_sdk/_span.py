"""Span: async context manager that records one LLM inference call.

Usage pattern (instrumented application side):

    async with Span(
        client=gateway_client,
        trace_id=otel_context.trace_id,
        span_id=otel_context.span_id,
        model=ModelInfo(provider="google", name="gemini-2.0-flash-001"),
        application_name="my-rag-app",
    ) as span:
        span.add_message(GenAIMessage(role=MessageRole.USER, content=prompt))
        response = await llm.generate(prompt)
        span.add_message(GenAIMessage(role=MessageRole.ASSISTANT, content=response.text))
        span.set_token_usage(TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        ))
    # GenAIEvent is built and POSTed to the gateway on __aexit__.

Design notes:
- ``Span`` never raises on send failure when ``raise_on_error=False``
  (the default) so instrumentation never breaks production app flow.
- Messages are accumulated in insertion order; the span does not enforce
  role ordering so it works for multi-turn and tool-call patterns.
- The span is not thread-safe; use one Span per coroutine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from obs_core.schemas import GenAIEvent, GenAIMessage, ModelInfo, TokenUsage

from obs_sdk._client import GatewayClientProtocol

logger = logging.getLogger(__name__)


class Span:
    """Accumulates LLM call data and emits a :class:`GenAIEvent` on exit.

    Args:
        client: Any object satisfying :class:`GatewayClientProtocol`.
        trace_id: OTel trace ID; must be supplied by the caller from context.
        span_id: OTel span ID for this specific LLM call.
        model: Identifies the model being called.
        application_name: Name of the instrumented application.
        parent_span_id: Set for nested/tool LLM calls within a trace.
        application_version: Optional semver of the application.
        environment: Deployment environment string.
        raise_on_error: If True, re-raise send failures (useful in tests).
        extra_attributes: Arbitrary key-value bag passed through to the event.
    """

    def __init__(
        self,
        *,
        client: GatewayClientProtocol,
        trace_id: str,
        span_id: str | None = None,
        model: ModelInfo,
        application_name: str,
        parent_span_id: str | None = None,
        application_version: str | None = None,
        environment: str = "production",
        raise_on_error: bool = False,
        extra_attributes: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._trace_id = trace_id
        self._span_id = span_id or str(uuid.uuid4())
        self._parent_span_id = parent_span_id
        self._model = model
        self._application_name = application_name
        self._application_version = application_version
        self._environment = environment
        self._raise_on_error = raise_on_error
        self._extra_attributes: dict[str, Any] = extra_attributes or {}

        self._messages: list[GenAIMessage] = []
        self._token_usage: TokenUsage | None = None
        self._started_at: datetime | None = None

    # ── Public mutation API ────────────────────────────────────────────────

    def add_message(self, message: GenAIMessage) -> None:
        """Append a conversation turn; call for both input and output turns."""
        self._messages.append(message)

    def set_token_usage(self, usage: TokenUsage) -> None:
        """Record token consumption reported by the model provider."""
        self._token_usage = usage

    def set_attribute(self, key: str, value: object) -> None:
        """Store an arbitrary attribute in the event's pass-through bag."""
        self._extra_attributes[key] = value

    # ── Context manager ────────────────────────────────────────────────────

    async def __aenter__(self) -> Span:
        self._started_at = datetime.now(tz=UTC)
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        ended_at = datetime.now(tz=UTC)

        # Require at least one message; skip send for empty spans.
        if not self._messages:
            logger.warning(
                "obs_sdk span exited with no messages; event not sent",
                extra={"trace_id": self._trace_id, "span_id": self._span_id},
            )
            return

        event = GenAIEvent(
            trace_id=self._trace_id,
            span_id=self._span_id,
            parent_span_id=self._parent_span_id,
            model=self._model,
            messages=self._messages,
            token_usage=self._token_usage,
            application_name=self._application_name,
            application_version=self._application_version,
            environment=self._environment,
            started_at=self._started_at or ended_at,
            ended_at=ended_at,
            attributes=self._extra_attributes,
        )

        try:
            await self._client.send_event(event)
        except Exception as exc:
            # Log the failure but never crash the instrumented application
            # unless the caller explicitly opts in via raise_on_error.
            logger.error(
                "obs_sdk failed to send event",
                extra={"event_id": event.event_id, "error": str(exc)},
            )
            if self._raise_on_error:
                raise
