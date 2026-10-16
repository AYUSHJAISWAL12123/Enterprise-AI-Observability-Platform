variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for resources"
  type        = string
  default     = "us-central1"
}

variable "k8s_namespace" {
  description = "Kubernetes namespace where apps are deployed"
  type        = string
  default     = "obs-platform"
}
