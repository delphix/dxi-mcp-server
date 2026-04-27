# Design: DLPXECO-13635 — Docker Support for MCP Server

**Vision**: `docs/DLPXECO-13635-vision.md`
**Functional spec**: `docs/DLPXECO-13635-functional.md`

---

## Overview

Five concrete artefacts ship in this PR:

1. `Dockerfile` (new) — multi-stage build, `python:3.11-slim` base, non-root runtime user, stdio entrypoint.
2. `.dockerignore` (new) — excludes host artefacts (`.git`, `.venv`, `logs/`, `docs/`, `.claude/`, IDE files, dev scripts).
3. `README.md` (modified, additive only) — new `## Docker` section + one new TOC entry.
4. `src/dct_mcp_server/core/logging.py` (modified, ~6 lines net) — read `DCT_LOG_DIR` env var and use it as the logs root when set.
5. `src/dct_mcp_server/config/config.py` (modified, ~3 lines net) — list `DCT_LOG_DIR` in `print_config_help()`.

The image is invoked by an MCP client using `docker run --rm -i …` (stdio transport). It is **not** a network service, has no `EXPOSE`, and has no `CMD` (only `ENTRYPOINT ["dct-mcp-server"]`).

## Architecture Changes

### Source Files to Modify

| File | Change type | Purpose | FR |
|------|-------------|---------|----|
| `Dockerfile` | **CREATE** | Two-stage build; runtime drops to UID 1000; entrypoint = `dct-mcp-server`. | FR-001, FR-004 |
| `.dockerignore` | **CREATE** | Trim build context — exclude `.git`, `.venv`, `logs/`, `docs/`, `.claude/`, IDE/OS junk, `start_mcp_server_*.sh`, `start_mcp_server_*.bat`, `__pycache__/`, `.env*`, etc. (with `!README.md` and `!LICENSE.md` re-included). | FR-002 |
| `README.md` | **MODIFY** (additive) | Add one TOC line `- [Docker](#docker)`; insert `## Docker` section between "Advanced Installation" and "Toolsets". No edits to existing prose. | FR-003 |
| `src/dct_mcp_server/core/logging.py` | **MODIFY** (~6 lines) | In `_setup_global_handlers`, when `log_file is None`, prefer `os.getenv("DCT_LOG_DIR")` over `project_root / "logs"`. Add `parents=True` to `logs_dir.mkdir(...)`. | FR-005 |
| `src/dct_mcp_server/config/config.py` | **MODIFY** (~3 lines) | In `print_config_help()`, add a line documenting `DCT_LOG_DIR`. | FR-005 |

### Files **NOT** Modified (regression guard for QR-3, QR-7)

These files must remain byte-identical to `origin/main`:

- `pyproject.toml`
- `requirements.txt`
- `start_mcp_server_uv.sh`, `start_mcp_server_python.sh`
- `start_mcp_server_windows_uv.bat`, `start_mcp_server_windows_python.bat`
- `src/dct_mcp_server/main.py`
- All files under `src/dct_mcp_server/tools/`
- All files under `src/dct_mcp_server/dct_client/`
- All files under `src/dct_mcp_server/toolsgenerator/`
- All `*.txt` files under `src/dct_mcp_server/config/toolsets/` and `mappings/`
- All files under `.github/`
- `LICENSE.md`, `.whitesource`, `uv.lock`

### Files Created (new artefacts only)

- `Dockerfile` (~60–80 lines)
- `.dockerignore` (~30–40 lines)
- `docs/DLPXECO-13635-*.md` — the spec/design/test-plan/etc. set (these stay in the repo on the branch but are excluded from the image by `.dockerignore`).

## Component Designs

### Dockerfile (FR-001, FR-004)

Two stages, both `FROM python:3.11-slim-bookworm`:

```
┌──────────────────────────────────┐    ┌──────────────────────────────────┐
│ Stage 1: builder (root)          │    │ Stage 2: runtime (USER app)      │
│                                  │    │                                  │
│ - WORKDIR /build                 │    │ - WORKDIR /app                   │
│ - pip install uv==<pin>          │    │ - useradd app (UID 1000)         │
│ - COPY pyproject.toml uv.lock    │    │ - mkdir -p /app/logs (chown app) │
│ - COPY src/, README.md, LICENSE  │ ─→ │ - COPY --from=builder /build/.venv /app/.venv │
│ - uv sync --frozen --no-dev      │    │ - COPY src/, pyproject.toml,     │
│                                  │    │       uv.lock, README, LICENSE   │
│                                  │    │ - ENV PATH=/app/.venv/bin:$PATH  │
│                                  │    │ - ENV PYTHONUNBUFFERED=1         │
│                                  │    │ - ENV DCT_LOG_DIR=/app/logs      │
│                                  │    │ - USER app                       │
│                                  │    │ - ENTRYPOINT ["dct-mcp-server"]  │
└──────────────────────────────────┘    └──────────────────────────────────┘
```

Key decisions:

- **Base image**: `python:3.11-slim-bookworm` (Debian Bookworm slim variant). Pinned by tag. Provides `python3.11`, `pip`, and a small Debian userspace. No `apt-get install` needed because `uv` ships pre-built wheels for Linux on PyPI.
- **`uv` version pin**: install `uv` in the builder stage with an explicit version (`pip install --no-cache-dir uv==0.5.x` — exact pin chosen at implement time from current `uv` releases). Avoids surprise breakage from a future `uv` major.
- **`uv sync --frozen --no-dev`**: deterministic install from `uv.lock`, skipping any dev-only groups. Materialises the `.venv` directory inside `/build/.venv`.
- **Why copy `.venv` between stages**: the entire Python environment (including the `dct-mcp-server` console script) is materialised in the builder stage and copied as a single layer to the runtime stage. The runtime stage is therefore reproducible and free of build-time tooling (`uv`, `pip` cache, apt cache).
- **Non-root user**: `groupadd -g 1000 app && useradd -u 1000 -g 1000 -m -s /bin/false app`. Shell is `/bin/false` because there's no need for interactive shell access.
- **`/app/logs` writable by app user**: created in the runtime stage as `mkdir -p /app/logs && chown -R app:app /app /app/.venv`. Bind-mounting from the host requires the host directory to be writable by UID 1000 (documented as EC-3 / pitfall in README).
- **`PYTHONUNBUFFERED=1`** is essential for stdio transport — Python must flush stdout/stderr line-by-line so the MCP client and the log stream are not delayed by buffering.
- **`DCT_LOG_DIR=/app/logs`** as a default ENV: ensures logs land in the predictable, writable, mountable directory inside the container. Users can override at `docker run` time.
- **OCI labels**: `org.opencontainers.image.title="dct-mcp-server"`, `description`, `source="https://github.com/delphix/dxi-mcp-server"`, `licenses="MIT"`, `version="2026.0.1.0-preview"` (matches `pyproject.toml`).
- **No `EXPOSE`**: stdio only.
- **No `CMD`**: `dct-mcp-server` takes no positional args.
- **No `HEALTHCHECK`**: stdio servers cannot meaningfully self-healthcheck without an MCP client driving them; adding one would create false negatives.

### .dockerignore (FR-002)

A pure exclusion list. Categories:

- Python build artefacts (`__pycache__/`, `*.pyc`, `*.pyo`, `build/`, `dist/`, `*.egg-info/`, `wheels/`)
- Virtualenvs (`.venv/`, `venv/`, `env/`)
- Logs (`logs/`, `*.log`, `mcp_server_setup_logfile.txt`)
- Env / secrets (`.env`, `.env.*`, `.env.local`, `.env.*.local`)
- VCS (`.git/`, `.gitignore`, `.github/`, `.whitesource`)
- Docs / specs (`docs/`, `*.md`)
- Re-include `README.md` and `LICENSE.md` with `!README.md`, `!LICENSE.md` (the project ships these)
- IDE / OS (`.vscode/`, `.idea/`, `*.swp`, `*.swo`, `*~`, `.DS_Store`, `Thumbs.db`)
- Project-specific (`.claude/`, `CLAUDE.md`, `.worktrees/`, `worktrees/`)
- Dev scripts (`start_mcp_server_*.sh`, `start_mcp_server_*.bat`)
- Test files (`tests/`, `test/`, `**/test_*.py`, `**/*_test.py`) — defensive even though no tests exist today.
- Docker/OCI artefacts that don't belong in the image (`Dockerfile`, `.dockerignore`) — not strictly required but standard practice; Docker handles `Dockerfile` itself specially.

### README.md `## Docker` section (FR-003)

Anchor: `## Docker` — the markdown autogenerated id `#docker` is unique on this page.

Insertion point: between the existing `## Advanced Installation` block (ends at line ~426 of `main`) and the `## Toolsets` block (starts at line ~428). One blank line above and below.

TOC change: a single line added between `- [Advanced Installation](#advanced-installation)` and `- [Toolsets](#toolsets)`:

```
- [Docker](#docker)
```

Section structure (subsections at level 3):

1. **Prerequisites** — Docker Engine 20.10+ (or Docker Desktop). For multi-arch, `docker buildx`. A valid DCT API key & base URL.
2. **Build the image** — single fenced bash block:
   ```
   git clone https://github.com/delphix/dxi-mcp-server.git
   cd dxi-mcp-server
   docker build -t dct-mcp-server:latest .
   ```
3. **Run the server (stdio)** — explanation: container is invoked **by the MCP client** using `docker run -i …`, not started in the background. Then a fenced bash block:
   ```
   docker run --rm -i \
     -e DCT_API_KEY="your-api-key" \
     -e DCT_BASE_URL="https://your-dct-host.example.com" \
     -e DCT_TOOLSET="self_service" \
     -e DCT_VERIFY_SSL="false" \
     dct-mcp-server:latest
   ```
4. **Environment variables** — short note: cross-link back to the existing `## Environment Variables` section. Plus a small table:

   | Variable | Default in container | Notes |
   |----------|----------------------|-------|
   | `DCT_API_KEY` | (none — required) | Required at runtime; do not bake into image. |
   | `DCT_BASE_URL` | (none — required) | |
   | `DCT_LOG_DIR` | `/app/logs` | Override to redirect logs (see below). |
   | `DCT_TOOLSET` | `self_service` | One of: `auto`, `self_service`, `self_service_provision`, `continuous_data_admin`, `platform_admin`, `reporting_insights`. |
   | `DCT_VERIFY_SSL` | `false` | |
   | `DCT_LOG_LEVEL` | `INFO` | |
   | `DCT_TIMEOUT` | `30` | |
   | `DCT_MAX_RETRIES` | `3` | |
   | `IS_LOCAL_TELEMETRY_ENABLED` | `false` | |

5. **Persist logs to the host** — fenced bash block:
   ```
   mkdir -p ./logs && sudo chown 1000:1000 ./logs
   docker run --rm -i \
     -e DCT_API_KEY="..." \
     -e DCT_BASE_URL="..." \
     -v "$(pwd)/logs:/app/logs" \
     dct-mcp-server:latest
   ```
   (Note about UID 1000 host permission requirement.)
6. **MCP client configuration with Docker** — three collapsible `<details>` blocks (matching existing README style), one each for Claude Desktop, Cursor, VS Code. Example for Claude Desktop:
   ```json
   {
     "mcpServers": {
       "delphix-dct": {
         "command": "docker",
         "args": [
           "run", "--rm", "-i",
           "-e", "DCT_API_KEY",
           "-e", "DCT_BASE_URL",
           "-e", "DCT_TOOLSET=self_service",
           "dct-mcp-server:latest"
         ],
         "env": {
           "DCT_API_KEY": "your-api-key",
           "DCT_BASE_URL": "https://your-dct-host.example.com"
         }
       }
     }
   }
   ```
   The `-e VAR` form (without `=`) tells `docker run` to inherit the value from the parent process's env, which `mcpServers.<name>.env` sets — this avoids embedding the API key in the `args` array.
7. **Multi-arch build (optional)** — `docker buildx create --use && docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server:latest .` with a note that `linux/amd64` is the primary supported architecture.
8. **Common pitfalls**:
   - "Container exits immediately" → forgot `-i`. The MCP client must run `docker run -i …`.
   - "No log files appear on the host" → bind-mount `/app/logs` and ensure host directory is owned by UID 1000 (or use `--user "$(id -u):$(id -g)"`).
   - "Build fails with `uv.lock` mismatch" → run `uv lock` on the host first, then rebuild.
   - "Can't connect from the client" → check `docker logs <container>` is **not** what you want — for stdio servers, run the MCP client interactively and check the client's own log; the container exits when stdin closes.

### `core/logging.py` change (FR-005)

Targeted patch in `_setup_global_handlers`, around the existing `if log_file is None:` block (lines 73–80):

**Before**:
```python
if log_file is None:
    project_root = self._get_project_root()
    logs_dir = project_root / "logs"
    log_file_path = logs_dir / "dct_mcp_server.log"
else:
    log_file_path = Path(log_file)
    logs_dir = log_file_path.parent

# Create logs directory
logs_dir.mkdir(exist_ok=True)
```

**After**:
```python
if log_file is None:
    env_log_dir = os.getenv("DCT_LOG_DIR")
    if env_log_dir:
        logs_dir = Path(env_log_dir)
    else:
        project_root = self._get_project_root()
        logs_dir = project_root / "logs"
    log_file_path = logs_dir / "dct_mcp_server.log"
else:
    log_file_path = Path(log_file)
    logs_dir = log_file_path.parent

# Create logs directory (parents=True so multi-segment DCT_LOG_DIR works on first run)
logs_dir.mkdir(parents=True, exist_ok=True)
```

Notes:

- `env_log_dir` is treated as truthy/falsy with bare `if env_log_dir:` so empty string `""` falls through to default behaviour (covers AC-4).
- `parents=True` is added to support nested paths like `/var/log/dct-mcp/server`.
- The existing `try/except` around `TimedRotatingFileHandler` (lines 86–99) already handles permission errors and falls back to console-only logging — no change there.
- `os` is already imported at the top of the file (line 6).
- This change is isolated to one method; no other callers of the logging module are affected.

### `config/config.py` change (FR-005)

Add one line in `print_config_help()` between the existing `IS_LOCAL_TELEMETRY_ENABLED` and `DCT_TOOLSET` lines (around line 60):

```python
print("  DCT_LOG_DIR      Override directory for log files (default: <project_root>/logs)")
```

No change to `get_dct_config()` — `DCT_LOG_DIR` is read directly by the logging subsystem when handlers are set up. It does not need to flow through the config dict because no other consumer needs it.

## Data Flow

### MCP client → containerised server (runtime)

```
┌──────────────┐  spawn (docker run -i)  ┌─────────────────────────────┐
│ MCP client   │ ─────────────────────→  │ docker run --rm -i …        │
│ (Claude Desk)│                          │  ▶ Docker daemon starts ctr │
│              │  stdin / stdout (JSON-   │  ▶ ENTRYPOINT dct-mcp-server│
│              │   RPC over MCP framing)  │  ▶ uv-installed Python 3.11 │
│              │ ◀─────────────────────── │     reads stdin, writes     │
│              │                          │     stdout for MCP frames   │
└──────────────┘                          │  ▶ stderr → docker logs     │
                                          │  ▶ /app/logs/*.log file     │
                                          │     (writable by UID 1000)  │
                                          └─────────────────────────────┘
```

When the client closes stdin, the server's stdio loop exits, the Python process returns, the `--rm` flag tells Docker to remove the container, and the client moves on. No daemon, no port, no detached state.

### Logs flow

```
Server process (UID 1000)
  │
  ├─ stderr   → Docker captures → `docker logs <id>` (ephemeral, --rm)
  └─ logging  → /app/logs/dct_mcp_server.log
                  │
                  └─ if -v <host>:/app/logs is set → host directory
                       (and via DCT_LOG_DIR override, any other in-container path)
```

## Build & Verification Plan

| Step | Command (run from worktree root) | Expected |
|------|----------------------------------|----------|
| B1 | `docker build -t dct-mcp-server:test .` | exit 0, image tagged |
| B2 | `docker image inspect dct-mcp-server:test --format '{{.Size}}'` | < 600 MB uncompressed (informational; QR-6 budget is < 250 MB compressed measured by `docker save \| gzip \| wc -c`) |
| B3 | `docker save dct-mcp-server:test \| gzip \| wc -c` | < 250 × 1024 × 1024 bytes (262144000) |
| B4 | `docker run --rm --entrypoint id dct-mcp-server:test` | `uid=1000(app) gid=1000(app)` |
| B5 | `docker run --rm --entrypoint sh dct-mcp-server:test -c 'ls -la /app && ls -la /app/logs'` | shows `.venv`, `src`, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE.md`; logs dir empty and owned by `app:app` |
| B6 | `docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://example.invalid dct-mcp-server:test < /dev/null` | starts, hits EOF on stdin, exits cleanly. Either logs `Starting MCP server with stdio transport...` then exits, or fails with a network/cert error — but **not** with a permission error or Python traceback unrelated to DCT connectivity. |
| B7 | `docker history --no-trunc dct-mcp-server:test \| grep -iE 'apk1\|password\|secret\|token' \| grep -v 'DCT_'` | empty output (no secret values, only env-var names) |
| B8 | `docker image inspect dct-mcp-server:test --format '{{.Config.Labels}}'` | non-empty `org.opencontainers.image.title`, `source` |
| L1 | Locally on host: `DCT_LOG_DIR=/tmp/dct-test ./start_mcp_server_uv.sh` (then Ctrl-C after a few seconds) | `/tmp/dct-test/dct_mcp_server.log` exists and contains startup lines |
| L2 | Locally on host: unset `DCT_LOG_DIR` and run `./start_mcp_server_uv.sh` | `<project_root>/logs/dct_mcp_server.log` updated as before (no regression) |
| L3 | Locally on host: `DCT_LOG_DIR=/proc/forbidden ./start_mcp_server_uv.sh` | warning printed to stderr, server still starts (console-only logging) |

Steps B1–B8 cover Docker-side acceptance; L1–L3 cover the `DCT_LOG_DIR` Python change.

## Security Considerations

- No secrets in the image. `DCT_API_KEY` is **never** baked in — it must be provided at `docker run` time. README explicitly warns against `ENV DCT_API_KEY=…` patterns.
- Non-root runtime (UID 1000). Even if an attacker compromised the server, they have no privileged operations available inside the container.
- Slim base image reduces the CVE surface vs. `python:3.11` (full).
- No shell on the runtime user (`/bin/false`) — limits exec-into-container abuse.
- No network ports exposed — image presents zero attack surface beyond the stdio it's invoked over.
- `.dockerignore` keeps `.env`, `.git/`, `.claude/`, and any local secrets out of the build context, so they never become recoverable from `docker history`.

## Open Questions / Deferred Decisions

- **Q1**: Should we publish the image to a registry (Docker Hub, GHCR) as part of the release pipeline? — **Deferred** (vision NG2). Track in a separate ticket.
- **Q2**: Should the project add a `docker-compose.yml` for users running multiple MCP servers side-by-side? — **Deferred** (vision NG3).
- **Q3**: Should `DCT_LOG_DIR` also be honoured by the session telemetry handler (`logs/sessions/{session_id}.log`)? — **Out of scope for this ticket**; the telemetry path is opt-in (`IS_LOCAL_TELEMETRY_ENABLED=false` by default), and a follow-up patch can extend the same env var to the session logger if there's demand. Documented in this design as future work; not required to satisfy DLPXECO-13635.
- **Q4**: Should we add a CI job that builds the Docker image on PR? — **Deferred** to whoever owns the CI pipeline; out of scope for "support hosting in a container" but a natural next step.

---

<!-- Cross-reference:
- Architecture Changes table is the canonical list for the implement phase and the validation FR Coverage section.
- B1–B8 and L1–L3 in Build & Verification feed directly into the test-evidence document.
- Files NOT Modified list is the authoritative source for QR-3 / QR-7 in validation.
- Defaults (e.g. DCT_LOG_DIR=/app/logs) are echoed in the README section so the docs and the Dockerfile cannot drift. -->
