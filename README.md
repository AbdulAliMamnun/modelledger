# ModelLedger

Dependabot for AI models — find every model your repository depends on, check a verified lifecycle ledger, and block risky dependencies in CI.

## The problem

Providers rename, deprecate, and retire models outside your repo. Model IDs are hardcoded strings scattered across source and configuration files. Teams find out when production breaks.

## Quickstart

```bash
pip install .
python -m modelledger.cli demo_repository
```

The bundled registry contains synthetic demo data, clearly labeled as such. The demo produces four findings:

```text
ModelLedger scan: .../demo_repository
[LOW] .env.example:1 demo-unknown-v1 (unknown, unknown)
[NONE] app.py:1 demo-active-v1 (ModelLedger Demo Provider, active)
[HIGH] app.py:2 demo-deprecated (ModelLedger Demo Provider, deprecated) -> replace with demo-active-v1
[CRITICAL] config.json:2 demo-retired-v1 (ModelLedger Demo Provider, retired) -> replace with demo-active-v1

4 model reference(s) found.
```

The retired dependency makes the command exit with status `1`, ready to block a CI job.

## What works today

- Comment-safe source discovery across Python, JavaScript, TypeScript, JSON, YAML, TOML, and environment templates. Python is parsed with the AST; other formats use conservative, syntax-aware literal extraction.
- A deterministic risk engine classifies active, deprecated, retired, and unknown models.
- CI-friendly exit codes: `1` for critical findings and `2` for input or registry errors (`0` otherwise).
- `--json` for machine-readable output.
- `--registry PATH` for an explicit lifecycle registry.

Common version-control, virtual-environment, dependency, cache, generated-output, and build directories are ignored, along with binary files and symlinks.

## Design principles

- **No LLM in the trust path.** Discovery and classification are deterministic and auditable.
- **No lifecycle fact without provenance.** Registry records require a source URL and last-verified date; bundled records are explicitly synthetic demo data.
- **Precision over recall.** ModelLedger reports high-confidence dependency references instead of guessing from every string.

## Roadmap

1. Verified real registry
2. `modelledger.lock`
3. Policy-as-code
4. GitHub Action + SARIF
5. Grounded GPT-5.6 migration planner

## Known limitations

- Unquoted inline YAML lists of model IDs are not detected.
- Unknown-model detection may flag generic deployment names as low-risk findings. Tuning is deferred until real registry data exists.
