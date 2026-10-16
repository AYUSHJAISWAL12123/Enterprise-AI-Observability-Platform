"""Structured JSON logging via structlog.

Call :func:`configure_logging` once at service startup.  Every subsequent
``structlog.get_logger()`` call returns a pre-configured bound logger that
emits machine-readable JSON, making logs indexable in Cloud Logging without
additional parsing rules.

Design notes:
- Timestamps are ISO-8601 UTC so Cloud Logging can parse them natively.
- The ``service`` and ``environment`` fields are injected globally so
  every log line carries them without per-call boilerplate.
- Plain ``logging`` (stdlib) is redirected to structlog so third-party
  library logs (e.g. httpx, google-cloud) share the same format.
"""

import logging
import sys

import structlog
from structlog.types import EventDict, Processor, WrappedLogger


def _drop_color_message_key(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    """Remove uvicorn's ``color_message`` key; keep only ``message``."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(
    *,
    log_level: str = "INFO",
    service_name: str = "obs-platform",
    environment: str = "development",
    render_json: bool = True,
) -> None:
    """Wire up structlog with shared processors and optional JSON rendering.

    Args:
        log_level: Standard Python log level string (e.g. ``"INFO"``).
        service_name: Injected as ``service`` in every log record.
        environment: Injected as ``environment`` in every log record.
        render_json: Emit JSON (production) or coloured console (dev).
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _drop_color_message_key,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Inject platform-wide fields into every event.
        _static_fields(service=service_name, environment=environment),
    ]

    if render_json:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def _static_fields(**fields: str) -> Processor:
    """Return a structlog processor that merges fixed key-value pairs."""

    def processor(
        _logger: WrappedLogger, _method: str, event_dict: EventDict
    ) -> EventDict:
        for k, v in fields.items():
            event_dict.setdefault(k, v)
        return event_dict

    return processor
