# obs-dashboard-api

FastAPI backend serving aggregated observability metrics and trace drill-downs for the React UI. Connects to BigQuery.

## Endpoints

* `GET /api/v1/metrics?hours=24` -> Aggregated statistics (total requests, average groundedness, etc.)
* `GET /api/v1/traces?limit=50&offset=0` -> Paginated list of recent traces
* `GET /api/v1/traces/{trace_id}` -> Complete trace details including `messages` and judge scores

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OBS_GCP_PROJECT_ID` | ✅ | — | GCP project |
| `OBS_BQ_DATASET_RAW` | | `obs_raw` | Source dataset for events |
| `OBS_BQ_TABLE_EVENTS` | | `genai_events` | Source table |
| `OBS_BQ_DATASET_METRICS` | | `obs_metrics` | Source dataset for evals |
| `OBS_BQ_TABLE_EVALS` | | `genai_evals` | Evals table |

## Running tests

```bash
uv sync --all-extras
uv run pytest services/dashboard_api/tests -v
```
