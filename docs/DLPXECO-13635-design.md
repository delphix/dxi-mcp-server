# Feature Design: Support for Hosting MCP Server in Docker Container

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Status**: Open

## Summary

This feature adds Docker container support for the DCT MCP Server, allowing users to run the server without needing Python or `uv` installed on their host machine. A `Dockerfile` and `.dockerignore` are added, along with a Docker section in the README covering multi-arch builds, running the container, persisting logs, and configuring MCP clients to use the Docker-based server. A minor fix to `core/logging.py` is also included to make log directory creation graceful when the directory cannot be created (needed to handle Docker environments where the working directory may not be writable at startup).


## Affected Components

- [x] `Dockerfile` — new file: multi-arch, non-root user, stdio transport
- [x] `.dockerignore` — new file: exclude Python artifacts, secrets, logs, dev tooling, `.mcp.json`
- [x] `README.md` — Docker section added to docs
- [x] `src/dct_mcp_server/core/logging.py` — graceful log dir creation (mkdir inside try block)
- [ ] `config/toolsets/*.txt` — no toolset changes
- [ ] `tools/*_endpoints_tool.py` — no tool changes
- [ ] `config/loader.py` — no loader changes
- [ ] `main.py` — no entry point changes
- [ ] `dct_client/client.py` — no client changes

## Architecture Changes

### Schema / Config Changes

None. All configuration continues to be supplied via environment variables. No new env vars are introduced — existing ones (`DCT_API_KEY`, `DCT_BASE_URL`, `DCT_TOOLSET`, `DCT_VERIFY_SSL`, `DCT_LOG_LEVEL`, `DCT_TIMEOUT`, `DCT_MAX_RETRIES`) are documented in the Docker README section.

### Source Files to Modify

- `src/dct_mcp_server/core/logging.py` — move `logs_dir.mkdir(exist_ok=True)` inside the `try` block so that a failure to create the log directory is handled gracefully rather than crashing the server.

### New Files (if any)

- `Dockerfile` — multi-arch Python 3.11-slim image with non-root user, stdio transport entry point
- `.dockerignore` — excludes `.venv/`, `__pycache__/`, `*.pyc`, `.env`, `logs/`, `.git/`, `.github/`, `.claude/`, `docs/`, startup `*.sh`/`*.bat` scripts

### README.md Changes

A new `## Docker` section is added to `README.md` with:
- Build instructions (standard + multi-arch `buildx`)
- `docker run` examples for Linux/macOS and Windows (Command Prompt and PowerShell)
- Log persistence via volume mount
- MCP client configuration snippets for Claude Desktop, Cursor/Windsurf, and VS Code Copilot using `docker run` as the command
- Table of Contents entry linking to the new section

## Version Compatibility

- **Python**: N/A inside the image — the image uses `python:3.11-slim` base
- **Docker**: Requires Docker 20.10+ (for `buildx`). Standard `docker build` works on older versions without multi-arch support.
- **Platforms**: `linux/amd64` and `linux/arm64` via `docker buildx`; Apple Silicon (M-series) native `arm64` via standard `docker build`
- **No branching needed**: No Python version branching — the Docker image pins `python:3.11-slim`

## Platform Behavior Notes

- **stdio transport**: The MCP server communicates via stdin/stdout. The `-i` flag on `docker run` is mandatory to keep stdin open; omitting it will silently break the MCP connection.
- **No HEALTHCHECK**: Stdio transport does not expose a port; HEALTHCHECK is not applicable.
- **Log directory**: Inside the container, logs go to `/app/logs`. When no volume is mounted, logs are ephemeral. If the `logs/` directory cannot be created (e.g. read-only filesystem), the server continues without file logging — console (stderr) logging still works.
- **Non-root user**: The container runs as `mcpuser` (uid/gid 1000) for security. Files under `/app` (including logs) are pre-owned by `mcpuser` during the image build.
- **API key prefix**: `DCTAPIClient` prepends `apk ` automatically — users must not add the prefix in env vars passed to the container.
- **`_get_project_root()` in logging.py**: Inside the Docker image, `__file__` resolves correctly under `/app/src/dct_mcp_server/core/logging.py`, so `parents[3]` gives `/app`. The `logs/` directory is pre-created and owned by `mcpuser` during the build.

## Open Questions / Risks

- **Image publishing**: The Dockerfile is added for local builds. No CI pipeline to publish to Docker Hub or GHCR is in scope for this ticket. If publishing is needed later, a GitHub Actions workflow can be added separately.
- **Windows Docker Desktop path separators**: Volume mount paths on Windows PowerShell use forward slashes (`${PWD}/logs:/app/logs`). This has been verified to work with Docker Desktop; confirm on WSL2 if needed.
- **File logging silently absent in Docker** (non-blocking, known limitation): When the package is installed via `pip install` in the Docker image, `_get_project_root()` resolves from site-packages (e.g. `/usr/local/lib/python3.11`), not `/app`. The log directory attempt will be at a wrong path, fail with a permissions error (non-root user), and be silently caught by the graceful mkdir fix. File logging is absent in the container; users should use `docker logs <container>` instead. The README Docker section should document this.
- **`.mcp.json` not excluded from Docker image**: The `.mcp.json` at the repo root is a dev tool config file. It should be added to `.dockerignore` to keep the image clean.

## Acceptance Criteria

1. A `Dockerfile` exists at the repo root and builds successfully with `docker build -t dct-mcp-server .`
2. The container runs as a non-root user (`mcpuser`, uid 1000)
3. The server starts and responds to MCP tool calls when run via `docker run --rm -i -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server`
4. Multi-arch build works: `docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server .`
5. `README.md` contains a `## Docker` section with build, run, log-persistence, and client-config examples
6. Log directory creation failure in a restricted Docker environment does not crash the server
7. `.dockerignore` is present and excludes secrets (`.env`), Python artifacts, and development files
