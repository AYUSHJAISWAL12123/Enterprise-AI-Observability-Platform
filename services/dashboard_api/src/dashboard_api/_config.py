"""Configuration for Dashboard API."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardSettings(BaseSettings):
    """Dashboard-specific settings (OBS_ prefix, same .env file)."""

    model_config = SettingsConfigDict(
        env_prefix="OBS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bq_dataset_metrics: str = Field(default="obs_metrics")
    bq_table_evals: str = Field(default="genai_evals")
