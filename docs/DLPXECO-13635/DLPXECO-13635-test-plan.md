# Test Plan: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Derived from**: `docs/DLPXECO-13635/DLPXECO-13635-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

Automated regression using `pytest` + `pytest-asyncio`; test runner = `pytest tests/ -v --cov=src/dct_mcp_server --cov-fail-under=4`. Unit tests for the logging fix live in `tests/core/test_logging.py`. Docker smoke tests are manual (no Docker daemon in CI for this ticket per NG2). See `.claude/test/testing.md` Track 2 for full setup.

## Environment / Landscape

- Landscape: local development machine with Docker 20.10+ installed (manual smoke tests) and Python 3.11+ (automated unit tests)
- Service under test: `dct-mcp-server` package (unit tests mock `__file__`; Docker tests use the built image)
- No VMs required — automated tests are pure unit tests with mocked filesystem paths; manual Docker tests run against `localhost` with a dummy `DCT_API_KEY`

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Minimum supported version; matches Docker base image | Yes |
| Python 3.12 | Tested in CI matrix | Yes |
| Docker 20.10+ (Linux/arm64 and amd64) | Required for container smoke tests | Yes (manual) |
| Docker Buildx multi-arch | Optional extension for multi-arch validation | No (smoke-only) |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | `_get_project_root()` returns `Path.cwd()` when `__file__` contains `site-packages` | FR-001 | Python 3.11, 3.12 | Return value equals `Path.cwd()` (primary guard triggered); no exception raised |
| S2 | `_get_project_root()` returns repo root when `__file__` is a dev-clone path (no `site-packages`) | FR-001 | Python 3.11, 3.12 | Return value equals the directory four levels above `logging.py`; `site-packages` guard does not trigger |
| S3 | `_get_project_root()` returns repo root for an editable install (`pip install -e .`) path | FR-001 | Python 3.11, 3.12 | `__file__` resolves to source tree (no `site-packages`); return value equals repo root |
| S4 | `_get_project_root()` returns `Path.cwd()` when `__file__` contains `site-packages` and the candidate path is also writable (primary guard takes precedence over secondary) | FR-001 | Python 3.11, 3.12 | Primary guard fires even when `os.access(candidate, os.W_OK)` would return True |
| S5 | `_setup_global_handlers` continues without file logging when log directory creation raises `PermissionError` | FR-001 | Python 3.11, 3.12 | Server does not crash; warning message `"Warning: Cannot create log directory"` is emitted to stderr; `TimedRotatingFileHandler` is not added |
| S6 | `docker build -t dct-mcp-server .` completes without errors from the project root | FR-002 | Docker 20.10+ (amd64) | Exit code 0; image `dct-mcp-server:latest` appears in `docker image ls` |
| S7 | Container runs as non-root user `mcpuser` (UID 1000) | FR-002 | Docker 20.10+ | `docker run --rm dct-mcp-server id` returns `uid=1000(mcpuser)` |
| S8 | Server starts without Python traceback inside Docker (logging path fix validated end-to-end) | FR-002, FR-001 | Docker 20.10+ | `docker run --rm -i -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost dct-mcp-server` exits with MCP handshake or connection-refused output; no traceback from logging setup |
| S9 | Log file is written to the mounted host volume | FR-002, FR-001 | Docker 20.10+ | `docker run --rm -i -v ./logs:/app/logs -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost dct-mcp-server` writes `./logs/dct_mcp_server.log` on the host |
| S10 | `.env` is not present in any Docker image layer | FR-003 | Docker 20.10+ | `docker run --rm dct-mcp-server env \| grep DCT_API_KEY` returns empty; no secret baked in |
| S11 | Build context excludes `docs/`, `.claude/`, `.git/` directories | FR-003 | Docker 20.10+ | `docker run --rm dct-mcp-server find /app -maxdepth 2 -type d` does not list `docs`, `.claude`, or `.git` |
| S12 | `docker compose up` starts with valid `.env` file and creates host log file | FR-004 | Docker 20.10+ | Exit code 0; `./logs/dct_mcp_server.log` created on host after startup |
| S13 | `docker compose up` fails non-zero when `.env` file is absent | FR-004 | Docker 20.10+ | Exit code non-zero; stderr contains `env file .env not found` |
| S14 | `## Running with Docker` section appears in README Table of Contents with a working anchor | FR-005 | N/A (doc check) | Markdown `[Running with Docker](#running-with-docker)` link is present in ToC; section anchor resolves on GitHub |
| S15 | All `docker run` examples in README include `--rm -i` and mandatory env vars | FR-005 | N/A (doc check) | Each example block contains `--rm`, `-i`, `-e DCT_API_KEY=`, and `-e DCT_BASE_URL=` |
| S16 | Existing pytest suite passes after the logging fix (regression guard) | FR-001 | Python 3.11, 3.12 | `pytest --cov=src/dct_mcp_server --cov-fail-under=4` exits 0; no previously passing test now fails |

## Out of Scope

- Docker Hub image publishing (Non-Goal NG1 — tracked in a separate PPM ticket)
- CI pipeline Docker build job (Non-Goal NG2 — `ci.yml` is not extended in this ticket)
- Kubernetes / Helm deployment testing (Non-Goal NG3)
- Multi-stage Dockerfile size optimisation (Non-Goal NG4)
- Container signing / SBOM validation (Non-Goal NG5)
- Windows Container (LTSC) variants (Non-Goal NG6)
- Load / performance testing of the containerised server (no SLA requirement in this ticket)

## Test Data Requirements

- Unit tests (S1–S5, S16): no external data; `unittest.mock.patch` is used to override `__file__` to controlled path strings
- Docker smoke tests (S6–S13): a machine with Docker 20.10+ installed; a dummy `DCT_API_KEY=test` and `DCT_BASE_URL=https://localhost` (connection failures are expected and acceptable)
- README doc checks (S14–S15): visual inspection of rendered Markdown on GitHub or `grip`/`markdown-preview` locally

## Exit Criteria

- All Required scenarios (S1–S16) PASS on all "Required = Yes" versions
- Smoke suite (existing `pytest tests/` excluding new test file) PASSes — `pytest --cov=src/dct_mcp_server --cov-fail-under=4` exits 0
- No scenario marked SKIPPED without a documented reason
- Docker smoke tests (S6–S13) confirmed manually on at least one platform (amd64 or arm64)

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-13635.spec.* (test-generation phase)
     - Each FR in docs/DLPXECO-13635/DLPXECO-13635-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/DLPXECO-13635/DLPXECO-13635-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
