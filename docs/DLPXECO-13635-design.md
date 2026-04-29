# Feature Design: DLPXECO-13635 — Docker Support for DCT MCP Server

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Status**: Proposed

## Summary

This feature adds first-class Docker packaging support to the DCT MCP Server by providing a production-ready `Dockerfile`, a `.dockerignore` file, and updated `README.md` documentation. The approach uses a `python:3.11-slim` Linux base image that builds the package directly from `pyproject.toml` using `pip install .`, exposes the existing `dct-mcp-server` CLI entry point as the container entry point, and keeps all credentials as runtime environment variables. No Python source code, toolset configuration, or existing MCP behaviour is changed — this is purely a packaging and documentation addition.

## Affected Components

| Component | Path | Change |
|-----------|------|--------|
| Dockerfile | `Dockerfile` (new) | Create — defines the container build process |
| .dockerignore | `.dockerignore` (new) | Create — reduces build context size, prevents credential leaks |
| README.md | `README.md` | Modify — add `## Docker` section and Table of Contents entry |
| Docs | `docs/` | No change — existing docs unaffected |
| Python source | `src/dct_mcp_server/` | No change — source unchanged |
| pyproject.toml | `pyproject.toml` | No change — entry point already defined |
| config/config.py | `src/dct_mcp_server/config/config.py` | No change — existing env var validation used as-is |

## Architecture Changes

### Schema / Config Changes

None. The feature adds packaging files only. No new environment variables are introduced. The existing env var set (`DCT_API_KEY`, `DCT_BASE_URL`, `DCT_TOOLSET`, `DCT_VERIFY_SSL`, `DCT_LOG_LEVEL`, `DCT_TIMEOUT`, `DCT_MAX_RETRIES`, `IS_LOCAL_TELEMETRY_ENABLED`) is documented in the README Docker section by reference — the definitions remain in the existing `## Environment Variables` section.

### Source Files to Modify

| File Path | Action | Purpose |
|-----------|--------|---------|
| `Dockerfile` | Create | Define multi-step container build: copy project files, install dependencies via `pip install .`, set `dct-mcp-server` as entry point |
| `.dockerignore` | Create | Exclude `logs/`, `venv/`, `.venv/`, `.claude/`, `docs/`, `*.pyc`, `__pycache__/`, `.git/`, `.github/`, `.env`, `*.bat`, `artifact.json` from build context |
| `README.md` | Modify | Add `## Docker` entry to Table of Contents; insert `## Docker` section after `## Advanced Installation` (line 304) with subsections: Quick Start (registry placeholder), Build from Source, Run the Container, Windows Compatibility, Connect Your MCP Client, Environment Variables Reference |

### New Files (if any)

- `Dockerfile` — Docker image build definition
- `.dockerignore` — Docker build context exclusion list

### Dockerfile Design Detail

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml requirements.txt ./

# Install package and all dependencies
RUN pip install --no-cache-dir .

# Copy application source
COPY src/ ./src/

# Runtime env vars — do NOT bake in values
# DCT_API_KEY and DCT_BASE_URL must be supplied at docker run time

ENTRYPOINT ["dct-mcp-server"]
```

Key decisions:
- `python:3.11-slim` — minimal attack surface, compatible with Docker Desktop on Windows (Linux containers mode)
- Layer ordering: manifests copied first → pip install → source copy. This maximises cache hits for code-only changes (pip layer is only invalidated when `pyproject.toml` or `requirements.txt` change)
- `pip install --no-cache-dir .` reads `pyproject.toml` `[project.scripts]` to install the `dct-mcp-server` console script into the image's `PATH`
- No `EXPOSE` directive — the server uses stdio transport by default; HTTP/SSE port (6790) binding is via `docker run -p 6790:6790` at runtime
- No credentials in `ARG` or `ENV` directives — `DCT_API_KEY` and `DCT_BASE_URL` are runtime-only
- `ENTRYPOINT` uses JSON array form (`["dct-mcp-server"]`) — not a shell form — so it works identically on Linux and Windows Docker Desktop

### README.md Section Structure

The new `## Docker` section (inserted after line 427 `## Advanced Installation` closing content) contains:

```
## Docker

### Quick Start (Docker Registry)
<placeholder pull command with note>

### Build from Source
docker build -t dct-mcp-server .

### Run the Container
docker run -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server

### Windows Compatibility
<callout about Linux containers mode>
<PowerShell example>

### Connect Your MCP Client
<port-based connection JSON snippet>

### Environment Variables Reference
<link to existing ## Environment Variables section>
```

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Python base image | `python:3.11-slim` | Matches project's `requires-python = ">=3.11"` constraint |
| Docker Desktop (Linux) | 20.10+ | Any modern Docker Engine version supports the features used |
| Docker Desktop (Windows) | 4.0+ | Linux container mode (default); Windows native containers not supported |
| Docker Desktop (macOS) | 4.0+ | Same Linux container execution as Linux host |
| FastMCP | >=2.13.2 | Installed from `pyproject.toml` — no version pinning change needed |
| DCT API | Any supported | The image behaviour matches the native Python behaviour exactly |

No version branching is required in `Dockerfile` or `.dockerignore`. The README Windows section is additive documentation only.

## Platform Behavior Notes

| Platform Behavior | Applies | Notes |
|-------------------|---------|-------|
| stdio transport | Yes | Default MCP transport — stdio does not cross container boundaries; README must document port-based connection for containerised deployments |
| SSL verification defaults to false | Yes | `DCT_VERIFY_SSL=false` is the default in `config.py`; this carries through to Docker; README should recommend setting `DCT_VERIFY_SSL=true` in production |
| API key prefix `apk ` | Yes | `DCTAPIClient` prepends automatically — users must NOT prefix in `-e DCT_API_KEY=...`; README Docker section links to existing env var docs which cover this |
| Telemetry opt-in | Yes | `IS_LOCAL_TELEMETRY_ENABLED=false` by default; container runs the same binary, same behaviour |
| Log file location | Partially | By default, logs write to `logs/` inside the container; to persist logs, users must mount `-v $(pwd)/logs:/app/logs`; README should note this |
| Tool generation temp dir | Yes | `$TEMP/dct_mcp_tools/` is written inside the container's filesystem at runtime — no volume mount required for functionality |

## Open Questions / Risks

| Item | Type | Status | Notes |
|------|------|--------|-------|
| Registry placeholder URL | Risk-Low | Non-blocking | The README will use `ghcr.io/delphix/dct-mcp-server:latest` as a placeholder; the actual registry must be populated when CI publishing is set up (NG1 in vision) |
| `uv.lock` in image | Question | Non-blocking | `pyproject.toml` + `pip install .` resolves dependencies from PyPI at build time; `uv.lock` is not used inside Docker (uv is not installed in the image). This is correct but means Docker builds may pick up newer transitive dependencies than `uv.lock` specifies. Mitigation: copy `requirements.txt` and use `pip install -r requirements.txt` first for pinned transitive deps, then `pip install .` for the package itself. |
| Port 6790 assumption in README | Question | Non-blocking | FastMCP/HTTP transport port 6790 is referenced in existing README. Verify this is the correct default for SSE/HTTP mode before finalising the `docker run -p` example. |
| Log volume mount | Documentation | Non-blocking | Container logs are ephemeral by default; README should mention `-v` mount for log persistence, but this is optional for most users. |

## Acceptance Criteria

Mapped from `docs/DLPXECO-13635-functional.md`:

- [ ] FR-001 / AC-1: `docker build -t dct-mcp-server .` completes with exit code 0 from a clean Docker daemon
- [ ] FR-001 / AC-2: `docker run -e DCT_API_KEY=test -e DCT_BASE_URL=https://fake.dct dct-mcp-server` starts the server and prints startup banner within 10 seconds
- [ ] FR-001 / AC-3: Running without env vars exits with an informative error, not a Python traceback
- [ ] FR-001 / AC-4: `docker inspect` shows no `DCT_API_KEY` or `DCT_BASE_URL` values baked into image layers
- [ ] FR-002 / AC-1: `docker build` context excludes `logs/` and `.claude/`; these directories are absent from the final image
- [ ] FR-002 / AC-2: `.dockerignore` excludes `.env` files
- [ ] FR-003 / AC-1: README contains a complete `## Docker` section with build, run, and client connection instructions
- [ ] FR-003 / AC-2: Docker section contains the placeholder registry pull command clearly marked as a placeholder
- [ ] FR-003 / AC-3: README Docker section contains a working `docker run` example with all required env vars shown
- [ ] FR-003 / AC-4: `## Docker` appears in the Table of Contents with a correct anchor link
- [ ] FR-004 / AC-1: Dockerfile uses `python:3.11-slim` (Linux base)
- [ ] FR-004 / AC-2: README Docker section includes Windows PowerShell `docker run` example or equivalent guidance
- [ ] FR-004 / AC-3: ENTRYPOINT uses JSON array form with `dct-mcp-server` CLI entry point (not a `.sh` script)
