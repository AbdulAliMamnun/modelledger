"""Command-line interface for ModelLedger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from .registry import load_registry
from .risk import assess_findings
from .scanner import scan_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelledger",
        description="Scan a repository for risky AI model dependencies.",
    )
    parser.add_argument("repository", nargs="?", default=".", help="repository to scan")
    parser.add_argument("--registry", type=Path, help="path to a model lifecycle registry")
    parser.add_argument("--json", action="store_true", dest="json_output", help="emit JSON")
    return parser


def _human_output(findings: list[dict], repository: Path, stream: TextIO) -> None:
    print(f"ModelLedger scan: {repository}", file=stream)
    if not findings:
        print("No model references found.", file=stream)
        return

    for finding in findings:
        replacement = (
            f" -> replace with {finding['recommended_replacement']}"
            if finding["recommended_replacement"]
            else ""
        )
        print(
            f"[{finding['risk'].upper()}] {finding['file_path']}:{finding['line_number']} "
            f"{finding['matched_alias']} ({finding['provider']}, "
            f"{finding['lifecycle_status']}){replacement}",
            file=stream,
        )
    print(f"\n{len(findings)} model reference(s) found.", file=stream)


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = stdout or sys.stdout

    try:
        repository = Path(args.repository).resolve()
        models = load_registry(args.registry) if args.registry else load_registry()
        findings = assess_findings(scan_repository(repository, models))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"modelledger: error: {error}", file=sys.stderr)
        return 2

    if args.json_output:
        json.dump(findings, output, indent=2)
        print(file=output)
    else:
        _human_output(findings, repository, output)
    return 1 if any(finding["risk"] == "critical" for finding in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
