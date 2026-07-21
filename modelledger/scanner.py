"""Recursive, context-aware source scanning for AI model identifiers."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable

from .registry import find_model, load_registry


SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".json", ".yaml", ".yml", ".toml",
}
ENV_EXAMPLE_NAMES = {
    ".env.example", ".env.local.example", ".env.test.example", ".env.template",
    "env.example", "env.template", "example.env", "sample.env", ".env.sample",
}
IGNORED_DIRECTORIES = {
    ".git", ".venv", "venv", "node_modules", "build", "dist", ".next", ".nuxt",
    ".output", "out", "vendor", "coverage", "target", "generated", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".tox",
}
MODEL_CONTEXTS = {
    "model", "model_id", "model_name", "models", "deployment", "deployment_name",
    "ai_model", "openai_model", "anthropic_model",
}
_CONTEXT_ALTERNATIVES = "|".join(sorted(MODEL_CONTEXTS, key=len, reverse=True))
_CONTEXT_KEY = rf'''(?:["'](?:{_CONTEXT_ALTERNATIVES})["']|(?:{_CONTEXT_ALTERNATIVES}))'''
LEADING_CONTEXT = re.compile(
    rf'''(?ix)
    ^\s*(?:(?:export\s+)?(?:const|let|var)\s+)?
    {_CONTEXT_KEY}
    \s*[:=]\s*
    '''
)
OBJECT_CONTEXT = re.compile(
    rf'''(?ix)
    (?:^|[{{,])\s*{_CONTEXT_KEY}
    \s*[:=]\s*
    '''
)
QUOTED_VALUE = re.compile(r'''["'`]([^"'`\r\n]+)["'`]''')
BARE_VALUE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._:/-]*)")


def _is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS or path.name.lower() in ENV_EXAMPLE_NAMES


def _read_source(path: Path, root: Path) -> str | None:
    """Read a contained regular file after repeating containment checks."""
    try:
        if path.is_symlink():
            return None
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return None
        with resolved.open("rb") as source:
            content = source.read()
    except OSError:
        return None
    if b"\0" in content[:8192]:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts[:-1]
        if any(part in IGNORED_DIRECTORIES for part in relative_parts):
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_relative_to(root):
            continue
        if _is_supported(path):
            yield path


def _context_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id.lower()
    if isinstance(node, ast.Attribute):
        return node.attr.lower()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.lower()
    return None


def _literal_values(node: ast.AST) -> list[tuple[int, str]]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [(node.lineno, node.value)]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [item for element in node.elts for item in _literal_values(element)]
    return []


class _PythonModelVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.values: list[tuple[int, str]] = []

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        if any(_context_name(target) in MODEL_CONTEXTS for target in node.targets):
            self.values.extend(_literal_values(node.value))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if _context_name(node.target) in MODEL_CONTEXTS and node.value is not None:
            self.values.extend(_literal_values(node.value))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        for keyword in node.keywords:
            if keyword.arg and keyword.arg.lower() in MODEL_CONTEXTS:
                self.values.extend(_literal_values(keyword.value))
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:  # noqa: N802
        for key, value in zip(node.keys, node.values):
            if key is not None and _context_name(key) in MODEL_CONTEXTS:
                self.values.extend(_literal_values(value))
        self.generic_visit(node)


def _python_values(text: str) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    visitor = _PythonModelVisitor()
    visitor.visit(tree)
    return visitor.values


def _strip_hash_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif character == "\\" and quote:
            escaped = True
        elif character in {'"', "'"}:
            quote = None if quote == character else character if quote is None else quote
        elif character == "#" and quote is None:
            return line[:index]
    return line


def _strip_c_comments(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    in_block = False
    quote: str | None = None
    for line in lines:
        result: list[str] = []
        index = 0
        escaped = False
        template_body = quote == "`"
        while index < len(line):
            pair = line[index:index + 2]
            character = line[index]
            if in_block:
                if pair == "*/":
                    in_block = False
                    index += 2
                else:
                    index += 1
                continue
            if template_body:
                result.append(" ")
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == "`":
                    quote = None
                    template_body = False
                index += 1
                continue
            if escaped:
                result.append(character)
                escaped = False
            elif character == "\\" and quote:
                result.append(character)
                escaped = True
            elif character in {'"', "'", "`"}:
                result.append(character)
                quote = None if quote == character else character if quote is None else quote
            elif quote is None and pair == "//":
                break
            elif quote is None and pair == "/*":
                in_block = True
                index += 2
                continue
            else:
                result.append(character)
            index += 1
        if quote in {'"', "'"}:
            quote = None
        cleaned.append("".join(result))
    return cleaned


def _strip_yaml_blocks(lines: list[str]) -> list[str]:
    """Blank YAML block scalar bodies while preserving original line numbers."""
    cleaned: list[str] = []
    block_indent: int | None = None
    block_header = re.compile(r"^\s*[^#\n]+:\s*[|>][+-]?\s*$")
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if block_indent is not None:
            if not line.strip() or indent > block_indent:
                cleaned.append("")
                continue
            block_indent = None
        cleaned.append(line)
        if block_header.match(line):
            block_indent = indent
    return cleaned


def _is_code_position(line: str, position: int) -> bool:
    quote: str | None = None
    escaped = False
    for character in line[:position]:
        if escaped:
            escaped = False
        elif character == "\\" and quote:
            escaped = True
        elif character in {'"', "'", "`"}:
            quote = None if quote == character else character if quote is None else quote
    return quote is None


def _context_matches(line: str) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    leading = LEADING_CONTEXT.search(line)
    if leading:
        matches.append(leading)
    matches.extend(
        match
        for match in OBJECT_CONTEXT.finditer(line)
        if _is_code_position(line, match.start())
        and not (leading and match.start() == leading.start())
    )
    return matches


def _text_values(text: str, path: Path) -> list[tuple[int, str]]:
    lines = text.splitlines()
    if path.suffix.lower() in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        lines = _strip_c_comments(lines)
    elif path.suffix.lower() in {".yaml", ".yml", ".toml"} or path.name.lower() in ENV_EXAMPLE_NAMES:
        lines = [_strip_hash_comment(line) for line in lines]
        if path.suffix.lower() in {".yaml", ".yml"}:
            lines = _strip_yaml_blocks(lines)

    values: list[tuple[int, str]] = []
    list_mode: str | None = None
    for line_number, line in enumerate(lines, start=1):
        if list_mode:
            if list_mode == "yaml" and line.strip() and not line.lstrip().startswith("-"):
                list_mode = None
            else:
                list_content = line.split("]", 1)[0] if list_mode == "bracket" else line
                values.extend(
                    (line_number, value) for value in QUOTED_VALUE.findall(list_content)
                )
                dash_value = re.match(r"^\s*-\s*([A-Za-z0-9][A-Za-z0-9._:/-]*)\s*$", line)
                if dash_value:
                    values.append((line_number, dash_value.group(1)))
                if list_mode == "bracket" and "]" in line:
                    list_mode = None
                if list_mode is not None or line.lstrip().startswith("-"):
                    continue

        for match in _context_matches(line):
            remainder = line[match.end():].strip()
            if remainder.startswith("["):
                list_content = remainder.split("]", 1)[0]
                values.extend(
                    (line_number, value) for value in QUOTED_VALUE.findall(list_content)
                )
                if "]" not in remainder:
                    list_mode = "bracket"
                continue
            quoted = QUOTED_VALUE.match(remainder)
            if quoted:
                values.append((line_number, quoted.group(1)))
                continue
            bare = BARE_VALUE.match(remainder)
            if bare:
                values.append((line_number, bare.group(1)))
            elif not remainder and path.suffix.lower() in {".yaml", ".yml"}:
                list_mode = "yaml"
    return values


def scan_repository(
    repository: str | Path,
    models: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return literal model references found in supported model-related contexts."""
    root = Path(repository).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository path is not a directory: {root}")

    registry = models if models is not None else load_registry()
    findings: list[dict[str, Any]] = []
    for path in sorted(_source_files(root)):
        text = _read_source(path, root)
        if text is None:
            continue
        values = _python_values(text) if path.suffix.lower() == ".py" else _text_values(text, path)
        seen: set[tuple[int, str]] = set()
        for line_number, matched_identifier in sorted(values):
            occurrence = (line_number, matched_identifier)
            if occurrence in seen:
                continue
            seen.add(occurrence)
            model = find_model(matched_identifier, registry)
            findings.append(
                {
                    "model_id": model["model_id"] if model else matched_identifier,
                    "matched_alias": matched_identifier,
                    "file_path": path.relative_to(root).as_posix(),
                    "line_number": line_number,
                    "provider": model["provider"] if model else "unknown",
                    "lifecycle_status": model["status"] if model else "unknown",
                    "recommended_replacement": model["recommended_replacement"] if model else None,
                    "deprecation_date": model["deprecation_date"] if model else None,
                    "shutdown_date": model["shutdown_date"] if model else None,
                }
            )
    return findings
