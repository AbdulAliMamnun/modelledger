from __future__ import annotations

from pathlib import Path

import modelledger.scanner as scanner
from modelledger.scanner import scan_repository


def test_python_ast_contexts_and_line_numbers(tmp_path: Path, models: list[dict]) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        """model = "active-latest"
model_id = "unknown-id"
model_name = "unknown-name"
models = ["active-v1", "unknown-list"]
deployment = "unknown-deployment"
deployment_name = "unknown-deployment-name"
AI_MODEL = "unknown-ai"
OPENAI_MODEL = "unknown-openai"
ANTHROPIC_MODEL = "unknown-anthropic"
client.create(model="deprecated-latest")
config = {"model": "retired-v1"}
""",
        encoding="utf-8",
    )

    findings = scan_repository(tmp_path, models)

    assert findings[0]["model_id"] == "active-v1"
    assert findings[0]["matched_alias"] == "active-latest"
    assert findings[0]["line_number"] == 1
    assert {finding["matched_alias"] for finding in findings} == {
        "active-latest", "unknown-id", "unknown-name", "active-v1", "unknown-list",
        "unknown-deployment", "unknown-deployment-name", "unknown-ai", "unknown-openai",
        "unknown-anthropic", "deprecated-latest", "retired-v1",
    }


def test_negative_python_contexts_do_not_produce_findings(
    tmp_path: Path, models: list[dict]
) -> None:
    (tmp_path / "app.py").write_text(
        '''"""model = "retired-v1" in documentation."""
# model = "retired-v1"
data_model = "retired-v1"
some_model_id = "retired-v1"
message = "retired-v1"
replacement = "retired-v1"
''',
        encoding="utf-8",
    )

    assert scan_repository(tmp_path, models) == []


def test_non_python_contexts_lists_and_comments(tmp_path: Path, models: list[dict]) -> None:
    (tmp_path / "config.json").write_text(
        '{"models": ["active-v1", "unknown-json"], "replacement": "retired-v1"}',
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text(
        '''// model = "retired-v1"
/* model: "retired-v1" */
const data_model = "retired-v1";
const config = { model: "deprecated-latest" };
const text = "retired-v1";
const documentation = 'model = "retired-v1"';
''',
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "models:\n  - active-v1\n  - unknown-yaml\nreplacement: retired-v1\n",
        encoding="utf-8",
    )

    findings = scan_repository(tmp_path, models)

    assert {finding["matched_alias"] for finding in findings} == {
        "active-v1", "unknown-json", "deprecated-latest", "unknown-yaml"
    }


def test_documentation_and_comments_do_not_produce_findings(
    tmp_path: Path, models: list[dict]
) -> None:
    (tmp_path / "app.js").write_text(
        '''// model: "retired-v1"
/* deployment: "retired-v1" */
const url = "https://example.com/models";
const prose = '{ model: "retired-v1" }';
const multilineProse = `
model: "retired-v1"
deployment: "retired-v1"
`;
''',
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "description: |\n  model: retired-v1\n  deployment: retired-v1\n",
        encoding="utf-8",
    )

    assert scan_repository(tmp_path, models) == []


def test_all_compact_object_contexts_are_reported(
    tmp_path: Path, models: list[dict]
) -> None:
    (tmp_path / "config.json").write_text(
        '{"model": "active-v1", "deployment": "retired-v1"}\n', encoding="utf-8"
    )
    (tmp_path / "app.js").write_text(
        'const config = { model: "active-latest", deployment_name: "deprecated-v1" };\n',
        encoding="utf-8",
    )

    findings = scan_repository(tmp_path, models)

    assert {(finding["file_path"], finding["matched_alias"], finding["line_number"])
            for finding in findings} == {
        ("config.json", "active-v1", 1),
        ("config.json", "retired-v1", 1),
        ("app.js", "active-latest", 1),
        ("app.js", "deprecated-v1", 1),
    }


def test_supported_file_types(tmp_path: Path, models: list[dict]) -> None:
    for filename in (
        "app.js", "app.jsx", "app.mjs", "app.cjs", "app.ts", "app.tsx",
        "config.json", "config.yaml", "config.yml", "config.toml",
    ):
        (tmp_path / filename).write_text('model = "active-v1"\n', encoding="utf-8")

    findings = scan_repository(tmp_path, models)

    assert {finding["file_path"] for finding in findings} == {
        "app.js", "app.jsx", "app.mjs", "app.cjs", "app.ts", "app.tsx",
        "config.json", "config.yaml", "config.yml", "config.toml",
    }


def test_environment_template_names_and_contexts(tmp_path: Path, models: list[dict]) -> None:
    names = (
        ".env.example", ".env.local.example", ".env.test.example", ".env.template",
        "env.example", "env.template",
    )
    for name in names:
        (tmp_path / name).write_text(
            "AI_MODEL=active-v1\nOPENAI_MODEL=unknown-openai\nANTHROPIC_MODEL=unknown-anthropic\n",
            encoding="utf-8",
        )

    findings = scan_repository(tmp_path, models)

    assert {finding["file_path"] for finding in findings} == set(names)
    assert len(findings) == len(names) * 3


def test_generated_directories_and_binary_files_are_ignored(
    tmp_path: Path, models: list[dict]
) -> None:
    ignored_names = (
        ".git", ".venv", "venv", "node_modules", "build", "dist", ".next", ".nuxt",
        ".output", "out", "vendor", "coverage", "target", "generated",
    )
    for directory in ignored_names:
        ignored = tmp_path / directory
        ignored.mkdir()
        (ignored / "config.py").write_text('model = "retired-v1"', encoding="utf-8")
    (tmp_path / "binary.py").write_bytes(b'model = "retired-v1"\0')

    assert scan_repository(tmp_path, models) == []


def test_symlinked_file_outside_repository_is_ignored(tmp_path: Path, models: list[dict]) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text('model = "retired-v1"', encoding="utf-8")
    (repository / "linked.py").symlink_to(outside)

    assert scan_repository(repository, models) == []


def test_file_swapped_to_external_symlink_before_read_is_ignored(
    tmp_path: Path, models: list[dict], monkeypatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "config.py"
    source.write_text('model = "active-v1"', encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text('model = "retired-v1"', encoding="utf-8")

    def swapped_source_files(root: Path):
        source.unlink()
        source.symlink_to(outside)
        yield source

    monkeypatch.setattr(scanner, "_source_files", swapped_source_files)

    assert scan_repository(repository, models) == []
