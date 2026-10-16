"""BigQuery Reader for the Dashboard API.

Abstracts complex analytical SQL queries behind a clean async protocol.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol, runtime_checkable

from dashboard_api.schemas import MetricSummary, TraceDetail, TraceSummary


@runtime_checkable
class ReaderProtocol(Protocol):
    """Protocol for dashboard data reads."""

    async def get_summary(self, hours: int) -> MetricSummary: ...
    async def list_traces(self, limit: int, offset: int) -> list[TraceSummary]: ...
    async def get_trace(self, trace_id: str) -> TraceDetail | None: ...


class BigQueryReader:
    def __init__(
        self,
        *,
        project_id: str,
        dataset_raw: str,
        table_raw: str,
        dataset_metrics: str,
        table_evals: str,
    ) -> None:
        self._project_id = project_id
        self._raw_ref = f"{project_id}.{dataset_raw}.{table_raw}"
        self._evals_ref = f"{project_id}.{dataset_metrics}.{table_evals}"
        self._client: Any = None

    def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    async def get_summary(self, hours: int) -> MetricSummary:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_summary_sync, hours)

    def _get_summary_sync(self, hours: int) -> MetricSummary:
        client = self._ensure_client()
        query = f"""
            SELECT
                COUNT(r.event_id) as total_events,
                COUNT(m.event_id) as evaluated_events,
                COALESCE(SUM(CAST(m.safety_flag AS INT64)), 0) as safety_violations,
                COALESCE(AVG(m.groundedness_score), 0.0) as avg_groundedness,
                COALESCE(AVG(m.relevance_score), 0.0) as avg_relevance,
                COALESCE(AVG(r.latency_ms), 0.0) as avg_latency_ms
            FROM `{self._raw_ref}` r
            LEFT JOIN `{self._evals_ref}` m ON r.event_id = m.event_id
            WHERE r.ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
        """  # noqa: S608
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("hours", "INT64", hours)]
        )
        row = next(iter(client.query(query, job_config=job_config).result()))

        return MetricSummary(
            total_events=row["total_events"],
            evaluated_events=row["evaluated_events"],
            safety_violations=row["safety_violations"],
            avg_groundedness=float(row["avg_groundedness"]),
            avg_relevance=float(row["avg_relevance"]),
            avg_latency_ms=float(row["avg_latency_ms"]),
        )

    async def list_traces(self, limit: int, offset: int) -> list[TraceSummary]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._list_traces_sync, limit, offset)

    def _list_traces_sync(self, limit: int, offset: int) -> list[TraceSummary]:
        client = self._ensure_client()
        query = f"""
            SELECT
                r.trace_id,
                r.event_id,
                r.application_name,
                r.model_name,
                r.latency_ms,
                r.started_at as timestamp,
                m.groundedness_score,
                m.relevance_score,
                m.safety_flag,
                m.embedding_distance
            FROM `{self._raw_ref}` r
            LEFT JOIN `{self._evals_ref}` m ON r.event_id = m.event_id
            ORDER BY r.started_at DESC
            LIMIT @limit OFFSET @offset
        """  # noqa: S608
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result())

        return [
            TraceSummary(
                trace_id=row["trace_id"],
                event_id=row["event_id"],
                application_name=row["application_name"],
                model_name=row["model_name"],
                latency_ms=float(row["latency_ms"] or 0.0),
                groundedness_score=row["groundedness_score"],
                relevance_score=row["relevance_score"],
                safety_flag=row["safety_flag"],
                embedding_distance=row["embedding_distance"],
                timestamp=row["timestamp"].isoformat() if row["timestamp"] else "",
            )
            for row in rows
        ]

    async def get_trace(self, trace_id: str) -> TraceDetail | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_trace_sync, trace_id)

    def _get_trace_sync(self, trace_id: str) -> TraceDetail | None:
        client = self._ensure_client()
        query = f"""
            SELECT
                r.trace_id,
                r.event_id,
                r.application_name,
                r.model_name,
                r.latency_ms,
                r.started_at as timestamp,
                r.messages,
                r.attributes,
                m.groundedness_score,
                m.relevance_score,
                m.safety_flag,
                m.embedding_distance,
                m.judge_rationale
            FROM `{self._raw_ref}` r
            LEFT JOIN `{self._evals_ref}` m ON r.event_id = m.event_id
            WHERE r.trace_id = @trace_id
            LIMIT 1
        """  # noqa: S608
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("trace_id", "STRING", trace_id)]
        )
        rows = list(client.query(query, job_config=job_config).result())
        if not rows:
            return None

        row = rows[0]
        # BQ stores messages and attributes as JSON strings
        messages = json.loads(row["messages"]) if row["messages"] else []
        attributes = json.loads(row["attributes"]) if row["attributes"] else {}

        return TraceDetail(
            trace_id=row["trace_id"],
            event_id=row["event_id"],
            application_name=row["application_name"],
            model_name=row["model_name"],
            latency_ms=float(row["latency_ms"] or 0.0),
            groundedness_score=row["groundedness_score"],
            relevance_score=row["relevance_score"],
            safety_flag=row["safety_flag"],
            embedding_distance=row["embedding_distance"],
            timestamp=row["timestamp"].isoformat() if row["timestamp"] else "",
            messages=messages,
            judge_rationale=row["judge_rationale"],
            attributes=attributes,
        )
