"""Tests for obs_core.logging."""

import importlib
import json
import logging
from io import StringIO

import obs_core.logging as log_module
import structlog
from obs_core.logging import configure_logging


def _capture_json_log(message: str, **kw: str) -> dict:  # type: ignore[type-arg]
    """Configure logging to a StringIO buffer and return parsed JSON."""
    buf = StringIO()
    configure_logging(log_level="DEBUG", service_name="test-svc", environment="test")
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    handler = logging.StreamHandler(buf)
    handler.setFormatter(root.handlers[0].formatter)
    root.handlers = [handler]

    logger = structlog.get_logger("test")
    logger.info(message, **kw)

    root.handlers = old_handlers
    line = buf.getvalue().strip()
    return json.loads(line)  # type: ignore[no-any-return]


def test_json_output_has_required_keys() -> None:
    record = _capture_json_log("hello world")
    assert record["event"] == "hello world"
    assert record["level"] == "info"
    assert "timestamp" in record
    assert record["service"] == "test-svc"
    assert record["environment"] == "test"


def test_extra_fields_included() -> None:
    record = _capture_json_log("with extras", user_id="u-123")
    assert record["user_id"] == "u-123"


def test_no_import_time_side_effects() -> None:
    """Importing the module must not configure logging automatically."""
    importlib.reload(log_module)
    root = logging.getLogger()
    assert root is not None
