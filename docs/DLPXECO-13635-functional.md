# DLPXECO-13635 — Docker Support: Functional Specification

> **Vision**: see [DLPXECO-13635-vision.md](DLPXECO-13635-vision.md)
> **Domain**: feature
> **Status**: ready for design

---

## Scope summary

Deliver a `Dockerfile` (and supporting build assets) plus README documentation that lets a user run `dct-mcp-server` from a container on macOS, Linux, and Windows hosts (Linux containers via Docker Desktop/WSL2). The container preserves the existing stdio transport and env-var contract. No changes to runtime behavior of the server itself.

---

## Functional Requirements

### FR-1 — Dockerfile builds a runnable image

**Description**: The repository root contains a `Dockerfile` that builds a Linux image which, when run, starts the DCT MCP server on stdio.

**Acceptance criteria**:
- AC-1.1 — `docker build -t dct-mcp-server:dev .` from the repo root completes successfully on a clean machine with only Docker installed.
- AC-1.2 — The build uses a pinned Python base image of the form `python:3.11.x-slim` (specific minor version pinned in the `Dockerfile`); not `python:latest`, not `python:3.11` (unpinned patch).
- AC-1.3 — The build uses a multi-stage approach: a `builder` stage installs dependencies, a `runtime` stage copies only the installed site-packages and source needed at runtime.
- AC-1.4 — The final image's `CMD` is `["python", "-m", "dct_mcp_server.main"]` (or equivalent that delegates to the same `main()` entry point used by `start_mcp_server_*.sh`).
- AC-1.5 — Dependencies are installed from `requirements.txt` (or `uv.lock` via `uv sync`) — pinned, deterministic. No `pip install <name>` of unpinned packages in the Dockerfile.
- AC-1.6 — The image declares `WORKDIR /app` and the source is at `/app/src/dct_mcp_server/`.
- AC-1.7 — The image runs as a non-root user (`appuser`, UID 1000) by default. The user owns `/app` and any writable directories (`/app/logs`).
- AC-1.8 — `ENTRYPOINT` is set so that flags passed to `docker run <image> <args>` are forwarded to the Python module (or are explicitly documented as not supported, with `CMD` as the only invocation).
- AC-1.9 — `docker images dct-mcp-server:dev` reports a final image size **≤ 250 MB** (compressed, as shown by `docker save | gzip | wc -c` or via registry push size reporting).
- AC-1.10 — The image build does **not** include `.git/`, `logs/`, `.venv/`, `__pycache__/`, `.claude/`, or `docs/DLPXECO-13635-*.md` (enforced via `.dockerignore`; verified by inspecting the built image with `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls -la /app'`).

### FR-2 — Server runs identically to local-clone invocation

**Description**: When the container is launched, the server's behavior — toolset registration, tool generation, DCT API calls, logging, telemetry — is functionally identical to running `python -m dct_mcp_server.main` from a local clone with the same env vars.

**Acceptance criteria**:
- AC-2.1 — `docker run --rm -i -e DCT_API_KEY=<k> -e DCT_BASE_URL=<u> dct-mcp-server:dev` starts the MCP server on stdio with no errors and accepts MCP `initialize` requests.
- AC-2.2 — The same set of MCP tools is registered inside the container as outside it for a given `DCT_TOOLSET` value (verified by issuing `tools/list` over stdio and comparing tool names + counts).
- AC-2.3 — All env vars listed in `.claude/rules/build-and-execution.md` (`DCT_API_KEY`, `DCT_BASE_URL`, `DCT_TOOLSET`, `DCT_VERIFY_SSL`, `DCT_LOG_LEVEL`, `DCT_TIMEOUT`, `DCT_MAX_RETRIES`, `IS_LOCAL_TELEMETRY_ENABLED`) are honored when passed via `-e` and produce the same effects as on host runs.
- AC-2.4 — A live DCT API call (any read action, e.g. `vdb_tool(action="search")`) made through the containerised server returns the same shape of response as the same call against a local-clone server pointed at the same DCT instance.
- AC-2.5 — `DCT_TOOLSET=auto` works inside the container — `enable_toolset()` and `disable_toolset()` MCP calls succeed and the running tool list updates as expected.
- AC-2.6 — Container logs (`logs/dct_mcp_server.log`) follow the same rotation policy as host runs. When `-v <host-path>:/app/logs` is mounted, log files appear on the host with the expected names.
- AC-2.7 — When `IS_LOCAL_TELEMETRY_ENABLED=true` is passed and `/app/logs/sessions/` is a mounted volume, session telemetry JSON files are written to the host.

### FR-3 — Cross-platform host support (macOS, Linux, Windows)

**Description**: The same image runs on macOS, Linux, and Windows hosts. Windows support uses Docker Desktop with the WSL2 backend (Linux containers). PowerShell, `cmd`, and Unix shell examples are provided.

**Acceptance criteria**:
- AC-3.1 — The image is built for `linux/amd64` and runs on:
  - macOS (Docker Desktop, Apple Silicon via emulation or arm64 build, Intel native)
  - Ubuntu 22.04+ (or any modern Linux with Docker Engine)
  - Windows 10/11 with Docker Desktop + WSL2 backend (Linux containers mode)
- AC-3.2 — The README documents the exact `docker run` command for each shell:
  - bash / zsh (macOS, Linux)
  - PowerShell (Windows)
  - `cmd.exe` (Windows fallback)
  with the env-var syntax adjusted per shell.
- AC-3.3 — The container's stdio is correctly attached on all three platforms — no CRLF / line-buffering issues observed when the MCP client (Claude Desktop, Cursor, VS Code Copilot) connects.
- AC-3.4 — Signal handling (SIGTERM, SIGINT) inside the container works such that `docker stop <id>` triggers the existing `handle_shutdown` coroutine in `main.py` and the lifespan finally-block closes the HTTP client. (Mitigation: `docker run --init` documented; the `Dockerfile` may also set `STOPSIGNAL SIGTERM` and use `tini` as PID 1 for robust signal forwarding.)
- AC-3.5 — Volume mounting works on Windows for the `logs/` directory using both `C:\path\to\logs` and `/c/path/to/logs` styles per shell, as documented.

### FR-4 — README documentation for Docker usage

**Description**: A new top-level section "Run with Docker" is added to `README.md`, fitting the existing structure (added under "Advanced Installation" or as a new top-level section, whichever the design phase chooses). It covers build, pull-from-placeholder, run, and MCP client wiring.

**Acceptance criteria**:
- AC-4.1 — A new section heading **"Run with Docker"** (or equivalent) exists in `README.md` and is linked from the table of contents.
- AC-4.2 — The section answers, in order:
  1. Prerequisites (Docker installed; for Windows, Docker Desktop with WSL2 backend).
  2. Build from source: `docker build -t dct-mcp-server:dev .`
  3. Pull from registry: `docker pull <PLACEHOLDER_REGISTRY>/delphix/dct-mcp-server:<tag>` — clearly marked as **placeholder pending registry provisioning** with a link to build-from-source as the current path.
  4. Run with required env vars (`DCT_API_KEY`, `DCT_BASE_URL`).
  5. Run with optional env vars (table referencing the existing env-var table, no duplication).
  6. Wire into MCP clients — at minimum a Claude Desktop config example showing the `docker run -i --rm ...` command form for the `command` field.
- AC-4.3 — The "Pull from registry" subsection contains a TODO marker (e.g. `<!-- TODO(DLPXECO-13635): swap placeholder for real registry URL once provisioned -->`) so the eventual registry URL update is grep-able.
- AC-4.4 — Example commands include both bash/zsh and PowerShell forms where they differ (env-var quoting in particular).
- AC-4.5 — The section warns that the container image is for local-development MCP usage; it does not introduce a hosted service. (Mirrors the stdio transport reality.)
- AC-4.6 — Existing `uvx` / `pip install` / local-clone install instructions are unchanged. The Docker section is additive.
- AC-4.7 — The README table of contents includes a link to the new section.

### FR-5 — `.dockerignore` keeps the build context lean

**Description**: A `.dockerignore` file at the repo root excludes files irrelevant to the runtime image, both for build speed and to prevent leaking dev artifacts (logs with credentials, `.env` files, the `.claude/` workspace, generated docs).

**Acceptance criteria**:
- AC-5.1 — A `.dockerignore` file exists at the repo root.
- AC-5.2 — At minimum the following are excluded: `.git/`, `.gitignore`, `.github/`, `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `*.pyo`, `logs/`, `.env`, `.env.*`, `*.log`, `.claude/`, `docs/`, `.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/`, `node_modules/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `start_mcp_server_*.sh`, `start_mcp_server_*.bat` (the in-container entrypoint does not need them).
- AC-5.3 — `docker build` context size (printed at the start of the build) is **< 5 MB**. Verified via `docker build --no-cache .` and inspecting the "Sending build context to Docker daemon" line.
- AC-5.4 — `src/dct_mcp_server/config/toolsets/*.txt` and `src/dct_mcp_server/config/mappings/manual_confirmation.txt` are **not** excluded — they are runtime-required.
- AC-5.5 — `pyproject.toml`, `requirements.txt`, and `README.md` are **not** excluded (needed for build / pip-install-of-self).

### FR-6 — Image security and hygiene

**Description**: The image follows container best practices appropriate for a tool-server image: pinned base, minimal layers, no embedded secrets, non-root runtime, no unnecessary packages.

**Acceptance criteria**:
- AC-6.1 — The image runs as a non-root user (`USER appuser` directive present, with explicit UID/GID, e.g. `1000:1000`).
- AC-6.2 — `docker run --rm dct-mcp-server:dev id` returns a non-zero UID/GID.
- AC-6.3 — No DCT credentials, API keys, registry tokens, or `.env` files are present in any layer (verified by `docker history --no-trunc dct-mcp-server:dev` and by `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'find / -name "*.env" -o -name "*api*key*" 2>/dev/null'`).
- AC-6.4 — Build-only tooling (`gcc`, build dependencies for any wheels that don't ship binaries) is present in the `builder` stage only and **not** in the final runtime image.
- AC-6.5 — `apt-get install -y --no-install-recommends` (or equivalent) is used; `rm -rf /var/lib/apt/lists/*` after package install in any stage that uses `apt`.
- AC-6.6 — `pip` cache is not retained in the final image (`--no-cache-dir` or explicit cache cleanup).
- AC-6.7 — `HEALTHCHECK` directive is **not** present (an MCP stdio server has no useful liveness probe; documented as intentional).
- AC-6.8 — `LABEL` directives include at minimum: `org.opencontainers.image.source=https://github.com/delphix/dxi-mcp-server`, `org.opencontainers.image.title="dct-mcp-server"`, `org.opencontainers.image.licenses=MIT`, and a `org.opencontainers.image.version` populated from the `pyproject.toml` version.

### FR-7 — Build does not require host network access to private resources

**Description**: The Docker build must work on any developer's machine with public internet only. It must not require access to internal Delphix-only registries, private PyPI mirrors, or pre-existing local images.

**Acceptance criteria**:
- AC-7.1 — The base image (`python:3.11.x-slim`) is pulled from Docker Hub (or any public mirror).
- AC-7.2 — Pip dependencies are pulled from public PyPI (`pypi.org`).
- AC-7.3 — The build does not `RUN curl` or `wget` to any private host. Any such fetch is from a public URL with a checksum verification or a pinned commit.
- AC-7.4 — A clean machine (no prior Docker image cache, no PyPI cache) can build the image successfully.

### FR-8 — Quality, lint, and structural constraints

**Description**: The Dockerfile is reviewed for common pitfalls; the README change passes existing project conventions.

**Acceptance criteria**:
- AC-8.1 — The Dockerfile passes `hadolint` (or equivalent dockerfile linter) with no errors. Warnings for stylistic preferences are acceptable but should be deliberately suppressed with comments.
- AC-8.2 — The README change preserves the existing markdown structure (heading hierarchy, table-of-contents formatting, code-fence languages).
- AC-8.3 — No existing rule files (`.claude/rules/*.md`) are silently violated; if any rule needs an extension to cover Docker (e.g. `.claude/rules/docker.md` or an addition to `build-and-execution.md`), the design phase calls it out and the implement phase adds it.
- AC-8.4 — No changes to `pyproject.toml` are required for the feature itself. (If a Docker-specific dependency is genuinely needed, the design phase justifies it.)

### FR-9 — Optional: docker-compose example

**Description**: A `docker-compose.yml` file at repo root may be added if and only if it materially improves the user experience for local development. It is **optional** and the design phase decides whether to include it.

**Acceptance criteria** *(only if the design phase decides to ship it)*:
- AC-9.1 — `docker compose up` (with a documented `.env` file containing `DCT_API_KEY` / `DCT_BASE_URL`) starts the server.
- AC-9.2 — The compose file uses the same image built by the `Dockerfile`; it does not duplicate runtime configuration.
- AC-9.3 — The `.env.example` file is added showing the expected env vars (with placeholder values, no real secrets).
- AC-9.4 — The README's Docker section references the compose file as an optional convenience.

*If the design phase decides not to ship compose, FR-9 is dropped from the implementation scope and AC-9.* are not evaluated.*

---

## Quality Rules (orthogonal to FR-*)

- **QR-1**: All new files use Unix line endings (`LF`). The `Dockerfile`, `.dockerignore`, and any `.sh` helpers are checked.
- **QR-2**: Markdown changes preserve existing whitespace conventions (no trailing whitespace, terminal newline present).
- **QR-3**: No `apk add` (Alpine) — the base is `python:3.11.x-slim` (Debian-based) per AC-1.2; package install commands use `apt-get`.
- **QR-4**: All shell snippets in the README's Docker section are tested by copy-paste — they must run as written, not require user-specific substitution beyond clearly bracketed placeholders (`<your-api-key>`, `<your-dct-host>`).
- **QR-5**: Existing project rules in `.claude/rules/` apply unchanged — Python code style, exception handling, logging via `get_logger`, the grouped-tool pattern. The container does not introduce new code patterns; it only repackages existing code.
- **QR-6**: The placeholder registry URL in the README uses a clearly-fake-looking host (e.g. `<registry-host>` or `registry.example.com`) — never a real-looking URL that might get accidentally pulled or cached.
- **QR-7**: Git workflow rules are honored — no force-push, no commits of `.env` / credentials / `logs/`. The `.dockerignore` and `.gitignore` are kept consistent for these patterns.

---

## Out of scope (explicit)

The following are **not** in scope for this ticket and must not be added by the implementation:

1. CI workflow to build and publish the image to a registry.
2. Helm chart, k8s manifests, or any orchestration assets beyond a single Dockerfile (and optional compose).
3. HTTP / SSE transport for MCP.
4. ARM64 image variant.
5. Native Windows containers (Server Core / Nano Server).
6. Changes to `start_mcp_server_*.sh` / `.bat` scripts — they remain as-is.
7. Changes to `main.py`, `dct_client/`, `tools/`, `config/`, `core/` — no source-code changes are required by this feature.

---

## Cross-references

- Vision: [DLPXECO-13635-vision.md](DLPXECO-13635-vision.md)
- Project rules: `.claude/rules/build-and-execution.md`, `.claude/rules/code-style.md`, `.claude/rules/git-workflow.md`
- MCP server entry point: `src/dct_mcp_server/main.py`
- Existing startup scripts (preserved): `start_mcp_server_uv.sh`, `start_mcp_server_python.sh`, `start_mcp_server_windows_uv.bat`, `start_mcp_server_windows_python.bat`
