"""Async retry helper with exponential backoff.

Kept as a standalone module so the retry policy can be tested and reused
independently of the HTTP client.  We avoid third-party retry libraries
(tenacity, stamina) to keep the SDK dependency footprint minimal.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def async_retry(
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator: retry an async function with exponential backoff + jitter.

    Exponential backoff prevents retry storms against a degraded gateway.
    Jitter (random fraction of the delay) avoids synchronised retries when
    many SDK instances fail at the same moment.

    Args:
        max_attempts: Total attempts before re-raising the last exception.
        base_delay: Initial delay in seconds before the first retry.
        max_delay: Cap on the computed delay to prevent very long waits.
        retryable_exceptions: Only retry on these exception types.
    """

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    # Add up to 25% jitter.
                    jitter = delay * 0.25 * (asyncio.get_event_loop().time() % 1)
                    sleep_for = delay + jitter
                    logger.warning(
                        "obs_sdk retry",
                        extra={
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "sleep_seconds": round(sleep_for, 3),
                            "error": str(exc),
                        },
                    )
                    await asyncio.sleep(sleep_for)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
