"""BigQuery state management for alerts.

We fetch recent metrics joined with raw event metadata, filtering out
any rows that have already generated an alert in `alerts_history`.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from alerts.schemas import Alert, MetricRow


@runtime_checkable
class StateProtocol(Protocol):
    """Protocol for reading metrics and saving alert history."""

    async def fetch_recent_metrics(self, lookback_minutes: int) -> list[MetricRow]: ...
    async def save_alerts(self, alerts: list[Alert]) -> int: ...


class BigQueryState:
    def __init__(
        self,
        *,
        project_id: str,
        dataset_raw: str,
        table_raw: str,
        dataset_metrics: str,
        table_evals: str,
        table_alerts: str,
    ) -> None:
        self._project_id = project_id
        self._raw_ref = f"{project_id}.{dataset_raw}.{table_raw}"
        self._evals_ref = f"{project_id}.{dataset_metrics}.{table_evals}"
        self._alerts_ref = f"{project_id}.{dataset_metrics}.{table_alerts}"
        self._client: Any = None

    def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    async def fetch_recent_metrics(self, lookback_minutes: int) -> list[MetricRow]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_sync, lookback_minutes)

    def _fetch_sync(self, lookback_minutes: int) -> list[MetricRow]:
        client = self._ensure_client()
        # Find evaluated metrics in the time window, joined with raw events
        # (for app name/trace ID), excluding those that already have an alert
        # in the history table.
        query = f"""
            SELECT
                m.event_id,
                e.trace_id,
                e.application_name,
                m.groundedness_score,
                m.relevance_score,
                m.safety_flag,
                m.embedding_distance,
                m.judge_rationale,
                m.evaluated_at
            FROM `{self._evals_ref}` m
            JOIN `{self._raw_ref}` e
                ON m.event_id = e.event_id
            LEFT JOIN `{self._alerts_ref}` a
                ON m.event_id = a.event_id
            WHERE m.evaluated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @minutes MINUTE)
              AND a.event_id IS NULL
        """  # noqa: S608
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("minutes", "INT64", lookback_minutes)
            ]
        )
        job = client.query(query, job_config=job_config)
        rows = list(job.result())

        return [
            MetricRow(
                event_id=row["event_id"],
                trace_id=row["trace_id"],
                application_name=row["application_name"],
                groundedness_score=row["groundedness_score"],
                relevance_score=row["relevance_score"],
                safety_flag=row["safety_flag"],
                embedding_distance=row["embedding_distance"],
                judge_rationale=row["judge_rationale"],
                evaluated_at=row["evaluated_at"],
            )
            for row in rows
        ]

    async def save_alerts(self, alerts: list[Alert]) -> int:
        """Write alerts to history table to prevent duplicate notifications."""
        if not alerts:
            return 0
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._save_sync, alerts)

    def _save_sync(self, alerts: list[Alert]) -> int:
        client = self._ensure_client()
        rows = [a.model_dump(mode="json") for a in alerts]

        errors = client.insert_rows_json(
            self._alerts_ref,
            rows,
            row_ids=[a.alert_id for a in alerts],
        )
        if errors:
            raise RuntimeError(f"BQ alert history insert failed: {errors[0]}")
        return len(rows)
