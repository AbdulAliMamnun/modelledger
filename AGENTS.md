# ModelLedger project instructions

- ModelLedger is a CLI developer tool: "Dependabot for AI models."
- Keep the Git root and repository layout unchanged.
- Use `.venv/bin/python` for Python commands.
- Keep lifecycle facts sourced. Synthetic fixtures and registry records must be labeled as demo data.
- Limit the product to the requested milestone. Do not add a web UI, authentication, billing, cloud infrastructure, alerts, a GitHub Action, rate-limit tracking, a lockfile, or migration planning unless explicitly requested.
- Preserve focused module boundaries: registry loading in `registry.py`, source discovery in `scanner.py`, classification in `risk.py`, and presentation/exit behavior in `cli.py`.
- Add or update pytest coverage with behavior changes.
- Ignore generated environments, dependency folders, build output, caches, and binary files while scanning.
