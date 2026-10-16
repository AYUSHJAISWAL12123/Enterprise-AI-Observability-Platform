"""Centralised, environment-variable-driven configuration.

A single :class:`Settings` instance should be created at service startup
and injected wherever needed.  Using pydantic-settings means every value
is validated and typed at construction time, catching misconfiguration
before the service accepts traffic.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    """Platform-wide settings loaded exclusively from environment variables.

    All services share this class so that GCP resource names, dataset IDs
    and feature flags are defined in one place and never hard-coded.
    """

    model_config = SettingsConfigDict(
        env_prefix="OBS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── GCP ───────────────────────────────────────────────────────────────────
    gcp_project_id: str = Field(..., description="GCP project ID")
    gcp_region: str = Field("us-central1", description="Primary GCP region")

    # ── Pub/Sub ───────────────────────────────────────────────────────────────
    pubsub_topic_raw_events: str = Field(..., description="Raw events Pub/Sub topic")
    pubsub_subscription_raw_events: str = Field(
        ..., description="Processor subscription on the raw events topic"
    )

    # ── BigQuery ──────────────────────────────────────────────────────────────
    bq_dataset_raw: str = Field("obs_raw", description="BigQuery raw dataset")
    bq_dataset_curated: str = Field("obs_curated", description="BigQuery curated dataset")
    bq_dataset_eval: str = Field("obs_eval", description="BigQuery eval dataset")
    bq_dataset_metrics: str = Field("obs_metrics", description="BigQuery metrics dataset")
    bq_table_events: str = Field("genai_events", description="Raw events table")

    # ── Service ───────────────────────────────────────────────────────────────
    environment: Environment = Field(Environment.DEVELOPMENT)
    log_level: LogLevel = Field(LogLevel.INFO)
    service_name: str = Field("obs-platform", description="Emitted in every log line")

    # ── Vertex AI ─────────────────────────────────────────────────────────────
    vertex_judge_model: str = Field(
        "gemini-2.0-flash-001", description="Gemini model used as LLM judge"
    )
    vertex_embedding_model: str = Field(
        "text-embedding-004", description="Vertex embedding model for drift detection"
    )

    @field_validator("gcp_project_id")
    @classmethod
    def project_id_not_empty(cls, v: str) -> str:
        """Fail fast rather than sending requests to a blank project."""
        if not v.strip():
            raise ValueError("gcp_project_id must not be empty")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-level singleton Settings instance.

    Use only at the top of a service's ``main()`` or in FastAPI lifespan;
    pass the result down via dependency injection.  The cache means
    environment is read exactly once per process.
    """
    return Settings()  # type: ignore[call-arg]
