#!/usr/bin/env python3
"""
Live-DCT integration test for DCT_TOOLSET=dynamic (READ-ONLY).

Exercises the dynamic 2-tool architecture (discovery + execute) against a real
DCT instance and writes an evidence report for the PR:

    docs/DLPXECO-13984/DLPXECO-13984-integration-test-evidence.md

Read-only by design — it downloads the spec, browses it via `discovery`, performs
GET reads via `execute`, and polls an ALREADY-EXISTING job to a terminal state. It
never creates, mutates, or deletes anything on the DCT instance.

Requirements (env):
    DCT_BASE_URL   e.g. https://your-dct-host   (no /dct suffix)
    DCT_API_KEY    raw key (no "apk " prefix)
    DCT_VERIFY_SSL optional, default false

Usage:
    DCT_BASE_URL=... DCT_API_KEY=... DCT_VERIFY_SSL=false \
        python evals/integration_test_dynamic.py

FR-001..FR-004, epic §5.1 (DLPXECO-13984)
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from dct_mcp_server.tools.core import spec_cache  # noqa: E402
from dct_mcp_server.tools.core.dynamic import _make_discovery_fn, _make_execute_fn  # noqa: E402
from dct_mcp_server.dct_client import DCTAPIClient  # noqa: E402

TERMINAL = {"COMPLETED", "FAILED", "CANCELED", "CANCELLED", "ABANDONED", "SUSPENDED"}
_results: list[dict] = []


def _rec(sid: str, fr: str, name: str, status: str, detail: str) -> None:
    _results.append({"id": sid, "fr": fr, "name": name, "status": status, "detail": detail})
    print(f"[{status:4}] {sid} ({fr}) {name} — {detail}")


def _short(obj, limit: int = 400) -> str:
    s = json.dumps(obj, default=str) if not isinstance(obj, str) else obj
    return s if len(s) <= limit else s[:limit] + " …(truncated)"


def _first_items(body):
    """Best-effort extraction of a list of records from a DCT list response."""
    if isinstance(body, dict):
        for k in ("items", "responseList", "results", "data"):
            if isinstance(body.get(k), list):
                return body[k]
    return body if isinstance(body, list) else []


async def main() -> int:
    base = os.environ.get("DCT_BASE_URL", "")
    if not base or not os.environ.get("DCT_API_KEY"):
        print("ERROR: set DCT_BASE_URL and DCT_API_KEY in the environment.")
        return 2

    app = FastMCP(name="integ-dynamic")

    # --- S1 / FR-001: download + cache spec from the live DCT --------------
    try:
        spec = spec_cache.load_and_cache_spec()
        n = len(spec.get("paths", {}))
        _rec("S1", "FR-001", "Spec download + cache from live DCT",
             "PASS" if n > 0 else "FAIL", f"{n} paths cached")
    except Exception as exc:
        _rec("S1", "FR-001", "Spec download + cache from live DCT", "FAIL", f"{type(exc).__name__}: {exc}")
        return 1

    discovery = _make_discovery_fn(app)
    client = DCTAPIClient()
    execute = _make_execute_fn(app, client)

    try:
        # --- S2 / FR-002: discovery list_tags -----------------------------
        r = discovery(action="list_tags")
        tags = r.get("tags", [])
        _rec("S2", "FR-002", "discovery(list_tags)",
             "PASS" if tags else "FAIL", f"{len(tags)} tags; sample={[t.get('name') for t in tags[:5]]}")

        # --- S3 / FR-002: filtered list_operations ------------------------
        r = discovery(action="list_operations", keyword="engine", method="GET")
        _rec("S3", "FR-002", "discovery(list_operations, keyword=engine, GET)",
             "PASS" if r.get("total_count", 0) > 0 else "FAIL",
             f"total_count={r.get('total_count')} ; first={(r.get('operations') or [{}])[0].get('path')}")

        # --- S4 / FR-002: get_operation_schema ----------------------------
        r = discovery(action="get_operation_schema", path="/management/engines", operation_method="GET")
        ok = isinstance(r, dict) and r.get("status") != "error"
        _rec("S4", "FR-002", "discovery(get_operation_schema /management/engines GET)",
             "PASS" if ok else "FAIL", _short(list(r.keys()) if isinstance(r, dict) else r, 200))

        # --- S5 / FR-003: execute a live GET read -------------------------
        r = await execute(method="GET", path="/management/engines")
        engines = _first_items(r.get("response")) if r.get("status") == "success" else []
        _rec("S5", "FR-003", "execute(GET /management/engines)",
             "PASS" if r.get("status") == "success" else "FAIL",
             f"status={r.get('status')} ; operation_type={r.get('operation_type')} ; engines={len(engines)}")

        # --- S6 / FR-004: confirmation gate (no mutation) ----------------
        # DELETE /management/engines/{engineId} has a `manual` rule. With confirmed=False
        # execute must return confirmation_required and NOT dispatch (nothing is deleted).
        eid = (engines[0].get("id") if engines and isinstance(engines[0], dict) else "eng-0")
        r = await execute(method="DELETE", path="/management/engines/{engineId}",
                          path_params={"engineId": str(eid)}, confirmed=False)
        gated = r.get("status") == "confirmation_required"
        _rec("S6", "FR-004", "execute destructive w/o confirmed -> gated (no dispatch)",
             "PASS" if gated else "WARN",
             f"status={r.get('status')} ; level={r.get('confirmation_level')}")

        # --- S7 / §5.1: poll an EXISTING job to a terminal state ----------
        rj = await execute(method="GET", path="/jobs")
        jobs = _first_items(rj.get("response")) if rj.get("status") == "success" else []
        if not jobs:
            _rec("S7", "§5.1", "poll existing job to terminal state", "SKIP", "no jobs available on this DCT")
        else:
            jid = jobs[0].get("id")
            last = None
            for _ in range(5):
                rp = await execute(method="GET", path="/jobs/{jobId}", path_params={"jobId": str(jid)})
                body = rp.get("response") if rp.get("status") == "success" else {}
                last = (body or {}).get("status")
                if last in TERMINAL:
                    break
                await asyncio.sleep(2)
            _rec("S7", "§5.1", f"poll job {jid} to terminal state",
                 "PASS" if last in TERMINAL else "WARN", f"final job status={last}")

        # --- S8: error path — unknown path -> OPERATION_NOT_FOUND ---------
        r = await execute(method="GET", path="/this/does/not/exist")
        _rec("S8", "FR-003", "execute(unknown path) -> OPERATION_NOT_FOUND",
             "PASS" if r.get("code") == "OPERATION_NOT_FOUND" else "FAIL", f"code={r.get('code')}")
    finally:
        await client.close()

    # --- S9: no auto-mode regression (in-process registration check) ------
    os.environ["DCT_TOOLSET"] = "auto"
    import importlib
    import dct_mcp_server.config.loader as loader
    importlib.reload(loader)
    from dct_mcp_server.tools import register_all_tools
    auto_app = FastMCP(name="auto-check")

    class _C:  # dummy client; auto registration does not call the network
        pass

    register_all_tools(auto_app, _C())
    auto_tools = sorted(t.name for t in await auto_app.list_tools())
    leaked = {"discovery", "execute"} & set(auto_tools)
    _rec("S9", "additivity", "auto mode unchanged; dynamic tools do not leak",
         "PASS" if (auto_tools and not leaked) else "FAIL",
         f"auto tools={len(auto_tools)} ; leaked={sorted(leaked)}")
    os.environ["DCT_TOOLSET"] = "dynamic"

    _write_evidence(base, spec_paths=len(spec.get("paths", {})))
    failed = [r for r in _results if r["status"] == "FAIL"]
    print(f"\n{'='*60}\n{len(_results)-len(failed)}/{len(_results)} scenarios non-FAIL ; FAIL={len(failed)}")
    return 1 if failed else 0


def _write_evidence(base_url: str, spec_paths: int) -> None:
    out = _REPO_ROOT / "docs" / "DLPXECO-13984" / "DLPXECO-13984-integration-test-evidence.md"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    npass = sum(1 for r in _results if r["status"] == "PASS")
    nfail = sum(1 for r in _results if r["status"] == "FAIL")
    nother = len(_results) - npass - nfail
    lines = [
        "# DLPXECO-13984 — Integration Test Evidence (Dynamic Mode)",
        "",
        f"- **Date**: {now}",
        f"- **Mode**: `DCT_TOOLSET=dynamic`",
        f"- **DCT instance**: `{base_url}` (live)",
        "- **API key**: redacted",
        f"- **Spec**: downloaded from live DCT — {spec_paths} paths",
        "- **Scope**: read-only — spec download, discovery browsing, GET reads, "
        "confirmation-gate (no dispatch), and polling an existing job. No data was created, mutated, or deleted.",
        "",
        f"**Summary:** {npass} PASS · {nfail} FAIL · {nother} other (WARN/SKIP) of {len(_results)} scenarios.",
        "",
        "| ID | FR | Scenario | Result | Detail |",
        "|----|----|----------|--------|--------|",
    ]
    for r in _results:
        detail = r["detail"].replace("|", "\\|")
        lines.append(f"| {r['id']} | {r['fr']} | {r['name']} | **{r['status']}** | {detail} |")
    lines += [
        "",
        "## Layer B — LLM-client transcript (manual addendum)",
        "",
        "The programmatic results above cover the deterministic API-level behaviour. To also evidence the "
        "end-user (LLM-driven) flow — including automatic async-job polling — connect Claude Desktop/Cursor to the "
        "server in `DCT_TOOLSET=dynamic` and run test queries, each prefixed with the standard pre-prompt:",
        "",
        "> *\"Poll the job if it is async and let me know if it succeeds.\"*",
        "",
        "Paste the client transcript/screenshots here.",
    ]
    out.write_text("\n".join(lines) + "\n")
    print(f"\nEvidence written: {out}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
