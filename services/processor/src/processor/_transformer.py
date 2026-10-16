"""Transform a GenAIEvent into a BigQuery row dictionary.

Keeping transformation in its own pure module (no I/O, no side effects)
makes it trivially testable and separates the concern of "what shape does
BQ need?" from "how do we write to BQ?".

BigQuery column naming follows snake_case.  Nested message content is
stored as a JSON string in a BQ JSON column so we never need a schema
migration when message structure evolves.

All timestamps are ISO-8601 strings; BQ infers TIMESTAMP from them when
the table is created with autodetect or when the schema uses TIMESTAMP type.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from obs_core.schemas import GenAIEvent


def event_to_bq_row(event: GenAIEvent) -> dict[str, Any]:
    """Convert a ``GenAIEvent`` to a flat BigQuery-compatible row dict.

    The ``event_id`` is used as the streaming-insert ``insertId`` (dedup
    key).  BigQuery deduplicates within a best-effort window (~1 minute);
    for stronger guarantees the caller should upgrade to Storage Write API
    with COMMITTED mode.

    Returns:
        A dict whose keys map directly to the ``obs_raw.genai_events`` schema.
    """
    usage = event.token_usage
    return {
        "event_id": event.event_id,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "parent_span_id": event.parent_span_id,
        "model_provider": event.model.provider,
        "model_name": event.model.name,
        "model_version": event.model.version,
        # Store messages as JSON so schema never needs migration for new fields.
        "messages": json.dumps(
            [m.model_dump(mode="json") for m in event.messages]
        ),
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
        "application_name": event.application_name,
        "application_version": event.application_version,
        "environment": event.environment,
        "started_at": event.started_at.isoformat(),
        "ended_at": event.ended_at.isoformat() if event.ended_at else None,
        "latency_ms": event.latency_ms,
        "attributes": json.dumps(event.attributes),
        "ingested_at": datetime.now(tz=UTC).isoformat(),
    }
