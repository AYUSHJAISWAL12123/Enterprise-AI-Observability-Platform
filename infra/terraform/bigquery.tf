resource "google_bigquery_dataset" "raw" {
  dataset_id  = "obs_raw"
  description = "Raw ingested events"
  location    = "US"
}

resource "google_bigquery_table" "events" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  table_id   = "genai_events"
  schema     = file("${path.module}/../../sql/schema_events.json")

  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }
}

resource "google_bigquery_dataset" "metrics" {
  dataset_id  = "obs_metrics"
  description = "Evaluated AI metrics and alerts"
  location    = "US"
}

resource "google_bigquery_table" "evals" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  table_id   = "genai_evals"
  schema     = file("${path.module}/../../sql/schema_evals.json")

  time_partitioning {
    type  = "DAY"
    field = "evaluated_at"
  }
}

resource "google_bigquery_table" "alerts" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  table_id   = "alerts_history"
  schema     = file("${path.module}/../../sql/schema_alerts.json")

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
}
