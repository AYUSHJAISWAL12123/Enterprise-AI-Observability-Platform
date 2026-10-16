# obs_core

Shared foundation package for the AI Observability Platform.

## What's in here

| Module | Purpose |
|---|---|
| `config.py` | `Settings` – all env-var config with validation |
| `logging.py` | `configure_logging()` – structlog JSON setup |
| `schemas.py` | `GenAIEvent` and friends – OTel GenAI telemetry schemas |

## Configuration

All variables use the `OBS_` prefix:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OBS_GCP_PROJECT_ID` | ✅ | — | GCP project |
| `OBS_GCP_REGION` | | `us-central1` | Primary region |
| `OBS_PUBSUB_TOPIC_RAW_EVENTS` | ✅ | — | Raw events topic |
| `OBS_PUBSUB_SUBSCRIPTION_RAW_EVENTS` | ✅ | — | Processor subscription |
| `OBS_BQ_DATASET_RAW` | | `obs_raw` | Raw BQ dataset |
| `OBS_ENVIRONMENT` | | `development` | `development\|staging\|production` |
| `OBS_LOG_LEVEL` | | `INFO` | Log level |
| `OBS_VERTEX_JUDGE_MODEL` | | `gemini-2.0-flash-001` | Judge model |

## Running tests

```bash
cd obs-platform
uv sync --all-extras
uv run pytest packages/obs_core/tests -v
```

## Linting & type-check

```bash
uv run ruff check packages/obs_core
uv run mypy packages/obs_core/src
```
