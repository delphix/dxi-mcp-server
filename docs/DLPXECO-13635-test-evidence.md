# Test Evidence: DLPXECO-13635 — Docker Support

**Captured during**: build phase, on `dlpx/pr/vinaybyrappa/dlpxeco-13635-docker-support`
**Host**: macOS Darwin 23.6.0 (arm64), Docker Engine 29.1.1 / Docker Desktop, Buildx 0.32.1
**Image tag**: `dct-mcp-server:test`
**Image digest**: `sha256:56f6b43a69f85c2dcffb869dee2ca44a6eea62f38e253dcc3ed89a0bacfbb4be`

## Build (S1)

| ID  | Result | Evidence |
|-----|--------|----------|
| S1.1 | PASS | `docker build -t dct-mcp-server:test .` → exit 0 (after fixing builder venv path mismatch — see "Build issue resolved" below). |
| S1.2 | PASS | Uncompressed: 210,223,081 bytes (≈ 200 MB). |
| S1.3 | PASS | Compressed: 62,310,791 bytes (≈ 59 MB) — well under 250 MB budget (76% headroom). |
| S1.4 (id) | PASS | `docker run --rm --entrypoint id dct-mcp-server:test` → `uid=1000(app) gid=1000(app) groups=1000(app)`. |
| S1.4 (/app contents) | PASS | `docker run --rm --entrypoint sh dct-mcp-server:test -c 'ls -A /app'` → `.venv  LICENSE.md  README.md  logs  pyproject.toml  src  uv.lock`. **Excluded items confirmed missing** (per `.dockerignore`): `.git`, `.claude`, `docs`, `CLAUDE.md`, `start_mcp_server_uv.sh`, `start_mcp_server_python.sh`, `Dockerfile`, `.dockerignore`, `.gitignore`, `.github`, `tests`. |
| S1.5 | PASS | `docker history --no-trunc dct-mcp-server:test \| grep -iE 'apk1\|password\|secret\|token' \| grep -v DCT_` → empty output (no secret values in any layer). |
| S1.6 | PASS | OCI labels present: `org.opencontainers.image.title=dct-mcp-server`, `description=Delphix DCT API MCP Server (stdio transport)`, `source=https://github.com/delphix/dxi-mcp-server`, `licenses=MIT`, `version=2026.0.1.0-preview`. |
| S1.7 | PASS | `docker image inspect … --format '{{.Config.User}}'` → `app`. |

### Build issue resolved

Initial build produced a venv with shebangs pointing at `/build/.venv/bin/python` (the builder-stage path) — exec failed in the runtime stage where the venv lives at `/app/.venv`. **Fix applied**: changed builder-stage `WORKDIR` to `/app` so venv is created at the same absolute path it lives at runtime, and updated the `COPY --from=builder` source to `/app/.venv`. After the fix, exec works and the server starts cleanly. This is documented in the Dockerfile comment near the builder `WORKDIR`.

## Runtime smoke (S2)

| ID  | Result | Evidence |
|-----|--------|----------|
| S2.1 | PASS | `docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://example.invalid dct-mcp-server:test < /dev/null` → exit 0. Server logs to stderr: tool registration ("Registered 2 tool modules"), `Starting MCP server with stdio transport...`, then `Closing DCT API client` on EOF. No tracebacks. |
| S2.2 | DEFERRED-noisy | `docker run --rm dct-mcp-server:test` (no `-i`) — documented as a pitfall, not a strict acceptance test. |
| S2.3 | PASS | `docker run --rm -i dct-mcp-server:test < /dev/null` (no `DCT_API_KEY`) → server prints `Configuration Error: DCT_API_KEY environment variable is required.` plus the full `print_config_help()` output (which includes the new `DCT_LOG_DIR` line). Exit 0 (server prints help and returns rather than throwing). |

## Logs persistence (S3)

| ID  | Result | Evidence |
|-----|--------|----------|
| S3.1 | PASS | `docker run --rm -i -v /tmp/dct-host-logs:/app/logs …` → `/tmp/dct-host-logs/dct_mcp_server.log` (4586 bytes) created on host with full startup log content. Note: on Docker Desktop for macOS, file ownership maps to host user (no host `chown` needed for this single-user dev environment). |
| S3.2 | PASS | `-e DCT_LOG_DIR=/var/log/dct-mcp -v /tmp/dct-host-logs2:/var/log/dct-mcp …` → log appears at `/tmp/dct-host-logs2/dct_mcp_server.log`. Confirms `DCT_LOG_DIR` env var override propagates correctly through the container. |
| S3.3 | PASS | `-e DCT_LOG_DIR=/proc/cant-write-here …` → stderr contains `Warning: Failed to create global log file /proc/cant-write-here/dct_mcp_server.log: [Errno 2] No such file or directory: '/proc/cant-write-here'`; server still emits `Starting MCP server with stdio transport...` and exits cleanly on EOF. **No traceback.** |

## `DCT_LOG_DIR` host behaviour (S4)

| ID  | Result | Evidence |
|-----|--------|----------|
| S4.1 | PASS | `DCT_LOG_DIR=/tmp/dct-host-logs3/srv .venv/bin/python -m dct_mcp_server.main < /dev/null` → `/tmp/dct-host-logs3/srv/dct_mcp_server.log` created. (Demonstrates `parents=True` honoured for nested paths.) |
| S4.2 | PASS | Same command without `DCT_LOG_DIR` → `<repo>/logs/dct_mcp_server.log` created (regression-protected default). |
| S4.3 | PASS | `DCT_LOG_DIR=""` → behaves identically to S4.2 (empty string treated as falsy). |
| S4.4 | PASS | `DCT_LOG_DIR=/proc/forbidden` → stderr `Warning: Failed to create global log file /proc/forbidden/dct_mcp_server.log: [Errno 30] Read-only file system: '/proc'`; server emits `Starting MCP server with stdio transport...`; no traceback; exit 0. |

## README (S5)

| ID  | Result | Evidence |
|-----|--------|----------|
| S5.1 | DEFERRED-manual | Live MCP-client smoke deferred to validation phase (requires real DCT instance). The instructions are self-contained and have been read end-to-end; commands match the actual built image. |
| S5.2 | PASS | `git diff origin/main -- README.md \| grep '^-[^-]'` → empty (zero existing lines removed). README diff is purely additive: +173 lines. |
| S5.3 | PASS | `grep -c '^## Docker$' README.md` → 1. |
| S5.4 | PASS | `grep -c '^- \[Docker\](#docker)$' README.md` → 1. |

## Multi-arch (S6)

| ID  | Result | Evidence |
|-----|--------|----------|
| S6.1 | PASS | `docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server:test-multi .` (using the `multiarch-builder` `docker-container` driver) → both architectures built without error. Buildkit produced `[linux/amd64 runtime 6/6]` and `[linux/arm64 runtime 6/6]` final stages successfully. Image stays in build cache (no `--push`/`--load`) which is the documented best-effort verification. |

## Live MCP-client smoke (S7)

DEFERRED-manual: requires a live DCT instance and a configured Claude Desktop / Cursor / VS Code Copilot client. The README JSON config blocks have been verified to match the actual built image's expectations (`docker run --rm -i …` invocation, env-var inheritance pattern). Reviewer should reproduce S7 against their own DCT tenant before approving for release.

## Existing host flows (S8)

| ID  | Result | Evidence |
|-----|--------|----------|
| S8.1 | PASS-implied | `pyproject.toml`, `uv.lock`, `start_mcp_server_uv.sh` are byte-identical to `origin/main` (verified by `git diff --stat`). The only Python change is in `core/logging.py` (additive `DCT_LOG_DIR` branch + mkdir-into-try refactor) and a one-line additive change in `config/config.py:print_config_help()`. The S4 series above demonstrates the default path is preserved. |
| S8.2 | PASS-implied | Same as S8.1 — no `pyproject.toml` change → `pip install` flow unchanged. |
| S8.3 | PASS | S4.1–S4.4 invoke the server via `python -m dct_mcp_server.main` which is the same code path `start_mcp_server_uv.sh` ends up at (`exec .venv/bin/python -m dct_mcp_server.main`). Default behaviour preserved. |

## Regression / protected-files diff

```
$ git diff --stat origin/main -- \
    pyproject.toml requirements.txt \
    start_mcp_server_uv.sh start_mcp_server_python.sh \
    start_mcp_server_windows_uv.bat start_mcp_server_windows_python.bat \
    src/dct_mcp_server/main.py \
    src/dct_mcp_server/tools/ \
    src/dct_mcp_server/dct_client/ \
    src/dct_mcp_server/toolsgenerator/ \
    src/dct_mcp_server/config/toolsets/ \
    src/dct_mcp_server/config/mappings/ \
    .github/ LICENSE.md .whitesource uv.lock
(empty output)
```

## Branch diff summary

```
$ git diff --stat origin/main
 README.md                           | 173 ++++++++++++++++++++++++++++++++++++
 src/dct_mcp_server/config/config.py |   3 +
 src/dct_mcp_server/core/logging.py  |  20 +++--
 3 files changed, 190 insertions(+), 6 deletions(-)
```

Plus untracked new files (will be added before commit): `Dockerfile` (~80 lines), `.dockerignore` (~95 lines).

## Coverage rollup (FR ↔ Evidence)

| FR     | Acceptance Criterion | Scenario | Result |
|--------|----------------------|----------|--------|
| FR-001 | AC-1 (build succeeds)        | S1.1 | PASS |
| FR-001 | AC-2 (non-root UID)          | S1.4 (id) | PASS |
| FR-001 | AC-3 (clean stdio start)     | S2.1 | PASS |
| FR-001 | AC-4 (size + user)           | S1.3, S1.7 | PASS |
| FR-002 | AC-1 (no host noise in /app) | S1.4 | PASS |
| FR-002 | AC-2 (build context lean)    | implicit (build context flowed through Dockerfile correctly; see S1) | PASS |
| FR-003 | AC-1 (TOC + heading)         | S5.3, S5.4 | PASS |
| FR-003 | AC-2 (required code blocks)  | S5.2 + manual inspection | PASS |
| FR-003 | AC-3 (Docker-only reader path) | S5.1 | DEFERRED-manual |
| FR-004 | AC-1 (UID 1000)              | S1.4 (id) | PASS |
| FR-004 | AC-2 (no secret strings)     | S1.5 | PASS |
| FR-004 | AC-3 (OCI labels)            | S1.6 | PASS |
| FR-005 | AC-1 (default unchanged)     | S4.2 | PASS |
| FR-005 | AC-2 (custom DCT_LOG_DIR)    | S3.2, S4.1 | PASS |
| FR-005 | AC-3 (graceful fallback)     | S3.3, S4.4 | PASS |
| FR-005 | AC-4 (empty string = unset)  | S4.3 | PASS |

All AC marked `PASS` or `DEFERRED-manual` (with explicit reason). No failures.

## Quality Rule checks

| Rule | Status | Evidence |
|------|--------|----------|
| QR-1 (non-root) | PASS | S1.4 (id) |
| QR-2 (no secrets) | PASS | S1.5 |
| QR-3 (host flows unchanged) | PASS | protected-files diff empty + S4 series + S8.3 |
| QR-4 (DCT_LOG_DIR backward compat) | PASS | S4.2, S4.3 (default + empty string both → default path) |
| QR-5 (all AC checked) | PASS | this rollup |
| QR-6 (image size < 250 MB) | PASS | S1.3 (59 MB compressed) |
| QR-7 (no new deps) | PASS | `pyproject.toml`, `requirements.txt`, `uv.lock` unchanged |
| QR-8 (uses get_logger) | PASS | inspection: no new `logging.getLogger` introduced; only existing `os.getenv` and `Path` calls used |
| QR-9 (README diff additive only) | PASS | S5.2 |
