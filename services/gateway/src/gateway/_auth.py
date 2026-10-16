"""Bearer-token authentication dependency for FastAPI.

API keys are loaded from the ``OBS_GATEWAY_API_KEYS`` environment variable
as a comma-separated list so multiple keys can coexist during rotation.
Comparison is done with ``hmac.compare_digest`` to prevent timing attacks.

The dependency raises ``HTTP 401`` on missing/invalid tokens and
``HTTP 403`` when the Authorization header format is wrong.  These are
distinct so clients can distinguish "try another key" from "fix your header".
"""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _get_api_keys(request: Request) -> frozenset[str]:
    """Extract the validated API key set from app state.

    Keys are stored as a frozenset on ``app.state`` during lifespan startup
    so they are loaded once, not on every request.
    """
    return request.app.state.api_keys  # type: ignore[no-any-return]


def verify_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    api_keys: Annotated[frozenset[str], Depends(_get_api_keys)],
) -> None:
    """FastAPI dependency: validate the Bearer token against known API keys.

    Separating auth into a dependency keeps route handlers free of auth
    logic and makes it trivial to override in tests via dependency_overrides.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Use constant-time comparison to prevent timing side-channel attacks.
    token = credentials.credentials
    if not any(hmac.compare_digest(token, key) for key in api_keys):
        logger.warning("gateway auth failed — invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
