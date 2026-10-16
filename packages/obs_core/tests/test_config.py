"""Tests for obs_core.config."""

import pytest
from obs_core.config import Environment, Settings, get_settings
from pydantic import ValidationError

MINIMAL_ENV = {
    "OBS_GCP_PROJECT_ID": "my-project",
    "OBS_PUBSUB_TOPIC_RAW_EVENTS": "raw-events",
    "OBS_PUBSUB_SUBSCRIPTION_RAW_EVENTS": "raw-events-sub",
}


def make_settings(**overrides: str) -> Settings:
    env = {**MINIMAL_ENV, **overrides}
    return Settings(**{k.removeprefix("OBS_").lower(): v for k, v in env.items()})  # type: ignore[arg-type]


def test_defaults_applied() -> None:
    s = make_settings()
    assert s.gcp_region == "us-central1"
    assert s.bq_dataset_raw == "obs_raw"
    assert s.environment == Environment.DEVELOPMENT


def test_overrides_respected() -> None:
    s = make_settings(OBS_GCP_REGION="europe-west4", OBS_ENVIRONMENT="production")
    assert s.gcp_region == "europe-west4"
    assert s.environment == Environment.PRODUCTION


def test_blank_project_id_rejected() -> None:
    with pytest.raises(ValidationError, match="gcp_project_id"):
        make_settings(OBS_GCP_PROJECT_ID="   ")


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBS_GCP_PROJECT_ID", "proj")
    monkeypatch.setenv("OBS_PUBSUB_TOPIC_RAW_EVENTS", "t")
    monkeypatch.setenv("OBS_PUBSUB_SUBSCRIPTION_RAW_EVENTS", "s")
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()
