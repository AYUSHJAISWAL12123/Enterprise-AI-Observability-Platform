"""Alert rules engine.

Evaluates metric rows against configured thresholds to generate Alerts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from alerts._config import AlertsSettings
from alerts.schemas import Alert, MetricRow, Severity


@runtime_checkable
class RulesEngineProtocol(Protocol):
    """Protocol for rule evaluation."""

    def evaluate(self, metric: MetricRow) -> list[Alert]: ...


class ConfiguredRulesEngine:
    """Evaluates metrics using thresholds from configuration."""

    def __init__(self, settings: AlertsSettings) -> None:
        self.settings = settings

    def evaluate(self, metric: MetricRow) -> list[Alert]:
        """Run all rules against a metric row. Returns all triggered alerts."""
        alerts = []
        now = datetime.now(tz=UTC).isoformat()

        # Rule 1: Safety Violations (Critical)
        if metric.safety_flag:
            alerts.append(
                Alert(
                    alert_id=f"{metric.event_id}-safety",
                    event_id=metric.event_id,
                    trace_id=metric.trace_id,
                    application_name=metric.application_name,
                    rule_name="SafetyViolation",
                    severity=Severity.CRITICAL,
                    message=f"Safety violation detected. Rationale: {metric.judge_rationale}",
                    created_at=now,
                )
            )

        # Rule 2: Low Groundedness (Warning)
        if metric.groundedness_score < self.settings.threshold_groundedness:
            alerts.append(
                Alert(
                    alert_id=f"{metric.event_id}-groundedness",
                    event_id=metric.event_id,
                    trace_id=metric.trace_id,
                    application_name=metric.application_name,
                    rule_name="LowGroundedness",
                    severity=Severity.WARNING,
                    message=f"Groundedness ({metric.groundedness_score}) below threshold. Rationale: {metric.judge_rationale}",
                    created_at=now,
                )
            )

        # Rule 3: High Embedding Drift (Warning)
        if metric.embedding_distance > self.settings.threshold_drift:
            alerts.append(
                Alert(
                    alert_id=f"{metric.event_id}-drift",
                    event_id=metric.event_id,
                    trace_id=metric.trace_id,
                    application_name=metric.application_name,
                    rule_name="EmbeddingDrift",
                    severity=Severity.WARNING,
                    message=f"Embedding distance ({metric.embedding_distance:.2f}) exceeded threshold.",
                    created_at=now,
                )
            )

        # (Relevance logic could be similarly added)

        return alerts
