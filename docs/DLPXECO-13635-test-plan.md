# Test Plan: DLPXECO-13635 — Docker Support

**Spec**: `docs/DLPXECO-13635-functional.md`
**Design**: `docs/DLPXECO-13635-design.md`

This project has no automated test suite — testing is via shell verification + MCP-client smoke tests, per `.claude/rules/testing.md`. The build phase produces `docs/DLPXECO-13635-test-evidence.md` recording the actual outputs.

## Scenarios

### S1: Build verification (FR-001, FR-002, FR-004)

| ID  | Step | Expected |
|-----|------|----------|
| S1.1 | `docker build -t dct-mcp-server:test .` (clean clone) | exit 0; image tagged |
| S1.2 | `docker save dct-mcp-server:test \| gzip \| wc -c` | < 262144000 (250 MB compressed) |
| S1.3 | `docker run --rm --entrypoint id dct-mcp-server:test` | `uid=1000(app) gid=1000(app)` |
| S1.4 | `docker run --rm --entrypoint sh dct-mcp-server:test -c 'ls -A /app'` | shows `.venv`, `src`, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE.md`, `logs`; **does not** show `.git`, `.claude`, `docs`, `CLAUDE.md`, `start_mcp_server_*.sh` |
| S1.5 | `docker history --no-trunc dct-mcp-server:test \| grep -iE 'apk1\|password\|secret' \| grep -v 'DCT_'` | empty |
| S1.6 | `docker image inspect dct-mcp-server:test --format '{{.Config.Labels}}'` | non-empty `org.opencontainers.image.title`, `source` |
| S1.7 | `docker image inspect dct-mcp-server:test --format '{{.Config.User}}'` | `app` |

### S2: Runtime smoke (FR-001 AC-3, EC-2)

| ID  | Step | Expected |
|-----|------|----------|
| S2.1 | `docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://example.invalid dct-mcp-server:test < /dev/null` | starts, prints config / startup logs to stderr, hits EOF on stdin, exits cleanly. No permission errors, no Python tracebacks unrelated to DCT connectivity. |
| S2.2 | `docker run --rm dct-mcp-server:test` (no `-i`) | exits quickly without serving any MCP traffic — documented pitfall, not a test failure if exit code is non-zero. |
| S2.3 | `docker run --rm -i dct-mcp-server:test < /dev/null` (no `DCT_API_KEY`) | exits with `print_config_help()` text on stderr, exit code 1. |

### S3: Logs persistence (FR-005, SC4, EC-3)

| ID  | Step | Expected |
|-----|------|----------|
| S3.1 | Host: `mkdir -p /tmp/dct-host-logs && sudo chown 1000:1000 /tmp/dct-host-logs`; then `docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://example.invalid -v /tmp/dct-host-logs:/app/logs dct-mcp-server:test < /dev/null` | After exit, `/tmp/dct-host-logs/dct_mcp_server.log` exists, non-empty, contains `Starting MCP server with stdio transport...` (or earlier setup log lines). |
| S3.2 | Same as S3.1 but with `-e DCT_LOG_DIR=/var/log/dct-mcp -v /tmp/dct-host-logs:/var/log/dct-mcp` | logs land in `/tmp/dct-host-logs/dct_mcp_server.log` (mounted to `/var/log/dct-mcp` inside the container). |
| S3.3 | Host directory not chowned to UID 1000: `mkdir -p /tmp/dct-host-logs-bad && chmod 700 /tmp/dct-host-logs-bad`; then run as S3.1 | Server prints warning to stderr (`Warning: Failed to create global log file …`) and continues with console-only logging — no traceback. |

### S4: `DCT_LOG_DIR` host behaviour (FR-005 AC-1..AC-4)

| ID  | Step | Expected |
|-----|------|----------|
| S4.1 | Host (no Docker): `DCT_LOG_DIR=/tmp/dct-host-test-logs ./start_mcp_server_uv.sh` (Ctrl-C after a few seconds). | `/tmp/dct-host-test-logs/dct_mcp_server.log` exists, non-empty. |
| S4.2 | Host: unset `DCT_LOG_DIR`; rm `<repo>/logs/dct_mcp_server.log`; `./start_mcp_server_uv.sh` (Ctrl-C). | `<repo>/logs/dct_mcp_server.log` re-created (regression check). |
| S4.3 | Host: `DCT_LOG_DIR=""` (empty string); same as S4.2 | Same default behaviour as S4.2. |
| S4.4 | Host: `DCT_LOG_DIR=/proc/forbidden ./start_mcp_server_uv.sh` (Ctrl-C). | Warning to stderr, server continues, no traceback. |

### S5: README accuracy (FR-003)

| ID  | Step | Expected |
|-----|------|----------|
| S5.1 | A reader with only Docker installed (no Python, no `uv`) follows the `## Docker` section in README.md top to bottom. | All commands run as written; reader connects an MCP client to the container successfully. |
| S5.2 | `git diff origin/main -- README.md \| grep '^-' \| grep -v '^---'` | empty — no existing lines removed. |
| S5.3 | `grep -c '^## Docker$' README.md` | 1 |
| S5.4 | `grep -c '^- \[Docker\](#docker)$' README.md` | 1 |

### S6: Multi-arch build (best-effort, vision SC1)

| ID  | Step | Expected |
|-----|------|----------|
| S6.1 | `docker buildx create --use --name dlpxeco-13635-builder` then `docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server:test-multi .` | Build completes for both platforms (no `--push` in this scenario; `--load` is single-arch only, so this is a build-only check). |
| S6.2 | If S6.1 fails on `linux/arm64` for a transitive dep, mark as known-best-effort and document in test-evidence. | Documented; not a blocker for vision SC1 (which says "primary supported arch is `linux/amd64`"). |

### S7: Live MCP client smoke (SC3)

| ID  | Step | Expected |
|-----|------|----------|
| S7.1 | Configure Claude Desktop per the new README JSON example with real `DCT_API_KEY` and `DCT_BASE_URL`. | Claude Desktop launches the container; tool list reflects the configured `DCT_TOOLSET` (default `self_service`); a read-only call (`vdb_tool(action="search")`) returns DCT data. |
| S7.2 | Repeat S7.1 with `DCT_TOOLSET=auto`. | Container exposes the 5 meta-tools; `enable_toolset` works. |

### S8: Existing host flows unchanged (QR-3)

| ID  | Step | Expected |
|-----|------|----------|
| S8.1 | `uvx --from <local-path> dct-mcp-server` with valid env vars. | Server starts as before; logs go to `<repo>/logs/dct_mcp_server.log` (or to `DCT_LOG_DIR` if set). |
| S8.2 | `pip install -e .` then `dct-mcp-server` with valid env vars. | Server starts as before. |
| S8.3 | `./start_mcp_server_uv.sh` with valid env vars. | Server starts as before. |

## Coverage map

| FR | Scenarios |
|----|-----------|
| FR-001 | S1.1, S1.3, S2.1, S2.3 |
| FR-002 | S1.4 |
| FR-003 | S5.1, S5.2, S5.3, S5.4 |
| FR-004 | S1.3, S1.5, S1.6, S1.7 |
| FR-005 | S3.1, S3.2, S3.3, S4.1, S4.2, S4.3, S4.4 |
| QR-1 | S1.3 |
| QR-2 | S1.5 |
| QR-3 | S8.1, S8.2, S8.3, regression diff in build phase |
| QR-4 | S4.2, S4.3 |
| QR-6 | S1.2 |
| QR-7 | regression diff in build phase |
| QR-9 | S5.2 |

## Versions / Environment

- Docker Engine: 29.x (developer host: 29.1.1; works on 20.10+).
- Docker Buildx: 0.32+ (developer host has 0.32.1) — only needed for S6.
- Python on host (for S4): 3.11+ as installed by `start_mcp_server_uv.sh`.
- DCT instance: a live tenant accessible from the developer host for S7.

## Out-of-scope tests (deferred)

- Image vulnerability scan (Trivy / Grype) — recommended follow-up; not blocking for DLPXECO-13635.
- Container resource benchmarks — unchanged from host (stdio transport has no throughput characteristics affected by containerisation).
- Registry push / pull — vision NG2.
