# Functional Specification: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Generated from**: Git commit history (commits 3bfa45f–f1942e5), revert analysis (8600e56), and vision doc

---

## FR-001: Fix Logging Path Detection for Installed-Package Environments

### Description
Corrects `GlobalLogger._get_project_root()` in `src/dct_mcp_server/core/logging.py` so that when the package is installed into a `site-packages` directory (as it is inside a Docker image), the log directory resolves to `Path.cwd()` rather than traversing upward into the Python library path.

### Input
- `__file__` (implicit): the resolved filesystem path of `logging.py` at runtime
- `sys.frozen` (implicit, optional): set by PyInstaller frozen builds — existing early-return path is preserved

### Processing
1. Resolve `Path(__file__)` to its absolute real path and store as `resolved_file`
2. Compute `candidate = resolved_file.parents[3]` (unchanged — still correct for dev-clone layout `src/dct_mcp_server/core/logging.py`)
3. **Primary guard**: Check whether `"site-packages"` appears **anywhere in `str(resolved_file)`** (not just in `str(candidate)`) — this authoritatively catches all standard install layouts (`pip install`, `pip install --user`, `uvx`, `pip install -e .` does NOT match since it points to the source tree)
4. **Secondary guard** (fallback for exotic install layouts not caught by primary): check `not os.access(str(candidate), os.W_OK)` — if `candidate` itself is not writable, fall back to CWD. This guard is subordinate to the primary; if the primary guard passes, the secondary is not evaluated.
5. If either condition is true → return `Path.cwd()` (inside Docker this is `/app`, which is writable and owned by `mcpuser`)
6. Otherwise → return `candidate` (the repo root in dev-clone or editable-install layout)
7. **Unwritable CWD fallback**: at the call site (`_setup_global_handlers`), if `logs_dir.mkdir(exist_ok=True)` raises `PermissionError`, catch the exception, emit a `WARNING` to stderr: `"Warning: Cannot create log directory {logs_dir}: {e}. File logging disabled."`, and skip the `TimedRotatingFileHandler` setup. The server continues without file logging. This is a degraded-mode scenario documented in the existing `except Exception` block (lines 95–99 of the original file).

### Output
- Docker / installed-package path: `Path('/app')` (CWD inside the container)
- Dev-clone path: `Path('/path/to/repo/root')` (four levels above `logging.py`)
- Side effect: `logs/dct_mcp_server.log` is created in the correct location at server startup

### Acceptance Criteria
- [ ] AC-1: Given `_get_project_root()` is called with `__file__` patched via `unittest.mock.patch` to a path containing `site-packages` (e.g. `/usr/local/lib/python3.11/site-packages/dct_mcp_server/core/logging.py`), then the return value equals `Path.cwd()` (primary guard triggered)
- [ ] AC-2: Given `__file__` patched to a dev-clone path not containing `site-packages` (e.g. `/home/user/dxi-mcp-server/src/dct_mcp_server/core/logging.py`), when `_get_project_root()` is called, then the return value is `/home/user/dxi-mcp-server` (four levels above); also verified for editable install (`pip install -e .`) which resolves to the same source tree path
- [ ] AC-3: Given the container starts with `WORKDIR /app`, when the server starts and emits its first log line, then `logs/dct_mcp_server.log` exists at `/app/logs/dct_mcp_server.log` inside the container
- [ ] AC-4: Given the logging fix is applied, when all existing tests run (`pytest --cov=src/dct_mcp_server --cov-fail-under=4`), then all tests pass (regression guard)

---

## FR-002: Dockerfile — Minimal Non-Root Container Image

### Description
Provides a `Dockerfile` at the project root that builds a minimal, non-root Docker image containing the `dct-mcp-server` entry point, suitable for MCP stdio transport with any supported MCP client.

### Input
- `pyproject.toml` and `README.md` (copied first for layer caching of the `pip install` step)
- `src/` directory (package source)
- Base image: `python:3.11-slim` (or pinned digest variant)

### Processing
1. Set `FROM python:3.11-slim` base image with `# syntax=docker/dockerfile:1` directive
2. Create a non-root group (`mcpuser`, GID 1000) and user (`mcpuser`, UID 1000, no home dir, `/bin/sh` shell) via `groupadd`/`useradd` in a single `RUN` layer to minimize layer count
3. Set `WORKDIR /app`
4. Copy `pyproject.toml` and `README.md` first (layer caching: these change less frequently than `src/`)
5. Copy `src/` directory
6. In a single `RUN` layer: `pip install --no-cache-dir .` + `mkdir -p /app/logs` + `chown -R mcpuser:mcpuser /app`
7. Switch to `USER mcpuser`
8. Set `CMD ["dct-mcp-server"]` (exec form, no ENTRYPOINT) — this allows full command override via `docker run dct-mcp-server sh -c "..."` for debugging; exec form (vs. shell form) ensures signals are delivered to PID 1 directly. **Note on `--init`/tini**: `dct-mcp-server` is a single-process server; zombie reaping is not a concern. `STOPSIGNAL SIGTERM` (Docker's default) is sufficient and the server's asyncio shutdown handles it correctly. `--init` is therefore a conscious opt-out.
9. No `EXPOSE` directive — MCP stdio transport uses no network ports
10. No `HEALTHCHECK` — not applicable to stdio-transport servers; health is determined by the MCP client connection lifecycle

### Output
- Success: Docker image tagged as specified (e.g. `dct-mcp-server:latest`) with the `dct-mcp-server` binary available at PATH
- Side effect: `docker image ls` shows the image under 300 MB
- Container runtime: `id` returns `uid=1000(mcpuser) gid=1000(mcpuser)`

### Acceptance Criteria
- [ ] AC-1: Given a machine with Docker 20.10+ and the project source, when `docker build -t dct-mcp-server .` is run, then the build completes without errors within 3 minutes on a standard workstation
- [ ] AC-2: Given the built image, when `docker run --rm dct-mcp-server id` is executed, then the output confirms `uid=1000(mcpuser)` — the container does not run as root
- [ ] AC-3: Given the built image, when `docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://localhost dct-mcp-server` is run, then the server starts (outputs an MCP handshake or connection-error message) without a Python traceback attributable to the logging path
- [ ] AC-4: Given `docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server .`, then the multi-arch build completes without errors (requires `buildx` with an appropriate builder)

---

## FR-003: .dockerignore — Lean Build Context

### Description
Provides a `.dockerignore` file at the project root that excludes files and directories from the Docker build context that are not needed at runtime, reducing build time and preventing accidental inclusion of secrets or large development artefacts.

### Input
- Implicit: the full project directory tree at `docker build` time

### Processing
Exclude the following categories from the build context:
1. **Python artefacts**: `.venv/`, `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`, `*.egg-info/`, `dist/`, `build/`
2. **Secrets and local config**: `.env`, `.env.*` (any dotenv file variant)
3. **Logs** (ephemeral; users should mount a volume): `logs/`
4. **Version control**: `.git/`, `.github/`
5. **Development tooling**: `.claude/`, `docs/`, `evals/` (LLM evaluation harness, not needed at runtime), `tests/` (test suite, not needed inside the image)
6. **Startup scripts** (not needed inside the image; entry point is the installed `dct-mcp-server` binary): `*.sh`, `*.bat`
7. **Common macOS/editor artefacts**: `.DS_Store`, `.vscode/`, `.idea/`, `*.swp`, `mcp.json`, `whitesource/`
8. **Note**: `requirements.txt` — the image uses `pip install .` via `pyproject.toml`; `requirements.txt` is not needed at build time. However, it should remain in the build context as it is referenced during `pip install .` dependency resolution. Do not exclude it.

Note: Any new root-level file added to the repo must be explicitly evaluated for exclusion — the `.dockerignore` excludes named patterns, not an allowlist. The Output section's description of the build context as "only `pyproject.toml`, `README.md`, `src/`" is aspirational; the true guarantee is that the exclusions above are applied.

### Output
- Docker build context excludes the categories listed above; the effective runtime-necessary set is `pyproject.toml`, `README.md`, `src/` (and `requirements.txt` if present — not excluded since it may be referenced by `pip install .`)
- The `.env` file is never included in any image layer

### Acceptance Criteria
- [ ] AC-1: Given a project directory containing a `.env` file, when `docker build` is run, then `docker run --rm dct-mcp-server env | grep DCT_API_KEY` returns nothing (the secret was not baked into the image)
- [ ] AC-2: Given `docker build --no-cache -t dct-mcp-server .` with a warm Docker daemon, the build context transfer completes in under 5 seconds on a local machine (lean context)
- [ ] AC-3: The final image does not contain `docs/`, `.claude/`, `.git/` directories when inspected with `docker run --rm dct-mcp-server find /app -maxdepth 2 -type d`

---

## FR-004: docker-compose.yml — Local Development Convenience

### Description
Provides a `docker-compose.yml` at the project root for developers who prefer `docker compose up` over manual `docker run` invocations, with `stdin_open: true` for MCP stdio transport, env-file support, and a log-volume mount.

### Input
- `.env` file on the developer's machine (not committed; listed in `.gitignore` and `.dockerignore`)
- `docker-compose.yml` itself

### Processing
The Compose file defines a single service `dct-mcp-server`:
1. `build: .` — builds from the local `Dockerfile`
2. `image: dct-mcp-server:local` — tags the built image for reuse
3. `stdin_open: true` — keeps stdin attached for MCP stdio protocol; **`tty: false`** is critical: combining `stdin_open: true` with `tty: true` allocates a pseudo-TTY, causing MCP clients to receive TTY escape sequences that break JSON-RPC framing
4. `env_file: - .env` — loads `DCT_API_KEY`, `DCT_BASE_URL`, and other env vars from `.env`; include a comment explaining users must create `.env` from the template in README. When `.env` is absent, Docker Compose V2 exits with a non-zero status and a clear `env file .env not found` error — this is a safe fail-fast behavior.
5. `volumes: - ./logs:/app/logs` — persists logs to the host `./logs/` directory

### Output
- `docker compose up` starts the MCP server with stdio transport, credentials from `.env`, and logs persisted to `./logs/`
- No network ports are exposed

### Acceptance Criteria
- [ ] AC-1: Given a `.env` file with valid `DCT_API_KEY` and `DCT_BASE_URL`, when `docker compose up` is run, then the container starts without error and `./logs/dct_mcp_server.log` is created on the host
- [ ] AC-2: Given no `.env` file, when `docker compose up` is run, then Docker Compose V2 exits non-zero with an `env file .env not found` error message (it does not silently start with empty credentials)
- [ ] AC-3: The `docker-compose.yml` contains an inline comment directing users to create `.env` from the documented env-var list in `README.md`

---

## FR-005: README.md — Docker Section

### Description
Adds a `## Running with Docker` section to `README.md` that enables any user to build, run, persist logs, and configure their MCP client to use the Docker-based server without referencing any other documentation.

### Input
- Existing `README.md` structure (Table of Contents entry added; section placed after `MCP Client Configuration` and before `Advanced Installation`)

### Processing
The section must include:
1. **Prerequisites block**: Docker 20.10+, a valid `DCT_API_KEY` and `DCT_BASE_URL`, and a local repository clone (for `docker build`)
2. **Build step**: `docker build -t dct-mcp-server .` with a note about multi-arch buildx
3. **Run step**: Linux/macOS `docker run` command with all required flags (`--rm -i`) and all mandatory env vars; include `DCT_VERIFY_SSL`, `DCT_TOOLSET`, and `DCT_LOG_LEVEL` as optional examples
4. **Windows run step**: Command Prompt (`^` continuation) and PowerShell (`` ` `` continuation) variants
5. **Log persistence**: Linux/macOS and Windows variants using `-v` volume mount; note that logs are ephemeral without the volume
6. **SSL / CA cert note**: Documents the `SSL_CERT_FILE` environment variable approach for private DCT instances with custom CA certs
7. **MCP Client Configuration subsections** (using `<details>` collapsible blocks to match the existing README pattern): Claude Desktop, Cursor/Windsurf, VS Code/Eclipse/IntelliJ — each with Linux/macOS and Windows variants
8. **Table of Contents update**: Add `[Running with Docker](#running-with-docker)` entry after `[Advanced Installation]` in the existing ToC

### Output
- `README.md` renders correctly on GitHub with all code blocks, callouts, and `<details>` sections properly formatted
- All `docker run` examples are copy-pasteable (no missing flags, no invisible characters)

### Acceptance Criteria
- [ ] AC-1: The `## Running with Docker` section appears in the README Table of Contents and links correctly to the section anchor
- [ ] AC-2: Each `docker run` example includes `--rm -i` and at minimum `-e DCT_API_KEY=` and `-e DCT_BASE_URL=`
- [ ] AC-3: A callout note explains that `-i` is required for MCP stdio communication (many users omit this flag)
- [ ] AC-4: The Claude Desktop, Cursor/Windsurf, and VS Code client configuration examples each show a `docker run` command as the `command` field with all required `args` entries
- [ ] AC-5: The Windows section provides both Command Prompt (`^`) and PowerShell (`` ` ``) variants
- [ ] AC-6: A note on custom CA certificates (`SSL_CERT_FILE`) is present for enterprise users with private DCT instances

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1: Backward compatibility — dev-clone logging | `_get_project_root()` must continue to return the repo root when running from a local clone (`__file__` not under `site-packages`) | Unit test `TestGetProjectRoot.test_dev_clone_returns_repo_root` added to `tests/core/test_logging.py` | Pending | — |
| QR-2: No secrets in Docker image layers | `.env` and `.env.*` must not appear in any image layer | Smoke test: `docker run --rm dct-mcp-server sh -c 'env | grep -i key | wc -l'` returns 0 without `-e DCT_API_KEY`; also verifiable via `docker history --no-trunc` inspection | Pending | — |
| QR-3: Non-root runtime | Container must not run as UID 0 | `docker run --rm dct-mcp-server id \| grep uid=1000` | Pending | — |
| QR-4: API backward compatibility preserved | No changes to public Python API, tool registration, or MCP protocol | Existing pytest suite passes with `--cov-fail-under=4` | Pending | — |
| QR-5: No new third-party dependencies | `pyproject.toml` dependencies must not change | `git diff pyproject.toml` shows no `dependencies` section changes | Pending | — |

---

## Edge Cases

- EC-1: `DCT_BASE_URL` points to a DCT instance with a self-signed or private CA certificate → `DCT_VERIFY_SSL=false` (default) suppresses the SSL error; for `DCT_VERIFY_SSL=true`, user must inject the CA cert via `SSL_CERT_FILE` environment variable or a `COPY` instruction in a derived image
- EC-2: User runs `docker run` without `-i` flag → stdin is not attached; MCP client immediately disconnects after receiving no response; README prominently documents `-i` as required
- EC-3: User attempts to run the server on a platform that does not support Linux containers (e.g. native Windows containers) → Dockerfile uses `python:3.11-slim` (Linux); note in README that Docker Desktop on Windows runs Linux containers by default
- EC-4: Log directory `/app/logs` inside the container is not mounted → logs are written to the container filesystem; they are lost when the container exits with `--rm`; README documents the `-v ./logs:/app/logs` volume mount
- EC-5: The `.env` file has Windows-style CRLF line endings → Docker Compose reads env files correctly on Linux; however, shell-style `export` sourcing would fail; README instructs users to use Unix LF line endings in `.env`
- EC-6: User builds the image and then upgrades the codebase without rebuilding → container runs old code; no auto-refresh mechanism; README notes `docker build` must be re-run after pulling updates
- EC-7: `mcpuser` (UID 1000) conflicts with an existing UID on the host when bind-mounting the log volume → files in `./logs/` are owned by UID 1000; this is cosmetic on Linux but may require `chown` on the host; noted in README
- EC-8: `docker buildx` is not available or no multi-arch builder is configured → standard `docker build` produces a single-platform image for the current host; multi-arch instructions wrapped in a note confirming `buildx` is required
- EC-9: `_get_project_root()` called from an editable install (`pip install -e .`) → `__file__` resolves to the source tree path (no `site-packages` in path); `parents[3]` correctly returns the repo root; behavior is identical to dev-clone mode
- EC-10: `_get_project_root()` called from a `pip install --user` install → `__file__` contains `site-packages` in the resolved path (e.g. `/home/user/.local/lib/python3.11/site-packages/...`); primary guard triggers and returns `Path.cwd()` correctly
- EC-11: CWD is unwritable when running from an installed package (e.g. invoked from `/` via `uvx`) → `logs_dir.mkdir(exist_ok=True)` raises `PermissionError`; server continues in degraded mode (file logging disabled, warning on stderr); MCP tool calls are unaffected

## Error Scenarios

- ERR-1: `docker build` fails because `pyproject.toml` has a syntax error or missing field → `pip install` layer fails with a clear error; the fix is a code change, not a Docker issue
- ERR-2: Container starts but `dct-mcp-server` exits immediately with a Python traceback from logging setup → root cause is typically the logging path bug (FR-001); fix is to verify the `_get_project_root()` change is present
- ERR-3: `mkdir /app/logs` in `Dockerfile` fails due to permission issue mid-build → `chown -R mcpuser:mcpuser /app` runs in the same `RUN` layer as `pip install` and `mkdir`, so failure here is a Dockerfile ordering issue; verified in build
- ERR-4: Volume mount `./logs:/app/logs` fails because `./logs` does not exist on the host → Docker creates the host directory automatically; no user action needed
- ERR-5: `docker compose up` fails with `invalid interpolation format` → user has `$` characters in their `.env` values; instruct to escape as `$$` or quote the value
- ERR-6: Server starts but MCP client shows no tools → user started with `DCT_TOOLSET=dynamic` (default) and `DCT_BASE_URL` is unreachable; tool generation fails silently and falls back to empty tool list; user should check `DCT_BASE_URL` and set a fixed toolset (e.g. `self_service`)
- ERR-7: `pip install` fails inside `docker build` due to PyPI being unreachable or a package version being yanked → Docker build layer fails with a pip error; fix: retry the build once network is available, or pre-download wheels and COPY them into a derived image. `--no-cache-dir` is already set so partial downloads are not an issue.
- ERR-8: The logging fix is merged and later found to regress an unanticipated install layout → rollback options: (a) revert `_get_project_root()` to the original `parents[3]` logic (safe for Docker users since they set `DCT_LOG_DIR`), or (b) introduce a `DCT_LOG_DIR` environment variable override that bypasses `_get_project_root()` entirely. Rollback path is documented here and in the PR description.

## Performance Considerations

- Docker image build time is expected to be 60–120 seconds on a standard workstation (dominated by `pip install` of all transitive dependencies); subsequent builds with layer cache are under 5 seconds if only `src/` changed
- Image size target is under 300 MB with `python:3.11-slim`; `--no-cache-dir` in the `pip install` step prevents pip's wheel cache from inflating the layer
- Container startup time for the MCP server is the same as non-Docker startup (< 2 seconds to first MCP handshake message); no additional Docker overhead is observable at the application layer

---

## Assumptions

_The following assumptions were made autonomously (interview mode active but no user context was provided):_

- A1: The primary reason for the previous revert was the logging path bug identified in commit 12950f6 — the fix must be re-applied as part of FR-001.
- A2: `docker-compose.yml` uses the `docker-compose.yml` filename (not `compose.yml`) for compatibility with Docker Compose V1 and V2.
- A3: The `.dockerignore` uses glob patterns compatible with the Moby/Docker `dockerignore` spec (not `.gitignore` syntax).
- A4: The README Docker section is placed after the existing MCP Client Configuration section and before the Advanced Installation section (matching the previously reverted README structure).
- A5: No Docker Hub image name or tag strategy is defined here — that is scoped to the future publish ticket.

---
<!-- Cross-reference: FR descriptions map to Goals (G1–G6) in the vision doc.
     FR Acceptance Criteria satisfy Success Criteria (SC1–SC6).
     Quality Rules and Edge Cases address Constraints and Risks from the vision doc. -->
