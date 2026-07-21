import io
import json
from pathlib import Path

from modelledger import cli


def test_json_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "scan_repository", lambda path, models: [{
        "model_id": "active-v1", "matched_alias": "active-v1", "file_path": "app.py",
        "line_number": 1, "provider": "Test", "lifecycle_status": "active",
        "recommended_replacement": None, "deprecation_date": None, "shutdown_date": None,
    }])
    output = io.StringIO()

    exit_code = cli.main([str(tmp_path), "--json"], stdout=output)

    payload = json.loads(output.getvalue())
    assert payload[0]["risk"] == "none"
    assert exit_code == 0


def test_critical_finding_returns_nonzero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "scan_repository", lambda path, models: [{
        "model_id": "retired-v1", "matched_alias": "retired-v1", "file_path": "app.py",
        "line_number": 1, "provider": "Test", "lifecycle_status": "retired",
        "recommended_replacement": "active-v1", "deprecation_date": "2025-01-01",
        "shutdown_date": "2026-01-01",
    }])

    assert cli.main([str(tmp_path)], stdout=io.StringIO()) == 1


def test_no_critical_findings_returns_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "scan_repository", lambda path, models: [])

    assert cli.main([str(tmp_path)], stdout=io.StringIO()) == 0


def test_valid_custom_registry_is_used(tmp_path: Path) -> None:
    registry = tmp_path / "models.yaml"
    registry.write_text(
        """schema_version: 1
models:
  - model_id: custom-v1
    aliases: [custom-latest]
    provider: Custom Provider
    status: active
    deprecation_date: null
    shutdown_date: null
    recommended_replacement: null
    source_url: https://models.example.com/custom-v1
    last_verified_date: '2026-07-21'
""",
        encoding="utf-8",
    )
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "app.py").write_text('model = "custom-latest"\n', encoding="utf-8")
    output = io.StringIO()

    exit_code = cli.main(
        [str(repository), "--registry", str(registry), "--json"], stdout=output
    )

    assert exit_code == 0
    finding = json.loads(output.getvalue())[0]
    assert finding["model_id"] == "custom-v1"
    assert finding["provider"] == "Custom Provider"


def test_malformed_custom_registry_returns_exit_code_two(
    tmp_path: Path, capsys
) -> None:
    registry = tmp_path / "models.yaml"
    registry.write_text("schema_version: 1\nmodels: [unterminated", encoding="utf-8")

    exit_code = cli.main(
        [str(tmp_path), "--registry", str(registry)], stdout=io.StringIO()
    )

    assert exit_code == 2
    error = capsys.readouterr().err
    assert "Invalid YAML in model registry" in error
    assert len(error.splitlines()) == 1


def test_wrong_registry_field_type_returns_exit_code_two(tmp_path: Path, capsys) -> None:
    registry = tmp_path / "models.yaml"
    registry.write_text(
        """schema_version: 1
models:
  - model_id: broken-v1
    aliases: []
    provider: Test
    status: [active]
    deprecation_date: null
    shutdown_date: null
    recommended_replacement: null
    source_url: https://example.com
    last_verified_date: '2026-07-19'
""",
        encoding="utf-8",
    )
    exit_code = cli.main(
        [str(tmp_path), "--registry", str(registry)], stdout=io.StringIO()
    )

    assert exit_code == 2
    assert "status must be a string" in capsys.readouterr().err


def test_file_repository_path_returns_exit_code_two(tmp_path: Path, capsys) -> None:
    file_path = tmp_path / "not-a-directory.py"
    file_path.write_text('model = "anything"\n', encoding="utf-8")

    exit_code = cli.main([str(file_path)], stdout=io.StringIO())

    assert exit_code == 2
    error = capsys.readouterr().err
    assert "Repository path is not a directory" in error
    assert len(error.splitlines()) == 1
