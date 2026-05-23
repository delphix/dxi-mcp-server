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

import click


# --layer name → pytest paths.
# "ci" is the merge-gate suite (no DCT credentials needed).
# "e2e" hits a real DCT instance and requires --base-url + --api-key.
# "all" runs everything in sequence (also requires DCT creds).
_LAYER_PATHS: dict[str, list[str]] = {
    "unit":        ["tests/unit"],
    "integration": ["tests/integration"],
    "functional":  ["tests/functional"],
    "ci":          ["tests/unit", "tests/integration", "tests/functional"],
    "e2e":         ["tests/e2e"],
    "all":         ["tests/unit", "tests/integration", "tests/functional", "tests/e2e"],
}

_LAYERS_NEEDING_DCT = {"e2e", "all"}


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--base-url",
    envvar="DCT_BASE_URL",
    help="DCT base URL (or set DCT_BASE_URL). Required for --layer e2e/all.",
)
@click.option(
    "--api-key",
    envvar="DCT_API_KEY",
    help="DCT API key (or set DCT_API_KEY). Required for --layer e2e/all.",
)
@click.option(
    "--layer",
    type=click.Choice(list(_LAYER_PATHS)),
    default="ci",
    show_default=True,
    help="Which test layer(s) to run. 'ci' = unit + integration + functional (no DCT needed).",
)
@click.option(
    "--workflow",
    help="Filter to workflows matching this name (passed to pytest as -k).",
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
    workflow: str | None,
    no_cleanup: bool,
    verbose: bool,
) -> None:
    """Run the DCT MCP Server test suite."""

    env = os.environ.copy()
    paths = _LAYER_PATHS[layer]

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
    if layer == "e2e":
        pytest_args.extend(["-m", "real_dct"])
    if workflow:
        pytest_args.extend(["-k", workflow])
    if verbose:
        pytest_args.extend(["--tb=long"])

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

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
