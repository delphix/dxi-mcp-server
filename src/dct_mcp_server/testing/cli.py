"""
dct-mcp-test — one runner, three invocation paths.

The same command is invoked from:
  - a terminal: `dct-mcp-test --layer ci`
  - GitHub Actions: `- run: dct-mcp-test --layer ci`
  - Claude Code: `/dct-mcp-test localhost --api-key abc`

Internally just wraps pytest with the right paths, markers, and env vars.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import click


# --layer name → pytest paths.
# "ci" is the merge-gate suite (no DCT credentials needed).
# "e2e" hits a real DCT instance and requires --base-url + --api-key.
# "llm" is Layer 5 — LLM-driven E2E via the Claude Code CLI against a real DCT.
# "connector" is the connector-workflow verification matrix (data-driven from
# schema.yaml); selected per connector with --connector.
# "all" runs everything in sequence (also requires DCT creds). It excludes "llm"
# on purpose: Layer 5 is advisory, needs the `claude` CLI, and may mutate.
_LAYER_PATHS: dict[str, list[str]] = {
    "unit":        ["tests/unit"],
    "integration": ["tests/integration"],
    "functional":  ["tests/functional"],
    "ci":          ["tests/unit", "tests/integration", "tests/functional"],
    "e2e":         ["tests/e2e"],
    "llm":         ["tests/llm_local"],
    "connector":   ["tests/llm_local/test_connector_workflows.py"],
    "scenarios":   ["tests/llm_local/test_scenarios.py"],
    "all":         ["tests/unit", "tests/integration", "tests/functional", "tests/e2e"],
}

# Marker passed to pytest -m for layers that select a subset by marker.
_LAYER_MARKERS: dict[str, str] = {
    "e2e": "real_dct",
    "llm": "llm_driven",
    "connector": "llm_driven",
    "scenarios": "scenario",
}

_LAYERS_NEEDING_DCT = {"e2e", "llm", "connector", "scenarios", "all"}

# Repo root (this file: src/dct_mcp_server/testing/cli.py → parents[3]).
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _connector_requirements(connector: str):
    """Load the connector requirements report from the test fixtures (checkout only)."""
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    try:
        from tests.llm_local.connector_fixtures import connector_requirements
    except Exception as exc:  # noqa: BLE001 — surface a clear CLI error
        raise click.ClickException(
            f"Could not load connector schema (run from a repo checkout): {exc}"
        )
    return connector_requirements(connector)


def _print_requirements(connector: str) -> None:
    """Print what a connector needs and what is still missing, then how to fix it."""
    req = _connector_requirements(connector)
    if req is None:
        raise click.ClickException(
            f"Unknown connector {connector!r}. Add it to "
            f"tests/fixtures/connectors/schema.yaml first."
        )

    click.secho(f"\n{req['display_name']}  (connector={req['connector']})", bold=True)
    click.echo(f"Workflows that will run: {', '.join(req['workflows']) or '(none defined)'}")

    click.secho("\nRequired inputs:", bold=True)
    for row in req["inputs"]:
        mark = click.style("✓", fg="green") if row["provided"] else click.style("✗ MISSING", fg="red")
        click.echo(f"  {mark}  {row['field']:<14} — {row['description']}")

    eng = click.style("✓", fg="green") if req["engine_ok"] else click.style("✗ MISSING", fg="red")
    click.echo(f"  {eng}  engine          — Delphix engine hostname + password")

    click.secho("\nProvide them via EITHER:", bold=True)
    exists = "exists" if req["secrets_file_exists"] else "NOT created yet"
    click.echo(f"  • file:    {req['secrets_file']}  ({exists})")
    click.echo(f"             copy tests/fixtures/connectors/.secrets.yaml.example and fill '{connector}'")
    click.echo(f"  • env vars: {req['env_prefix']}<FIELD>  (e.g. {req['env_prefix']}TARGET_HOST)")

    if req["missing"] or not req["engine_ok"]:
        click.secho(f"\n⚠ Not ready to run — fill the MISSING fields above.", fg="yellow")
    else:
        click.secho(f"\n✓ Ready. Run: dct-mcp-test --connector {connector} "
                    f"--base-url <url> --api-key <key>", fg="green")

# IMPORTANT for live layers (e2e/llm/scenarios): run this CLI from the non-editable
# safe-run venv so the server generates tools into $TEMP, not src/:
#     .venv-live/bin/dct-mcp-test --layer scenarios --persona continuous_data_admin


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--base-url",
    envvar="DCT_BASE_URL",
    help="DCT base URL (or set DCT_BASE_URL). Required for --layer e2e/llm/all.",
)
@click.option(
    "--api-key",
    envvar="DCT_API_KEY",
    help="DCT API key (or set DCT_API_KEY). Required for --layer e2e/llm/all.",
)
@click.option(
    "--layer",
    type=click.Choice(list(_LAYER_PATHS)),
    default=None,
    help="Which test layer(s) to run. Default 'ci' = unit + integration + functional "
         "(no DCT needed). Defaults to 'connector' when --connector is given.",
)
@click.option(
    "--connector",
    help="For --layer connector: which connector to test (e.g. mysql, db2, postgresql). "
         "Sets CONNECTOR_TYPE. Use with --show-requirements to see what it needs.",
)
@click.option(
    "--show-requirements",
    is_flag=True,
    help="Print what --connector needs (hosts/creds) and what is still missing, then exit. "
         "Does not run any tests or touch DCT.",
)
@click.option(
    "--workflow",
    help="Filter to workflows matching this name (passed to pytest as -k).",
)
@click.option(
    "--persona",
    help="For --layer scenarios: comma-separated personas to run "
         "(e.g. self_service,continuous_data_admin). Sets SCENARIO_PERSONAS.",
)
@click.option(
    "--mutations",
    is_flag=True,
    help="For --layer scenarios: include mutation-tier prompts (default: read-only).",
)
@click.option(
    "--scenario-limit",
    type=int,
    default=0,
    help="For --layer scenarios: cap scenarios per persona (0 = no cap).",
)
@click.option(
    "--report",
    type=click.Path(),
    help="Write a JUnit-XML report to this path (machine-readable pass/skip/fail).",
)
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Skip the e2e cleanup pass. Dangerous on a persistent DCT — leaves orphaned resources.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Pass --tb=long to pytest for more detailed failure output.",
)
def main(
    base_url: str | None,
    api_key: str | None,
    layer: str,
    connector: str | None,
    show_requirements: bool,
    workflow: str | None,
    persona: str | None,
    mutations: bool,
    scenario_limit: int,
    report: str | None,
    no_cleanup: bool,
    verbose: bool,
) -> None:
    """Run the DCT MCP Server test suite."""

    # --show-requirements is a pure inspection path: print what the connector
    # needs and exit. Never touches DCT, never runs pytest.
    if show_requirements:
        _print_requirements(connector or os.environ.get("CONNECTOR_TYPE", "mysql"))
        return

    # --connector implies the connector layer unless an explicit layer was given.
    if layer is None:
        layer = "connector" if connector else "ci"

    env = os.environ.copy()

    # The connector layer is connector-driven: --connector selects which matrix.
    if layer == "connector":
        ctype = connector or os.environ.get("CONNECTOR_TYPE", "mysql")
        env["CONNECTOR_TYPE"] = ctype
        env["LLM_ALLOW_MUTATION"] = "1"   # workflows mutate; this layer implies it
        # Preflight: fail fast with a clear message instead of 10 min into a run.
        req = _connector_requirements(ctype)
        if req is None:
            raise click.UsageError(
                f"Unknown connector {ctype!r}. Add it to schema.yaml. "
                f"Supported: {', '.join(_connector_requirements('mysql')['supported_connectors'])}"
            )
        if req["missing"] or not req["engine_ok"]:
            raise click.UsageError(
                f"Connector {ctype!r} is missing required inputs: "
                f"{', '.join(req['missing']) or 'engine creds'}. "
                f"Run: dct-mcp-test --connector {ctype} --show-requirements"
            )
        # Per-run results file the report exporter consumes.
        results = Path("test-results") / f"connector-workflows-{ctype}.jsonl"
        results.parent.mkdir(parents=True, exist_ok=True)
        if results.exists():
            results.unlink()  # fresh run
        env["CONNECTOR_WORKFLOW_RESULTS"] = str(results)
    elif connector:
        # --connector given without the connector layer — still honor it.
        env["CONNECTOR_TYPE"] = connector

    paths = _LAYER_PATHS[layer]

    # The scenario layer is persona-driven: --persona selects which catalogs to run.
    if layer == "scenarios":
        if not persona:
            raise click.UsageError(
                "--layer scenarios requires --persona (e.g. --persona self_service,"
                "continuous_data_admin). Available: self_service, self_service_provision, "
                "continuous_data_admin, platform_admin, reporting_insights, auto."
            )
        env["SCENARIO_PERSONAS"] = persona
        if mutations:
            env["SCENARIO_MUTATIONS"] = "1"
        if scenario_limit:
            env["SCENARIO_LIMIT"] = str(scenario_limit)

    # E2E layers need DCT credentials; refuse to run silently against an
    # empty target. Generate a run tag so the cleanup pass can find what
    # this run created on the real DCT.
    if layer in _LAYERS_NEEDING_DCT:
        if not base_url or not api_key:
            raise click.UsageError(
                f"--layer {layer} requires both --base-url and --api-key "
                f"(or DCT_BASE_URL and DCT_API_KEY env vars)."
            )
        env["DCT_BASE_URL"] = base_url
        env["DCT_API_KEY"] = api_key
        env["E2E_RUN_TAG"] = f"e2e-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        click.secho(f"E2E_RUN_TAG = {env['E2E_RUN_TAG']}", fg="cyan")

    # Build pytest args. -v always; -k filters; --tb=long if verbose.
    pytest_args = [sys.executable, "-m", "pytest", *paths, "-v"]
    if layer in _LAYER_MARKERS:
        pytest_args.extend(["-m", _LAYER_MARKERS[layer]])
    if workflow:
        pytest_args.extend(["-k", workflow])
    if verbose:
        pytest_args.extend(["--tb=long"])
    if report:
        pytest_args.extend([f"--junit-xml={report}"])

    click.secho(f"→ {' '.join(pytest_args)}", fg="green")
    result = subprocess.run(pytest_args, env=env)

    # On e2e layers, always run the cleanup pass unless explicitly disabled —
    # even if the main tests failed, the resources they created must be cleaned.
    if layer in _LAYERS_NEEDING_DCT and not no_cleanup:
        cleanup_path = "tests/e2e/cleanup"
        if os.path.isdir(cleanup_path):
            click.secho(f"\n→ cleanup: pytest {cleanup_path}", fg="yellow")
            subprocess.run(
                [sys.executable, "-m", "pytest", cleanup_path, "-v"],
                env=env,
            )
        # If tests/e2e/cleanup/ doesn't exist yet (PoC stage), skip silently.

    # Connector layer: turn the JSONL results into Results.csv + Summary.csv.
    if layer == "connector":
        results_file = env.get("CONNECTOR_WORKFLOW_RESULTS", "")
        if results_file and os.path.exists(results_file):
            report_script = str(_REPO_ROOT / "scripts" / "connector_workflow_report.py")
            out_base = f"test-results/{connector or 'mysql'}-MCP-test-results"
            click.secho(f"\n→ report: {results_file} → {out_base}(Results|Summary).csv", fg="yellow")
            subprocess.run(
                [sys.executable, report_script, results_file, "--out-base", out_base],
                env=env,
            )
        else:
            click.secho("\n(no workflow results recorded — nothing to report)", fg="yellow")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
