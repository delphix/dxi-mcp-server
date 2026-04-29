# Feature Design: Docker Container Support for DCT MCP Server

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Status**: Proposed

## Summary

This feature adds Docker container packaging to the DCT MCP Server (`dct-mcp-server`), enabling operators to run the server in a fully isolated, reproducible container on Linux and Windows (via Docker Desktop with Linux containers). The implementation consists of three purely additive artifacts: a `Dockerfile` at the repository root using `python:3.11-slim`, a `docker-compose.yml` for single-command startup, and a new `## Running with Docker` section in `README.md`. No runtime code in `src/` is modified — this is packaging and documentation only, satisfying the Non-Goal constraint in the vision doc.

## Affected Components

- [ ] `src/dct_mcp_server/main.py` — Entry point (no changes)
- [ ] `src/dct_mcp_server/config/config.py` — Config loading (no changes)
- [ ] `src/dct_mcp_server/dct_client/client.py` — HTTP client (no changes)
- [ ] `src/dct_mcp_server/tools/` — Tool modules (no changes)
- [x] `Dockerfile` — **NEW**: containerised build and runtime for the server
- [x] `docker-compose.yml` — **NEW**: single-command operator startup
- [x] `README.md` — **MODIFY**: add `## Running with Docker` section with Linux and Windows instructions and placeholder registry URL
- [ ] `pyproject.toml` — unchanged (already defines `dct-mcp-server` as CLI entry point)
- [ ] `requirements.txt` — unchanged (dependency list used in Docker build)
- [ ] `start_mcp_server_*.{sh,bat}` — unchanged (existing scripts remain functional)

## Architecture Changes

### Schema / Config Changes

No schema or configuration changes. The `Dockerfile` and `docker-compose.yml` consume existing environment variables (`DCT_API_KEY`, `DCT_BASE_URL`, and optional variables) passed at `docker run` time or via `.env` file — no new variables are introduced.

### Source Files to Modify

| File | Action | Purpose | Maps to FR |
|------|--------|---------|------------|
| `Dockerfile` | Create | Multi-stage (or single-stage slim) image that installs dependencies from `pyproject.toml`/`requirements.txt` and launches `dct-mcp-server` via the pip-installed CLI entry point | FR-001 |
| `docker-compose.yml` | Create | Service definition referencing `Dockerfile`, environment variable pass-through from `.env` or inline, optional `logs/` volume mount | FR-002 |
| `README.md` | Modify | Add `## Running with Docker` section with subsections: Prerequisites, Build the image, Run with docker run, Run with docker-compose, Windows (Docker Desktop), Pre-built image (coming soon) | FR-003 |

### New Files (if any)

| File | Purpose |
|------|---------|
| `Dockerfile` | Docker image build instructions |
| `docker-compose.yml` | Compose service definition for operator-friendly startup |
| `.env.example` | Example environment file documenting required and optional variables (prevents operators from accidentally committing real credentials; README references this file) |

### Dockerfile Design

```dockerfile
FROM python:3.11-slim

# Prevents Python from buffering stdout/stderr (important for MCP stdio transport)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy dependency manifests first to leverage layer caching
COPY requirements.txt pyproject.toml ./

# Install the package and its dependencies
# Using pip install -e . installs the package in editable mode so the CLI entry point works
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

# Create logs directory for runtime log output
RUN mkdir -p /app/logs

# Default entrypoint: run the MCP server via the installed CLI entry point
ENTRYPOINT ["dct-mcp-server"]
```

Key design decisions:
- `PYTHONUNBUFFERED=1` ensures stdout/stderr are not buffered, which is critical for the MCP stdio transport — buffered output would break the MCP protocol framing.
- `pip install -e .` installs the package using `pyproject.toml`, making the `dct-mcp-server` CLI entry point available as a system command inside the container.
- No `EXPOSE` directive is needed — the server uses stdio transport, not TCP.
- No `DCT_API_KEY` or `DCT_BASE_URL` baked into the image — these are runtime-only (passed via `-e` flags or `.env` file).
- `python:3.11-slim` base image satisfies the Python 3.11 requirement and minimises image size.
- LF line endings enforced by the Dockerfile's `\n` separators — no CRLF risk on Windows-built images.

### docker-compose.yml Design

```yaml
services:
  dct-mcp-server:
    build: .
    image: dct-mcp-server:local
    env_file:
      - .env
    environment:
      # Required — must be set in .env or overridden here
      - DCT_API_KEY
      - DCT_BASE_URL
      # Optional with defaults
      - DCT_TOOLSET=${DCT_TOOLSET:-self_service}
      - DCT_VERIFY_SSL=${DCT_VERIFY_SSL:-false}
      - DCT_LOG_LEVEL=${DCT_LOG_LEVEL:-INFO}
      - DCT_TIMEOUT=${DCT_TIMEOUT:-30}
      - DCT_MAX_RETRIES=${DCT_MAX_RETRIES:-3}
      - IS_LOCAL_TELEMETRY_ENABLED=${IS_LOCAL_TELEMETRY_ENABLED:-false}
    volumes:
      - ./logs:/app/logs
    stdin_open: true
    tty: false
    restart: "no"
```

Key design decisions:
- `env_file: .env` allows operators to manage credentials in a `.env` file (not committed to git).
- `volumes: ./logs:/app/logs` mounts the host `logs/` directory for persistent log access.
- `stdin_open: true` and `tty: false` are required for the MCP stdio transport: `stdin_open` keeps stdin open (equivalent to `docker run -i`), while `tty: false` avoids TTY allocation which would corrupt binary MCP framing.
- `restart: "no"` prevents compose from silently restarting a failed container that may be crashing due to missing credentials.
- `build: .` means `docker-compose up --build` always builds from local source — no attempt to pull a registry image.

### README.md Design

A new `## Running with Docker` section is inserted before `## Toolsets` (preserving all existing sections and their order). The section contains:

1. `### Prerequisites` — Docker Desktop or Docker Engine installed; Linux containers mode for Windows.
2. `### Build the image` — `docker build -t dct-mcp-server .`
3. `### Run with docker run` — `docker run -i --rm -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server`; notes on `-i` flag requirement for stdio transport.
4. `### Run with docker-compose` — copy `.env.example` to `.env`, fill in credentials, run `docker-compose up --build`.
5. `### Windows (Docker Desktop)` — note that Linux containers mode is required; how to check in Docker Desktop settings; equivalent `docker run` command using PowerShell env var syntax.
6. `### Pre-built image (coming soon)` — placeholder text with `ghcr.io/delphix/dct-mcp-server:latest` clearly marked as "not yet published".
7. `### Troubleshooting` — MCP client configuration for containerised server, log access via `docker logs`.

The Table of Contents in README.md is updated to include the new `[Running with Docker](#running-with-docker)` entry.

### MCP Client Configuration for Containerised Server

Because the MCP server uses stdio transport, running it in Docker requires the MCP client to launch the container process. The README Docker section will include a MCP client configuration snippet:

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-e", "DCT_API_KEY=your-api-key",
               "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
               "dct-mcp-server"]
    }
  }
}
```

This is distinct from `docker-compose up` (which starts the server as a daemon) — for MCP client integration, `docker run -i` is the correct pattern.

## Version Compatibility

| Component | Compatibility | Notes |
|-----------|---------------|-------|
| Python | 3.11 (pinned via `python:3.11-slim` base image) | Matches `requires-python = ">=3.11"` in `pyproject.toml` |
| Docker Engine | 20.10+ (Linux), Docker Desktop 4.x+ (Windows/macOS) | `docker-compose.yml` uses Compose v2 syntax (`services:` at root, no `version:` key) |
| Docker Compose | v2 (Compose plugin or standalone `docker compose`) | No `version:` key; uses `services:` as root — compatible with both `docker-compose` CLI and `docker compose` plugin |
| MCP server code | No version branching needed — packaging only | `src/` is untouched; no runtime behavior changes |
| Platform | linux/amd64 (native Linux builds), linux/amd64 via Docker Desktop (Windows/macOS) | ARM64 builders (Apple Silicon) must use `--platform linux/amd64` for amd64 deployment |

No breaking changes. Existing startup scripts (`start_mcp_server_*.sh`, `*.bat`) are not modified and remain fully functional.

## Platform Behavior Notes

| Behavior | Relevance | Notes |
|----------|-----------|-------|
| stdio transport | Critical | MCP stdio transport requires `stdin_open: true` in compose and `-i` flag in `docker run` — without this, the MCP client cannot send requests and the container exits immediately |
| stdout buffering | Critical | `PYTHONUNBUFFERED=1` prevents Python's default stdio buffering from breaking MCP framing |
| Windows Docker Desktop | Required for Windows users | Must use Linux containers mode (not Windows containers) — documented explicitly in README |
| ARM64 / Apple Silicon | Build-time only | `docker build` on Apple Silicon produces `linux/arm64` by default; deploying to amd64 hosts requires `--platform linux/amd64` — noted in README |
| Log directory | Operator-visible | Container writes logs to `/app/logs/`; compose mounts `./logs:/app/logs` so host can access logs without `docker exec` |
| Credential handling | Security | No credentials in image; all secrets via runtime env vars or `.env` file; `.env` excluded from git via `.gitignore` note in README |
| Signal handling | Normal | FastMCP/uvicorn handles SIGTERM for graceful shutdown; `docker stop` sends SIGTERM then SIGKILL after timeout — acceptable |
| DCT_BASE_URL trailing slash | Consistent | Existing server validates this; container inherits the same validation logic with no additional handling needed |

## Open Questions / Risks

| Item | Severity | Resolution |
|------|----------|------------|
| `.env` file in `.gitignore` — should `.env.example` be committed? | Low | Yes: `.env.example` is a template with no real credentials and should be committed. `.env` (with real values) should be in `.gitignore`. README will note this distinction. |
| Multi-arch image (ARM64 + amd64) — scope? | Low | Out of scope per NG1 (no CI/CD). README documents `--platform linux/amd64` for Apple Silicon users who deploy to amd64 hosts. |
| `docker-compose.yml` `version:` field — deprecated? | Low | Compose v2 does not require a `version:` key. Omitting it is the modern correct approach. If users see a deprecation warning on older Compose v1, they should upgrade. |
| MCP client must launch container — is `docker-compose up` usable with stdio? | Medium | `docker-compose up` starts the service detached or in foreground but cannot be used directly as a `command` in MCP client config for stdio transport. The README must clearly distinguish: (1) `docker run -i` for MCP client stdio integration, (2) `docker-compose up` for running as a standalone daemon (e.g. SSE-mode or future HTTP transport). Currently the server is stdio-only, so `docker run -i` is the primary integration path. |
| Image name conflict with future registry publish | Low | README placeholder uses `ghcr.io/delphix/dct-mcp-server:latest` — when the CI/CD pipeline (NG1) is eventually built, the `docker-compose.yml` `image:` field will need updating from `dct-mcp-server:local` to the registry image name. Non-blocking. |

## Acceptance Criteria

### FR-001: Dockerfile
- [x] AC-1: `docker build -t dct-mcp-server .` completes with exit code 0 on Linux
- [x] AC-2: `docker run --rm -i -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server` starts the MCP server and does not exit immediately
- [x] AC-3: Starting without `DCT_API_KEY` causes the container to exit with a clear error message
- [x] AC-4: Container starts without path or line-ending errors on Windows Docker Desktop (Linux containers mode)

### FR-002: docker-compose.yml
- [x] AC-1: `docker-compose up --build` with a valid `.env` file builds and starts the container successfully
- [x] AC-2: `docker-compose up` without a `.env` file exits with a clear error about missing configuration
- [x] AC-3: `docker-compose down` stops and removes the container cleanly

### FR-003: README Documentation
- [x] AC-1: User following `Build the image` instructions can run `docker build` successfully on Linux
- [x] AC-2: Windows users following the Windows (Docker Desktop) subsection can run the container without additional research
- [x] AC-3: Placeholder URL section is clearly marked "coming soon" and not presented as a live pullable image
- [x] AC-4: No existing README sections removed or reordered
