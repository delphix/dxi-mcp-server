"""
Unit tests for testing/cli.py — the dct-mcp-test CLI entry point.

Uses Click's test runner (CliRunner) + mocked subprocess.run so no real
pytest or DCT instance is needed. The CliRunner catches SystemExit naturally.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dct_mcp_server.testing.cli import main


@pytest.fixture()
def runner():
    return CliRunner()


def _proc(returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# Helpers: invoke with subprocess mocked
# ---------------------------------------------------------------------------


def _invoke(runner, args, *, env=None, is_dir=False, returncode=0):
    """Invoke CLI with subprocess.run mocked out.

    CliRunner catches SystemExit by default (catch_exceptions=True),
    so sys.exit() in main() becomes the result.exit_code.
    """
    call_log = []

    def fake_run(cmd, **kwargs):
        call_log.append(cmd)
        return _proc(returncode)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=is_dir):
            result = runner.invoke(main, args, env=env, catch_exceptions=True)
    return result, call_log


# ---------------------------------------------------------------------------
# Basic layer invocations (no DCT creds needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layer", ["unit", "integration", "functional", "ci"])
def test_layers_no_creds_exits_zero(runner, layer):
    result, calls = _invoke(runner, ["--layer", layer])
    assert result.exit_code == 0
    assert len(calls) == 1  # one subprocess call


@pytest.mark.parametrize("layer", ["unit", "integration", "functional", "ci"])
def test_layers_subprocess_args_include_pytest(runner, layer):
    result, calls = _invoke(runner, ["--layer", layer])
    pytest_cmd = calls[0]
    assert "pytest" in " ".join(str(a) for a in pytest_cmd)


def test_unit_layer_paths(runner):
    result, calls = _invoke(runner, ["--layer", "unit"])
    assert any("tests/unit" in str(a) for a in calls[0])


def test_ci_layer_includes_all_three(runner):
    result, calls = _invoke(runner, ["--layer", "ci"])
    cmd_str = " ".join(str(a) for a in calls[0])
    assert "tests/unit" in cmd_str
    assert "tests/integration" in cmd_str
    assert "tests/functional" in cmd_str


# ---------------------------------------------------------------------------
# layer=scenarios validation
# ---------------------------------------------------------------------------


def test_scenarios_without_persona_raises(runner):
    result = runner.invoke(main, ["--layer", "scenarios"], catch_exceptions=True)
    # Click UsageError → exit_code == 2
    assert result.exit_code == 2
    assert "persona" in result.output.lower()


def test_scenarios_with_persona_and_creds(runner):
    result, calls = _invoke(
        runner,
        [
            "--layer",
            "scenarios",
            "--persona",
            "self_service",
            "--base-url",
            "https://dct.example.com",
            "--api-key",
            "test-key",
        ],
    )
    assert result.exit_code == 0


def test_scenarios_sets_persona_env(runner):
    captured_env = {}

    def fake_run(cmd, env=None, **kwargs):
        if env:
            captured_env.update(env)
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                [
                    "--layer",
                    "scenarios",
                    "--persona",
                    "self_service",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    assert captured_env.get("SCENARIO_PERSONAS") == "self_service"


def test_scenarios_mutations_flag(runner):
    captured_env = {}

    def fake_run(cmd, env=None, **kwargs):
        if env:
            captured_env.update(env)
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                [
                    "--layer",
                    "scenarios",
                    "--persona",
                    "self_service",
                    "--mutations",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    assert captured_env.get("SCENARIO_MUTATIONS") == "1"


def test_scenarios_no_mutations_flag(runner):
    captured_env = {}

    def fake_run(cmd, env=None, **kwargs):
        if env:
            captured_env.update(env)
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                [
                    "--layer",
                    "scenarios",
                    "--persona",
                    "self_service",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    assert "SCENARIO_MUTATIONS" not in captured_env


def test_scenarios_scenario_limit(runner):
    captured_env = {}

    def fake_run(cmd, env=None, **kwargs):
        if env:
            captured_env.update(env)
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                [
                    "--layer",
                    "scenarios",
                    "--persona",
                    "self_service",
                    "--scenario-limit",
                    "5",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    assert captured_env.get("SCENARIO_LIMIT") == "5"


# ---------------------------------------------------------------------------
# layer=e2e validation
# ---------------------------------------------------------------------------


def test_e2e_without_creds_raises(runner):
    # Clear any env-injected creds (autouse _set_test_env sets them globally)
    result = runner.invoke(
        main,
        ["--layer", "e2e"],
        env={"DCT_BASE_URL": "", "DCT_API_KEY": ""},
        catch_exceptions=True,
    )
    assert result.exit_code == 2
    assert (
        "base-url" in result.output.lower()
        or "api-key" in result.output.lower()
        or "require" in result.output.lower()
    )


def test_e2e_with_creds_runs(runner):
    result, calls = _invoke(
        runner,
        [
            "--layer",
            "e2e",
            "--base-url",
            "https://dct.example.com",
            "--api-key",
            "my-key",
        ],
    )
    assert result.exit_code == 0
    assert len(calls) >= 1


def test_e2e_sets_dct_env_vars(runner):
    captured_env = {}

    def fake_run(cmd, env=None, **kwargs):
        if env:
            captured_env.update(env)
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                [
                    "--layer",
                    "e2e",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    assert captured_env.get("DCT_BASE_URL") == "https://dct.example.com"
    assert captured_env.get("DCT_API_KEY") == "my-key"
    assert "E2E_RUN_TAG" in captured_env
    assert captured_env["E2E_RUN_TAG"].startswith("e2e-")


def test_e2e_cleanup_runs_when_dir_exists(runner):
    call_count = {"n": 0}

    def fake_run(cmd, env=None, **kwargs):
        call_count["n"] += 1
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=True):
            runner.invoke(
                main,
                [
                    "--layer",
                    "e2e",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    # Main run + cleanup run = 2
    assert call_count["n"] >= 2


def test_e2e_cleanup_skipped_when_dir_missing(runner):
    call_count = {"n": 0}

    def fake_run(cmd, env=None, **kwargs):
        call_count["n"] += 1
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                [
                    "--layer",
                    "e2e",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                ],
                catch_exceptions=True,
            )

    assert call_count["n"] == 1


def test_e2e_no_cleanup_flag_skips_cleanup(runner):
    call_count = {"n": 0}

    def fake_run(cmd, env=None, **kwargs):
        call_count["n"] += 1
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=True):
            runner.invoke(
                main,
                [
                    "--layer",
                    "e2e",
                    "--base-url",
                    "https://dct.example.com",
                    "--api-key",
                    "my-key",
                    "--no-cleanup",
                ],
                catch_exceptions=True,
            )

    # Cleanup skipped — only the main run
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# layer=all
# ---------------------------------------------------------------------------


def test_all_requires_creds(runner):
    # Clear any env-injected creds (autouse _set_test_env sets them globally)
    result = runner.invoke(
        main,
        ["--layer", "all"],
        env={"DCT_BASE_URL": "", "DCT_API_KEY": ""},
        catch_exceptions=True,
    )
    assert result.exit_code == 2


def test_all_with_creds_runs(runner):
    result, calls = _invoke(
        runner,
        [
            "--layer",
            "all",
            "--base-url",
            "https://dct.example.com",
            "--api-key",
            "my-key",
        ],
    )
    assert result.exit_code == 0


def test_all_includes_e2e_path(runner):
    result, calls = _invoke(
        runner,
        [
            "--layer",
            "all",
            "--base-url",
            "https://dct.example.com",
            "--api-key",
            "my-key",
        ],
    )
    cmd_str = " ".join(str(a) for a in calls[0])
    assert "tests/e2e" in cmd_str


# ---------------------------------------------------------------------------
# --report flag
# ---------------------------------------------------------------------------


def test_report_flag_passes_junit_xml(runner):
    result, calls = _invoke(runner, ["--layer", "unit", "--report", "/tmp/report.xml"])
    assert result.exit_code == 0
    cmd_str = " ".join(str(a) for a in calls[0])
    assert "junit-xml" in cmd_str
    assert "/tmp/report.xml" in cmd_str


# ---------------------------------------------------------------------------
# --workflow flag
# ---------------------------------------------------------------------------


def test_workflow_flag_passes_k_filter(runner):
    result, calls = _invoke(runner, ["--layer", "unit", "--workflow", "test_vdb"])
    assert result.exit_code == 0
    cmd_list = calls[0]
    assert "-k" in cmd_list
    assert "test_vdb" in cmd_list


# ---------------------------------------------------------------------------
# --verbose flag
# ---------------------------------------------------------------------------


def test_verbose_flag_passes_tb_long(runner):
    result, calls = _invoke(runner, ["--layer", "unit", "--verbose"])
    assert result.exit_code == 0
    assert "--tb=long" in calls[0]


# ---------------------------------------------------------------------------
# Non-zero exit propagation
# ---------------------------------------------------------------------------


def test_exit_code_propagated(runner):
    result, _ = _invoke(runner, ["--layer", "unit"], returncode=2)
    # sys.exit(2) becomes SystemExit which CliRunner turns into exit_code=2
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Env var fallback for --base-url / --api-key
# ---------------------------------------------------------------------------


def test_env_var_base_url_used(runner):
    captured_env = {}

    def fake_run(cmd, env=None, **kwargs):
        if env:
            captured_env.update(env)
        return _proc(0)

    with patch("subprocess.run", side_effect=fake_run):
        with patch("os.path.isdir", return_value=False):
            runner.invoke(
                main,
                ["--layer", "e2e"],
                env={
                    "DCT_BASE_URL": "https://from-env.example.com",
                    "DCT_API_KEY": "env-key",
                },
                catch_exceptions=True,
            )

    assert captured_env.get("DCT_BASE_URL") == "https://from-env.example.com"


# ---------------------------------------------------------------------------
# Layer markers
# ---------------------------------------------------------------------------


def test_e2e_layer_includes_real_dct_marker(runner):
    result, calls = _invoke(
        runner,
        [
            "--layer",
            "e2e",
            "--base-url",
            "https://dct.example.com",
            "--api-key",
            "my-key",
        ],
    )
    cmd_list = calls[0]
    assert "-m" in cmd_list
    assert "real_dct" in cmd_list


def test_ci_layer_no_marker(runner):
    result, calls = _invoke(runner, ["--layer", "ci"])
    cmd_list = calls[0]
    # "-m" always appears in "python -m pytest"; check no marker value is added
    assert "real_dct" not in cmd_list
    assert "llm_driven" not in cmd_list
    assert "scenario" not in cmd_list
