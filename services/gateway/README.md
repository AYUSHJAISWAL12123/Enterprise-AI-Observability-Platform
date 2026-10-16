# obs-gateway

Ingestion gateway for the AI Observability Platform. Receives `GenAIEvent` payloads from instrumented apps via the `obs_sdk`, redacts PII, and publishes to Pub/Sub for downstream processing.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/events` | Bearer token | Ingest a GenAI telemetry event |
| `GET` | `/health` | None | Liveness probe |
| `GET` | `/ready` | None | Readiness probe |

## Configuration (environment variables)

| Variable | Required | Description |
|---|---|---|
| `OBS_GCP_PROJECT_ID` | ✅ | GCP project |
| `OBS_PUBSUB_TOPIC_RAW_EVENTS` | ✅ | Pub/Sub topic for raw events |
| `OBS_PUBSUB_SUBSCRIPTION_RAW_EVENTS` | ✅ | (used by processor, set here for shared config) |
| `OBS_GATEWAY_API_KEYS` | ✅ | Comma-separated bearer tokens (rotate without downtime) |
| `OBS_ENVIRONMENT` | | `development\|staging\|production` (default: `development`) |
| `OBS_LOG_LEVEL` | | `INFO` (default) |

## Running locally

```bash
# Set required env vars
export OBS_GCP_PROJECT_ID=my-project
export OBS_PUBSUB_TOPIC_RAW_EVENTS=raw-events
export OBS_PUBSUB_SUBSCRIPTION_RAW_EVENTS=raw-events-sub
export OBS_GATEWAY_API_KEYS=dev-secret-key

# Run
cd obs-platform
uv run uvicorn gateway.main:app --reload --port 8080
```

## Running tests

```bash
uv sync --all-extras
uv run pytest services/gateway/tests -v
```

## PII Redaction

The gateway redacts the following patterns from message content before publishing:

| Pattern | Placeholder |
|---|---|
| Email addresses | `[EMAIL]` |
| Phone numbers | `[PHONE]` |
| SSNs | `[SSN]` |
| Credit card numbers | `[CREDIT_CARD]` |
| IPv4 addresses | `[IP_ADDRESS]` |

To upgrade to Cloud DLP, replace `gateway/_pii.py` — the interface is unchanged.
