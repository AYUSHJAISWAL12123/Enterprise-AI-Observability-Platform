"""FastAPI router for Dashboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from dashboard_api._reader import ReaderProtocol
from dashboard_api.schemas import MetricSummary, TraceDetail, TraceSummary

router = APIRouter(prefix="/api/v1")


def _get_reader(request: Request) -> ReaderProtocol:
    """Extract reader from app state."""
    reader = getattr(request.app.state, "reader", None)
    if not reader:
        raise HTTPException(status_code=503, detail="Reader not configured")
    return reader

@router.get("/metrics", response_model=MetricSummary)
async def get_metrics(
    request: Request,
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
) -> MetricSummary:
    """Get aggregated metrics over the specified time window."""
    reader = _get_reader(request)
    return await reader.get_summary(hours=hours)

@router.get("/traces", response_model=list[TraceSummary])
async def list_traces(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TraceSummary]:
    """Get a paginated list of recent traces."""
    reader = _get_reader(request)
    traces: list[TraceSummary] = await reader.list_traces(limit=limit, offset=offset)
    return traces


@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace(
    request: Request,
    trace_id: str,
) -> TraceDetail:
    """Get detailed information for a single trace, including messages."""
    reader = _get_reader(request)
    trace = await reader.get_trace(trace_id=trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace
