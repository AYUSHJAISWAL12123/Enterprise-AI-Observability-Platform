"""Tests for processor._transformer."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from obs_core.schemas import GenAIEvent, GenAIMessage, MessageRole, ModelInfo, TokenUsage
from processor._transformer import event_to_bq_row

MODEL = ModelInfo(provider="google", name="gemini-2.0-flash-001")
MSG = GenAIMessage(role=MessageRole.USER, content="Hello")


def _event(**kw: object) -> GenAIEvent:
    base: dict[str, object] = {
        "trace_id": "t-1",
        "span_id": "s-1",
        "model": MODEL,
        "messages": [MSG],
        "application_name": "test-app",
    }
    base.update(kw)
    return GenAIEvent(**base)  # type: ignore[arg-type]


def test_required_fields_present() -> None:
    row = event_to_bq_row(_event())
    for field in ("event_id", "trace_id", "span_id", "model_name", "messages",
                  "application_name", "environment", "started_at", "ingested_at"):
        assert field in row, f"missing field: {field}"


def test_event_id_is_dedup_key() -> None:
    e = _event()
    row = event_to_bq_row(e)
    assert row["event_id"] == e.event_id


def test_messages_stored_as_json_string() -> None:
    row = event_to_bq_row(_event())
    parsed = json.loads(row["messages"])
    assert isinstance(parsed, list)
    assert parsed[0]["role"] == "user"
    assert parsed[0]["content"] == "Hello"


def test_token_usage_fields() -> None:
    e = _event(token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5))
    row = event_to_bq_row(e)
    assert row["prompt_tokens"] == 10
    assert row["completion_tokens"] == 5
    assert row["total_tokens"] == 15


def test_no_token_usage_yields_none_fields() -> None:
    row = event_to_bq_row(_event())
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None
    assert row["total_tokens"] is None


def test_latency_ms_computed() -> None:
    now = datetime.now(tz=UTC)
    e = _event(started_at=now, ended_at=now + timedelta(milliseconds=300))
    row = event_to_bq_row(e)
    assert row["latency_ms"] == pytest.approx(300.0, rel=1e-3)


def test_latency_ms_none_without_ended_at() -> None:
    row = event_to_bq_row(_event())
    assert row["latency_ms"] is None


def test_attributes_stored_as_json() -> None:
    e = _event(attributes={"k": "v", "n": 42})
    row = event_to_bq_row(e)
    parsed = json.loads(row["attributes"])
    assert parsed == {"k": "v", "n": 42}


def test_model_fields_flattened() -> None:
    row = event_to_bq_row(_event())
    assert row["model_provider"] == "google"
    assert row["model_name"] == "gemini-2.0-flash-001"
