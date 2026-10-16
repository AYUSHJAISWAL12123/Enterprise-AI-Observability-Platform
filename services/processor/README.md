# obs-processor

Pub/Sub → BigQuery stream processor. Pulls `GenAIEvent` messages from a Pub/Sub subscription, parses and transforms them, and writes to BigQuery with `event_id`-based deduplication.

## Processing flow

```
Pub/Sub subscription
  └─ pull (sync, up to N messages)
       ├─ ValidationError → nack → Dead-Letter Topic
       └─ valid GenAIEvent
            └─ BigQuery streaming insert (insertId = event_id)
                 ├─ success → ack
                 └─ BigQueryWriteError → nack (retry)
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OBS_GCP_PROJECT_ID` | ✅ | — | GCP project |
| `OBS_PUBSUB_SUBSCRIPTION_RAW_EVENTS` | ✅ | — | Pull subscription |
| `OBS_BQ_DATASET_RAW` | | `obs_raw` | Target dataset |
| `OBS_BQ_TABLE_EVENTS` | | `genai_events` | Target table |
| `OBS_ENVIRONMENT` | | `development` | |
| `OBS_LOG_LEVEL` | | `INFO` | |

## Running tests

```bash
uv sync --all-extras
uv run pytest services/processor/tests -v
```

## BigQuery schema

The `obs_raw.genai_events` table is created by Terraform (see `infra/terraform/`).
Key columns: `event_id` (dedup key), `messages` (JSON), `ingested_at` (TIMESTAMP).

## Upgrade path

To replace streaming inserts with Storage Write API (stronger dedup guarantees):
replace `BigQueryWriter` in `_writer.py` — `WriterProtocol` is unchanged.
