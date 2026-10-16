"""Tests for alerts worker."""

import pytest
from alerts.schemas import Alert, MetricRow, Severity
from alerts.worker import run_alerts


class FakeState:
    def __init__(self, metrics: list[MetricRow]) -> None:
        self.metrics = metrics
        self.saved_alerts: list[Alert] = []

    async def fetch_recent_metrics(self, lookback_minutes: int) -> list[MetricRow]:
        return self.metrics

    async def save_alerts(self, alerts: list[Alert]) -> int:
        self.saved_alerts.extend(alerts)
        return len(alerts)


class FakeEngine:
    def __init__(self, alerts_to_yield: list[Alert]) -> None:
        self.alerts_to_yield = alerts_to_yield

    def evaluate(self, metric: MetricRow) -> list[Alert]:
        return self.alerts_to_yield


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[Alert] = []

    async def send(self, alert: Alert) -> None:
        self.sent.append(alert)


@pytest.fixture
def dummy_metric() -> MetricRow:
    return MetricRow(
        event_id="e-1",
        trace_id="t-1",
        application_name="app",
        groundedness_score=5,
        relevance_score=5,
        safety_flag=False,
        embedding_distance=0.1,
        judge_rationale="ok",
        evaluated_at="2025-01-01T00:00:00Z",
    )


@pytest.fixture
def dummy_alert() -> Alert:
    return Alert(
        alert_id="a-1",
        event_id="e-1",
        trace_id="t-1",
        application_name="app",
        rule_name="Rule",
        severity=Severity.WARNING,
        message="msg",
        created_at="2025-01-01T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_run_alerts_empty_queue() -> None:
    state = FakeState([])
    engine = FakeEngine([])
    notif = FakeNotifier()

    written = await run_alerts(
        state=state, engine=engine, notifiers=[notif], lookback_minutes=60
    )
    assert written == 0


@pytest.mark.asyncio
async def test_run_alerts_sends_and_saves(
    dummy_metric: MetricRow, dummy_alert: Alert
) -> None:
    state = FakeState([dummy_metric])
    engine = FakeEngine([dummy_alert])
    notif1 = FakeNotifier()
    notif2 = FakeNotifier()

    written = await run_alerts(
        state=state, engine=engine, notifiers=[notif1, notif2], lookback_minutes=60
    )
    assert written == 1
    assert len(state.saved_alerts) == 1
    assert state.saved_alerts[0] == dummy_alert

    # Both notifiers received the alert
    assert len(notif1.sent) == 1
    assert len(notif2.sent) == 1
