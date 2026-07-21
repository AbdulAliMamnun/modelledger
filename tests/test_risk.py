from datetime import date

import pytest

from modelledger.risk import classify_risk


@pytest.mark.parametrize(
    ("status", "shutdown_date", "expected"),
    [
        ("retired", "2025-01-01", "critical"),
        ("deprecated", "2026-08-01", "high"),
        ("deprecated", "2027-01-01", "medium"),
        ("deprecated", None, "medium"),
        ("unknown", None, "low"),
        ("active", None, "none"),
    ],
)
def test_risk_classification(status: str, shutdown_date: str | None, expected: str) -> None:
    assert classify_risk(
        {"lifecycle_status": status, "shutdown_date": shutdown_date},
        today=date(2026, 7, 19),
    ) == expected
