"""
Layer 5 — Connector workflow verification (data-driven, full matrix).

Mirrors DLPXECO-13687: validate virtualization workflows via the DCT MCP server.
Reads the per-connector `workflows:` matrix from tests/fixtures/connectors/schema.yaml
and, for each row, hands Claude a plain-English task through the MCP server and checks:

  1. RIGHT TOOL    — expect_tool appears in the tools Claude called
  2. RIGHT ACTION  — expect_action appears in that tool's actions
  3. COMPLETED     — (mutations) an INDEPENDENT read confirms the effect

Row `kind` controls the verdict:
  readonly       — list/show; PASS if tool+action correct
  mutation       — PASS if tool+action correct AND completion verified
  expected_error — op should be rejected; EXPECTED-ERROR if the LLM attempted it
                   (the server relayed the rejection) — does NOT fail the suite
  na             — not applicable to this connector; N/A — does NOT fail the suite
  destructive    — harms shared infra (engine register/deregister); SKIPPED unless
                   CONNECTOR_DESTRUCTIVE=1

Connector selected by CONNECTOR_TYPE (default mysql). Fully autonomous: credentials
from .secrets.yaml or DCT_CONNECTOR_<TYPE>_* env vars; Claude runs with
bypassPermissions + the auto-confirm/idempotency pre-prompt.

Every row's verdict is appended (immediately) to CONNECTOR_WORKFLOW_RESULTS
(default test-results/connector-workflows.jsonl). Build the CSVs with:

    python scripts/connector_workflow_report.py <that file>

GATED: skipped unless LLM_ALLOW_MUTATION=1 and connector secrets are present.
Run only against a DISPOSABLE / CLONED DCT.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.llm_local.conftest import license_blocked
from tests.llm_local.connector_fixtures import (
    ConnectorSpec,
    load_engine_spec,
    load_workflows,
)

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_DESTRUCTIVE = os.environ.get("CONNECTOR_DESTRUCTIVE") == "1"
_CONNECTOR = os.environ.get("CONNECTOR_TYPE", "mysql").lower()
_WORKFLOWS = load_workflows(_CONNECTOR)
_RESULTS_PATH = Path(
    os.environ.get("CONNECTOR_WORKFLOW_RESULTS", "test-results/connector-workflows.jsonl")
)


# Sections whose scenarios act on a DB host and therefore need host + credentials.
# Engine / Connector(toolkit) / System operate at the ENGINE level only.
_HOST_DEPENDENT_SECTIONS = {"Environment", "dSource", "VDB"}


def _skip_reason(spec: ConnectorSpec, section: str = "") -> str | None:
    if not _MUTATION:
        return "Set LLM_ALLOW_MUTATION=1 to run connector workflow tests."
    # Host/credential checks apply only to host-dependent sections; engine-level
    # scenarios (Engine, Connector/toolkit, System) need no DB host.
    if section in _HOST_DEPENDENT_SECTIONS:
        if not spec.target_host:
            return (
                f"No target_host for '{spec.connector_type}'. "
                f"Run: dct-mcp-test --connector {spec.connector_type} --show-requirements"
            )
        if not spec.env_password or not spec.link_password:
            return (
                f"Missing credentials for '{spec.connector_type}'. "
                f"Run: dct-mcp-test --connector {spec.connector_type} --show-requirements"
            )
    return None


def _context(spec: ConnectorSpec) -> dict[str, str]:
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    eng = load_engine_spec()

    # Unique-per-run staging/VDB serverId + port + mount, so reruns never collide
    # with a stale NFS mount left by a prior run's dSource/VDB. Derived from the
    # run tag → stable within a run (all scenarios agree), distinct across runs.
    # dSource and VDB get DIFFERENT ids/ports/mounts. Range kept inside 200–860.
    import hashlib, string
    h = hashlib.md5(run_tag.encode()).hexdigest()
    base = 200 + (int(h, 16) % 600)               # 200..799
    ds_server_id = base
    ds_staging_port = 2000 + base                 # e.g. 2417
    ds_mount_path = f"/mnt/link/{ds_staging_port}"
    vdb_server_id = base + 60                      # distinct from dSource id
    vdb_port = 2000 + vdb_server_id
    vdb_mount_path = f"/mnt/link/vdb{vdb_port}"

    # 6-char alphanumeric dSource name, generated per run (not hardcoded). Stable
    # within a run (derived from the run tag) so every scenario agrees on it;
    # distinct across runs so a fresh link is exercised each time. First char is a
    # letter (DCT object names should not start with a digit).
    _alnum = string.ascii_lowercase + string.digits
    dsource_name = "".join(_alnum[int(h[i * 2:i * 2 + 2], 16) % 36] for i in range(6))
    if dsource_name[0].isdigit():
        dsource_name = "d" + dsource_name[1:]
    # Optional override to target an EXISTING dSource by name (e.g. to re-run
    # disable/enable against a dSource a prior run already linked).
    dsource_name = os.environ.get("E2E_DSOURCE_NAME") or dsource_name

    # VDB name: short (<=8 chars) alphanumeric, generated per run from a DIFFERENT
    # slice of the hash than the dSource (so they never collide). First char a
    # letter. Overridable with E2E_VDB_NAME to target an existing VDB.
    vdb_name = "".join(_alnum[int(h[i * 2:i * 2 + 2], 16) % 36] for i in range(8, 16))[:8]
    if vdb_name[0].isdigit():
        vdb_name = "v" + vdb_name[1:]
    # Override (to target an existing VDB) is used VERBATIM — not truncated.
    vdb_name = os.environ.get("E2E_VDB_NAME") or vdb_name

    return {
        "display_name": spec.display_name,
        "connector": spec.connector_type,
        "engine_name": eng.name or "wf-test-engine",
        "engine_hostname": eng.hostname,
        "engine_username": eng.username,
        "engine_password": eng.password,
        "toolkit_file": spec.toolkit_file,
        "dsource_name": dsource_name,
        "vdb_name": vdb_name,
        "source_host": spec.source_host,
        "target_host": spec.target_host,
        "env_user": spec.env_user,
        "env_password": spec.env_password,
        "link_user": spec.link_user,
        "link_password": spec.link_password,
        "source_config_name": spec.source_config_name,
        "dsource_link_action": spec.dsource_link_action,
        "provision_action": spec.provision_action,
        # unique-per-run staging + VDB allocation
        "ds_server_id": str(ds_server_id),
        "ds_staging_port": str(ds_staging_port),
        "ds_mount_path": ds_mount_path,
        "vdb_server_id": str(vdb_server_id),
        "vdb_port": str(vdb_port),
        "vdb_mount_path": vdb_mount_path,
    }


def _fmt(template, ctx: dict[str, str]) -> str:
    return (template or "").format(**ctx).strip()


# Keys whose values must never be written to the results file.
_SECRET_KEYS = ("pass", "password", "secret", "api_key", "apikey", "token", "credential")


def _step_sequence(result) -> list[str]:
    """Ordered 'tool/action' list of every MCP call the LLM made (no raw inputs)."""
    seq = []
    for c in result.tool_calls:
        action = c.input.get("action")
        seq.append(f"{c.name}/{action}" if action else c.name)
    return seq


def _detailed_calls(result) -> list[dict]:
    """Ordered tool calls with non-secret inputs, for the step-by-step transcript."""
    calls = []
    for c in result.tool_calls:
        safe_input = {
            k: ("***" if any(s in k.lower() for s in _SECRET_KEYS) else v)
            for k, v in c.input.items()
        }
        calls.append({"tool": c.name, "action": c.input.get("action"), "input": safe_input})
    return calls


def _record(row: dict) -> None:
    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _RESULTS_PATH.open("a") as fh:
        fh.write(json.dumps(row) + "\n")


def _base_row(step: dict, ctx: dict, idx: int) -> dict:
    return {
        "section": step.get("section", ""),
        "connector": _CONNECTOR,
        "row": idx,
        "workflow": step["id"],
        "kind": step.get("kind", "mutation"),
        "description": step.get("description", ""),
        "prompt": _fmt(step.get("prompt"), ctx),
        "expected_tool": step.get("expect_tool", "data_tool"),
        "expected_action": _fmt(step.get("expect_action", ""), ctx),
    }


@pytest.mark.skipif(not _WORKFLOWS, reason=f"No workflows defined for connector '{_CONNECTOR}'")
@pytest.mark.parametrize(
    "idx,step",
    list(enumerate(_WORKFLOWS, start=1)),
    ids=[w["id"] for w in _WORKFLOWS],
)
def test_connector_workflow(
    idx: int,
    step: dict,
    connector_spec: ConnectorSpec,
    llm_driver_for_connector,
):
    ctx = _context(connector_spec)
    kind = step.get("kind", "mutation")
    row = _base_row(step, ctx, idx)

    # Gates that still record a row so the CSV shows every step.
    reason = _skip_reason(connector_spec, step.get("section", ""))
    if reason:
        _record({**row, "actual_tools": [], "actual_actions": [], "tool_correct": False,
                 "action_correct": False, "operation_completed": False,
                 "status": "SKIPPED", "evidence": reason})
        pytest.skip(reason)

    if kind == "destructive" and not _DESTRUCTIVE:
        note = "destructive to shared infra — set CONNECTOR_DESTRUCTIVE=1 to run"
        _record({**row, "actual_tools": [], "actual_actions": [], "tool_correct": False,
                 "action_correct": False, "operation_completed": False,
                 "status": "SKIPPED", "evidence": note})
        pytest.skip(note)

    expect_tool = row["expected_tool"]
    expect_action = row["expected_action"]
    timeout = int(step.get("timeout", 900))

    # Result row is initialized with ERROR defaults and written in a finally block,
    # so EVERY step is captured — even if the driver raises (timeout, crash). The
    # user requirement: record all steps irrespective of pass/fail.
    result = {**row, "actual_tools": [], "actual_actions": [],
              "tool_correct": False, "action_correct": False,
              "operation_completed": False, "status": "ERROR", "evidence": "",
              "act_steps": [], "act_calls": [], "act_narration": "",
              "verify_steps": [], "verify_narration": ""}
    _written = {"done": False}

    def _flush():
        if not _written["done"]:
            _record(result)
            _written["done"] = True

    try:
        # ── Act ─────────────────────────────────────────────────────────────────
        # For state-changing steps, force confirmed=true up front in the PROMPT (the
        # user turn is more salient than the system pre-prompt). The MCP confirmation
        # gate otherwise makes the model stop and ask "Shall I proceed?", which a
        # non-interactive run can't answer.
        act_prompt = _fmt(step["prompt"], ctx)
        if kind in ("mutation", "setup", "destructive"):
            act_prompt += (
                "\n\nIMPORTANT: This is automated — there is no human to confirm. In EVERY "
                "tool call that changes state (register/create/link/provision/refresh/"
                "snapshot/enable/disable/start/stop/rollback/delete/unregister), pass the "
                "parameter confirmed=true in your FIRST call. If any response still says "
                "confirmation_required, immediately repeat the call with confirmed=true. "
                "Never ask whether to proceed."
            )
        act = llm_driver_for_connector(act_prompt, timeout=timeout)

        tools_used = sorted(act.tools_used)
        actions = act.actions_for(expect_tool)
        result.update(actual_tools=tools_used, actual_actions=actions,
                      act_steps=_step_sequence(act), act_calls=_detailed_calls(act),
                      act_narration=(act.final_text or "")[:4000],
                      evidence=(act.final_text or "")[:600])

        if license_blocked(act):
            note = f"DCT license does not permit '{step['id']}'"
            result.update(status="SKIPPED", evidence=note)
            _flush()
            pytest.skip(note)

        tool_ok = expect_tool in act.tools_used
        # expect_action may list several equally-valid actions separated by "|"
        # (e.g. an env update done via update_environment OR update_environment_host).
        # The step is action-correct if the LLM used ANY of them.
        expected_actions = [a.strip() for a in expect_action.split("|") if a.strip()]
        action_ok = any(a in actions for a in expected_actions) if expected_actions else tool_ok

        # ── Verify completion (mutations + setup) ────────────────────────────────
        # We do NOT substring-match the LLM's prose for presence/absence — that is
        # fooled when the model NARRATES the entity it is confirming gone (e.g.
        # "rh95-mys-t1 does not appear"). Instead we make the verify emit an
        # explicit verdict token and parse that.
        completed = True
        verify_prompt = _fmt(step.get("verify_prompt", ""), ctx)
        if kind in ("mutation", "setup") and verify_prompt:
            contains = _fmt(step.get("verify_contains", ""), ctx)
            absent = _fmt(step.get("verify_absent", ""), ctx)
            # verify_expect: a STATE assertion that must hold after the op (e.g.
            # "the dSource X is DISABLED"). Stronger than presence — catches a
            # no-op or 500 that leaves the object present but unchanged.
            expect = _fmt(step.get("verify_expect", ""), ctx)
            target = contains or absent
            vp = verify_prompt
            if expect:
                vp += (
                    f"\n\nThen decide whether this statement is TRUE based on the "
                    f"result: \"{expect}\". End your reply with one final line that is "
                    f"EXACTLY 'VERDICT: PASS' (statement true) or 'VERDICT: FAIL' "
                    f"(statement false) — nothing else on that line."
                )
            elif target:
                vp += (
                    f"\n\nThen decide whether an item named EXACTLY '{target}' is "
                    f"present in that result. End your reply with one final line that "
                    f"is EXACTLY 'VERDICT: PRESENT' or 'VERDICT: ABSENT' — nothing else "
                    f"on that line."
                )
            verify = llm_driver_for_connector(vp, timeout=300)
            vtext = verify.final_text or ""
            result.update(verify_steps=_step_sequence(verify),
                          verify_narration=vtext[:2000],
                          evidence=vtext[:600])
            import re as _re
            if expect:
                m = _re.findall(r"VERDICT:\s*(PASS|FAIL)", vtext, _re.I)
                completed = bool(m) and m[-1].upper() == "PASS"
            else:
                verdicts = _re.findall(r"VERDICT:\s*(PRESENT|ABSENT)", vtext, _re.I)
                verdict = verdicts[-1].upper() if verdicts else None
                if contains:
                    completed = (verdict == "PRESENT") if verdict else (contains in vtext)
                if absent:
                    completed = (verdict == "ABSENT") if verdict else (absent not in vtext)

        # ── Verdict ──────────────────────────────────────────────────────────────
        # setup: idempotent — PASS if the object is present afterwards, regardless
        # of whether it was created now or already existed.
        if kind == "setup":
            status = "PASS" if completed else "FAIL"
        elif kind == "expected_error":
            status = "EXPECTED-ERROR" if tool_ok else "FAIL"
        elif kind == "na":
            status = "N/A" if tool_ok else "FAIL"
        elif kind == "readonly":
            status = "PASS" if (tool_ok and action_ok) else "FAIL"
        else:  # mutation / destructive
            status = "PASS" if (tool_ok and action_ok and completed) else "FAIL"

        result.update(tool_correct=tool_ok, action_correct=action_ok,
                      operation_completed=completed, status=status)
        _flush()

        # ── Assert (only PASS-required kinds fail the suite) ─────────────────────
        if kind == "setup":
            assert completed, (
                f"[{step['id']}] prerequisite not present after setup — dependent tests "
                f"would fail.\n{result['evidence']}"
            )
            return
        if kind in ("expected_error", "na"):
            assert tool_ok, (
                f"[{step['id']}] expected the LLM to attempt {expect_tool!r}; "
                f"tools used: {tools_used}\n{act.final_text[:300]}"
            )
            return
        assert tool_ok, (
            f"[{step['id']}] expected tool {expect_tool!r} not called. "
            f"Tools used: {tools_used}\n{act.final_text[:300]}"
        )
        if expect_action:
            assert action_ok, (
                f"[{step['id']}] expected action {expect_action!r} not called on "
                f"{expect_tool}. Actions seen: {actions}"
            )
        if kind == "mutation":
            assert completed, (
                f"[{step['id']}] operation not confirmed by independent read.\n{result['evidence']}"
            )
    except BaseException as exc:  # noqa: BLE001 — record then re-raise (incl. timeouts)
        if result["status"] == "ERROR":
            result["evidence"] = (f"{type(exc).__name__}: {exc}")[:600]
        raise
    finally:
        _flush()
