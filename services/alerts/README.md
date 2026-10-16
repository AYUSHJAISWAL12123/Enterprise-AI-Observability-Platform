# obs-alerts

Alert rules engine. Runs as a CronJob to evaluate recent metrics against configurable thresholds and routes them to Slack or PagerDuty. Deduplicates alerts using BigQuery.

## Processing flow

```
BigQuery (obs_metrics.genai_evals + obs_raw.genai_events)
  └─ SELECT (last N minutes, WHERE event_id NOT IN alerts_history)
       └─ Rules Engine (Thresholds & Anomalies)
            ├─ WARNING -> SlackNotifier
            ├─ CRITICAL -> SlackNotifier + PagerDutyNotifier
            └─ BigQuery streaming insert (obs_metrics.alerts_history)
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OBS_GCP_PROJECT_ID` | ✅ | — | GCP project |
| `OBS_BQ_DATASET_METRICS` | | `obs_metrics` | Target dataset |
| `OBS_BQ_TABLE_EVALS` | | `genai_evals` | Metrics table |
| `OBS_BQ_TABLE_ALERTS` | | `alerts_history` | History for deduplication |
| `OBS_THRESHOLD_GROUNDEDNESS` | | `3` | Alert if metric < this |
| `OBS_THRESHOLD_DRIFT` | | `0.8` | Alert if distance > this |
| `OBS_SLACK_WEBHOOK_URL` | | — | Slack Webhook URL |
| `OBS_PAGERDUTY_ROUTING_KEY` | | — | PD Events API V2 key |
| `OBS_ALERT_LOOKBACK_MINUTES` | | `60` | Lookback window |

## Running tests

```bash
uv sync --all-extras
uv run pytest services/alerts/tests -v
```
