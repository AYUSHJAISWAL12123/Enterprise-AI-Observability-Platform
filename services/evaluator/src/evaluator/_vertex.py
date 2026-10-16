"""Vertex AI evaluator — LLM-as-judge and embedding drift.

Uses the new ``google-genai`` SDK.  The ``VertexProtocol`` allows testing
the worker loop without invoking real LLM endpoints.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import structlog
from pydantic import ValidationError

from evaluator._prompts import JUDGE_SYSTEM_PROMPT
from evaluator.schemas import EvalScoreCard

logger = structlog.get_logger(__name__)


@runtime_checkable
class VertexProtocol(Protocol):
    """Structural interface for LLM evaluation and embeddings."""

    async def evaluate_judge(self, messages_json: str) -> EvalScoreCard:
        """Run LLM-as-judge on the conversation history."""
        ...

    async def compute_drift(self, messages_json: str) -> float:
        """Compute cosine distance from a baseline for drift detection."""
        ...


class VertexEvaluator:
    """Production implementation calling Google Cloud Vertex AI.

    Args:
        project_id: GCP project id.
        location: GCP region (e.g., 'us-central1').
        judge_model: e.g. 'gemini-2.0-flash-001'.
        embedding_model: e.g. 'text-embedding-004'.
    """

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        judge_model: str,
        embedding_model: str,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._judge_model = judge_model
        self._embedding_model = embedding_model
        # Typed Any because google-genai may not have full stubs available.
        self._client: Any = None

    def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            # Import delayed so tests don't require credentials.
            from google import genai

            # Use vertexai=True for enterprise features/compliance.
            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._location,
            )
        return self._client

    async def evaluate_judge(self, messages_json: str) -> EvalScoreCard:
        """Call Gemini with Structured Outputs to grade the interaction."""
        client = self._ensure_client()
        from google.genai import types

        # Use async API
        response = await client.aio.models.generate_content(
            model=self._judge_model,
            contents=messages_json,
            config=types.GenerateContentConfig(
                system_instruction=JUDGE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=EvalScoreCard,
                temperature=0.0,  # Deterministic judging
            ),
        )

        text = response.text
        if not text:
            raise ValueError("Judge returned empty response")

        try:
            return EvalScoreCard.model_validate_json(text)
        except ValidationError as exc:
            logger.error(
                "judge failed to follow schema",
                response_text=text,
                exc_info=exc,
            )
            # Fallback scores so the pipeline doesn't jam, but flagged for review.
            return EvalScoreCard(
                groundedness=3,
                relevance=3,
                safety_flag=True,  # Fail safe
                rationale=f"Failed to parse judge output: {text[:100]}...",
            )

    async def compute_drift(self, messages_json: str) -> float:
        """Compute an embedding for the interaction and calculate drift.

        In a real system, you would compute cosine distance against a known
        centroid of 'normal' traffic. For this reference implementation, we
        mock the baseline distance logic by returning the norm of the vector
        as a placeholder metric.
        """
        client = self._ensure_client()
        response = await client.aio.models.embed_content(
            model=self._embedding_model,
            contents=messages_json,
        )
        # Extract the first embedding vector.
        vector = response.embeddings[0].values
        # Placeholder: Return the sum of absolute values as a dummy "drift" score.
        # In production: 1.0 - sum(a * b for a, b in zip(vector, centroid))
        return float(sum(abs(v) for v in vector) / len(vector))
