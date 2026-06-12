# Test Plan: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Derived from**: `docs/DLPXECO-13635/DLPXECO-13635-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

Automated regression using `pytest` + `pytest-asyncio`, driven by Claude per `.claude/test/testing.md` Track 2. Docker-specific scenarios are tested by spawning the server via `docker run -i --rm -e ...` as the subprocess command in `StdioServerParameters` (in place of the usual launch script) and asserting MCP responses. Image build and hygiene tests use `subprocess.run(["docker", ...])` assertions in the same `pytest` file. A manual smoke-test track (Track 1) verifies the `initialize` + tool call path against a live DCT instance using both the `docker run` and `uvx` paths to confirm behavioral parity.

## Environment / Landscape

- Landscape: Local developer machine with Docker Desktop (macOS) or Docker Desktop + WSL2 (Windows)
- Docker version: 20.10+ (BuildKit enabled by default)
- Service under test: live DCT instance specified in `.claude/test/test-infra.md` via `DCT_API_KEY` / `DCT_BASE_URL`
- No new VMs required — Docker containers are the test boundary
- Precondition: `docker build -t dct-mcp-server .` must complete before test scenarios S1–S17 run (S1 itself validates the build)

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| `python:3.11-slim` (Docker image) | Minimum Python version per `pyproject.toml`; primary build target | Yes |
| `linux/amd64` | Default platform target; CI runner platform | Yes |
| `linux/arm64` (Apple Silicon local build) | Developer build platform; behavioral parity with amd64 (smoke only) | No (smoke-only) |
| Existing `uvx` / `pip install` paths | Backward compatibility — must be unaffected | Yes |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | `docker build -t dct-mcp-server .` completes without error from a clean repo | FR-001 | linux/amd64 | Exit code 0; no error lines in build output |
| S2 | Compressed image size is ≤ 500 MB | FR-001 (AC-1, SC5) | linux/amd64 | `docker save dct-mcp-server \| gzip \| wc -c` ≤ 524288000 bytes |
| S3 | Runtime user is `appuser` (non-root) | FR-001 (AC-2, SC3) | linux/amd64 | `docker run --rm dct-mcp-server id` prints `uid=1000(appuser)`; `docker inspect` Config.User = `appuser` |
| S4 | Package imports correctly inside container | FR-001 (AC-3) | linux/amd64 | `docker run --rm dct-mcp-server python -c "import dct_mcp_server.config.loader; print('ok')"` prints `ok` with exit code 0 |
| S5 | Missing `DCT_API_KEY` / `DCT_BASE_URL` produces a descriptive error (not traceback) | FR-001 (AC-4) | linux/amd64 | Container exits non-zero; stderr contains a human-readable message (not `Traceback (most recent call last)`) |
| S6 | `.git/`, `logs/`, `__pycache__/`, `.env` files are absent from the image | FR-001 (AC-5), FR-002 (AC-1) | linux/amd64 | `docker run --rm dct-mcp-server find / -name ".git" -o -name ".env" -o -name "*.pyc" 2>/dev/null \| head -5` returns empty |
| S7 | `docs/api-external.yaml` is present inside the image | FR-002 (AC-2) | linux/amd64 | `docker run --rm dct-mcp-server python -c "import importlib.resources; print('found')"` + `find /app -name "api-external.yaml"` returns a path |
| S8 | `tests/` and `evals/` are absent from the image | FR-002 (AC-3) | linux/amd64 | `docker run --rm dct-mcp-server ls /app/tests 2>&1` exits non-zero with "No such file" |
| S9 | `docker run -i --rm -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server` responds to MCP `initialize` | FR-001 (SC2), FR-004 | linux/amd64 | Piping a valid `initialize` JSON-RPC request returns an `initialize` response with `serverInfo.name = "dct-mcp-server"` and a non-empty `tools` list |
| S10 | Container `initialize` response matches `uvx` path response for same DCT instance | FR-001 (G5, SC6) | linux/amd64 | `serverInfo.name` is identical; `tools` list is non-empty in both; `vdb_tool(action="search")` returns HTTP 200 in both |
| S11 | No credentials in image layers or Config.Env | FR-001 (SC3), Quality Rule | linux/amd64 | `docker history --no-trunc dct-mcp-server \| grep -iE 'apk\|DCT_API_KEY\|DCT_BASE_URL'` returns empty; `docker inspect` Config.Env does not contain secret values |
| S12 | `.env` file bind-mounted at `/app/.env` is silently ignored | FR-001 (EC-15), Quality Rule | linux/amd64 | `docker run --rm -v $(pwd)/test.env:/app/.env -e DCT_API_KEY=override ... python -c "import os; assert os.getenv('DCT_API_KEY')=='override'"` exits 0 |
| S13 | Image `LABEL` contains `maintainer`, `version`, and `description` fields | FR-001 (step 7) | linux/amd64 | `docker inspect --format '{{json .Config.Labels}}' dct-mcp-server` returns JSON with non-empty values for all three fields |
| S14 | All `pip install` lines in Dockerfile use `-r requirements.txt`; no bare version-floating installs | FR-001, Quality Rule: Reproducible build | linux/amd64 | Static check: `grep -E "^RUN pip install" Dockerfile` lines all contain `-r requirements.txt` or `pip install .`; no `pip install <package>` without a pin |
| S15 | README contains "Run with Docker" section with bash, PowerShell, and cmd.exe `docker run` commands | FR-003 (AC-1) | N/A (doc) | `grep -c "PowerShell\|cmd.exe\|bash" README.md` ≥ 3; section heading present in ToC |
| S16 | README MCP client config snippets use `-i` flag and do not use `-t`; `--init` is documented | FR-004 (AC-1, AC-2) | N/A (doc) | `grep "docker run" README.md \| grep -v " -i "` returns empty; `grep "\-\-init" README.md` returns at least one match |
| S17 | Registry placeholder URL is present and annotated as TODO/pending | FR-005 (AC-1, AC-2, AC-3) | N/A (doc) | `grep "registry-host" README.md` returns a match; adjacent text contains "pending" or "TODO" or equivalent callout |
| S18 | `docker run` without `-i` flag exits immediately without MCP response | FR-004 (EC-1) | linux/amd64 | Container started without `-i` exits with code 0 and no MCP `initialize` response on stdout |
| S19 | Existing pytest tests in `tests/` all pass with no changes to `src/` | FR-001 (SC6), Quality Rule: API backward compatibility | Existing test suite | `pytest tests/ -v` exits 0; `git diff src/` is empty |

## Out of Scope

- Kubernetes/Helm packaging (NG1 — tracked separately)
- HTTP/SSE transport testing (NG2 — server uses stdio only)
- Multi-arch image publishing and `linux/arm64` full test coverage (NG3 — follow-up ticket)
- CI/CD pipeline for automated registry push (NG4 — follow-up ticket)
- Native Windows containers / Server Core (NG5)
- Changes to existing `start_mcp_server_*.sh` / `.bat` scripts (NG6)
- docker-compose production configuration testing (NG7)
- Load testing or concurrency testing of the container (Performance Consideration — not an MCP concern)
- SSL with custom CA bundle (EC-11 — documented as workaround in README; no code change)

## Test Data Requirements

- A built Docker image tagged `dct-mcp-server` (prerequisite for S1–S14, S18; S1 itself is the build test)
- `DCT_API_KEY` and `DCT_BASE_URL` present in `.claude/settings.local.json` under `mcpServers.dct.env` (required for S9, S10, S12; see `.claude/test/test-infra.md`)
- A small `test.env` file with a single `DCT_API_KEY=should-be-ignored` line for S12 (created by the test setup fixture)
- No seeded DCT data required — S9 and S10 only verify `initialize` and `vdb_tool(action="search")` availability, not specific VDB records

## Exit Criteria

- All Required scenarios (S1–S19) PASS on all Required versions
- Smoke suite (existing tests in `tests/` excluding `DLPXECO-13635`) PASSes
- No scenario marked SKIPPED without a documented reason
- `git diff src/` is empty — zero changes to existing MCP server source

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-13635-test-suite.py (test-generation phase)
     - Each FR in docs/DLPXECO-13635/DLPXECO-13635-functional.md → at least one scenario here:
       FR-001 → S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13, S14, S18, S19
       FR-002 → S6, S7, S8, S14
       FR-003 → S15, S17
       FR-004 → S9, S16, S18
       FR-005 → S17
     - Versions column → subset of docs/DLPXECO-13635/DLPXECO-13635-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
