"""Gateway-specific configuration extending the shared obs_core Settings.

Gateway needs two additional config values not shared across services:
the comma-separated API key list and the Pub/Sub topic.  Rather than
subclassing Settings (which creates fragile coupling), we load them as
a separate small model so each service owns only what it needs.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Gateway-specific settings (OBS_ prefix, same .env file)."""

    model_config = SettingsConfigDict(
        env_prefix="OBS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gateway_api_keys: str = Field(
        ...,
        description="Comma-separated bearer tokens accepted by the gateway.",
    )

    @field_validator("gateway_api_keys")
    @classmethod
    def at_least_one_key(cls, v: str) -> str:
        """Fail fast if the operator forgot to set API keys."""
        keys = [k.strip() for k in v.split(",") if k.strip()]
        if not keys:
            raise ValueError("OBS_GATEWAY_API_KEYS must contain at least one key")
        return v

    def parsed_api_keys(self) -> frozenset[str]:
        """Return the key list as an immutable set for O(1) membership tests."""
        return frozenset(k.strip() for k in self.gateway_api_keys.split(",") if k.strip())
