"""Configuration for the alerts engine."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlertsSettings(BaseSettings):
    """Alerts-specific settings (OBS_ prefix, same .env file)."""

    model_config = SettingsConfigDict(
        env_prefix="OBS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bq_dataset_metrics: str = Field(default="obs_metrics")
    bq_table_evals: str = Field(default="genai_evals")
    bq_table_alerts: str = Field(
        default="alerts_history",
        description="Table recording sent alerts for deduplication.",
    )

    # Thresholds
    threshold_groundedness: int = Field(default=3, description="Alert if score < this.")
    threshold_relevance: int = Field(default=3, description="Alert if score < this.")
    threshold_drift: float = Field(default=0.8, description="Alert if distance > this.")

    # Integrations
    slack_webhook_url: SecretStr | None = Field(default=None)
    pagerduty_routing_key: SecretStr | None = Field(default=None)

    alert_lookback_minutes: int = Field(
        default=60,
        description="How far back to check for un-alerted metrics.",
    )
