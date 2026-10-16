# Enterprise AI Observability Platform

A scalable, event-driven platform deployed on Google Kubernetes Engine (GKE) to evaluate, alert on, and observe Large Language Model interactions in production. 

## Architecture

1. **Ingestion (`obs_sdk` & `services/gateway`)**: Edge AI applications send telemetry to a FastAPI ingestion gateway. Data is validated, PII is redacted, and events are buffered into Pub/Sub.
2. **Streaming (`services/processor`)**: A background worker streams events from Pub/Sub into BigQuery for durable storage, ensuring idempotency.
3. **Automated Evaluation (`services/evaluator`)**: A Kubernetes CronJob polls BigQuery for new, unevaluated interactions and delegates them to Vertex AI (`Gemini`) for LLM-as-a-judge scoring (Groundedness, Relevance, Safety, Embedding Drift).
4. **Alerts Engine (`services/alerts`)**: Evaluates metrics against predefined thresholds and routes critical violations to PagerDuty or Slack, heavily deduplicated via BigQuery state.
5. **Dashboard (`services/dashboard_api` & `web/dashboard`)**: A Vite + React application providing a complete overview of AI performance and deep drill-downs into interaction failures.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic, Structlog, `google-genai`, `google-cloud-bigquery`
- **Frontend**: React 18, Vite, Tailwind CSS, TypeScript
- **Infrastructure**: Terraform, Kustomize, GitHub Actions, Docker Compose

## Getting Started Locally

### Prerequisites
- [uv](https://github.com/astral-sh/uv) package manager
- Docker Desktop
- Node.js v20+ (for UI dev)
- GCP Project with BigQuery, Pub/Sub, and Vertex AI enabled

### 1. GCP Setup
Ensure you are authenticated:
```bash
gcloud auth application-default login
```

Create a `.env` file at the root:
```env
OBS_ENVIRONMENT=development
OBS_GCP_PROJECT_ID=your-project-id
OBS_GATEWAY_AUTH_TOKENS=dev-secret-key
```

Provision infrastructure:
*(Note: Run Terraform in `infra/terraform` or manually create the datasets/topics if preferred).*

### 2. Run the Backend Sandbox
Spin up the Gateway, Processor, Evaluator, Alerts, and API locally using `docker-compose`:
```bash
make build
make up
```

### 3. Run the Frontend UI
```bash
cd web/dashboard
npm install
npm run dev
```

### 4. Simulate Traffic
Once the backend is running, simulate AI application traces:
```bash
make simulate
```
Check the UI at `http://localhost:5173` to watch the traces flow from `Ingested` -> `Evaluated` -> `Alerted`.
