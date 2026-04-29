# Functional Specification: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Generated from**: Acceptance criteria in Jira ticket DLPXECO-13635 — Support for Hosting MCP Server in docker container

---

## FR-001: Provide a Dockerfile for containerised deployment

### Description
Enables building a Docker image that packages the DCT MCP Server and all its dependencies, allowing operators to run the server in a container on Linux and Windows (via Docker Desktop with Linux containers).

### Input
- Repository source code at the repository root
- `pyproject.toml` / `requirements.txt` specifying Python dependencies
- `DCT_API_KEY` environment variable (required at runtime, not at build time)
- `DCT_BASE_URL` environment variable (required at runtime, not at build time)
- Optional runtime env vars: `DCT_TOOLSET`, `DCT_VERIFY_SSL`, `DCT_LOG_LEVEL`, `DCT_TIMEOUT`, `DCT_MAX_RETRIES`, `IS_LOCAL_TELEMETRY_ENABLED`

### Processing
1. Use `python:3.11-slim` (or equivalent pinned slim variant) as the base image
2. Set working directory to `/app`
3. Copy `pyproject.toml`, `requirements.txt`, and source code into the image
4. Install dependencies via `pip install` (or `uv pip install` if uv is available in the build context)
5. Set `CMD` or `ENTRYPOINT` to launch `dct-mcp-server` (the package CLI entry point defined in `pyproject.toml`)
6. Expose any required ports (if applicable — MCP stdio mode may not need a port)
7. Ensure the image is compatible with Linux/amd64 and Windows Docker Desktop (Linux containers mode)

### Output
- Success: Docker image named `dct-mcp-server` (or as specified) that starts the MCP server process on `docker run`
- Failure (build): clear error from `pip install` or missing dependency — build exits non-zero
- Failure (runtime): container exits with a clear error message if `DCT_API_KEY` or `DCT_BASE_URL` is not set

### Acceptance Criteria
- [ ] AC-1: Given the repository root, when `docker build -t dct-mcp-server .` is run on Linux, then the build completes with exit code 0
- [ ] AC-2: Given the built image and required env vars, when `docker run --rm -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server` is run, then the MCP server process starts and does not exit immediately
- [ ] AC-3: Given missing `DCT_API_KEY`, when the container starts, then it exits with a clear error message (not a silent crash)
- [ ] AC-4: Given the built image, when run on Windows Docker Desktop (Linux containers mode), then the container starts without path or line-ending errors

---

## FR-002: Provide a docker-compose.yml for single-command startup

### Description
Enables operators to start the DCT MCP Server container with a single `docker-compose up` command, with environment variable configuration managed via a `.env` file or inline compose configuration.

### Input
- `docker-compose.yml` file at the repository root
- `.env` file (optional) or inline environment variable definitions with `DCT_API_KEY` and `DCT_BASE_URL`

### Processing
1. Define a `dct-mcp-server` service in `docker-compose.yml`
2. Reference the local `Dockerfile` (or a registry image placeholder) as the build source
3. Map required environment variables from the host or `.env` file into the container
4. Include a volume mount for `logs/` directory to persist log files on the host (optional but recommended)
5. Document that `docker-compose up --build` triggers a fresh build

### Output
- Success: `docker-compose up` starts the MCP server container in the foreground (or `-d` for detached)
- Failure (missing env): compose startup fails with a clear error that `DCT_API_KEY` or `DCT_BASE_URL` is not set

### Acceptance Criteria
- [ ] AC-1: Given a valid `.env` file with `DCT_API_KEY` and `DCT_BASE_URL`, when `docker-compose up --build` is run, then the container builds and starts successfully
- [ ] AC-2: Given no `.env` file and no inline env vars, when `docker-compose up` is run, then the container exits with a clear error about missing configuration
- [ ] AC-3: Given the compose file, when `docker-compose down` is run, then the container is stopped and removed cleanly

---

## FR-003: Add Docker deployment documentation to README

### Description
Provides clear, step-by-step instructions in the README for building and running the MCP server via Docker, covering both Linux and Windows users, and includes a placeholder for the official Docker image URL.

### Input
- Existing `README.md` at repository root
- The `Dockerfile` and `docker-compose.yml` added by FR-001 and FR-002
- A placeholder Docker image URL (e.g. `ghcr.io/delphix/dct-mcp-server:latest` — clearly marked as "coming soon")

### Processing
1. Add a new `## Running with Docker` section to `README.md` (or equivalent heading)
2. Include subsections: `Prerequisites`, `Build the image`, `Run with docker run`, `Run with docker-compose`
3. Add Windows-specific notes under a `### Windows (Docker Desktop)` subsection — note that Linux containers mode is required
4. Add a `### Pre-built image (coming soon)` subsection with the placeholder registry URL and a note that it will be available once published
5. Preserve all existing README sections — do not remove or reorder any existing content

### Output
- Success: README contains the new Docker section with all subsections populated with correct, runnable commands
- No existing README sections are removed or moved

### Acceptance Criteria
- [ ] AC-1: Given the updated README, when a user follows the `Build the image` instructions on Linux, then `docker build` completes successfully
- [ ] AC-2: Given the updated README, when a Windows user follows the `Windows (Docker Desktop)` instructions, then they can run the container without additional research
- [ ] AC-3: Given the placeholder URL section, when a reviewer reads it, then it is clearly marked as "coming soon" and does not appear to be a live, pullable image
- [ ] AC-4: Given the updated README, when the existing README sections are reviewed, then no existing content has been removed or reordered

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| Scope limited to packaging | No changes to server runtime code (`src/`) beyond what is required for container compatibility | `git diff --stat` review — `src/` changes must be minimal and justified | | |
| API backward compatibility | Existing startup scripts (`start_mcp_server_*.sh`, `*.bat`) must remain functional after this change | Manual verification that existing scripts still work | | |
| No hardcoded credentials | `Dockerfile` and `docker-compose.yml` must not contain hardcoded `DCT_API_KEY` or `DCT_BASE_URL` values | Grep for hardcoded key patterns in new files | | |
| Cross-platform line endings | `Dockerfile` and shell commands within it must use LF line endings to avoid Windows-host build failures | `file Dockerfile` check; no CRLF in Dockerfile | | |

---

## Edge Cases

- EC-1: User runs `docker build` on a machine with no internet access → build fails at `pip install`; mitigation: document offline build option or multi-stage build with pre-downloaded wheels
- EC-2: `DCT_BASE_URL` includes a trailing `/dct` path component → container starts but API calls fail silently; mitigation: add startup validation that strips or warns about the `/dct` suffix (consistent with existing server behavior)
- EC-3: User mounts a local `logs/` directory that already contains old log files → new container writes into existing log directory; this is acceptable and expected behavior, no special handling needed
- EC-4: Docker image is built on ARM64 (Apple Silicon) but deployed on amd64 → multi-arch build or explicit platform flag needed; document `--platform linux/amd64` in README
- EC-5: User provides `DCT_VERIFY_SSL=true` but the DCT server uses a self-signed certificate → SSL verification fails inside container; document that the CA certificate can be injected via volume mount or `REQUESTS_CA_BUNDLE` env var

## Error Scenarios

- ERR-1: `pip install` fails inside Docker build due to a missing system dependency → add required system packages to `apt-get install` in Dockerfile; build exits with clear pip error message
- ERR-2: Container starts but MCP server crashes immediately → container exit code is non-zero; operator should check `docker logs <container>` — document this in README troubleshooting section
- ERR-3: `docker-compose.yml` references a registry image URL that does not yet exist → `docker-compose pull` fails; mitigation: configure compose to build locally by default (`build: .`) so pull is not attempted unless explicitly requested

## Performance Considerations

N/A — Docker packaging is a build-time concern. The containerised server has the same runtime performance characteristics as the non-containerised version. Image size should be minimised using `python:3.11-slim` to reduce pull times, but no specific performance SLA is required for image build or container startup.

---
