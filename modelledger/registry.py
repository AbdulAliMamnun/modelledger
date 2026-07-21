"""Load and query ModelLedger's AI model lifecycle registry."""

from __future__ import annotations

from datetime import date
from importlib import resources
from pathlib import Path
import re
from typing import Any, TextIO
from urllib.parse import urlparse

import yaml


REQUIRED_FIELDS = {
    "model_id",
    "aliases",
    "provider",
    "status",
    "deprecation_date",
    "shutdown_date",
    "recommended_replacement",
    "source_url",
    "last_verified_date",
}
VALID_STATUSES = {"active", "deprecated", "retired"}


def _iso_date(value: Any, field: str, model_id: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError(f"{model_id}: {field} must be an ISO date or null")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(f"{model_id}: {field} must be an ISO date or null") from error


def _validate_model(model: Any, index: int, today: date) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise ValueError(f"Registry entry {index} must be a mapping")

    missing = REQUIRED_FIELDS - model.keys()
    if missing:
        raise ValueError(
            f"Registry entry {index} is missing fields: {', '.join(sorted(missing))}"
        )

    model_id = model["model_id"]
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError(f"Registry entry {index} has an invalid model_id")
    if not isinstance(model["provider"], str) or not model["provider"].strip():
        raise ValueError(f"{model_id}: provider must be a non-empty string")

    status = model["status"]
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise ValueError(
            f"{model_id}: status must be a string equal to one of "
            f"{', '.join(sorted(VALID_STATUSES))}"
        )
    aliases = model["aliases"]
    if not isinstance(aliases, list) or not all(
        isinstance(alias, str) and alias.strip() for alias in aliases
    ):
        raise ValueError(f"{model_id}: aliases must be a list of non-empty strings")

    replacement = model["recommended_replacement"]
    if replacement is not None and (
        not isinstance(replacement, str) or not replacement.strip()
    ):
        raise ValueError(
            f"{model_id}: recommended_replacement must be a non-empty string or null"
        )
    source_url = model["source_url"]
    if not isinstance(source_url, str):
        raise ValueError(f"{model_id}: source_url must be an absolute HTTP or HTTPS URL")
    parsed_url = urlparse(source_url)
    try:
        host = parsed_url.hostname
        parsed_url.port
    except ValueError:
        host = None
    plausible_host = bool(
        host
        and not parsed_url.username
        and not parsed_url.password
        and not any(character.isspace() for character in source_url)
        and (
            host == "localhost"
            or (
                "." in host
                and not host.startswith(".")
                and not host.endswith(".")
                and all(
                    re.fullmatch(r"[A-Za-z0-9-]+", label)
                    and not label.startswith("-")
                    and not label.endswith("-")
                    for label in host.split(".")
                )
            )
        )
    )
    if parsed_url.scheme not in {"http", "https"} or not plausible_host:
        raise ValueError(f"{model_id}: source_url must be an absolute HTTP or HTTPS URL")

    validated = dict(model)
    for field in ("deprecation_date", "shutdown_date", "last_verified_date"):
        validated[field] = _iso_date(model[field], field, model_id)
    if validated["last_verified_date"] is None:
        raise ValueError(f"{model_id}: last_verified_date cannot be null")

    deprecation = validated["deprecation_date"]
    shutdown = validated["shutdown_date"]
    if status == "deprecated" and deprecation is None:
        raise ValueError(f"{model_id}: deprecated models require a deprecation_date")
    if status == "retired" and shutdown is None:
        raise ValueError(f"{model_id}: retired models require a shutdown_date")
    if deprecation and shutdown and date.fromisoformat(shutdown) < date.fromisoformat(deprecation):
        raise ValueError(f"{model_id}: shutdown_date cannot precede deprecation_date")
    if status == "active" and any(
        value is not None and date.fromisoformat(value) <= today
        for value in (deprecation, shutdown)
    ):
        raise ValueError(f"{model_id}: active models cannot have past lifecycle dates")
    return validated


def _load_yaml(stream: TextIO, source: object) -> Any:
    try:
        return yaml.safe_load(stream)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in model registry: {source}") from error


def load_registry(
    path: str | Path | None = None, *, today: date | None = None
) -> list[dict[str, Any]]:
    """Load and validate the packaged registry or an explicit registry path."""
    if path is None:
        resource = resources.files("modelledger").joinpath("data/models.yaml")
        with resource.open(encoding="utf-8") as registry_file:
            registry = _load_yaml(registry_file, "modelledger/data/models.yaml")
    else:
        registry_path = Path(path)
        with registry_path.open(encoding="utf-8") as registry_file:
            registry = _load_yaml(registry_file, registry_path)

    schema_version = registry.get("schema_version") if isinstance(registry, dict) else None
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("Model registry must declare integer schema_version: 1")
    models = registry.get("models")
    if not isinstance(models, list):
        raise ValueError("Model registry must contain a models list")

    validated = [
        _validate_model(model, index, today or date.today())
        for index, model in enumerate(models)
    ]
    identifiers: dict[str, dict[str, Any]] = {}
    for model in validated:
        for identifier in [model["model_id"], *model["aliases"]]:
            if identifier in identifiers:
                raise ValueError(f"Duplicate model identifier or alias: {identifier}")
            identifiers[identifier] = model

    for model in validated:
        replacement = model["recommended_replacement"]
        if replacement is None:
            continue
        target = identifiers.get(replacement)
        if target is None:
            raise ValueError(
                f"{model['model_id']}: recommended_replacement does not resolve: {replacement}"
            )
        if target is model:
            raise ValueError(
                f"{model['model_id']}: recommended_replacement cannot refer to itself"
            )
    return validated


def find_model(
    model_id: str, models: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Find a model by canonical identifier or exact alias."""
    for model in models if models is not None else load_registry():
        if model["model_id"] == model_id or model_id in model["aliases"]:
            return model
    return None
