"""Main entrypoint for Uvicorn."""

from obs_core.config import Settings
from obs_core.logging import configure_logging

from dashboard_api.app import create_app

# Initialise logging before creating the app so startup logs are structured
_settings = Settings()
configure_logging(
    log_level=_settings.log_level.value,
    service_name=_settings.service_name,
    environment=_settings.environment.value,
)

# Exposed for uvicorn to import
app = create_app(settings=_settings)
