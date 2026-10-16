"""FastAPI app factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from obs_core.config import Settings

from dashboard_api._config import DashboardSettings
from dashboard_api._reader import BigQueryReader
from dashboard_api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise state when the server starts."""
    settings = getattr(app.state, "settings", Settings())
    dash_settings = getattr(app.state, "dash_settings", DashboardSettings())

    # Set reader into state only if it hasn't been mocked for tests
    if not hasattr(app.state, "reader"):
        app.state.reader = BigQueryReader(
            project_id=settings.gcp_project_id,
            dataset_raw=settings.bq_dataset_raw,
            table_raw=settings.bq_table_events,
            dataset_metrics=dash_settings.bq_dataset_metrics,
            table_evals=dash_settings.bq_table_evals,
        )
    yield


def create_app(
    settings: Settings | None = None,
    dash_settings: DashboardSettings | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Observability Dashboard API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Allow tests to inject config before lifespan runs
    if settings:
        app.state.settings = settings
    if dash_settings:
        app.state.dash_settings = dash_settings

    app.include_router(router)
    return app
