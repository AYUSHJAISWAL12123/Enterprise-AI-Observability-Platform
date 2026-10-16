"""obs_core - shared foundation for the AI Observability Platform.

Exports the public surface area: config, logging setup, and schemas.
Nothing in this package has import-time side effects; callers must
explicitly call :func:`configure_logging` before emitting logs.
"""

from obs_core.config import Settings
from obs_core.logging import configure_logging
from obs_core.schemas import (
    GenAIEvent,
    GenAIMessage,
    MessageRole,
    ModelInfo,
    TokenUsage,
)

__all__ = [
    "GenAIEvent",
    "GenAIMessage",
    "MessageRole",
    "ModelInfo",
    "Settings",
    "TokenUsage",
    "configure_logging",
]
