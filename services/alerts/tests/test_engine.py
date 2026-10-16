"""Tests for alerts engine rules."""

from datetime import UTC, datetime

from alerts._config import AlertsSettings
from alerts.engine import ConfiguredRulesEngine
from alerts.schemas import MetricRow, Severity


def _metric(**kw: object) -> MetricRow:
    base = {
        "event_id": "e-1",
        "trace_id": "t-1",
        "application_name": "app",
        "groundedness_score": 5,
        "relevance_score": 5,
        "safety_flag": False,
        "embedding_distance": 0.1,
        "judge_rationale": "ok",
        "evaluated_at": datetime.now(tz=UTC).isoformat(),
    }
    base.update(kw)
    return MetricRow(**base)  # type: ignore[arg-type]


def test_rules_safe_metric() -> None:
    settings = AlertsSettings()
    engine = ConfiguredRulesEngine(settings)
    alerts = engine.evaluate(_metric())
    assert len(alerts) == 0


def test_rules_safety_violation() -> None:
    settings = AlertsSettings()
    engine = ConfiguredRulesEngine(settings)
    alerts = engine.evaluate(_metric(safety_flag=True))
    assert len(alerts) == 1
    assert alerts[0].rule_name == "SafetyViolation"
    assert alerts[0].severity == Severity.CRITICAL


def test_rules_low_groundedness() -> None:
    settings = AlertsSettings(threshold_groundedness=4)
    engine = ConfiguredRulesEngine(settings)
    alerts = engine.evaluate(_metric(groundedness_score=3))
    assert len(alerts) == 1
    assert alerts[0].rule_name == "LowGroundedness"
    assert alerts[0].severity == Severity.WARNING


def test_rules_multiple_violations() -> None:
    settings = AlertsSettings(threshold_groundedness=4)
    engine = ConfiguredRulesEngine(settings)
    # Both safety and groundedness breached
    alerts = engine.evaluate(_metric(safety_flag=True, groundedness_score=2))
    assert len(alerts) == 2
    rule_names = {a.rule_name for a in alerts}
    assert rule_names == {"SafetyViolation", "LowGroundedness"}
