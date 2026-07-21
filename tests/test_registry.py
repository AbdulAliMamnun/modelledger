from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from modelledger.registry import find_model, load_registry


TODAY = date(2026, 7, 19)


def registry_yaml(models: str, schema_version: str = "1") -> str:
    return f"schema_version: {schema_version}\nmodels:\n{models}"


def model_yaml(
    *,
    model_id: str = "test-v1",
    aliases: str = "[test-latest]",
    status: str = "active",
    deprecation_date: str = "null",
    shutdown_date: str = "null",
    replacement: str = "null",
    source_url: str = "https://example.com/models",
) -> str:
    return f"""  - model_id: {model_id}
    aliases: {aliases}
    provider: Test Provider
    status: {status}
    deprecation_date: {deprecation_date}
    shutdown_date: {shutdown_date}
    recommended_replacement: {replacement}
    source_url: {source_url}
    last_verified_date: '2026-07-19'
"""


def write_registry(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_default_packaged_registry_loads() -> None:
    models = load_registry(today=TODAY)

    assert {model["model_id"] for model in models} == {
        "demo-active-v1", "demo-deprecated-v1", "demo-retired-v1"
    }


def test_load_explicit_registry_and_match_alias(tmp_path: Path) -> None:
    path = write_registry(tmp_path, registry_yaml(model_yaml()))

    models = load_registry(path, today=TODAY)

    assert find_model("test-latest", models)["model_id"] == "test-v1"
    assert find_model("not-registered", models) is None


def test_malformed_yaml_is_normalized(tmp_path: Path) -> None:
    path = write_registry(tmp_path, "schema_version: 1\nmodels: [unterminated")

    with pytest.raises(ValueError, match="Invalid YAML in model registry") as error:
        load_registry(path, today=TODAY)

    assert error.value.__cause__ is not None


@pytest.mark.parametrize("status", ["[active]", "1", "true"])
def test_status_must_be_a_supported_string(tmp_path: Path, status: str) -> None:
    path = write_registry(tmp_path, registry_yaml(model_yaml(status=status)))

    with pytest.raises(ValueError, match="status must be a string"):
        load_registry(path, today=TODAY)


def test_deprecated_requires_deprecation_date(tmp_path: Path) -> None:
    path = write_registry(tmp_path, registry_yaml(model_yaml(status="deprecated")))

    with pytest.raises(ValueError, match="require a deprecation_date"):
        load_registry(path, today=TODAY)


def test_retired_requires_shutdown_date(tmp_path: Path) -> None:
    path = write_registry(
        tmp_path,
        registry_yaml(model_yaml(status="retired", deprecation_date="'2025-01-01'")),
    )

    with pytest.raises(ValueError, match="require a shutdown_date"):
        load_registry(path, today=TODAY)


def test_shutdown_cannot_precede_deprecation(tmp_path: Path) -> None:
    path = write_registry(
        tmp_path,
        registry_yaml(model_yaml(
            status="deprecated",
            deprecation_date="'2026-07-01'",
            shutdown_date="'2026-06-01'",
        )),
    )

    with pytest.raises(ValueError, match="cannot precede"):
        load_registry(path, today=TODAY)


@pytest.mark.parametrize(
    ("deprecation_date", "shutdown_date"),
    [("'2026-07-01'", "null"), ("null", "'2026-07-01'")],
)
def test_active_rejects_past_lifecycle_dates(
    tmp_path: Path, deprecation_date: str, shutdown_date: str
) -> None:
    path = write_registry(
        tmp_path,
        registry_yaml(model_yaml(
            deprecation_date=deprecation_date, shutdown_date=shutdown_date
        )),
    )

    with pytest.raises(ValueError, match="active models cannot have past lifecycle dates"):
        load_registry(path, today=TODAY)


def test_schema_version_rejects_boolean(tmp_path: Path) -> None:
    path = write_registry(tmp_path, registry_yaml(model_yaml(), schema_version="true"))

    with pytest.raises(ValueError, match="integer schema_version"):
        load_registry(path, today=TODAY)


@pytest.mark.parametrize(
    "source_url",
    [
        "example.com/models",
        "ftp://example.com/models",
        "not-a-url",
        "https://example",
        "https://example.com bad/path",
        "https://-example.com/models",
        "https://example.com:invalid/models",
    ],
)
def test_source_url_must_be_absolute_http_url(tmp_path: Path, source_url: str) -> None:
    path = write_registry(
        tmp_path, registry_yaml(model_yaml(source_url=source_url))
    )

    with pytest.raises(ValueError, match="absolute HTTP or HTTPS URL"):
        load_registry(path, today=TODAY)


@pytest.mark.parametrize(
    "source_url", ["https://models.example.com/v1", "http://localhost:8000/models"]
)
def test_source_url_accepts_plausible_http_authority(
    tmp_path: Path, source_url: str
) -> None:
    path = write_registry(tmp_path, registry_yaml(model_yaml(source_url=source_url)))

    assert load_registry(path, today=TODAY)[0]["source_url"] == source_url


def test_replacement_must_resolve(tmp_path: Path) -> None:
    path = write_registry(
        tmp_path, registry_yaml(model_yaml(replacement="missing-v2"))
    )

    with pytest.raises(ValueError, match="does not resolve"):
        load_registry(path, today=TODAY)


@pytest.mark.parametrize("replacement", ["test-v1", "test-latest"])
def test_replacement_cannot_resolve_to_self(tmp_path: Path, replacement: str) -> None:
    path = write_registry(
        tmp_path, registry_yaml(model_yaml(replacement=replacement))
    )

    with pytest.raises(ValueError, match="cannot refer to itself"):
        load_registry(path, today=TODAY)


def test_replacement_can_resolve_through_alias(tmp_path: Path) -> None:
    models = (
        model_yaml(model_id="old-v1", aliases="[]", status="deprecated",
                   deprecation_date="'2026-01-01'", replacement="new-latest")
        + model_yaml(model_id="new-v2", aliases="[new-latest]")
    )
    path = write_registry(tmp_path, registry_yaml(models))

    loaded = load_registry(path, today=TODAY)

    assert loaded[0]["recommended_replacement"] == "new-latest"
