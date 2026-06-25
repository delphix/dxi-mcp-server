# DLPXECO-14257 — Build & Evaluation

This is a pure-Python package (no compile step). "Build" mirrors the CI `lint` and
`build` jobs: ruff lint + format check, an import smoke test, and an sdist/wheel build.

## Build command(s) used

```bash
# Lint (CI: ruff check . --output-format=github)
git ls-files '*.py' | xargs uv run ruff check --output-format=concise

# Format (CI: ruff format --check .)
git ls-files '*.py' | xargs uv run ruff format --check

# Import smoke test (catches broken imports after the auto-mode removal)
DCT_TOOLSET=dynamic uv run python -c "import dct_mcp_server.main; ..."

# Package build (CI: build sdist + wheel)
uv build
```

## Outcome — success

| Step | Result |
|---|---|
| `ruff check` (lint) | **All checks passed!** |
| `ruff format --check` | **42 files already formatted** (after formatting `config/loader.py`) |
| Import smoke | **imports OK** — `find_endpoint`, `get_spec_chunk`, `resolve_confirmation`, `get_confirmation_for_operation_dynamic` all import; `config.is_auto_mode` → absent; `config.META_TOOLS` → absent |
| `uv build` | **Successfully built** `dct_mcp_server-2026.0.2.0rc0.tar.gz` + `…-py3-none-any.whl` |

## Output excerpts

```
=== ruff check (lint) ===
All checks passed!

=== import smoke test ===
imports OK
config has is_auto_mode: False
config has META_TOOLS: False

=== uv build ===
Successfully built dist/dct_mcp_server-2026.0.2.0rc0.tar.gz
Successfully built dist/dct_mcp_server-2026.0.2.0rc0-py3-none-any.whl
```

## Action taken

- One follow-up was required: removing the `META_TOOLS` constant left a stray blank line in `config/loader.py` that `ruff format --check` flagged. Ran `ruff format` on the file; re-check then reported all 42 files formatted. No other fixes needed.

Build is green. Proceeding to unit tests.

## Unit tests

New test module: `tests/test_remove_auto_mode.py` — 13 tests mapped to the ticket ACs.

### Command

```bash
# New module
uv run pytest tests/test_remove_auto_mode.py -q
# Full suite + coverage (CI: pytest --cov=src/dct_mcp_server --cov-fail-under=4)
uv run --extra dev pytest --cov=src/dct_mcp_server -q
```

### Results

| Run | Result |
|---|---|
| `tests/test_remove_auto_mode.py` | **13 passed** |
| Full suite (`--extra dev`) | **66 passed** |
| Coverage | **8% total** — above the CI floor of 4% (`--cov-fail-under=4`) |

```
=== tests/test_remove_auto_mode.py ===
13 passed, 1 warning in 0.74s

=== full suite (--extra dev) ===
66 passed in 1.85s
TOTAL  5802  5356  8%
```

### Coverage of the change (mapped to ACs)

- **AC-1** — `DCT_TOOLSET=auto` raises `ValueError`; `auto` absent from the valid-values list.
- **AC-2** — default toolset is `dynamic`; `is_auto_mode`/`META_TOOLS` removed from `config`/`loader`; the auto meta-tools (`register_meta_tools`, `enable_toolset`, `disable_toolset`, `execute_action`, `list_available_toolsets`, `get_toolset_tools`, `check_operation_confirmation`, `initialize_tool_inventory`) and `register_meta_tools_only` are gone.
- **AC-3** — `get_modules_for_toolset("self_service")` still resolves; personas still in `get_available_toolsets()`.
- **AC-4** — `resolve_confirmation` returns the rule shape; `get_confirmation_for_operation_dynamic("DELETE", …)` → `manual`.
- **Retained helpers** — `find_endpoint`/`get_spec_chunk` importable from `tools.core`; `get_spec_chunk` resolves a `$ref` against a stub spec; `find_endpoint` degrades gracefully with no spec.

### Note on the environment

A plain `uv run pytest` (without the `dev` extra) reports 8 failures in `tests/test_client_retry.py` because `pytest-asyncio` is not loaded in that invocation (`Unknown config option: asyncio_mode`). Running with `--extra dev` (matching CI) loads the plugin and all 66 tests pass. The failures are an environment artifact, not a regression from this change.

Tests pass. Proceeding to commit.
