from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def models() -> list[dict[str, Any]]:
    return [
        {
            "model_id": "active-v1",
            "aliases": ["active-latest"],
            "provider": "Test Provider",
            "status": "active",
            "deprecation_date": None,
            "shutdown_date": None,
            "recommended_replacement": None,
            "source_url": "https://example.com/models",
            "last_verified_date": "2026-07-19",
        },
        {
            "model_id": "deprecated-v1",
            "aliases": ["deprecated-latest"],
            "provider": "Test Provider",
            "status": "deprecated",
            "deprecation_date": "2026-01-01",
            "shutdown_date": "2026-08-01",
            "recommended_replacement": "active-v1",
            "source_url": "https://example.com/models",
            "last_verified_date": "2026-07-19",
        },
        {
            "model_id": "retired-v1",
            "aliases": [],
            "provider": "Test Provider",
            "status": "retired",
            "deprecation_date": "2025-01-01",
            "shutdown_date": "2026-01-01",
            "recommended_replacement": "active-v1",
            "source_url": "https://example.com/models",
            "last_verified_date": "2026-07-19",
        },
    ]
