"""Streamlit demo for the deterministic ModelLedger scanning pipeline."""

from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
import json
from pathlib import Path

import streamlit as st

from modelledger.registry import load_registry
from modelledger.risk import assess_findings
from modelledger.scanner import scan_repository


APP_ROOT = Path(__file__).resolve().parent
DEMO_REPOSITORY = APP_ROOT / "demo_repository"
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}


st.set_page_config(
    page_title="ModelLedger · Deterministic model dependency scanning",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --background: #0B0E14;
        --surface: #151B26;
        --border: #232B3A;
        --text: #E6EAF2;
        --secondary: #8B94A7;
        --accent: #22D3EE;
        --critical: #F43F5E;
        --high: #F59E0B;
        --medium: #EAB308;
        --low: #60A5FA;
        --none: #34D399;
        --mono: "SFMono-Regular", "SF Mono", "JetBrains Mono", ui-monospace,
                Menlo, Monaco, Consolas, monospace;
    }

    .stApp, [data-testid="stAppViewContainer"] { background: var(--background); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"] { color: var(--secondary); }
    .block-container { max-width: 1280px; padding-top: 3.2rem; padding-bottom: 2rem; }

    .ml-header { margin-bottom: 2rem; }
    .ml-wordmark {
        color: var(--text);
        font-size: clamp(2.5rem, 6vw, 4.8rem);
        font-weight: 760;
        letter-spacing: -0.07em;
        line-height: 1;
        text-shadow: 0 0 30px rgba(34, 211, 238, 0.22);
    }
    .ml-tagline {
        color: var(--accent);
        font-family: var(--mono);
        font-size: 0.92rem;
        letter-spacing: 0.08em;
        margin-top: 0.75rem;
        text-transform: uppercase;
    }
    .ml-subtitle { color: var(--secondary); font-size: 1.02rem; margin-top: 0.45rem; }

    h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] { color: var(--text); }
    h2 { font-size: 1.1rem !important; letter-spacing: -0.01em; margin-top: 1.8rem !important; }

    [data-testid="stTextInput"] input {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        color: var(--text);
        font-family: var(--mono);
    }
    [data-testid="stTextInput"] input:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 1px var(--accent), 0 0 18px rgba(34, 211, 238, 0.12);
    }
    [data-testid="stBaseButton-primary"] {
        background: var(--accent);
        border: 1px solid var(--accent);
        border-radius: 12px;
        color: #0B0E14;
        font-weight: 750;
        min-height: 2.6rem;
    }
    [data-testid="stBaseButton-primary"]:hover {
        background: #22D3EE;
        border-color: #22D3EE;
        box-shadow: 0 0 22px rgba(34, 211, 238, 0.2);
        color: #0B0E14;
    }

    .ml-metrics {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1.5rem 0 2rem;
    }
    .ml-stat {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        min-height: 112px;
        padding: 1rem;
    }
    .ml-stat-label { color: var(--secondary); font-size: 0.76rem; letter-spacing: 0.04em; }
    .ml-stat-value { color: var(--text); font-family: var(--mono); font-size: 2rem; font-weight: 750; }
    .ml-stat-caption { color: var(--secondary); font-size: 0.7rem; margin-top: 0.2rem; }
    .ml-value-critical { color: var(--critical); }
    .ml-value-high { color: var(--high); }
    .ml-value-medium { color: var(--medium); }
    .ml-value-muted { color: var(--secondary); }
    .ml-ci-fail { box-shadow: 0 0 16px rgba(244, 63, 94, 0.12); }
    .ml-ci-fail .ml-stat-value { color: var(--critical); }
    .ml-ci-pass { box-shadow: 0 0 16px rgba(52, 211, 153, 0.12); }
    .ml-ci-pass .ml-stat-value { color: var(--none); }

    .ml-finding {
        align-items: center;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        display: grid;
        gap: 0.75rem 1rem;
        grid-template-columns: 7rem minmax(12rem, 1.2fr) minmax(12rem, 1fr) minmax(10rem, auto);
        margin-bottom: 0.65rem;
        padding: 1rem;
    }
    .ml-chip {
        border: 1px solid currentColor;
        border-radius: 999px;
        font-family: var(--mono);
        font-size: 0.67rem;
        font-weight: 750;
        letter-spacing: 0.07em;
        padding: 0.28rem 0.52rem;
        text-align: center;
        width: fit-content;
    }
    .critical { color: var(--critical); box-shadow: 0 0 13px rgba(244, 63, 94, 0.16); }
    .high { color: var(--high); box-shadow: 0 0 13px rgba(245, 158, 11, 0.16); }
    .medium { color: var(--medium); box-shadow: 0 0 13px rgba(234, 179, 8, 0.16); }
    .low { color: var(--low); box-shadow: 0 0 13px rgba(96, 165, 250, 0.16); }
    .none { color: var(--none); box-shadow: 0 0 13px rgba(52, 211, 153, 0.16); }
    .ml-model, .ml-location, .ml-replacement { font-family: var(--mono); }
    .ml-model { color: var(--text); font-size: 0.9rem; font-weight: 650; }
    .ml-meta { color: var(--secondary); font-size: 0.78rem; }
    .ml-location { color: var(--secondary); font-size: 0.76rem; text-align: right; }
    .ml-replacement { color: var(--secondary); font-size: 0.74rem; margin-top: 0.3rem; }

    [data-testid="stExpander"] {
        background: var(--surface);
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }
    [data-testid="stCode"] code, code, pre { font-family: var(--mono) !important; }
    .ml-copy-hint { color: var(--secondary); font-family: var(--mono); font-size: 0.72rem; }
    .ml-footer {
        border-top: 1px solid var(--border);
        color: var(--secondary);
        font-size: 0.78rem;
        margin-top: 2.5rem;
        padding: 1.2rem 0 0.5rem;
    }
    .ml-footer a { color: var(--accent); text-decoration: none; }

    @media (max-width: 850px) {
        .ml-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .ml-finding { grid-template-columns: 1fr; }
        .ml-location { text-align: left; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def run_scan(repository_text: str) -> tuple[Path, list[dict], int]:
    """Run the same deterministic pipeline used by the CLI."""
    repository = Path(repository_text).expanduser().resolve()
    models = load_registry()
    findings = assess_findings(scan_repository(repository, models))
    exit_code = 1 if any(item["risk"] == "critical" for item in findings) else 0
    return repository, findings, exit_code


def render_metrics(findings: list[dict], exit_code: int) -> None:
    counts = Counter(item["risk"] for item in findings)
    medium_low = counts["medium"] + counts["low"]
    stats = [
        ("Total references", len(findings), "", "", ""),
        ("Critical", counts["critical"], "", "ml-value-critical" if counts["critical"] else "ml-value-muted", ""),
        ("High", counts["high"], "", "ml-value-high" if counts["high"] else "ml-value-muted", ""),
        ("Medium / Low", medium_low, "", "ml-value-medium" if medium_low else "ml-value-muted", ""),
        ("CI exit code", exit_code, "what your pipeline sees", "", "ml-ci-fail" if exit_code else "ml-ci-pass"),
    ]
    cards = "".join(
        f'<div class="ml-stat {card_class}"><div class="ml-stat-label">{label}</div>'
        f'<div class="ml-stat-value {value_class}">{value}</div>'
        f'<div class="ml-stat-caption">{caption}</div></div>'
        for label, value, caption, value_class, card_class in stats
    )
    st.markdown(f'<div class="ml-metrics">{cards}</div>', unsafe_allow_html=True)


def render_finding(finding: dict) -> None:
    risk = finding["risk"]
    replacement = finding.get("recommended_replacement")
    replacement_html = (
        f'<div class="ml-replacement">→ replace with {escape(str(replacement))}</div>'
        if replacement
        else ""
    )
    st.markdown(
        f"""
        <div class="ml-finding">
            <span class="ml-chip {risk}">{escape(risk.upper())}</span>
            <div><div class="ml-model">{escape(str(finding['matched_alias']))}</div>{replacement_html}</div>
            <div class="ml-meta">{escape(str(finding['provider']))} · {escape(str(finding['lifecycle_status']))}</div>
            <div class="ml-location">{escape(str(finding['file_path']))}:{int(finding['line_number'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def matched_source(repository: Path, findings: list[dict]) -> list[tuple[str, str]]:
    """Read matched source files and mark the lines reported by the scanner."""
    matches: dict[str, set[int]] = defaultdict(set)
    for finding in findings:
        matches[finding["file_path"]].add(finding["line_number"])

    rendered: list[tuple[str, str]] = []
    for relative_path, line_numbers in sorted(matches.items()):
        source_path = (repository / relative_path).resolve()
        if not source_path.is_relative_to(repository) or not source_path.is_file():
            continue
        try:
            lines = source_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        width = max(2, len(str(len(lines))))
        content = "\n".join(
            f"{'>' if number in line_numbers else ' '} {number:>{width}} | {line}"
            for number, line in enumerate(lines, start=1)
        )
        rendered.append((relative_path, content))
    return rendered


st.markdown(
    """
    <header class="ml-header">
        <div class="ml-wordmark">ModelLedger</div>
        <div class="ml-tagline">Dependabot for AI models</div>
        <div class="ml-subtitle">Deterministic, auditable model-dependency scanning.</div>
    </header>
    """,
    unsafe_allow_html=True,
)

path_column, button_column = st.columns([5, 1], vertical_alignment="bottom")
with path_column:
    repository_input = st.text_input(
        "Repository path",
        value=str(DEMO_REPOSITORY),
        help="Local repository directory to scan. No files are modified.",
    )
with button_column:
    scan_requested = st.button("Scan repository", type="primary", use_container_width=True)

if scan_requested:
    try:
        st.session_state["scan_result"] = run_scan(repository_input)
        st.session_state.pop("scan_error", None)
    except (OSError, RuntimeError, ValueError) as error:
        st.session_state.pop("scan_result", None)
        st.session_state["scan_error"] = str(error)

if error_message := st.session_state.get("scan_error"):
    st.error(f"Scan failed: {error_message}", icon="⚠️")

if result := st.session_state.get("scan_result"):
    repository, findings, exit_code = result
    render_metrics(findings, exit_code)

    st.markdown("## Findings")
    if findings:
        for finding in sorted(findings, key=lambda item: SEVERITY_ORDER[item["risk"]]):
            render_finding(finding)
    else:
        st.success("No model references found.")

    files_column, json_column = st.columns(2)
    with files_column:
        with st.expander("Scanned files", expanded=True):
            sources = matched_source(repository, findings)
            if sources:
                for relative_path, content in sources:
                    st.caption(relative_path)
                    st.code(content, language=None)
            else:
                st.caption("No matched source files to display.")
    with json_column:
        with st.expander("JSON output", expanded=True):
            st.markdown('<div class="ml-copy-hint">pipe --json into CI</div>', unsafe_allow_html=True)
            st.code(json.dumps(findings, indent=2), language="json")

st.markdown(
    """
    <footer class="ml-footer">
        Every result is reproducible: same input → same findings → same exit code.
        Registry entries carry source URLs and verification dates. ·
        <a href="https://github.com/AbdulAliMamnun/modelledger" target="_blank">GitHub repository ↗</a>
    </footer>
    """,
    unsafe_allow_html=True,
)
