# DLPXECO-13635 — Docker Support: Test Plan

> **Source documents**:
> - Vision: [DLPXECO-13635-vision.md](DLPXECO-13635-vision.md)
> - Functional spec: [DLPXECO-13635-functional.md](DLPXECO-13635-functional.md)
> - Design: [DLPXECO-13635-design.md](DLPXECO-13635-design.md) (canonical test matrix in §6)
> **Purpose**: condensed, executable test plan for the `test` phase. Mirrors design §6.

---

## 1. Project testing convention

Per `.claude/rules/testing.md`, this repository has **no automated test suite**. Verification is split between:

- **Build-time / introspection** checks (`docker build`, `docker history`, `docker inspect`, `ls` inside the image). Implementer runs these at the end of the `implement` phase and re-runs them in `validate`.
- **Runtime** checks against a live DCT instance through a real MCP client (Claude Desktop, optionally VS Code Copilot). Tester runs these in the `test` phase.

The test plan therefore has no `pytest`, `unittest`, or framework dependencies. Each test is a deterministic shell command or a manual MCP-client interaction with a documented expected outcome.

---

## 2. Versions to cover

**Hosts**:
- macOS (Apple Silicon, Docker Desktop with WSL2-equivalent Linux VM) — primary dev surface.
- Linux (Ubuntu 22.04+ or any modern x86_64 distro with Docker Engine).
- Windows 11 with Docker Desktop + WSL2 backend (Linux containers mode).

**Container platform**:
- `linux/amd64` only (per vision §3 / functional AC-3.1). On Apple Silicon hosts this runs via Rosetta emulation through Docker Desktop — that's the supported path for v1.

**MCP clients**:
- Claude Desktop (primary).
- VS Code Copilot (smoke-test only — verifies stdio over Docker works on a different MCP implementation; covers R1 — Windows stdio risk).

**Toolsets** (from `.claude/rules/testing/`):
- `self_service` — primary happy-path coverage (smallest, default).
- `continuous_data_admin` — large-toolset regression (22 tools) to catch import / packaging gaps.
- `auto` — dynamic-toolset coverage to confirm Docker doesn't break runtime tool switching.

**DCT version**: whatever the tester has access to. The test phase records the exact version in `docs/DLPXECO-13635-test-evidence.md`.

---

## 3. Test categories

| ID prefix | Phase | Category |
|-----------|-------|----------|
| **T-BLD-*** | `implement` (then `validate`) | Build-time and Dockerfile lint |
| **T-IMG-*** | `implement` (then `validate`) | Image introspection (no live DCT needed) |
| **T-RUN-*** | `test` | Runtime against a live DCT through an MCP client |
| **T-DOC-*** | `implement` + `validate` | README and rules-file checks |

---

## 4. Test scenarios

### 4.1 T-BLD — Build-time

| ID | Scenario | Command | Expected | FR/AC |
|----|----------|---------|----------|-------|
| T-BLD-1 | Clean build from scratch | `docker build --no-cache --pull -t dct-mcp-server:dev .` | Exit 0; build context line ≤ 5 MB | FR-1 / AC-1.1, FR-7 / AC-7.1..7.4 |
| T-BLD-2 | Build context size | Read first build line | "Sending build context to Docker daemon" reports < 5 MB | AC-5.3 |
| T-BLD-3 | Compressed image size | `docker save dct-mcp-server:dev \| gzip -c \| wc -c` | ≤ 250 MB (262144000 bytes) | AC-1.9 |
| T-BLD-4 | No build deps in runtime layers | `docker history --no-trunc dct-mcp-server:dev` | No `gcc` / `build-essential` in layers added after the `FROM ... AS runtime` line; no `/var/lib/apt/lists` content; no `.cache/pip` entries | AC-6.4 / AC-6.5 / AC-6.6 |
| T-BLD-5 | OCI labels present | `docker inspect dct-mcp-server:dev \| jq '.[0].Config.Labels'` | Includes `org.opencontainers.image.source`, `.title`, `.licenses`, `.version` | AC-6.8 |
| T-BLD-6 | No HEALTHCHECK | `docker inspect dct-mcp-server:dev \| jq '.[0].Config.Healthcheck'` | `null` | AC-6.7 |
| T-BLD-7 | STOPSIGNAL = SIGTERM | `docker inspect dct-mcp-server:dev \| jq '.[0].Config.StopSignal'` | `"SIGTERM"` | AC-3.4 |
| T-BLD-8 | Cross-platform build (arm64 host → amd64 image) | On Apple Silicon: `docker build --platform=linux/amd64 -t dct-mcp-server:dev .` | Exit 0; image runs without errors via emulation | AC-3.1 |
| T-BLD-9 | Hadolint clean | `docker run --rm -i hadolint/hadolint < Dockerfile` | No error-level findings; warnings either zero or each suppressed with an inline `# hadolint ignore=...` comment | AC-8.1 |

### 4.2 T-IMG — Image introspection

| ID | Scenario | Command | Expected | FR/AC |
|----|----------|---------|----------|-------|
| T-IMG-1 | Non-root runtime user | `docker run --rm dct-mcp-server:dev id` (override CMD: `--entrypoint sh -c 'id'`) | UID=1000 GID=1000 (or `appuser`) | AC-1.7, AC-6.1, AC-6.2 |
| T-IMG-2 | No dev artefacts in image | `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls -la /app && (ls /app/.git 2>&1 \|\| true) && (ls /app/.claude 2>&1 \|\| true)'` | `/app` shows only `src/`, `docs/api-external.yaml`, `pyproject.toml`, `requirements.txt`, `logs/` (empty); `.git/`, `.claude/`, `.venv/`, `docs/DLPXECO-13635-*.md` absent | AC-1.10 |
| T-IMG-3 | Toolset config files present | `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls /app/src/dct_mcp_server/config/toolsets && ls /app/src/dct_mcp_server/config/mappings'` | All 6 toolset `.txt` files (`self_service`, `self_service_provision`, `continuous_data_admin`, `platform_admin`, `reporting_insights`, `auto`); `manual_confirmation.txt` present | AC-5.4, R8 |
| T-IMG-4 | Bundled OpenAPI spec | `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls -la /app/docs/api-external.yaml'` | File present; non-zero size | R3 mitigation |
| T-IMG-5 | No credentials in any layer | `docker history --no-trunc dct-mcp-server:dev \| grep -iE '(api[_-]?key\|password\|secret\|\.env)'` then `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'find / -name "*.env" -o -name "*api*key*" 2>/dev/null \| head'` | First grep returns nothing; second find returns nothing | AC-6.3 |
| T-IMG-6 | Loader smoke test | `docker run --rm --entrypoint python dct-mcp-server:dev -c "import dct_mcp_server.config.loader; print('ok')"` (and equivalent for `dct_mcp_server.main`) | Prints `ok`; no exception | R8, FR-2 |

### 4.3 T-RUN — Live DCT runtime

Pre-condition for all T-RUN-*: tester has a reachable DCT instance, a valid `DCT_API_KEY`, and Claude Desktop installed.

| ID | Scenario | Setup / Action | Expected | FR/AC |
|----|----------|----------------|----------|-------|
| T-RUN-1 | Server starts and accepts initialize | Configure Claude Desktop with the README-documented `docker run -i --rm ...` command for `DCT_TOOLSET=self_service`. Open a new conversation. | Claude Desktop shows the `delphix-dct` server connected; `tools/list` (implicit, reflected in available tools) includes `vdb_tool`, `vdb_group_tool`, `dsource_tool`, `snapshot_tool`, `bookmark_tool`, `job_tool`, `timeflow_tool` | AC-2.1, AC-2.2 |
| T-RUN-2 | Env vars honored, large toolset works | Same setup with `-e DCT_TOOLSET=continuous_data_admin -e DCT_LOG_LEVEL=DEBUG -v "$(pwd)/logs:/app/logs"` | Tool list reflects `continuous_data_admin` (22 tools); `logs/dct_mcp_server.log` contains DEBUG-level entries on the host | AC-2.3, AC-2.6 |
| T-RUN-3 | Live API parity | From Claude Desktop using `self_service`, run `vdb_tool(action="search")`. Then run the same call against a host-clone server (`./start_mcp_server_uv.sh`) pointed at the same DCT. | Same JSON shape, same tool count, same VDB list | AC-2.4 |
| T-RUN-4 | Auto mode end-to-end | Setup with `-e DCT_TOOLSET=auto`. Walk through `.claude/rules/testing/auto.md` steps 1, 4, 12–14, 18–19, 34–36 (subset that proves enable/disable/list_changed). | Each step matches its expected output in the auto.md spec | AC-2.5 |
| T-RUN-5 | Persistent logs | Run T-RUN-2 setup; after a Claude Desktop session, inspect host `./logs/`. | `dct_mcp_server.log` exists on host, owned by UID 1000, contains session entries | AC-2.6 |
| T-RUN-6 | Telemetry opt-in | Add `-e IS_LOCAL_TELEMETRY_ENABLED=true` to T-RUN-5 setup; run a few tool calls. | `./logs/sessions/<session_id>.log` exists on host with valid JSON entries | AC-2.7 |
| T-RUN-7 | Windows host smoke test | Repeat T-RUN-1 from Windows 11 + Docker Desktop + WSL2 + Claude Desktop, using the **PowerShell** form of `docker run` from the README. Repeat with VS Code Copilot configured for `DCT_TOOLSET=self_service`. | Server connects in both clients; at least one read action (`vdb_tool(action="search")`) succeeds. No CRLF / line-buffer errors in the log. | AC-3.1, AC-3.2, AC-3.3 |
| T-RUN-8 | Clean shutdown on `docker stop` | Start the container detached: `docker run -d -i --name dct-test -e DCT_API_KEY=... -e DCT_BASE_URL=... -v "$(pwd)/logs:/app/logs" dct-mcp-server:dev`. Then `docker stop dct-test`. | Container exits within the configured `STOPTIMEOUT` (default 10s); host log shows the lifespan-finally output (HTTP client closed, telemetry session ended). | AC-3.4 |
| T-RUN-9 | Confirmation flow over Docker stdio | From Claude Desktop using `self_service`, attempt to delete a throwaway test bookmark per `.claude/rules/testing/self_service.md` step 56. | First call returns `confirmation_required`; "yes, go ahead and confirm" executes the delete; bookmark gone from DCT | exercises confirmation system through containerized stdio |

### 4.4 T-DOC — Documentation

| ID | Scenario | Command / Action | Expected | FR/AC |
|----|----------|------------------|----------|-------|
| T-DOC-1 | Section + TOC entry | `grep -n '^### Run with Docker' README.md && grep -n '\[Run with Docker\]' README.md` | Both grep matches return non-empty results; TOC entry precedes the section | AC-4.1, AC-4.7 |
| T-DOC-2 | Section answers the 6 FR-4 questions in order | Manual review of section content vs. AC-4.2 list (prereqs → build → pull → run → optional env → MCP client wiring) | Each item present in the listed order | AC-4.2 |
| T-DOC-3 | Registry placeholder | `grep -n 'TODO(DLPXECO-13635)' README.md && grep -n '<registry-host>' README.md` | Both matches present; no real-looking registry hostname | AC-4.3, QR-6 |
| T-DOC-4 | Multi-shell examples | Manual review — each `docker run` snippet is shown for bash/zsh AND PowerShell (cmd shown when env-var quoting differs) | Both shells covered everywhere they differ | AC-4.4 |
| T-DOC-5 | Local-development warning | `grep -n 'local-development' README.md` (or equivalent phrase) inside the Docker section | Match present in Docker section | AC-4.5 |
| T-DOC-6 | No regressions to existing install paths | `git diff main..HEAD -- README.md` | Only additions in `### Run with Docker` (and TOC); no edits to existing sections | AC-4.6 |
| T-DOC-7 | LF endings on new files | `file Dockerfile .dockerignore` | "ASCII text" — no CRLF | QR-1 |
| T-DOC-8 | No trailing whitespace, terminal newline | `git diff --check` | Clean | QR-2 |
| T-DOC-9 | `.claude/rules/build-and-execution.md` updated | Manual review for a "Run with Docker" subsection mirroring existing structure | Subsection present | AC-8.3 |

---

## 5. Test evidence file

The `test` phase produces `docs/DLPXECO-13635-test-evidence.md` containing:

1. Header — Docker version, Docker Desktop version (if applicable), host OS for each T-RUN-* execution, DCT version, MCP client version(s).
2. One row per test (T-BLD-*, T-IMG-*, T-RUN-*, T-DOC-*) with columns: ID, status (PASS / FAIL / SKIP-with-reason), evidence (command output snippet, screenshot file reference, or "N/A — manual review").
3. Aggregate summary — count of PASS / FAIL / SKIP, and a one-line verdict.

---

## 6. Coverage map (FR + Quality Rule → tests)

| Item | Tests |
|------|-------|
| FR-1 (Dockerfile builds runnable image) | T-BLD-1, T-BLD-3, T-IMG-1, T-IMG-2 |
| FR-2 (parity with local-clone) | T-RUN-1, T-RUN-2, T-RUN-3, T-RUN-4, T-RUN-5, T-RUN-6, T-IMG-6 |
| FR-3 (cross-platform host) | T-BLD-8, T-RUN-7, T-RUN-8 |
| FR-4 (README) | T-DOC-1..6 |
| FR-5 (.dockerignore) | T-BLD-2, T-IMG-3 |
| FR-6 (image security) | T-IMG-1, T-IMG-5, T-BLD-4..7 |
| FR-7 (no private build deps) | T-BLD-1 (with `--no-cache --pull`) |
| FR-8 (lint, structure) | T-BLD-9, T-DOC-1, T-DOC-9 |
| QR-1 (LF) | T-DOC-7 |
| QR-2 (whitespace, terminal newline) | T-DOC-8 |
| QR-3 (no Alpine) | Dockerfile review (no `apk` directives present) |
| QR-4 (README snippets copy-paste runnable) | T-RUN-1 (uses copy-pasted command), T-DOC-4 |
| QR-5 (no new code patterns) | Verified by absence of changes to `src/dct_mcp_server/` |
| QR-6 (placeholder host fake) | T-DOC-3 |
| QR-7 (.dockerignore + .gitignore consistency for secrets/logs) | Manual review of both ignore files |

Every FR-* and QR-* maps to at least one test. No orphan tests.
