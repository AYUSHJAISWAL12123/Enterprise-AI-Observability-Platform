"""FastAPI application factory for the ingestion gateway.

Using a factory function (``create_app``) instead of a module-level ``app``
variable prevents import-time side effects and makes it straightforward to
create isolated app instances in tests with different configurations.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from obs_core.config import Settings
from obs_core.logging import configure_logging

from gateway._config import GatewaySettings
from gateway._publisher import PubSubPublisher
from gateway.routes import router


def create_app(
    *,
    settings: Settings | None = None,
    gateway_settings: GatewaySettings | None = None,
) -> FastAPI:
    """Build and return a configured FastAPI application.

    Accepts optional pre-built settings so tests can inject fakes without
    touching environment variables.  In production, both are ``None`` and
    are constructed from env vars inside the lifespan.

    Args:
        settings: Shared platform settings; constructed from env if not given.
        gateway_settings: Gateway-only settings; constructed from env if not given.
    """
    _settings = settings
    _gw_settings = gateway_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        nonlocal _settings, _gw_settings
        s = _settings or Settings()
        gw = _gw_settings or GatewaySettings()

        configure_logging(
            log_level=s.log_level.value,
            service_name=s.service_name,
            environment=s.environment.value,
        )

        app.state.api_keys = gw.parsed_api_keys()
        app.state.publisher = PubSubPublisher(
            project_id=s.gcp_project_id,
            topic_id=s.pubsub_topic_raw_events,
        )

        yield  # application is running

        # Cleanup: nothing async to close for the sync pubsub client.

    app = FastAPI(
        title="obs-platform Ingestion Gateway",
        version="0.1.0",
        description="Validates GenAI telemetry events, redacts PII, publishes to Pub/Sub.",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app
