"""FastAPI route handlers for the ingestion gateway.

Route logic is kept thin — validation is delegated to Pydantic (via the
request body type), PII redaction to ``_pii``, and publishing to
``_publisher``.  Each route handler does exactly one thing so it is
easy to read and test.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from obs_core.schemas import GenAIEvent

from gateway._auth import verify_token
from gateway._pii import redact_event
from gateway._publisher import PublisherProtocol

logger = structlog.get_logger(__name__)

router = APIRouter()


def _get_publisher(request: Request) -> PublisherProtocol:
    """Extract the publisher from app state (injected during lifespan)."""
    return request.app.state.publisher


@router.post(
    "/v1/events",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_token)],
    summary="Ingest a GenAI telemetry event",
)
async def ingest_event(
    event: GenAIEvent,
    publisher: Annotated[PublisherProtocol, Depends(_get_publisher)],
) -> JSONResponse:
    """Validate, redact PII, and publish a GenAI telemetry event.

    Returns 202 (Accepted) rather than 201 because publishing to Pub/Sub is
    fire-and-acknowledge — the event has been accepted for processing but
    may not yet be written to BigQuery.

    The ``event_id`` in the response body is the idempotency key clients
    can use to correlate this ingestion with downstream evaluation results.
    """
    clean_event = redact_event(event)
    message_id = await publisher.publish_event(clean_event)

    logger.info(
        "gateway event accepted",
        event_id=clean_event.event_id,
        trace_id=clean_event.trace_id,
        application_name=clean_event.application_name,
        message_id=message_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"event_id": clean_event.event_id, "message_id": message_id},
    )


@router.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    """Kubernetes liveness probe — always returns 200 if the process is alive."""
    return JSONResponse({"status": "ok"})


@router.get("/ready", include_in_schema=False)
async def ready(request: Request) -> JSONResponse:
    """Kubernetes readiness probe — returns 200 only when publisher is wired up."""
    publisher = getattr(request.app.state, "publisher", None)
    if publisher is None:
        return JSONResponse(
            {"status": "not ready", "reason": "publisher not initialised"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return JSONResponse({"status": "ready"})
