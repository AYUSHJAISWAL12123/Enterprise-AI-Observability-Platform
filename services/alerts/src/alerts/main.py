"""Alerts service CronJob entrypoint."""

import asyncio
import sys

from obs_core.config import Settings
from obs_core.logging import configure_logging

from alerts._bq import BigQueryState
from alerts._config import AlertsSettings
from alerts._notifiers import PagerDutyNotifier, SlackNotifier
from alerts.engine import ConfiguredRulesEngine
from alerts.worker import run_alerts


async def _main() -> None:
    settings = Settings()
    alerts_settings = AlertsSettings()

    configure_logging(
        log_level=settings.log_level.value,
        service_name=settings.service_name,
        environment=settings.environment.value,
    )

    state = BigQueryState(
        project_id=settings.gcp_project_id,
        dataset_raw=settings.bq_dataset_raw,
        table_raw=settings.bq_table_events,
        dataset_metrics=alerts_settings.bq_dataset_metrics,
        table_evals=alerts_settings.bq_table_evals,
        table_alerts=alerts_settings.bq_table_alerts,
    )

    engine = ConfiguredRulesEngine(alerts_settings)

    notifiers = [
        SlackNotifier(
            alerts_settings.slack_webhook_url.get_secret_value()
            if alerts_settings.slack_webhook_url else None
        ),
        PagerDutyNotifier(
            alerts_settings.pagerduty_routing_key.get_secret_value()
            if alerts_settings.pagerduty_routing_key else None
        ),
    ]

    try:
        await run_alerts(
            state=state,
            engine=engine,
            notifiers=notifiers,
            lookback_minutes=alerts_settings.alert_lookback_minutes,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
