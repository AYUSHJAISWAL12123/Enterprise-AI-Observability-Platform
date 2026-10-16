"""Configuration specific to the evaluator worker."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EvaluatorSettings(BaseSettings):
    """Evaluator-specific settings (OBS_ prefix, same .env file)."""

    model_config = SettingsConfigDict(
        env_prefix="OBS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bq_dataset_metrics: str = Field(
        default="obs_metrics",
        description="Dataset where evaluation scores are written.",
    )
    bq_table_evals: str = Field(
        default="genai_evals",
        description="Table where evaluation scores are written.",
    )
    vertex_judge_model: str = Field(
        default="gemini-2.0-flash-001",
        description="Model used for LLM-as-judge (must support Structured Outputs).",
    )
    vertex_embedding_model: str = Field(
        default="text-embedding-004",
        description="Model used for drift calculation.",
    )
    eval_batch_size: int = Field(
        default=50,
        description="Number of events to evaluate in one CronJob execution.",
    )
