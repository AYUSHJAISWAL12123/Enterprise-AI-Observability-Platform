resource "google_pubsub_topic" "events" {
  name = "obs-events-topic"
}

resource "google_pubsub_subscription" "processor" {
  name  = "obs-events-sub"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 20
  
  # Protect against poison pills
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.events_dlq.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_topic" "events_dlq" {
  name = "obs-events-dlq"
}
