"""BigQuery writer — streaming inserts with insertId-based deduplication.

``insertId`` (set to ``event_id``) is BigQuery's best-effort dedup key for
streaming inserts.  It deduplicates within approximately 1 minute, which is
sufficient for our retry window.  If stronger exactly-once guarantees are
needed, replace ``BigQueryWriter`` with a Storage Write API implementation
— the ``WriterProtocol`` interface is unchanged.

Rows are written in batches to amortise per-request overhead.  Partial
failures (some rows succeed, some fail) are reported via ``InsertErrors``;
the writer raises on any error so the worker can nack the entire batch for
redelivery rather than silently dropping data.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

from obs_core.schemas import GenAIEvent

from processor._transformer import event_to_bq_row

logger = logging.getLogger(__name__)


@runtime_checkable
class WriterProtocol(Protocol):
    """Structural interface for writing events to the data store."""

    async def write_events(self, events: list[GenAIEvent]) -> int:
        """Write a batch of events; return the number successfully written."""
        ...


class BigQueryWriteError(Exception):
    """Raised when BigQuery streaming insert returns insert errors."""


class BigQueryWriter:
    """Writes GenAIEvents to BigQuery via streaming inserts.

    Args:
        project_id: GCP project owning the dataset.
        dataset_id: BigQuery dataset ID (e.g. ``obs_raw``).
        table_id: BigQuery table ID (e.g. ``genai_events``).
    """

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str,
        table_id: str,
    ) -> None:
        self._project_id = project_id
        self._dataset_id = dataset_id
        self._table_id = table_id
        # Typed Any: google-cloud-bigquery stubs are partial.
        self._client: Any = None  # lazy init

    def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    @property
    def _table_ref(self) -> str:
        return f"{self._project_id}.{self._dataset_id}.{self._table_id}"

    async def write_events(self, events: list[GenAIEvent]) -> int:
        """Serialise events to rows and stream-insert into BigQuery."""
        if not events:
            return 0
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._insert_sync, events)

    def _insert_sync(self, events: list[GenAIEvent]) -> int:
        """Blocking insert; runs in a thread pool executor."""
        client = self._ensure_client()
        rows = [event_to_bq_row(e) for e in events]

        # Pass event_id as the BQ insertId for best-effort deduplication.
        errors = client.insert_rows_json(
            self._table_ref,
            rows,
            row_ids=[e.event_id for e in events],
        )

        if errors:
            # errors is a list of dicts; surface the first for diagnostics.
            raise BigQueryWriteError(
                f"BigQuery insert errors for {len(errors)} rows: {errors[0]}"
            )

        logger.info(
            "processor wrote %d rows to BigQuery",
            len(rows),
            extra={"table": self._table_ref},
        )
        return len(rows)
