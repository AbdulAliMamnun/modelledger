"""Risk classification for model lifecycle findings."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable


APPROACHING_SHUTDOWN_DAYS = 90


def classify_risk(model: dict[str, Any], today: date | None = None) -> str:
    """Classify one model using lifecycle status and shutdown proximity."""
    current_date = today or date.today()
    status = model.get("lifecycle_status", model.get("status", "unknown"))
    shutdown_value = model.get("shutdown_date")
    shutdown_date = date.fromisoformat(shutdown_value) if shutdown_value else None

    if status in {"retired", "shutdown"} or (
        shutdown_date is not None and shutdown_date <= current_date
    ):
        return "critical"
    if status == "deprecated":
        if shutdown_date is not None and 0 < (shutdown_date - current_date).days <= APPROACHING_SHUTDOWN_DAYS:
            return "high"
        return "medium"
    if status == "unknown":
        return "low"
    return "none"


def assess_findings(
    findings: Iterable[dict[str, Any]], today: date | None = None
) -> list[dict[str, Any]]:
    """Add a risk level to each scanner finding."""
    return [dict(finding, risk=classify_risk(finding, today)) for finding in findings]
