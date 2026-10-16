"""obs_sdk - Client SDK for AI apps to emit GenAI telemetry.

Public surface area is intentionally small.  Internal modules (_retry,
_client, _span) are private by convention.
"""

from obs_sdk._client import GatewayClientProtocol, GatewayError, HttpGatewayClient
from obs_sdk._span import Span

__all__ = [
    "GatewayClientProtocol",
    "GatewayError",
    "HttpGatewayClient",
    "Span",
]
