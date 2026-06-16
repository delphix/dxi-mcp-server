#!/usr/bin/env python3
"""
Generate a comprehensive HTML + Markdown test report from pytest-json-report outputs.

Usage:
    python scripts/generate_test_report.py \
        --l123 test-results/l123.json \
        --l4   test-results/l4.json   \
        --l5   test-results/l5.json   \
        --out  test-results/test-report-2026-06-16.html

Layers:
  L1 = tests/unit           (no creds, pure unit)
  L2 = tests/integration    (no creds, mocked HTTP)
  L3 = tests/functional     (no creds, full stack)
  L4 = tests/e2e            (real DCT, no LLM)
  L5 = tests/llm_local      (real DCT + Claude CLI)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Helpers ────────────────────────────────────────────────────────────────────

LAYER_LABEL = {
    "l1": "L1 — Unit",
    "l2": "L2 — Integration",
    "l3": "L3 — Functional",
    "l4": "L4 — Real DCT (no LLM)",
    "l5": "L5 — LLM-driven (real DCT + Claude CLI)",
}

STATUS_EMOJI = {"passed": "✅", "failed": "❌", "skipped": "⏭", "error": "💥"}
STATUS_COLOR = {
    "passed": "#4caf50",
    "failed": "#f44336",
    "skipped": "#9e9e9e",
    "error": "#ff5722",
}


def _extract_l5_detail(stdout: str) -> list[dict[str, Any]]:
    """Parse L5_DETAIL: lines from captured stdout."""
    details = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("L5_DETAIL:"):
            try:
                details.append(json.loads(line[len("L5_DETAIL:"):]))
            except json.JSONDecodeError:
                pass
    return details


def _docstring(test: dict) -> str:
    """Best-effort description from pytest-json-report metadata."""
    doc = test.get("metadata", {}).get("doc", "")
    if doc:
        return doc.strip().split("\n")[0]
    # For skipped tests, extract the skip reason
    if test.get("outcome") == "skipped":
        setup = test.get("setup", {}) or {}
        longrepr = setup.get("longrepr", "")
        if longrepr:
            if isinstance(longrepr, (list, tuple)) and len(longrepr) >= 3:
                return str(longrepr[2]).replace("Skipped: ", "").strip()
            if isinstance(longrepr, str):
                return longrepr.split("\n")[-1].replace("Skipped: ", "").strip()[:120]
    # Fall back to humanised function name
    nodeid = test.get("nodeid", "")
    parts = nodeid.rsplit("::", 1)
    return parts[-1].replace("_", " ").strip() if parts else nodeid


def _outcome(test: dict) -> str:
    """Normalized outcome string."""
    call = test.get("call", {}) or {}
    setup = test.get("setup", {}) or {}
    teardown = test.get("teardown", {}) or {}
    # Determine worst phase outcome
    for phase in (call, setup, teardown):
        if phase.get("outcome") in ("failed", "error"):
            return phase["outcome"]
    if call.get("outcome") == "passed":
        return "passed"
    if call.get("outcome") == "skipped" or setup.get("outcome") == "skipped":
        return "skipped"
    return test.get("outcome", "unknown")


def _stdout(test: dict) -> str:
    call = test.get("call", {}) or {}
    return call.get("stdout") or call.get("longrepr") or ""


def _short_id(nodeid: str) -> str:
    """Strip the file prefix, keep module::func."""
    parts = nodeid.split("::")
    return "::".join(parts[1:]) if len(parts) > 1 else nodeid


def load_report(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text())
    return data.get("tests", [])


# ── HTML template ─────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #0f1419;
  --surface: #1a2030;
  --border: #2a3548;
  --accent: #4fc3f7;
  --text: #e0e6f0;
  --muted: #7a8fa8;
  --pass: #4caf50;
  --fail: #f44336;
  --skip: #9e9e9e;
  --err:  #ff5722;
}
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0; font-family: 'Segoe UI', system-ui, sans-serif;
  background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.6;
}
h1 { color: var(--accent); margin: 0 0 4px; font-size: 1.6rem; }
h2 { color: var(--accent); font-size: 1.15rem; margin: 24px 0 8px; }
header {
  background: var(--surface); border-bottom: 2px solid var(--accent);
  padding: 20px 32px 16px; position: sticky; top: 0; z-index: 10;
}
.meta { color: var(--muted); font-size: 12px; margin-top: 2px; }
main { padding: 24px 32px 48px; max-width: 1600px; }
.summary-grid {
  display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 28px;
}
.stat-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 20px; min-width: 120px;
}
.stat-card .num { font-size: 1.8rem; font-weight: 700; }
.stat-card .lbl { font-size: 11px; color: var(--muted); text-transform: uppercase; }
.pass-card .num { color: var(--pass); }
.fail-card .num { color: var(--fail); }
.skip-card .num { color: var(--skip); }
.total-card .num { color: var(--accent); }
.layer-section {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; margin-bottom: 20px; overflow: hidden;
}
.layer-header {
  background: #1f2d3f; padding: 10px 18px; font-weight: 600;
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; user-select: none;
}
.layer-header .badges { display: flex; gap: 8px; }
.badge {
  padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
}
.badge-pass { background: #1b3a1b; color: var(--pass); }
.badge-fail { background: #3a1b1b; color: var(--fail); }
.badge-skip { background: #2a2a2a; color: var(--skip); }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th {
  background: #162030; color: var(--muted); font-size: 11px;
  text-transform: uppercase; letter-spacing: .05em;
  padding: 7px 10px; text-align: left; border-bottom: 1px solid var(--border);
}
td { padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #1e2d40; }
.status-pill {
  display: inline-block; padding: 1px 9px; border-radius: 20px;
  font-size: 11px; font-weight: 600; white-space: nowrap;
}
.pill-passed { background: #1b3a1b; color: var(--pass); }
.pill-failed  { background: #3a1b1b; color: var(--fail); }
.pill-skipped { background: #2a2a2a; color: var(--skip); }
.pill-error   { background: #3a2a1b; color: var(--err); }
.test-id { font-family: 'JetBrains Mono', monospace; color: var(--accent); font-size: 11px; }
.desc { color: var(--text); }
details { margin-top: 6px; }
summary { cursor: pointer; color: var(--muted); font-size: 11px; }
summary:hover { color: var(--accent); }
.l5-block {
  background: #111820; border: 1px solid var(--border); border-radius: 6px;
  margin-top: 8px; padding: 10px 14px;
}
.l5-label { color: #a0c4e8; font-size: 11px; font-weight: 600; margin-bottom: 4px; }
.l5-prompt { color: #c8d8e8; font-size: 11px; margin-bottom: 6px; white-space: pre-wrap; }
.l5-tools { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.tool-chip {
  background: #1a3050; color: var(--accent); border-radius: 4px;
  padding: 1px 8px; font-size: 10px; font-family: monospace;
}
.l5-text { color: var(--muted); font-size: 11px; white-space: pre-wrap; }
.err-block {
  background: #2a1010; border-left: 3px solid var(--fail);
  padding: 8px 12px; border-radius: 4px; font-size: 11px;
  font-family: monospace; white-space: pre-wrap; color: #f08080;
  max-height: 200px; overflow-y: auto;
}
"""

_JS = """
document.querySelectorAll('.layer-header').forEach(h => {
  h.addEventListener('click', () => {
    const body = h.nextElementSibling;
    body.style.display = body.style.display === 'none' ? '' : 'none';
  });
});
"""


def _pill(outcome: str) -> str:
    cls = {"passed": "pill-passed", "failed": "pill-failed", "skipped": "pill-skipped"}.get(
        outcome, "pill-error"
    )
    emoji = STATUS_EMOJI.get(outcome, "?")
    return f'<span class="status-pill {cls}">{emoji} {outcome}</span>'


def _render_l5_details(test: dict) -> str:
    stdout = _stdout(test)
    details = _extract_l5_detail(stdout)
    if not details:
        return ""
    blocks = []
    for d in details:
        label = d.get("label", "")
        prompt = d.get("prompt", "")
        tools = d.get("tools_used", [])
        calls = d.get("tool_calls", [])
        text = d.get("final_text", "")

        tool_chips = "".join(
            f'<span class="tool-chip">{t}</span>' for t in tools
        ) or "<span style='color:var(--muted)'>none</span>"

        call_lines = ""
        if calls:
            rows = []
            for c in calls:
                action = c.get("action") or "-"
                keys = ", ".join(c.get("input_keys", []))
                rows.append(
                    f"<tr><td class='test-id'>{c['tool']}</td>"
                    f"<td>{action}</td>"
                    f"<td style='color:var(--muted)'>{keys}</td></tr>"
                )
            call_lines = (
                "<table style='margin-top:6px'>"
                "<tr><th>Tool</th><th>Action</th><th>Input keys</th></tr>"
                + "".join(rows)
                + "</table>"
            )

        blocks.append(
            f'<div class="l5-block">'
            f'<div class="l5-label">{label}</div>'
            f'<div class="l5-prompt"><b>Prompt:</b> {_esc(prompt)}</div>'
            f'<div class="l5-tools">{tool_chips}</div>'
            f"{call_lines}"
            f'<div class="l5-text" style="margin-top:6px"><b>Response:</b> {_esc(text)}</div>'
            f"</div>"
        )
    return "<details><summary>MCP tool calls & prompts</summary>" + "".join(blocks) + "</details>"


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _error_block(test: dict) -> str:
    call = test.get("call", {}) or {}
    longrepr = call.get("longrepr", "") or ""
    if not longrepr or _outcome(test) in ("passed", "skipped"):
        return ""
    return (
        "<details><summary>Error detail</summary>"
        f'<div class="err-block">{_esc(str(longrepr)[:2000])}</div>'
        "</details>"
    )


def _render_layer(layer_key: str, tests: list[dict], is_l5: bool = False) -> str:
    if not tests:
        return (
            f'<div class="layer-section">'
            f'<div class="layer-header">{LAYER_LABEL.get(layer_key, layer_key)}'
            f'<span class="badges"><span class="badge badge-skip">no results</span></span></div>'
            f'<div style="padding:16px;color:var(--muted)">No test results found for this layer.</div>'
            f"</div>"
        )

    counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for t in tests:
        o = _outcome(t)
        counts[o] = counts.get(o, 0) + 1

    badges = ""
    if counts["passed"]:
        badges += f'<span class="badge badge-pass">✅ {counts["passed"]} passed</span>'
    if counts["failed"]:
        badges += f'<span class="badge badge-fail">❌ {counts["failed"]} failed</span>'
    if counts["skipped"]:
        badges += f'<span class="badge badge-skip">⏭ {counts["skipped"]} skipped</span>'
    if counts["error"]:
        badges += f'<span class="badge badge-fail">💥 {counts["error"]} error</span>'

    rows = []
    for t in tests:
        outcome = _outcome(t)
        short = _short_id(t.get("nodeid", ""))
        desc = _docstring(t)
        duration = t.get("call", {}) or {}
        dur_s = duration.get("duration", 0)
        dur_str = f"{dur_s:.1f}s" if isinstance(dur_s, (int, float)) else ""

        l5_html = _render_l5_details(t) if is_l5 else ""
        err_html = _error_block(t)

        rows.append(
            f"<tr>"
            f"<td class='test-id'>{_esc(short)}</td>"
            f"<td>{_pill(outcome)}</td>"
            f"<td class='desc'>{_esc(desc)}{l5_html}{err_html}</td>"
            f"<td style='color:var(--muted)'>{dur_str}</td>"
            f"</tr>"
        )

    header_extra = "th:nth-child(4){width:60px}" if rows else ""
    table = (
        "<table>"
        "<tr><th>Test</th><th>Result</th><th>Description / Detail</th><th>Duration</th></tr>"
        + "".join(rows)
        + "</table>"
    )

    return (
        f'<div class="layer-section">'
        f'<div class="layer-header">{LAYER_LABEL.get(layer_key, layer_key)}'
        f'<span class="badges">{badges}</span></div>'
        f"<div>{table}</div>"
        f"</div>"
    )


def generate_html(
    l123: list[dict],
    l4: list[dict],
    l5: list[dict],
    run_date: str,
) -> str:
    # Split l123 by path prefix
    l1 = [t for t in l123 if "tests/unit/" in t.get("nodeid", "")]
    l2 = [t for t in l123 if "tests/integration/" in t.get("nodeid", "")]
    l3 = [t for t in l123 if "tests/functional/" in t.get("nodeid", "")]

    all_tests = l1 + l2 + l3 + l4 + l5
    total = len(all_tests)
    passed = sum(1 for t in all_tests if _outcome(t) == "passed")
    failed = sum(1 for t in all_tests if _outcome(t) == "failed")
    skipped = sum(1 for t in all_tests if _outcome(t) in ("skipped", "error"))

    summary = (
        f'<div class="summary-grid">'
        f'<div class="stat-card total-card"><div class="num">{total}</div><div class="lbl">Total</div></div>'
        f'<div class="stat-card pass-card"><div class="num">{passed}</div><div class="lbl">Passed</div></div>'
        f'<div class="stat-card fail-card"><div class="num">{failed}</div><div class="lbl">Failed</div></div>'
        f'<div class="stat-card skip-card"><div class="num">{skipped}</div><div class="lbl">Skipped/Error</div></div>'
        f"</div>"
    )

    body = (
        summary
        + _render_layer("l1", l1)
        + _render_layer("l2", l2)
        + _render_layer("l3", l3)
        + _render_layer("l4", l4)
        + _render_layer("l5", l5, is_l5=True)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DCT MCP Server — Test Report {run_date}</title>
<style>{_CSS}</style>
</head>
<body>
<header>
  <h1>DCT MCP Server — Test Report</h1>
  <div class="meta">
    Generated: {run_date} &nbsp;|&nbsp;
    Branch: dlpx/pr/chaitali/test-suite-poc &nbsp;|&nbsp;
    DCT: https://localhost:443
  </div>
</header>
<main>
{body}
</main>
<script>{_JS}</script>
</body>
</html>"""


def generate_markdown(
    l123: list[dict],
    l4: list[dict],
    l5: list[dict],
    run_date: str,
) -> str:
    lines = [
        f"# DCT MCP Server — Test Report",
        f"",
        f"**Generated:** {run_date}  ",
        f"**Branch:** dlpx/pr/chaitali/test-suite-poc  ",
        f"**DCT:** https://localhost:443",
        f"",
    ]

    def layer_section(key: str, tests: list[dict], is_l5: bool = False):
        counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
        for t in tests:
            o = _outcome(t)
            counts[o] = counts.get(o, 0) + 1

        lines.append(f"## {LAYER_LABEL.get(key, key)}")
        lines.append(
            f"**{counts['passed']} passed · {counts['failed']} failed · {counts['skipped']} skipped**"
        )
        lines.append("")

        if not tests:
            lines.append("_No results_")
            lines.append("")
            return

        lines.append("| Test | Result | Description |")
        lines.append("|------|--------|-------------|")
        for t in tests:
            outcome = _outcome(t)
            short = _short_id(t.get("nodeid", ""))
            desc = _docstring(t)
            emoji = STATUS_EMOJI.get(outcome, "?")
            lines.append(f"| `{short}` | {emoji} {outcome} | {desc} |")
            if is_l5:
                details = _extract_l5_detail(_stdout(t))
                for d in details:
                    label = d.get("label", "")
                    prompt = d.get("prompt", "")[:300].replace("\n", " ")
                    tools = ", ".join(d.get("tools_used", []))
                    lines.append(f"|   ↳ **{label}** | | Prompt: `{prompt}` / Tools: `{tools}` |")
        lines.append("")

    l1 = [t for t in l123 if "tests/unit/" in t.get("nodeid", "")]
    l2 = [t for t in l123 if "tests/integration/" in t.get("nodeid", "")]
    l3 = [t for t in l123 if "tests/functional/" in t.get("nodeid", "")]

    for key, tests in [("l1", l1), ("l2", l2), ("l3", l3), ("l4", l4), ("l5", l5)]:
        layer_section(key, tests, is_l5=(key == "l5"))

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate HTML test report from pytest-json-report outputs")
    ap.add_argument("--l123", type=Path, help="pytest-json-report for L1+L2+L3")
    ap.add_argument("--l4",   type=Path, help="pytest-json-report for L4")
    ap.add_argument("--l5",   type=Path, help="pytest-json-report for L5")
    ap.add_argument("--out",  type=Path, default=Path("test-results/test-report.html"))
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d %H:%M"))
    args = ap.parse_args()

    l123 = load_report(args.l123)
    l4   = load_report(args.l4)
    l5   = load_report(args.l5)

    print(f"Loaded: L1+L2+L3={len(l123)}, L4={len(l4)}, L5={len(l5)} tests", file=sys.stderr)

    html = generate_html(l123, l4, l5, args.date)
    md   = generate_markdown(l123, l4, l5, args.date)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    md_out = args.out.with_suffix(".md")
    md_out.write_text(md)

    print(f"HTML report: {args.out}", file=sys.stderr)
    print(f"Markdown  : {md_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
