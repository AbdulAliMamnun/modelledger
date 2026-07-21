# ModelLedger

ModelLedger is "Dependabot for AI models." It scans source repositories for model dependencies, matches known identifiers and aliases against a lifecycle registry, and reports lifecycle risk.

Milestone 1 is a local CLI prototype. The bundled lifecycle records are clearly labeled synthetic demo data and must not be treated as real provider lifecycle facts.

## Setup

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

The `test` extra installs pytest plus the setuptools and wheel tooling required by the packaging regression test.

## Run the demo

Human-readable output:

```bash
.venv/bin/python -m modelledger.cli demo_repository
```

JSON output:

```bash
.venv/bin/python -m modelledger.cli demo_repository --json
```

To scan with an explicit registry:

```bash
.venv/bin/python -m modelledger.cli demo_repository --registry path/to/models.yaml
```

The demo intentionally includes a retired model, so the command exits with status `1`. A scan exits `0` when no critical findings exist and `2` when input or registry validation fails.

## Registry schema

`modelledger/data/models.yaml` declares `schema_version: 1` and a `models` list. Every record requires a canonical `model_id`, aliases, provider, status (`active`, `deprecated`, or `retired`), deprecation and shutdown dates, recommended replacement, source URL, and last verified date. The registry is installed as package data, so the default CLI registry works outside a source checkout.

The scanner examines Python, JavaScript, TypeScript, JSON, YAML, TOML, and environment-template files recursively. Python detection uses the AST; other formats conservatively extract literal values from model-related assignments, call/object keys, structured configuration keys, environment variables, and model lists. Comments, docstrings, arbitrary strings, replacement metadata, dynamic expressions, and positional call arguments are intentionally not treated as model dependencies. It skips common version-control, virtual-environment, dependency, cache, generated-output, and build directories, binary files, and symlinks.

## Known limitations

- Unquoted inline YAML lists of model IDs are not detected.
- Unknown-model detection may flag generic deployment names as low-risk findings. Tuning is deferred until real registry data exists.
