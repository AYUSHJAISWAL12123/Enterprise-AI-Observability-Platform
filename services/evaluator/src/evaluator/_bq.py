"""BigQuery Reader and Writer for evaluator state.

The Reader queries the raw events table for rows that do not yet have a
corresponding entry in the metrics table.

The Writer persists the EvalResult rows into the metrics table using
streaming inserts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

from evaluator.schemas import EvalResult, UnevaluatedEvent

logger = logging.getLogger(__name__)


@runtime_checkable
class ReaderProtocol(Protocol):
    """Protocol for fetching unevaluated events."""

    async def fetch_unevaluated(self, limit: int) -> list[UnevaluatedEvent]: ...


@runtime_checkable
class WriterProtocol(Protocol):
    """Protocol for saving evaluation results."""

    async def write_results(self, results: list[EvalResult]) -> int: ...


class BigQueryReader:
    """Reads unevaluated events from BigQuery."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_raw: str,
        table_raw: str,
        dataset_metrics: str,
        table_metrics: str,
    ) -> None:
        self._project_id = project_id
        self._raw_ref = f"{project_id}.{dataset_raw}.{table_raw}"
        self._metrics_ref = f"{project_id}.{dataset_metrics}.{table_metrics}"
        self._client: Any = None

    def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    async def fetch_unevaluated(self, limit: int) -> list[UnevaluatedEvent]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_sync, limit)

    def _fetch_sync(self, limit: int) -> list[UnevaluatedEvent]:
        client = self._ensure_client()
        query = f"""
            SELECT
                r.event_id,
                r.trace_id,
                r.messages
            FROM `{self._raw_ref}` r
            LEFT JOIN `{self._metrics_ref}` m
                ON r.event_id = m.event_id
            WHERE m.event_id IS NULL
            ORDER BY r.ingested_at ASC
            LIMIT @limit
        """  # noqa: S608
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("limit", "INT64", limit)
            ]
        )
        job = client.query(query, job_config=job_config)
        rows = list(job.result())

        events = []
        for row in rows:
            events.append(
                UnevaluatedEvent(
                    event_id=row["event_id"],
                    trace_id=row["trace_id"],
                    messages_json=row["messages"],
                    raw_row=dict(row.items()),
                )
            )
        return events


class BigQueryWriter:
    """Writes evaluation scores to the metrics dataset."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_metrics: str,
        table_metrics: str,
    ) -> None:
        self._project_id = project_id
        self._metrics_ref = f"{project_id}.{dataset_metrics}.{table_metrics}"
        self._client: Any = None

    def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    async def write_results(self, results: list[EvalResult]) -> int:
        if not results:
            return 0
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._write_sync, results)

    def _write_sync(self, results: list[EvalResult]) -> int:
        client = self._ensure_client()
        rows = [r.model_dump(mode="json") for r in results]

        # Use event_id as the insertId for deduplication
        errors = client.insert_rows_json(
            self._metrics_ref,
            rows,
            row_ids=[r.event_id for r in results],
        )
        if errors:
            raise RuntimeError(f"BQ insert failed: {errors[0]}")
        return len(rows)
