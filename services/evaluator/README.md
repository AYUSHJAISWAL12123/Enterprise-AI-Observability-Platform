# obs-evaluator

Kubernetes CronJob worker that reads raw events from BigQuery and evaluates them using Vertex AI (LLM-as-judge & embeddings).

## Processing flow

```
BigQuery (obs_raw.genai_events)
  └─ SELECT WHERE event_id NOT IN metrics
       └─ Vertex AI (concurrently per event)
            ├─ gemini-2.0-flash-001 (LLM-as-judge: groundedness, relevance, safety)
            ├─ text-embedding-004 (Drift: cosine distance)
            └─ BigQuery streaming insert (obs_metrics.genai_evals)
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OBS_GCP_PROJECT_ID` | ✅ | — | GCP project |
| `OBS_GCP_REGION` | | `us-central1` | Vertex AI region |
| `OBS_BQ_DATASET_RAW` | | `obs_raw` | Source dataset |
| `OBS_BQ_TABLE_EVENTS` | | `genai_events` | Source table |
| `OBS_BQ_DATASET_METRICS` | | `obs_metrics` | Target dataset |
| `OBS_BQ_TABLE_EVALS` | | `genai_evals` | Target table |
| `OBS_VERTEX_JUDGE_MODEL` | | `gemini-2.0-flash-001` | Must support Structured Outputs |
| `OBS_VERTEX_EMBEDDING_MODEL` | | `text-embedding-004` | Used for drift metrics |
| `OBS_EVAL_BATCH_SIZE` | | `50` | Number of events per CronJob execution |

## Running tests

```bash
uv sync --all-extras
uv run pytest services/evaluator/tests -v
```
