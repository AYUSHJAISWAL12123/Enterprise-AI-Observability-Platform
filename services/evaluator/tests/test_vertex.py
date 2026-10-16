"""Tests for Vertex AI evaluator integration."""

from __future__ import annotations

import json

import pytest
from evaluator._vertex import VertexEvaluator, VertexProtocol
from evaluator.schemas import EvalScoreCard


class DummyGenerateResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class DummyEmbedResponse:
    class Embedding:
        def __init__(self, values: list[float]) -> None:
            self.values = values

    def __init__(self, values: list[float]) -> None:
        self.embeddings = [self.Embedding(values)]


class DummyModels:
    def __init__(self, json_response: str, embed_vector: list[float]) -> None:
        self._json_response = json_response
        self._embed_vector = embed_vector

    async def generate_content(self, **kwargs: object) -> DummyGenerateResponse:
        return DummyGenerateResponse(self._json_response)

    async def embed_content(self, **kwargs: object) -> DummyEmbedResponse:
        return DummyEmbedResponse(self._embed_vector)


class DummyAio:
    def __init__(self, models: DummyModels) -> None:
        self.models = models


class DummyClient:
    def __init__(self, json_response: str, embed_vector: list[float]) -> None:
        self.aio = DummyAio(DummyModels(json_response, embed_vector))


@pytest.fixture
def good_scorecard() -> str:
    return json.dumps(
        {
            "groundedness": 5,
            "relevance": 4,
            "safety_flag": False,
            "rationale": "Looks good.",
        }
    )


@pytest.mark.asyncio
async def test_vertex_protocol_satisfied() -> None:
    evaluator = VertexEvaluator(
        project_id="test",
        location="test",
        judge_model="m1",
        embedding_model="m2",
    )
    assert isinstance(evaluator, VertexProtocol)


@pytest.mark.asyncio
async def test_evaluate_judge_success(good_scorecard: str) -> None:
    evaluator = VertexEvaluator(
        project_id="test",
        location="test",
        judge_model="m1",
        embedding_model="m2",
    )
    evaluator._client = DummyClient(good_scorecard, [0.1, 0.2])

    result = await evaluator.evaluate_judge("messages_json")
    assert isinstance(result, EvalScoreCard)
    assert result.groundedness == 5
    assert result.relevance == 4
    assert result.safety_flag is False


@pytest.mark.asyncio
async def test_evaluate_judge_fallback_on_bad_json() -> None:
    evaluator = VertexEvaluator(
        project_id="test",
        location="test",
        judge_model="m1",
        embedding_model="m2",
    )
    evaluator._client = DummyClient('{"bad": "schema"}', [0.1])

    # Should not raise, should return fallback safe scorecard
    result = await evaluator.evaluate_judge("messages_json")
    assert result.safety_flag is True
    assert result.groundedness == 3
    assert result.relevance == 3
    assert "Failed to parse" in result.rationale


@pytest.mark.asyncio
async def test_compute_drift() -> None:
    evaluator = VertexEvaluator(
        project_id="test",
        location="test",
        judge_model="m1",
        embedding_model="m2",
    )
    # mock vector [0.5, -0.5] -> absolute sum is 1.0, len is 2 -> mean is 0.5
    evaluator._client = DummyClient("{}", [0.5, -0.5])

    drift = await evaluator.compute_drift("messages_json")
    assert drift == pytest.approx(0.5)
