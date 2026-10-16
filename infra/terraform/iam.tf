# 1. Gateway
resource "google_service_account" "gateway" {
  account_id   = "obs-gateway-sa"
  display_name = "Gateway Service Account"
}
resource "google_pubsub_topic_iam_member" "gateway_pubsub" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.gateway.email}"
}

# 2. Processor
resource "google_service_account" "processor" {
  account_id   = "obs-processor-sa"
  display_name = "Processor Service Account"
}
resource "google_pubsub_subscription_iam_member" "processor_sub" {
  subscription = google_pubsub_subscription.processor.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.processor.email}"
}
resource "google_bigquery_dataset_iam_member" "processor_bq" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.processor.email}"
}

# 3. Evaluator
resource "google_service_account" "evaluator" {
  account_id   = "obs-evaluator-sa"
  display_name = "Evaluator Service Account"
}
resource "google_project_iam_member" "evaluator_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.evaluator.email}"
}
resource "google_bigquery_dataset_iam_member" "evaluator_bq_metrics" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.evaluator.email}"
}
resource "google_bigquery_dataset_iam_member" "evaluator_bq_raw" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.evaluator.email}"
}

# Workload Identity bindings (Mapping GSA to KSA)
locals {
  services = {
    gateway   = google_service_account.gateway.email
    processor = google_service_account.processor.email
    evaluator = google_service_account.evaluator.email
  }
}

resource "google_service_account_iam_member" "workload_identity" {
  for_each           = local.services
  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${each.key}-ksa]"
}
