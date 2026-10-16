"""Notifiers for outbound alerting."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import httpx

from alerts.schemas import Alert, Severity

logger = logging.getLogger(__name__)


@runtime_checkable
class NotifierProtocol(Protocol):
    """Protocol for sending alerts to external systems."""

    async def send(self, alert: Alert) -> None: ...


class SlackNotifier:
    """Sends warnings and critical alerts to a Slack Webhook."""

    def __init__(self, webhook_url: str | None) -> None:
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=5.0)

    async def send(self, alert: Alert) -> None:
        if not self._webhook_url:
            return

        icon = "🚨" if alert.severity == Severity.CRITICAL else "⚠️"
        payload = {
            "text": f"{icon} *{alert.rule_name}* in `{alert.application_name}`\n"
            f"> {alert.message}\n"
            f"_Trace: {alert.trace_id}_"
        }
        try:
            resp = await self._client.post(self._webhook_url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Slack webhook failed", exc_info=exc)


class PagerDutyNotifier:
    """Routes CRITICAL alerts to PagerDuty Events API V2."""

    PD_URL = "https://events.pagerduty.com/v2/enqueue"

    def __init__(self, routing_key: str | None) -> None:
        self._routing_key = routing_key
        self._client = httpx.AsyncClient(timeout=5.0)

    async def send(self, alert: Alert) -> None:
        if not self._routing_key or alert.severity != Severity.CRITICAL:
            # PD is only for critical severity
            return

        payload = {
            "routing_key": self._routing_key,
            "event_action": "trigger",
            "dedup_key": alert.alert_id,
            "payload": {
                "summary": f"{alert.rule_name} for {alert.application_name}",
                "severity": "critical",
                "source": alert.application_name,
                "custom_details": {
                    "trace_id": alert.trace_id,
                    "event_id": alert.event_id,
                    "message": alert.message,
                },
            },
        }
        try:
            resp = await self._client.post(self.PD_URL, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("PagerDuty enqueue failed", exc_info=exc)
