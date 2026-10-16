"""Alerts orchestration loop."""

from __future__ import annotations

import asyncio

import structlog

from alerts._bq import StateProtocol
from alerts._notifiers import NotifierProtocol
from alerts.engine import RulesEngineProtocol

logger = structlog.get_logger(__name__)


async def run_alerts(
    *,
    state: StateProtocol,
    engine: RulesEngineProtocol,
    notifiers: list[NotifierProtocol],
    lookback_minutes: int,
) -> int:
    """Fetch recent metrics, evaluate rules, notify, and record history."""
    metrics = await state.fetch_recent_metrics(lookback_minutes=lookback_minutes)
    if not metrics:
        logger.info("alerts empty queue")
        return 0

    alerts_to_send = []
    for metric in metrics:
        triggered = engine.evaluate(metric)
        alerts_to_send.extend(triggered)

    if not alerts_to_send:
        logger.info("alerts no rules triggered", evaluated_metrics=len(metrics))
        return 0

    # 1. Dispatch notifications concurrently
    dispatch_tasks = []
    for alert in alerts_to_send:
        for notifier in notifiers:
            dispatch_tasks.append(notifier.send(alert))

    await asyncio.gather(*dispatch_tasks)

    # 2. Save history to avoid duplicate alerts on the next run
    # If this fails, the CronJob crashes and alerts might be duplicated,
    # which is preferable to silent dropping (at-least-once delivery).
    written: int = await state.save_alerts(alerts_to_send)

    logger.info(
        "alerts cycle complete",
        metrics_checked=len(metrics),
        alerts_sent=written,
    )
    return written
