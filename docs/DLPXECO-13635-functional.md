# Functional Specification: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Generated from**: Acceptance criteria in Jira ticket and vision doc

---

## FR-001: Create a production-ready Dockerfile

### Description

Provides a `Dockerfile` at the project root that builds a self-contained Docker image of the DCT MCP Server using a Python 3.11 slim base image, installs all dependencies from `pyproject.toml`, and sets the correct entry point so `docker run` starts the server.

### Input

- Project source files at build time: `src/`, `pyproject.toml`, `requirements.txt`, `uv.lock`
- Runtime env vars: `DCT_API_KEY` (required), `DCT_BASE_URL` (required), `DCT_TOOLSET` (optional), `DCT_VERIFY_SSL` (optional), `DCT_LOG_LEVEL` (optional), `DCT_TIMEOUT` (optional), `DCT_MAX_RETRIES` (optional), `IS_LOCAL_TELEMETRY_ENABLED` (optional)

### Processing

1. Start from `python:3.11-slim` base image
2. Set `WORKDIR /app`
3. Copy `pyproject.toml` and `requirements.txt` into the image
4. Run `pip install --no-cache-dir .` to install the package and all dependencies
5. Copy remaining source files (`src/`, any config files needed at runtime)
6. Set `ENTRYPOINT ["dct-mcp-server"]` using the CLI entry point defined in `pyproject.toml`
7. Expose no port by default (stdio mode); document port binding in README for HTTP mode
8. Do not bake in `DCT_API_KEY` or `DCT_BASE_URL` — leave them as runtime env vars

### Output

- Success: A Docker image that when run starts the MCP server, prints startup banner to stdout, and waits for MCP protocol input
- Failure (missing env vars): Server exits with a clear error message indicating which env var is missing (existing behaviour from `config.py`)
- Side effect: `.dockerignore` file created to exclude `logs/`, `venv/`, `.claude/`, `docs/`, `*.pyc`, `__pycache__/`, `.git/`

### Acceptance Criteria

- [ ] AC-1: Given a clean Docker daemon, when `docker build -t dct-mcp-server .` is run from the project root, then the build completes with exit code 0 and no errors
- [ ] AC-2: Given the image is built, when `docker run -e DCT_API_KEY=test -e DCT_BASE_URL=https://fake.dct dct-mcp-server` is run, then the server starts and its startup banner appears in stdout within 10 seconds
- [ ] AC-3: Given the image is built, when env vars are omitted, then the server exits with an informative error (not a Python traceback) indicating the missing configuration
- [ ] AC-4: The image does not contain `DCT_API_KEY` or `DCT_BASE_URL` values baked in — confirmed by inspecting image layers with `docker inspect`

---

## FR-002: Create a .dockerignore file

### Description

Provides a `.dockerignore` file that excludes non-essential files from the Docker build context, reducing image size and preventing accidental inclusion of secrets, logs, or development artefacts.

### Input

- Project root directory structure at build time

### Processing

1. Create `.dockerignore` at the project root
2. Exclude: `logs/`, `venv/`, `.venv/`, `.claude/`, `docs/`, `*.pyc`, `__pycache__/`, `.git/`, `.github/`, `*.md` (except `README.md`), `.env`, `*.bat` (Windows scripts not needed in Linux container), `artifact.json`
3. Include: `src/`, `pyproject.toml`, `requirements.txt`

### Output

- Success: `.dockerignore` file at project root; `docker build` context is significantly smaller
- Side effect: Build time reduced by excluding large directories like `.git/` and `docs/`

### Acceptance Criteria

- [ ] AC-1: Given `.dockerignore` exists, when `docker build` runs, then `logs/` and `.claude/` directories are not present in the final image
- [ ] AC-2: The `.dockerignore` excludes `.env` files to prevent credential files being accidentally included in the build context

---

## FR-003: Add Docker section to README.md

### Description

Updates `README.md` with a dedicated `## Docker` section containing step-by-step instructions for building and running the MCP server in a Docker container, including a placeholder registry pull URL, environment variable configuration, and how to connect an MCP client to the containerised server.

### Input

- Existing `README.md` content
- Docker operational model: Linux containers on Docker Desktop (Windows compatible), port-based MCP client connection

### Processing

1. Add `## Docker` to the Table of Contents in README.md
2. Insert a new `## Docker` section after `## Advanced Installation` section
3. Section must contain the following sub-sections:
   a. **Quick Start (Docker Registry)**: `docker pull <registry-placeholder>/dct-mcp-server:latest` with a clear note that the placeholder will be updated when the image is published
   b. **Build from Source**: `docker build -t dct-mcp-server .` command
   c. **Run the Container**: `docker run` command with all relevant `-e` flags for env vars, and `-p 6790:6790` for port mapping
   d. **Windows Compatibility**: Note that Linux containers (Docker Desktop default) are used; no WSL required
   e. **Connect Your MCP Client**: Show the `"port": 6790` JSON snippet for connecting Claude Desktop / Cursor / VS Code to the running container
   f. **Environment Variables Reference**: Refer readers to the existing Environment Variables section

### Output

- Success: `README.md` updated with `## Docker` section; Table of Contents updated with link
- Failure: No change to existing README content (additive only — existing sections must not be modified or removed)

### Acceptance Criteria

- [ ] AC-1: Given the updated README, when an engineer searches for "Docker" in the document, they find a complete section with build, run, and client connection instructions
- [ ] AC-2: The Docker section contains the placeholder registry pull command clearly marked as a placeholder (e.g. with a comment or note)
- [ ] AC-3: The README Docker section contains a working `docker run` example with all required env vars shown
- [ ] AC-4: The `## Docker` entry appears in the Table of Contents and links to the correct section anchor

---

## FR-004: Windows Docker compatibility documented and verified

### Description

Ensures the Docker image works on Windows by using a Linux-based image (compatible with Docker Desktop on Windows in Linux container mode), and documents Windows-specific guidance in the README so Windows users can follow the same Docker workflow.

### Input

- Docker Desktop on Windows (Linux container mode — the default)
- `DCT_API_KEY` and `DCT_BASE_URL` env vars set via PowerShell or Command Prompt

### Processing

1. Use `python:3.11-slim` (Linux-based) — this runs correctly under Docker Desktop on Windows in Linux mode
2. In the README Docker section, add a callout: "Windows users: Ensure Docker Desktop is set to use Linux containers (the default). This image does not use Windows-native containers."
3. Provide a Windows PowerShell `docker run` example using `$env:DCT_API_KEY` or `-e` flags
4. Do not use Linux-only shell features (e.g., `/bin/bash` scripts) in the Dockerfile CMD/ENTRYPOINT — use the Python entry point directly so it runs identically on both platforms

### Output

- Success: Windows users running Docker Desktop in Linux container mode can `docker build` and `docker run` using the same commands as Linux users (with PowerShell env var syntax differences noted)
- The README Windows callout is concise and non-blocking for Linux users

### Acceptance Criteria

- [ ] AC-1: The Dockerfile uses `python:3.11-slim` (Linux base), ensuring it runs under Docker Desktop on Windows without requiring Windows Server containers
- [ ] AC-2: The README Docker section includes a Windows PowerShell `docker run` example or clearly documents that the Linux example works unchanged on Docker Desktop for Windows
- [ ] AC-3: The ENTRYPOINT in the Dockerfile uses the `dct-mcp-server` CLI entry point (not a `.sh` script), making it OS-agnostic

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| API backward compatibility preserved | Docker packaging must not change MCP tool behaviour or env var names | Manual: compare tool list before/after containerisation | | |
| No credentials baked into image | `DCT_API_KEY` and `DCT_BASE_URL` must never appear as `ARG` or `ENV` with values in the Dockerfile | grep Dockerfile for `DCT_API_KEY` and `DCT_BASE_URL` — neither should appear as a set value | | |
| Existing README sections unchanged | The Docker section is additive only — no existing README content is removed or reordered | diff README.md before and after; verify no existing headings removed | | |
| Image uses minimal base | Use `python:3.11-slim` not `python:3.11` (full) to minimise attack surface and image size | Check `FROM` line in Dockerfile | | |
| Scope limited to stated ticket | No refactoring of Python source, toolset config, or non-Docker files | git diff must show only Dockerfile, .dockerignore, README.md, and docs/ changes | | |

---

## Edge Cases

- EC-1: User runs `docker build` without a `.dockerignore` — large `.git/` directory included in context, causing slow build; mitigated by `.dockerignore` being part of this feature
- EC-2: `DCT_BASE_URL` contains a trailing `/dct` path — server rejects it with existing validation; Docker does not change this behaviour; document in README that the URL format requirement is unchanged
- EC-3: User attempts to run with `docker run dct-mcp-server` without any `-e` flags — server should exit with the existing config validation error, not a Python import error; this is existing behaviour from `config.py`
- EC-4: MCP client configured to use stdio transport tries to connect to dockerised server — stdio does not cross container boundaries; README must document the port-based connection method as the correct approach for containerised deployment
- EC-5: User on Windows with Docker Desktop in Windows container mode (not the default) — the Linux image will not run; document that Linux container mode is required

## Error Scenarios

- ERR-1: `docker build` fails due to network unavailability (cannot fetch Python packages) — standard Docker network error; no special handling needed; user should retry with network access
- ERR-2: Port 6790 already in use when running the container — Docker will report the port conflict; README should document using `-p <alternative-port>:6790` to remap
- ERR-3: Dockerfile `COPY` fails because source path has changed — would indicate a project restructure; mitigated by using `src/` as the copy target which is stable
- ERR-4: `pip install .` inside Docker fails for a dependency — would surface as a build error; standard Python packaging troubleshooting applies; no special Docker handling needed

## Performance Considerations

- Docker image build should complete in under 3 minutes on a standard developer machine with network access (caching layers after the first build will be under 30 seconds for code-only changes)
- Container startup time should be under 10 seconds (matching SC2); the server itself is I/O-bound on first tool generation, not CPU-bound
- Image size target: under 300 MB using `python:3.11-slim` base with only production dependencies installed (no dev tools, no test frameworks)

---
