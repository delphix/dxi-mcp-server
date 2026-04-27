# Functional Specification: DLPXECO-13635

**Jira**: DLPXECO-13635 — Support for Hosting MCP Server in docker container
**Generated from**: Acceptance criteria in DLPXECO-13635 + vision doc (`DLPXECO-13635-vision.md`).

---

## FR-001: Provide a Dockerfile that packages and runs the MCP server

### Description
Add a top-level `Dockerfile` that builds a runnable image of `dct-mcp-server`, runs as a non-root user, uses a Python 3.11 slim base, installs dependencies from `pyproject.toml` / `uv.lock`, and starts the server via the existing `dct-mcp-server` console script over stdio. Maps to vision G1 and G3.

### Input
- Build context: the repository root, after `.dockerignore` filtering (FR-002).
- No build-time secrets are accepted; `DCT_API_KEY` and `DCT_BASE_URL` are passed at runtime only.
- Optional build args (none required by default; reserved for future use).

### Processing
1. **Builder stage**: `FROM python:3.11-slim AS builder`. Install `uv` (pinned version) via `pip install --no-cache-dir uv==<pinned>`; copy only the files needed to resolve and build (`pyproject.toml`, `uv.lock`, `README.md`, `LICENSE.md`, and the `src/` tree); run `uv sync --frozen --no-dev` to materialise a `.venv` containing all runtime dependencies and the project itself in editable-or-installed form.
2. **Runtime stage**: `FROM python:3.11-slim`. Set `WORKDIR /app`. Create a non-root user (`app`, UID 1000) and group; create `/app/logs` owned by `app:app` with mode `0755`.
3. Copy the materialised `.venv` from the builder stage to `/app/.venv` and copy `src/`, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE.md` into `/app`.
4. Set `PATH=/app/.venv/bin:$PATH` so that `dct-mcp-server` and `python` resolve to the venv.
5. Set `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DCT_LOG_DIR=/app/logs` so logs land in a known writable location by default and stdout/stderr are not buffered (important for stdio transport).
6. Document — but do not require — the standard runtime env vars via `# ENV …` comments: `DCT_API_KEY`, `DCT_BASE_URL`, `DCT_TOOLSET`, `DCT_VERIFY_SSL`, `DCT_LOG_LEVEL`, `DCT_TIMEOUT`, `DCT_MAX_RETRIES`, `DCT_LOG_DIR`, `IS_LOCAL_TELEMETRY_ENABLED`.
7. `USER app`. `ENTRYPOINT ["dct-mcp-server"]`. No `CMD` — server takes no positional args.
8. Do **not** declare `EXPOSE` for any port — transport is stdio, not network.

### Output
- A buildable, runnable image such that `docker build -t dct-mcp-server .` succeeds from a clean clone.
- Image layers contain `/app/.venv`, `/app/src/dct_mcp_server/...`, `/app/pyproject.toml`, `/app/uv.lock`, `/app/README.md`, `/app/LICENSE.md`, and an empty writable `/app/logs/`.
- Default runtime command: `dct-mcp-server` running as UID 1000.
- Failure modes:
  - Missing required env vars (`DCT_API_KEY`) → server exits 1 with the config-help message printed to stderr (existing behaviour, unchanged).
  - Non-writable `DCT_LOG_DIR` → server logs the warning to stderr and continues with console-only logging (FR-005 ERR-1).

### Acceptance Criteria
- [ ] **AC-1**: Given a clean checkout of the branch, when `docker build -t dct-mcp-server:test .` is run from the repo root, then it completes with exit 0 and produces an image tag `dct-mcp-server:test`.
- [ ] **AC-2**: Given the built image, when `docker run --rm --entrypoint id dct-mcp-server:test` is run, then the output shows `uid=1000` (non-zero).
- [ ] **AC-3**: Given the built image, when `docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://example.invalid dct-mcp-server:test < /dev/null` is run, then the server starts and either logs `Starting MCP server with stdio transport...` to stderr before exiting on EOF, or fails fast with a clear DCT connectivity error — but not with a Python traceback or `permission denied` on the logs directory.
- [ ] **AC-4**: Given the image, when `docker image inspect dct-mcp-server:test` is checked, the resulting image's compressed size is < 250 MB and the configured user is `app` (UID 1000).

---

## FR-002: Provide a `.dockerignore` to exclude build noise and host artefacts

### Description
Add a `.dockerignore` at the repo root that excludes everything not needed for the runtime image — local virtual envs, caches, logs, IDE files, OS artefacts, the `.git` directory, the `docs/` directory, and any local-only files. Maps to vision G3 and SC6.

### Input
- The repository tree as it exists in the worktree at build time.

### Processing
1. Exclude Python build outputs: `__pycache__/`, `*.py[oc]`, `build/`, `dist/`, `wheels/`, `*.egg-info`.
2. Exclude virtualenvs: `.venv/`, `venv/`, `env/`.
3. Exclude logs: `logs/`, `*.log`, `mcp_server_setup_logfile.txt`.
4. Exclude env / secrets files: `.env`, `.env.*`, `.env.local`, `.env.*.local`.
5. Exclude IDE / editor / OS junk: `.vscode/`, `.idea/`, `*.swp`, `*.swo`, `*~`, `.DS_Store`, `Thumbs.db`.
6. Exclude VCS metadata and CI: `.git/`, `.github/`, `.whitesource`, `.gitignore`.
7. Exclude documentation, tests, and the docs we just generated: `docs/`, `tests/`, `test/`, `*.md` (with `!README.md` and `!LICENSE.md` re-included so the image still ships those — they're referenced from `pyproject.toml` `readme` and inform the help/license display).
8. Exclude Claude / project-specific: `.claude/`, `CLAUDE.md`.
9. Exclude shell / batch startup scripts that are dev-host-only: `start_mcp_server_*.sh`, `start_mcp_server_*.bat`.
10. Exclude `.worktrees/`, `worktrees/` (in case the user adopts the same worktree convention later).

### Output
- A `.dockerignore` file at repo root containing all exclusion rules above.
- After `docker build`, `docker image history dct-mcp-server:test --no-trunc` shows no `__pycache__`, `.git`, `logs/`, or `docs/` entries in any layer.

### Acceptance Criteria
- [ ] **AC-1**: Given the `.dockerignore` and a built image, when running `docker run --rm --entrypoint sh dct-mcp-server:test -c 'ls -la /app'`, the output does not contain `.git`, `.venv` from the host (only `/app/.venv` from the builder stage), `__pycache__`, `logs/` with files, `docs/`, `.claude/`, or `start_mcp_server_*.sh`.
- [ ] **AC-2**: Given a host clone where the user has run `./start_mcp_server_uv.sh` (which creates a host-side `.venv/` and `logs/`), when `docker build` is run, then build context size is significantly smaller than the host clone size — verified by checking `docker build`'s "Sending build context to Docker daemon" output is under ~15 MB.

---

## FR-003: Document Docker usage in README.md

### Description
Add a "Docker" section to `README.md` (and a corresponding TOC entry) that explains how to build the image, run the container with required and optional env vars, mount logs, connect each supported MCP client, and troubleshoot common pitfalls. Maps to vision G2.

### Input
- The current `README.md` structure (TOC at line 9–22, "Advanced Installation" at line 304, "Quick Start" at line 38).
- The existing MCP-client config blocks (Claude Desktop, Cursor, VS Code) used as the model for the new Docker config blocks.

### Processing
1. Add a new top-level `## Docker` section between "Advanced Installation" and "Toolsets" (after line ~426 in the current README).
2. Add a TOC entry `- [Docker](#docker)` to the Table of Contents block.
3. The `## Docker` section contains the following subsections, in order:
   - **Prerequisites**: Docker Engine 20.10+ (or Docker Desktop), Docker Buildx for multi-arch (optional), required env vars.
   - **Build**: a `docker build -t dct-mcp-server .` command, plus a multi-arch buildx alternative for `linux/amd64,linux/arm64`.
   - **Run (stdio mode for MCP clients)**: explanation that the container runs over stdio and is invoked **by the MCP client**, not run as a daemon. Show the canonical `docker run --rm -i -e DCT_API_KEY=… …` invocation.
   - **Environment variables**: a one-line cross-link back to the existing `## Environment Variables` section, plus an explicit table noting that `DCT_LOG_DIR` defaults to `/app/logs` inside the container.
   - **Persisting logs**: `-v $(pwd)/logs:/app/logs` example, plus alternate `-e DCT_LOG_DIR=/var/log/dct-mcp -v /var/log/dct-mcp:/var/log/dct-mcp`.
   - **MCP client configuration (Docker)**: a JSON block per supported client (Claude Desktop, Cursor, VS Code) showing `"command": "docker"` and `"args": ["run", "--rm", "-i", "-e", "DCT_API_KEY=…", "-e", "DCT_BASE_URL=…", "dct-mcp-server"]`.
   - **Common pitfalls**: stdin not attached → server appears to exit; logs not persisting → mount `/app/logs`; non-root permissions on a mounted host directory → ensure host directory is writable by UID 1000 or use `--user $(id -u):$(id -g)`.
   - **Multi-arch (optional)**: brief `docker buildx create --use && docker buildx build --platform linux/amd64,linux/arm64 …` block, marked as "best-effort, primary arch is `linux/amd64`".
4. Do not modify any other README content (no edits to Quick Start, Environment Variables, Toolsets, Available Tools, etc., except the one TOC line).

### Output
- An updated `README.md` with one new TOC entry and one new `## Docker` section, ~120–180 lines net additional content.
- All other lines in the README are byte-identical to `main` (verified in validation phase via `git diff origin/main -- README.md` showing only additions in those two regions).

### Acceptance Criteria
- [ ] **AC-1**: Given the updated `README.md`, the TOC contains a `- [Docker](#docker)` entry, and exactly one `## Docker` section exists at heading level 2.
- [ ] **AC-2**: The `## Docker` section contains, at minimum, fenced code blocks for: `docker build`, `docker run … -i …`, a Claude Desktop JSON config using `"command": "docker"`, and a logs-mount example (`-v …:/app/logs`).
- [ ] **AC-3**: A reader who has only Docker installed (no Python, no `uv`) and a valid DCT API key can follow the Docker section top to bottom and reach a connected MCP client without consulting any other section.

---

## FR-004: Run the container as a non-root user with a minimal, secure footprint

### Description
The image must use `python:3.11-slim` (or equivalent) as its base, run as a non-root UID at runtime, and avoid known-bad Docker patterns (root user, build-time secrets, unpinned `:latest` base, unnecessary system packages). Maps to vision G3 and SC5/SC6.

### Input
- The `Dockerfile` from FR-001.

### Processing
1. Pin base image: `FROM python:3.11-slim` with an explicit Debian release tag if available (e.g. `python:3.11-slim-bookworm`).
2. Install only the minimum apt packages needed to install `uv` and run `uv sync` (none expected for `python:3.11-slim` since `uv` ships pre-built wheels). If any apt install is needed, follow it with `apt-get clean && rm -rf /var/lib/apt/lists/*` in the same `RUN` to avoid layer bloat.
3. Add `RUN groupadd -g 1000 app && useradd -u 1000 -g 1000 -m -s /bin/false app` and ensure `/app` and `/app/logs` are owned by `app:app`.
4. Use `USER app` before `ENTRYPOINT`. The entrypoint must not require root.
5. Do not set `ENV DCT_API_KEY=…` or any other secret. Do not `COPY` any `.env` files.
6. Multi-stage build: builder stage may run as root for `uv sync`; runtime stage runs as `app`.
7. Image labels: include `org.opencontainers.image.title`, `description`, `source` (URL), `licenses`, `version` (read from `pyproject.toml` if practical, else hard-coded matching the package version).

### Output
- A runtime stage that drops privileges to UID 1000 before `ENTRYPOINT`.
- No secrets in any layer; `docker history` shows no `ENV` or `ARG` of secret values.
- OCI labels present and machine-readable.

### Acceptance Criteria
- [ ] **AC-1**: Given the built image, when `docker run --rm --entrypoint id dct-mcp-server:test` is run, output contains `uid=1000(app)` and `gid=1000(app)`.
- [ ] **AC-2**: Given the built image, `docker history --no-trunc dct-mcp-server:test` does not contain any literal API key, JWT, password, or other secret string. (Verified by grep for `apk1`, `secret`, `password`, `token` in the history output — all matches must be the documented ENV-var names, not values.)
- [ ] **AC-3**: Given the built image, `docker image inspect dct-mcp-server:test --format '{{.Config.Labels}}'` shows non-empty values for `org.opencontainers.image.title` and `org.opencontainers.image.source`.

---

## FR-005: Honour `DCT_LOG_DIR` environment variable in the logging setup

### Description
Wire the `DCT_LOG_DIR` env var through `dct_mcp_server.core.logging.GlobalLogger.setup` so users can redirect log output to a host-mounted directory inside a container without editing code. Default behaviour (logs at `<project_root>/logs/` when env var is unset) is preserved exactly. Maps to vision G4 and SC4.

### Input
- Existing `GlobalLogger.setup(log_level, log_file, disable_logging)` signature in `src/dct_mcp_server/core/logging.py` (line 38).
- New env var: `DCT_LOG_DIR` — absolute path, optional, no default value at the env level.

### Processing
1. In `_setup_global_handlers` (line 65 in `core/logging.py`), when `log_file is None`, before computing `logs_dir = project_root / "logs"`, check `os.getenv("DCT_LOG_DIR")`.
2. If `DCT_LOG_DIR` is set and non-empty: set `logs_dir = Path(os.getenv("DCT_LOG_DIR"))`. Compute `log_file_path = logs_dir / "dct_mcp_server.log"`. Skip the project-root branch.
3. If `DCT_LOG_DIR` is unset or empty string: keep the existing `project_root / "logs"` behaviour exactly.
4. The directory creation step (`logs_dir.mkdir(exist_ok=True)`) is shared. Add `parents=True` to that `mkdir` call so a multi-segment `DCT_LOG_DIR` like `/var/log/dct-mcp/server` works on first run.
5. If the `mkdir` or the `TimedRotatingFileHandler` construction fails (e.g. permission denied on a mounted directory), the existing fallback already prints a warning to stderr and falls back to console-only logging (lines 95–99) — no behaviour change there. Cover this in ERR-1.
6. Update the `print_config_help()` text in `src/dct_mcp_server/config/config.py` to list `DCT_LOG_DIR` alongside the other optional env vars (description: "Override directory for log files; defaults to `<project_root>/logs`").
7. No change to `get_dct_config()` — `DCT_LOG_DIR` is read directly by the logging module, not stored in the config dict, since the logging module already initialises before `get_dct_config()` runs (see `main.py` line 37 vs line 47).

### Output
- Updated `core/logging.py` with `DCT_LOG_DIR` honoured.
- Updated `config/config.py:print_config_help()` listing the env var.
- No new dependencies. No public API additions on the logging module.
- Default behaviour byte-identical for any caller that does not set `DCT_LOG_DIR`.

### Acceptance Criteria
- [ ] **AC-1**: Given `DCT_LOG_DIR` unset, when the server starts, then logs are written to `<project_root>/logs/dct_mcp_server.log` (existing behaviour, regression check).
- [ ] **AC-2**: Given `DCT_LOG_DIR=/tmp/dct-test-logs` (a writable directory) and the env var exported before `dct-mcp-server` runs, when the server starts, then `/tmp/dct-test-logs/dct_mcp_server.log` is created and contains the expected startup log lines.
- [ ] **AC-3**: Given `DCT_LOG_DIR=/proc/forbidden` (a non-writable / non-creatable path), when the server starts, then a warning is printed to stderr (`Warning: Failed to create global log file …`) and the server continues running with console logging only — no Python exception escapes.
- [ ] **AC-4**: Given `DCT_LOG_DIR=""` (empty string), when the server starts, then it behaves exactly as if the env var were unset (default project-root path).

---

## Quality Rules

| Rule  | Description                                                                                                       | Enforcement                                                                                                                                                                            | Status  | Evidence |
|-------|-------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|----------|
| QR-1  | Container must run as non-root.                                                                                   | Validation phase: `docker run --rm --entrypoint id <image>` shows non-zero UID. Captured in test-evidence.                                                                            | pending |          |
| QR-2  | No secret values baked into image.                                                                                | Validation phase: `docker history --no-trunc <image>` greps clean for known secret patterns (`apk1`, `password`, `token`, `secret`, `key=`).                                          | pending |          |
| QR-3  | Existing host-install flows (`uvx`, `pip install`, `start_mcp_server_uv.sh`) must continue to work unchanged.    | Validation phase: `git diff origin/main -- pyproject.toml requirements.txt start_mcp_server_uv.sh start_mcp_server_python.sh start_mcp_server_windows_*.bat src/dct_mcp_server/tools/` shows zero changes. | pending |          |
| QR-4  | `DCT_LOG_DIR` change is backward-compatible — when unset, behaviour is byte-identical to current `main`.          | Validation phase: read both code paths and confirm the only divergence happens when `os.getenv("DCT_LOG_DIR")` is truthy.                                                              | pending |          |
| QR-5  | All FR Acceptance Criteria are checked off in the validation report.                                              | Validation phase fills in checkboxes; if any AC is unchecked, validation verdict is FAIL.                                                                                              | pending |          |
| QR-6  | Image size budget: < 250 MB compressed.                                                                            | Build phase records `docker image ls` size; recorded in test-evidence.                                                                                                                 | pending |          |
| QR-7  | No new third-party Python dependencies introduced.                                                                | `git diff origin/main -- requirements.txt pyproject.toml` shows no additions to `dependencies` or `requirements`.                                                                      | pending |          |
| QR-8  | Code-style rule: any new logging code uses `get_logger(__name__)` (not `logging.getLogger`); per `.claude/rules/code-style.md`. | Code review of FR-005 patch.                                                                                                                                                          | pending |          |
| QR-9  | README diff is additive only — no existing lines modified except one TOC line.                                    | `git diff origin/main -- README.md` shows only `+` lines for the TOC entry and the new section.                                                                                        | pending |          |

---

## Edge Cases

- **EC-1**: `DCT_LOG_DIR` set to a path containing whitespace (e.g. `/var/log/dct mcp server`) → `Path()` handles it correctly; mkdir succeeds; verified by AC-2 generalisation.
- **EC-2**: Container started without `-i` flag (no stdin) → MCP server reads EOF immediately, exits cleanly with a non-zero exit code; documented in README "Common pitfalls".
- **EC-3**: User mounts a host directory to `/app/logs` that is owned by host UID != 1000 → file writes fail with EACCES inside the container; documented mitigation: use `--user $(id -u):$(id -g)` on `docker run` or `chown 1000:1000` on the host directory before mount.
- **EC-4**: User builds on Apple Silicon (`linux/arm64`) without buildx → single-arch image is produced for the host architecture; works fine; multi-arch is opt-in.
- **EC-5**: User builds with a stale `uv.lock` after editing `pyproject.toml` → `uv sync --frozen` fails with a clear error; user must run `uv lock` on the host before rebuilding. Documented in README "Common pitfalls".
- **EC-6**: User runs `docker run` without `DCT_API_KEY` → server exits 1 with `print_config_help()` output to stderr (existing behaviour preserved).

## Error Scenarios

- **ERR-1**: `DCT_LOG_DIR` points to a non-writable or non-creatable path → `Path.mkdir()` raises `OSError` (`PermissionError`/`FileNotFoundError`); caught by the existing try/except around `TimedRotatingFileHandler` (lines 86–99 in `core/logging.py`); server logs warning to stderr and continues with console-only logging. **No behaviour change to the existing fallback path.**
- **ERR-2**: `docker build` fails because `uv.lock` is out of sync with `pyproject.toml` → builder stage `uv sync --frozen` exits non-zero; build aborts with a clear message; no partial image tagged.
- **ERR-3**: User passes invalid `DCT_LOG_LEVEL` (e.g. `TRACE`) → existing config validation in `get_dct_config()` raises `ValueError` and `main.py` prints `print_config_help()` to stderr (existing behaviour, unchanged).
- **ERR-4**: Image is run on a host with no MCP client driving stdin (e.g. CI smoke test that just `docker run`s) → server starts, logs initialisation, hits EOF on stdin, exits cleanly. Used in build phase smoke verification.
- **ERR-5**: `apt-get` step in the builder stage fails due to network or upstream mirror outage → build aborts at that layer; caught by build-phase manual retry. Documented as a transient build issue, not a defect.

## Performance Considerations

N/A — Docker support is a packaging change; the server's request-handling performance is unchanged. The only operation on the critical path is image build time (one-off per release) and container cold-start (a few hundred ms of Python interpreter + tool registration). No throughput, latency, or concurrency targets are introduced beyond what already exists for the host-installed server.

---

<!-- Cross-reference:
- FR-001, FR-002, FR-004 satisfy vision G1 and G3; SC1, SC2, SC5, SC6.
- FR-003 satisfies vision G2; SC3 (which is a manual smoke test recorded in test-evidence).
- FR-005 satisfies vision G4; SC4.
- Quality Rules QR-3 and QR-7 enforce vision constraint C5 ("Docker support must not break existing flows") and NG4 ("no refactor of unrelated code").
- Edge Cases EC-2 and EC-3 mitigate vision risks "stdio + PID-1" and "non-root + host mount permissions".
- FR IDs above are referenced in tasks-template (Spec References) and validation-template (FR Coverage). -->
