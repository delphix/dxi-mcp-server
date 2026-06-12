# Functional Specification: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Generated from**: Ticket description and acceptance criteria for DLPXECO-13635 (Docker Support for DCT MCP Server)

---

## FR-001: Dockerfile for Containerised DCT MCP Server Runtime

### Description
Provides a `Dockerfile` at the repo root that builds a minimal, reproducible, non-root Linux container image that runs `dct-mcp-server` via `python -m dct_mcp_server.main`, configurable entirely through the documented `DCT_*` environment variables.

### Input
- `pyproject.toml` — package metadata and `requires-python = ">=3.11"` constraint
- `requirements.txt` — pinned runtime dependencies
- `src/dct_mcp_server/` — application source tree
- `docs/api-external.yaml` — bundled OpenAPI spec (bundled fallback)
- `src/dct_mcp_server/config/toolsets/*.txt` — toolset configuration files
- `src/dct_mcp_server/config/mappings/manual_confirmation.txt` — confirmation rules

### Processing
1. Use a multi-stage build:
   - **Build stage** (`python:3.11-slim` base): install dependencies from `requirements.txt` into a virtualenv at `/app/venv`; copy the `src/` tree and install the package in editable mode or via `pip install .`
   - **Runtime stage** (`python:3.11-slim` base): copy the virtualenv from the build stage; copy the installed package; do not include build tools, pip cache, or `.git` in the final layer
2. Create a non-root user and group (`appuser`, uid 1000) in the runtime stage; `chown` `/app` and `/app/logs` to `appuser`
3. Set `WORKDIR /app`; set `USER appuser`
4. Expose no network ports — this is a stdio MCP server
5. Set `CMD ["python", "-m", "dct_mcp_server.main"]` as the entrypoint — do not call `start_mcp_server_*.sh`
6. Create `/app/logs` directory in the Dockerfile (`mkdir -p /app/logs`) and `chown` it to `appuser` — `core/logging.py` derives the log path from `Path(__file__).resolve().parents[3]` (resolves to `/app/logs` when the package is installed at `/app`). There is no `DCT_LOG_DIR` env var; the log directory is fixed at install time. Users can redirect logs to a different location by volume-mounting `/app/logs`.
7. Include a `LABEL` with `maintainer`, `version`, and `description` metadata

### Output
- Success: `docker build -t dct-mcp-server .` produces an image ≤ 500 MB (compressed) that passes a startup smoke test
- Failure modes: missing `requirements.txt` or `src/` → build fails with a clear error at the `COPY` step

### Acceptance Criteria
- [ ] AC-1: Given a clean repo with no pre-existing virtualenv, when `docker build -t dct-mcp-server .` is run, then the build completes without error and the image size is ≤ 500 MB
- [ ] AC-2: Given the built image, when `docker inspect dct-mcp-server` is run, then the runtime user is `appuser` (not root)
- [ ] AC-3: Given the built image, when `docker run --rm dct-mcp-server python -c "import dct_mcp_server.config.loader; print('ok')"` is run, then it prints `ok` without error, confirming all config files were copied correctly
- [ ] AC-4: Given the built image, when no `DCT_API_KEY` or `DCT_BASE_URL` is provided, then the server exits with a non-zero code and a descriptive error message (not a Python traceback)
- [ ] AC-5: Given `.git/`, `logs/`, `__pycache__/`, and `.env` files exist in the repo, then they must not appear in the built image (enforced by `.dockerignore`)

---

## FR-002: .dockerignore for Lean Build Context

### Description
Provides a `.dockerignore` file at the repo root that excludes development artifacts, credentials, logs, and generated files from the Docker build context, keeping the build fast and the image free of sensitive content.

### Input
- Repo root directory contents including: `.git/`, `logs/`, `__pycache__/`, `*.pyc`, `.env`, `*.bat`, `.venv/`, `tests/`, `evals/`, `docs/`, `uv.lock` (only `requirements.txt` is needed in the image)

### Processing
1. Exclude from build context: `.git/`, `.gitignore`, `logs/`, `__pycache__/`, `*.pyc`, `*.pyo`, `.venv/`, `venv/`, `.env`, `*.env`, `mcp.json`, `docs/` (spec docs, not `docs/api-external.yaml`), `evals/`, `tests/`, `*.md` (except README if needed), `uv.lock`, `.claude/`, `start_mcp_server_*.sh`, `start_mcp_server_*.bat`, `whitesource/`
2. Explicitly keep (do not exclude): `src/`, `pyproject.toml`, `requirements.txt`, `docs/api-external.yaml` (bundled spec fallback)
3. Use pattern comments to explain intent for each exclusion group

### Output
- `.dockerignore` at the repo root
- `docker build` context transfer size is < 5 MB (contains only source, config, and the bundled spec)

### Acceptance Criteria
- [ ] AC-1: Given `docker build -t dct-mcp-server .` with `--progress=plain`, then no `.git/` entries, no `logs/` entries, no `__pycache__` entries, no `.env` files appear in the context transfer output
- [ ] AC-2: Given `docs/api-external.yaml` exists, then it is present inside the built image at the expected path (needed for bundled spec fallback)
- [ ] AC-3: Given `tests/` and `evals/` exist in the repo, then they do not appear inside the built image

---

## FR-003: README "Run with Docker" Documentation Section

### Description
Adds a dedicated "Run with Docker" section to the README covering Docker prerequisites, `docker build` and `docker run` commands for macOS/Linux (bash) and Windows (PowerShell and cmd.exe), MCP client JSON configuration snippets, and a registry placeholder URL.

### Input
- Existing README structure (Table of Contents, MCP Client Configuration section)
- Environment variable table from the README (reuse existing variable definitions)
- MCP client config examples for Claude Desktop, Cursor, VS Code Copilot

### Processing
1. Insert "Run with Docker" entry in the Table of Contents, positioned after "Advanced Installation"
2. Write the section with these subsections:
   - **Prerequisites**: Docker Desktop (with WSL2 on Windows) or Docker Engine; no Python or uv required on the host
   - **Build the image**: single `docker build` command; note that this step requires internet access for base image and pip packages
   - **Run the server** (macOS/Linux bash): `docker run -i --rm -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server`
   - **Run the server** (Windows PowerShell): equivalent `docker run` with `$env:` variable syntax
   - **Run the server** (Windows cmd.exe): equivalent `docker run` with `%VAR%` syntax
   - **MCP client configuration**: Claude Desktop `mcp.json` snippet using `docker run -i --rm ...` as the command; Cursor `settings.json` equivalent; VS Code Copilot `mcp.json` equivalent
   - **Persist logs** (optional): `-v $(pwd)/logs:/app/logs` volume mount example with a note about user permissions (`--user $(id -u):$(id -g)` on Linux)
   - **Using a registry image** (placeholder): `docker pull <registry-host>/delphix/dct-mcp-server:<tag>` with a prominent TODO/pending note
   - **SSL and proxy notes**: how to pass `DCT_VERIFY_SSL=true` and `HTTP_PROXY`/`HTTPS_PROXY`; explicitly note that a CA bundle path is NOT supported via env var in the current codebase (`dct_client/client.py` passes `verify_ssl` as a bool to `httpx.AsyncClient`); users needing a custom CA must build a custom image layer using `update-ca-certificates`
3. Cross-reference the existing [Environment Variables](#environment-variables) section for the full variable list rather than duplicating it

### Output
- Updated `README.md` with the new "Run with Docker" section
- Existing sections are unchanged; the new section is self-contained

### Acceptance Criteria
- [ ] AC-1: The README contains a "Run with Docker" section with working `docker run` commands for bash, PowerShell, and cmd.exe
- [ ] AC-2: The README contains MCP client configuration JSON snippets for at least Claude Desktop and Cursor using `docker run -i --rm ...`
- [ ] AC-3: The registry placeholder URL is present and clearly marked as TODO/pending provisioning
- [ ] AC-4: The Table of Contents includes a link to the new section
- [ ] AC-5: All environment variable references in the Docker section point to the canonical [Environment Variables](#environment-variables) section rather than duplicating definitions

---

## FR-004: Windows Compatibility for Docker Stdio Transport

### Description
Ensures that the Docker stdio transport works correctly on Windows hosts (Docker Desktop + WSL2) by providing tested command examples and documenting known Windows-specific caveats (line-buffering, CRLF, signal handling, TTY allocation).

### Input
- Docker run command to be used in MCP client `mcp.json` on a Windows host
- Known behaviors: Docker on Windows with `-i` (no `-t`) preserves stdio; CRLF translation in `cmd.exe`; PowerShell encoding differences

### Processing
1. Use `-i` flag (not `-t`) in all `docker run` examples — this keeps stdin open without allocating a pseudo-TTY, which breaks stdio MCP transport
2. Use `--init` flag to ensure proper signal handling (PID 1 process reaping) — document this as recommended
3. For PowerShell: provide `docker run -i --rm --init -e DCT_API_KEY="$env:DCT_API_KEY" ...` syntax
4. For cmd.exe: provide `docker run -i --rm --init -e DCT_API_KEY=%DCT_API_KEY% ...` syntax
5. Document in the README:
   - Why `-t` must NOT be used with MCP stdio clients
   - The `--init` flag recommendation
   - If the container exits immediately, check that the MCP client is passing `-i`
   - Windows Docker Desktop requires WSL2 backend (not Hyper-V) for reliable stdio behavior

### Output
- README documentation for Windows-specific Docker usage
- MCP client JSON examples that use the correct flags

### Acceptance Criteria
- [ ] AC-1: The `docker run` command in the MCP client config snippets uses `-i` and does not use `-t`
- [ ] AC-2: The README notes the `--init` flag as recommended for proper signal handling
- [ ] AC-3: The README includes a PowerShell `docker run` example with `$env:` variable expansion syntax
- [ ] AC-4: The README includes a cmd.exe `docker run` example with `%VAR%` variable syntax
- [ ] AC-5: The README contains a troubleshooting note explaining why `-t` breaks stdio MCP transport

---

## FR-005: Registry Placeholder and Future Distribution Path

### Description
Documents a placeholder registry URL in the README for the future `docker pull`-based distribution path, clearly marked as pending provisioning, so that teams can reference the expected URL format without being blocked.

### Input
- Ticket requirement #4: "A documented placeholder of the form `<registry-host>/delphix/dct-mcp-server:<tag>`"

### Processing
1. Include in the "Run with Docker" section a subsection titled "Using a Pre-Built Registry Image (Pending Provisioning)"
2. Show the placeholder pull command: `docker pull <registry-host>/delphix/dct-mcp-server:<tag>`
3. Mark with a visible callout: "TODO: The official registry is not yet provisioned. Build from source (see above) until this URL is available."
4. Show the equivalent `docker run` using the pulled image so users can swap in the registry image once available with no other changes

### Output
- README subsection with placeholder URL and TODO callout
- Build-from-source fallback clearly visible so users are never blocked

### Acceptance Criteria
- [ ] AC-1: The README contains a placeholder registry pull command of the form `docker pull <registry-host>/delphix/dct-mcp-server:<tag>`
- [ ] AC-2: The placeholder is clearly annotated as TODO/pending, not presented as a working command
- [ ] AC-3: A build-from-source alternative is visible within the same section so users are not blocked

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| API backward compatibility | Existing `uvx` / `pip install` / local-clone paths must continue to work identically; no changes to `main.py`, `dct_client/`, or any existing `*_endpoints_tool.py` files | `git diff --name-only HEAD~1` must show only `Dockerfile`, `.dockerignore`, `README.md`, and files under `docs/`; `git diff src/` must be empty; all existing pytest tests pass with exit code 0 | Pending | |
| Non-root runtime | Container must run as a non-root user (`appuser`, uid 1000) to meet image hygiene standards | `docker inspect --format '{{.Config.User}}' dct-mcp-server` must return `appuser`; `docker run --rm dct-mcp-server id` must print `uid=1000(appuser)`; Dockerfile contains no `USER root` line after the `appuser` switch | Pending | |
| No credentials in image layers | `DCT_API_KEY`, `DCT_BASE_URL`, and any `.env` files must not be baked into any image layer | `docker history --no-trunc dct-mcp-server \| grep -iE 'apk|DCT_API_KEY|DCT_BASE_URL'` must return empty; `docker inspect dct-mcp-server \| jq '.[0].Config.Env'` must not contain secret values; `.dockerignore` review confirms `.env` exclusion | Pending | |
| Reproducible build | Image must build deterministically from pinned `requirements.txt`; no floating `pip install latest` | All `pip install` lines in the Dockerfile reference `requirements.txt` with `-r` flag only; no bare `pip install <package-name>` without `-r` or explicit `==` version pin; `docker build --no-cache` produces the same package set on two consecutive runs (verified by `docker run --rm dct-mcp-server pip freeze \| sort`) | Pending | |
| Stdio transport parity | Container started with `docker run -i --rm ...` must respond identically to the `uvx` path for the same MCP initialize + tool call sequence | Manual smoke-test: pipe a valid `initialize` JSON-RPC request via stdin to both paths against the same DCT instance; both must return an `initialize` response with the same `serverInfo.name` (`dct-mcp-server`) and a non-empty `tools` list; `vdb_tool(action="search")` must return HTTP 200 responses in both paths | Pending | |
| Image size budget | Compressed image size must not exceed 500 MB | `docker image inspect --format '{{.Size}}' dct-mcp-server` divided by 1048576 must be ≤ 500 (MB uncompressed); compressed size verified via `docker save dct-mcp-server \| gzip \| wc -c` — result must be ≤ 524288000 bytes (500 MB) | Pending | |
| No `.env` auto-loading in container | The server must not silently read a `.env` file placed at `/app/.env` — there is no `python-dotenv` dependency | `docker run --rm -v $(pwd)/test.env:/app/.env -e DCT_API_KEY=override dct-mcp-server python -c "import os; assert os.getenv('DCT_API_KEY')=='override'"` must succeed; confirms env var from `.env` file did not override the `-e` flag (since dotenv is not loaded at all) | Pending | |

---

## Edge Cases

- EC-1: User runs `docker run` without `-i` flag (interactive stdin) → MCP client receives no response; container exits immediately with code 0. README troubleshooting section explains this and requires `-i`.
- EC-2: Container runs as `appuser` but user mounts a host `logs/` volume owned by root → Write to `/app/logs` fails silently or raises `PermissionError`. Mitigation: README documents `--user $(id -u):$(id -g)` override and `chmod 777 ./logs` on the host side.
- EC-3: `DCT_API_KEY` or `DCT_BASE_URL` not set at `docker run` time → Server exits with the standard config validation error from `config.py`. Container exit code is non-zero. README instructs users to pass `-e DCT_API_KEY=...` and `-e DCT_BASE_URL=...`.
- EC-4: Corporate proxy requires `HTTPS_PROXY` but user does not pass it → `DCTAPIClient` (httpx) honors the `HTTPS_PROXY` env var automatically if passed via `-e`; no code change needed. README documents the `-e HTTPS_PROXY=...` flag.
- EC-5: User adds `-t` flag (allocate TTY) alongside `-i` → Docker allocates a pseudo-TTY; MCP binary protocol over stdio breaks due to CRLF injection and buffering. README explicitly warns against `-t` and explains why.
- EC-6: `docker build` is run in a corporate network where `docker pull python:3.11-slim` is blocked → Build fails with a network error. README documents mirroring the base image via `docker pull python:3.11-slim && docker tag python:3.11-slim <mirror>/python:3.11-slim` and updating the `FROM` line.
- EC-7: `docs/api-external.yaml` is absent from the Docker build context (e.g. excluded by `.dockerignore` error) → Server starts but falls back to downloading from DCT; if DCT is unreachable in a CI context, spec load fails. Mitigation: `.dockerignore` must explicitly not exclude `docs/api-external.yaml`; FR-001 AC-2 verifies this.
- EC-8: User builds the image on `linux/arm64` (Apple Silicon) and tries to run it on `linux/amd64` → Docker will error on the platform mismatch. README notes that the initial image targets `linux/amd64`; Apple Silicon users building locally get a native arm64 image that may not match deployment targets.
- EC-9: Container is started with `--restart=always` as a long-running daemon (not the intended MCP stdio pattern) → Each MCP client session needs its own `docker run -i` invocation; a daemon container cannot multiplex MCP stdio sessions. README explains the per-session `docker run -i` pattern.
- EC-10: User tries to use `docker exec` to run a second MCP session inside a running container → MCP stdio is bound to the container's main process; `docker exec` attaches a new shell, not an MCP client. Document in README that each MCP session is its own `docker run -i` invocation.
- EC-11: **SSL certificate verification with a corporate CA** — user sets `DCT_VERIFY_SSL=true` but DCT uses a self-signed or corporate CA cert not in the default system bundle → `httpx` raises `ssl.SSLCertVerificationError`; the container exits with `DCTClientError`. The current codebase does not support `DCT_SSL_CERT_FILE`; `verify_ssl` is passed as a bool. Workaround: build a custom derived image that copies the CA cert to `/usr/local/share/ca-certificates/` and runs `update-ca-certificates`. Document this pattern in the README troubleshooting section.
- EC-12: **Container killed mid-MCP-session (SIGKILL or OOM)** — if the container is force-killed (e.g. `docker kill`, OOM eviction) while an MCP tool call is in flight, the in-progress HTTP request to DCT is abandoned without a response; the lifespan `finally` block does NOT run (SIGKILL bypasses Python signal handlers); the HTTP client is not closed gracefully; any in-progress DCT mutation (e.g. VDB delete mid-confirmation) may be left in an indeterminate state. Mitigation: document that `docker stop` (SIGTERM, 10s grace) should always be preferred over `docker kill`; `main.py` signal handlers respond to SIGTERM; use `--stop-timeout 15` in `docker run` for destructive operations.
- EC-13: **Concurrent `docker run` invocations sharing the same `DCT_SPEC_CACHE_PATH` host volume** — if two containers mount the same host path for `DCT_SPEC_CACHE_PATH`, both may attempt to write the spec YAML simultaneously at startup (no file lock is used in `spec_cache.py`). This is a TOCTOU race on the cache file: one container writes a partial file while the other reads it, producing a `yaml.YAMLError` and a `MCPError("SPEC_LOAD_FAILED")`. Mitigation: each container instance should use an isolated `DCT_SPEC_CACHE_PATH` or rely on the default ephemeral `/tmp/dct_mcp_tools/` inside the container's own filesystem.
- EC-14: **`docker build` with no internet access (fully offline/air-gapped build)** — `docker build` requires pulling `python:3.11-slim` from Docker Hub and downloading packages from PyPI during `pip install -r requirements.txt`. Both will fail in an air-gapped environment. Mitigation: (a) pre-pull and retag the base image from an internal mirror and update `FROM` in the Dockerfile, or (b) use `docker save`/`docker load` to transfer a pre-built image. README must document the offline distribution pattern via `docker save dct-mcp-server | gzip > dct-mcp-server.tar.gz` and `docker load < dct-mcp-server.tar.gz`.
- EC-15: **User mounts a `.env` file expecting environment variable auto-loading** — the server has no `python-dotenv` dependency; `os.getenv()` reads only the process environment, not any file. A file bind-mounted at `/app/.env` is silently ignored. If the user relies on this for secrets, the server exits with `ValueError: DCT_API_KEY environment variable is required`. README must explicitly document that variables must be passed via `-e KEY=VALUE` or `--env-file /path/to/env.file` (Docker's own `--env-file`, not python-dotenv).
- EC-16: **`linux/arm64` image built on Apple Silicon deployed to `linux/amd64` CI or production** — Docker Desktop on Apple Silicon defaults to building `linux/arm64` images. If pushed to a registry and pulled on an `amd64` host without `--platform linux/amd64` at build time, the container crashes with `exec format error`. Mitigation: README documents `docker build --platform linux/amd64 -t dct-mcp-server .` explicitly for cross-platform builds; NG3 defers multi-arch manifest list to a follow-up.

## Error Scenarios

- ERR-1: `pip install -r requirements.txt` fails during `docker build` due to a transient PyPI connectivity issue → Build exits non-zero with pip error output. **Recovery**: retry with `docker build --no-cache -t dct-mcp-server .`; if a mirror or proxy is needed, set `--build-arg http_proxy=...` and `--build-arg https_proxy=...`. **Rollback**: no image is produced; no existing image is overwritten. Previous tagged image (if any) remains usable.
- ERR-2: The `appuser` creation step fails because uid 1000 is already taken in the base image → Build fails with `useradd: user 'appuser' already exists` or silently creates a duplicate user entry. **Recovery**: update the Dockerfile to use `--uid 10001` or check for the existing user with `id appuser` before creating. **Prevention**: CI build against the pinned base image will catch this; pin the exact digest of `python:3.11-slim` in the `FROM` line.
- ERR-3: `dct_mcp_server.main` module not found at container runtime → `ModuleNotFoundError: No module named 'dct_mcp_server'`. Cause: `COPY src/ /app/src/` or `pip install .` step was incomplete or the package was installed in the build stage virtualenv but not copied to the runtime stage. **Recovery**: rebuild the image; verify the multi-stage `COPY --from=build` instruction copies the installed package site-packages. **Detection**: FR-001 AC-3 smoke test catches this at build validation time.
- ERR-4: Server raises `MCPError("SPEC_LOAD_FAILED")` in `dynamic` mode because DCT is unreachable at container start → Container exits immediately with a non-zero code and log message `SPEC_LOAD_FAILED: Could not download the DCT OpenAPI spec`. Note: unlike persona toolsets, dynamic mode has no bundled-spec fallback (see `spec_cache.py`). **Recovery**: (a) ensure DCT is reachable from the container's network, (b) switch to a persona toolset (`DCT_TOOLSET=self_service`) if DCT spec endpoint is blocked, (c) provide a previously cached spec file via `DCT_SPEC_CACHE_PATH` mounted from the host. **Rollback**: for persona toolsets, `docs/api-external.yaml` coverage is enforced by FR-002 AC-2.
- ERR-5: Image is built but the `logs/` directory does not exist inside the container → First log write fails; `logging.py` prints `Warning: Failed to create global log file ...` to `stderr` and continues (the `TimedRotatingFileHandler` failure is caught); the console handler on `stderr` still works. **Recovery**: Dockerfile must create `/app/logs` with `mkdir -p` and `chown appuser` in the runtime stage. ERR-5 is non-fatal by current code behavior but produces a degraded logging experience.
- ERR-6: Container killed with SIGKILL (e.g. OOM, `docker kill`) while a destructive MCP operation (e.g. VDB delete) is in the confirmation flow but not yet executed → The Python process is terminated without running lifespan `finally`; the DCT HTTP client session is abandoned; the pending operation is NOT executed (the `confirmed=True` call was never made). **Recovery**: MCP client session is terminated; the AI assistant must restart and re-issue the full confirmation sequence. No DCT state is corrupted because the API call was not dispatched. **Note**: if SIGKILL occurs after `confirmed=True` is sent but before the HTTP response returns, the DCT operation may be in-flight; check DCT audit logs.
- ERR-7: `DCT_API_KEY` supplied with the `apk ` prefix (e.g. `DCT_API_KEY=apk mykey123`) → `client.py` prepends another `apk ` producing `Authorization: apk apk mykey123`; DCT returns HTTP 401. Container log shows `HTTP 401: ...`. **Recovery**: remove the `apk ` prefix from the env var value; set `DCT_API_KEY=mykey123`. **Detection**: smoke-test against a live DCT instance as part of the acceptance test plan.

## Performance Considerations

- Image build time should be < 3 minutes on a standard developer machine with a warm Docker layer cache (base image already pulled)
- Container startup time (to MCP `initialize` response) must be ≤ 5 seconds, matching the existing `uvx` / `pip install` startup budget
- `docker run` cold-start (base image pull + startup) is a one-time cost; not on the MCP hot path
- The multi-stage build pattern reduces the final image size by excluding pip, setuptools, and other build-only dependencies; target ≤ 500 MB compressed
- `.dockerignore` keeps the build context transfer under 5 MB to avoid slow context uploads over network Docker daemons (e.g. remote Docker on a build server)
- No performance considerations apply to the MCP tool execution path itself — the container adds no overhead beyond a standard process boundary

---
<!-- Cross-reference:
     FR-001 (Dockerfile) → G1, G5, G6, SC1, SC2, SC3, SC5
     FR-002 (.dockerignore) → G6, SC1
     FR-003 (README Docker section) → G2, G3, G4, SC4
     FR-004 (Windows compatibility) → G3, SC4
     FR-005 (Registry placeholder) → G4
     Quality Rules address Constraints and Risks from vision.md
     FR-IDs defined here are referenced in tasks-template (Spec References) and validation-template (FR Coverage). -->
