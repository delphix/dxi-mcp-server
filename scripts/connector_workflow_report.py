#!/usr/bin/env python3
"""
Turn connector-workflow JSONL results into two CSVs (Jira-style):

    <base>(Results).csv  — one row per workflow step, full detail
    <base>(Summary).csv  — rollup per connector × workflow with pass/fail + accuracy

Usage:
    python scripts/connector_workflow_report.py test-results/connector-workflows.jsonl
    python scripts/connector_workflow_report.py results.jsonl --out-base "DLPXECO-13687-MYSQL"

The JSONL is written by tests/llm_local/test_connector_workflows.py — one line per
workflow step. Each line has: connector, workflow, description, prompt,
expected_tool, actual_tools, tool_correct, expected_action, actual_actions,
action_correct, operation_completed, status, evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


# Jira-style detail sheet (mirrors DLPXECO-13687 ...(Results).csv).
RESULTS_COLUMNS = [
    "Section",
    "Row",
    "Testcase",
    "Prompt",
    "Result",
    "Tool Correct",
    "Action Correct",
    "Expected Tool/Action",
    "Actual Tool(s)",
    "Notes",
]

# Valid result statuses, in display order for the tally.
STATUS_ORDER = ["PASS", "FAIL", "EXPECTED-ERROR", "N/A", "PARTIAL", "SKIPPED", "ERROR"]


def _load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _yn(v) -> str:
    return "YES" if v else "NO"


def _pct(n: int, d: int) -> str:
    return f"{round(n / d * 100)}%" if d else "n/a"


def write_results(rows: list[dict], out: Path) -> None:
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(RESULTS_COLUMNS)
        for r in rows:
            exp = r.get("expected_tool", "")
            if r.get("expected_action"):
                exp = f"{exp} / {r['expected_action']}"
            w.writerow([
                r.get("section", ""),
                r.get("row", ""),
                r.get("workflow", ""),
                (r.get("prompt", "") or "").replace("\n", " "),
                r.get("status", ""),
                _yn(r.get("tool_correct")),
                _yn(r.get("action_correct")),
                exp,
                ", ".join(r.get("actual_tools", []) or []),
                (r.get("evidence", "") or "").replace("\n", " ")[:500],
            ])


def write_summary(rows: list[dict], out: Path, connector: str) -> None:
    total = len(rows)
    tally = Counter(r.get("status", "?") for r in rows)
    # Accuracy excludes rows that never ran (SKIPPED).
    ran = [r for r in rows if r.get("status") != "SKIPPED"]
    tool_ok = sum(1 for r in ran if r.get("tool_correct"))
    # "Acceptable" = not an outright FAIL (PASS / EXPECTED-ERROR / N/A all count).
    acceptable = sum(1 for r in rows if r.get("status") in ("PASS", "EXPECTED-ERROR", "N/A"))

    by_section: dict[str, Counter] = {}
    for r in rows:
        by_section.setdefault(r.get("section", "?"), Counter())[r.get("status", "?")] += 1

    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([f"Connector Workflow Validation via DCT MCP Server — {connector}", ""])
        w.writerow(["", ""])
        w.writerow(["Connector", connector])
        w.writerow(["Total steps", total])
        w.writerow(["Tool-selection accuracy (of steps that ran)", _pct(tool_ok, len(ran))])
        w.writerow(["Acceptable (PASS/EXPECTED-ERROR/N-A)", f"{acceptable}/{total}  ({_pct(acceptable, total)})"])
        w.writerow(["", ""])
        w.writerow(["Result tally", ""])
        for status in STATUS_ORDER:
            if tally.get(status):
                w.writerow([status, tally[status]])
        w.writerow(["", ""])
        w.writerow(["Per-section", "  ".join(s for s in STATUS_ORDER)])
        for section, counts in by_section.items():
            cells = "  ".join(f"{s}={counts[s]}" for s in STATUS_ORDER if counts.get(s))
            w.writerow([section, cells])


def write_steps(rows: list[dict], out: Path) -> None:
    """Human-readable per-step transcript — every step, pass or fail, with the
    exact ordered MCP tool calls the LLM made and its narration."""
    lines: list[str] = ["# Connector Workflow — Step-by-Step Transcript", ""]
    last_section = None
    for r in rows:
        section = r.get("section", "")
        if section != last_section:
            lines.append(f"\n## {section}\n")
            last_section = section
        status = r.get("status", "?")
        lines.append(f"### [{status}] {r.get('row')}. {r.get('workflow')}  ({r.get('kind')})")
        lines.append(f"- **Description:** {r.get('description','')}")
        lines.append(f"- **Prompt:** {r.get('prompt','')}")
        exp = r.get("expected_tool", "")
        if r.get("expected_action"):
            exp += f" / {r['expected_action']}"
        lines.append(f"- **Expected:** {exp}")
        lines.append(f"- **Tool correct:** {_yn(r.get('tool_correct'))}   "
                     f"**Action correct:** {_yn(r.get('action_correct'))}   "
                     f"**Completed:** {_yn(r.get('operation_completed'))}")
        act_steps = r.get("act_steps") or []
        if act_steps:
            lines.append(f"- **MCP calls (act), in order:**")
            for i, s in enumerate(act_steps, 1):
                lines.append(f"    {i}. `{s}`")
        else:
            lines.append(f"- **MCP calls (act):** (none recorded)")
        if r.get("verify_steps"):
            lines.append(f"- **MCP calls (verify):** " +
                         ", ".join(f"`{s}`" for s in r["verify_steps"]))
        if r.get("act_narration"):
            snippet = r["act_narration"].strip().replace("\n", "\n  > ")
            lines.append(f"- **LLM said:**\n  > {snippet}")
        if r.get("evidence") and not r.get("act_narration"):
            lines.append(f"- **Evidence:** {r['evidence']}")
        lines.append("")
    out.write_text("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", type=Path, help="Path to the connector-workflows JSONL results file")
    ap.add_argument(
        "--out-base",
        help="Base name for the CSVs (default: derived from the JSONL filename). "
             "Produces '<base>(Results).csv' and '<base>(Summary).csv'.",
    )
    args = ap.parse_args(argv)

    if not args.jsonl.exists():
        print(f"error: no results file at {args.jsonl}", file=sys.stderr)
        return 1

    rows = _load(args.jsonl)
    if not rows:
        print(f"error: {args.jsonl} is empty — no workflow steps recorded", file=sys.stderr)
        return 1

    base = args.out_base or str(args.jsonl.with_suffix(""))
    results_csv = Path(f"{base}(Results).csv")
    summary_csv = Path(f"{base}(Summary).csv")
    results_csv.parent.mkdir(parents=True, exist_ok=True)

    connector = rows[0].get("connector", "connector")
    steps_md = Path(f"{base}(Steps).md")
    write_results(rows, results_csv)
    write_summary(rows, summary_csv, connector)
    write_steps(rows, steps_md)

    statuses = Counter(r.get("status") for r in rows)
    print(f"Wrote {results_csv}  ({len(rows)} steps)")
    print(f"Wrote {summary_csv}")
    print(f"Wrote {steps_md}")
    tally = "  ".join(f"{s}={statuses[s]}" for s in STATUS_ORDER if statuses.get(s))
    print(f"  {tally}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
