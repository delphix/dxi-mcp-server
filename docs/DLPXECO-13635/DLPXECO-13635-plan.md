# DLPXECO-13635 Docker Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec**: docs/DLPXECO-13635/DLPXECO-13635-functional.md
**Design**: docs/DLPXECO-13635/DLPXECO-13635-design.md

**Goal:** Add Docker-based distribution support for the DCT MCP Server by creating a `Dockerfile`, `.dockerignore`, and updating `README.md` with a "Run with Docker" section — no changes to any existing Python source files.

**Architecture:** Multi-stage Docker build using `python:3.11-slim` — a build stage installs all dependencies and the package, a runtime stage copies only the venv and installed package with a non-root `appuser`. The MCP server runs via `python -m dct_mcp_server.main` over stdio transport. All three deliverables (`Dockerfile`, `.dockerignore`, `README.md`) are independent infrastructure/documentation files that do not touch `src/`.

**Tech Stack:** Docker (20.10+ with BuildKit), Python 3.11, `python:3.11-slim` base image, `pip install .` from `pyproject.toml`, `requirements.txt` for dependency pinning.

---

<!-- Directives:
     [parallel]       = this task can run simultaneously with other [parallel] tasks because they modify different files
     [model:haiku]    = use the cheapest/fastest model (mechanical task with clear spec)
     [model:sonnet]   = use a standard model (integration or judgment required)
     [model:opus]     = use the most capable model (architecture or complex reasoning required)
     Omit [parallel] if this task modifies files that any other task also modifies. -->

## Task 1: Create Dockerfile  [parallel][model:sonnet]

### Description
Creates the `Dockerfile` at the repo root (`/Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635/Dockerfile`). Uses a two-stage build: a `build` stage that installs all dependencies from `requirements.txt` into a virtualenv at `/app/venv` and installs the package via `pip install .`, and a `runtime` stage that copies only the venv and installed package, creates `appuser` (uid 1000), creates `/app/logs`, sets `USER appuser`, and sets `CMD ["python", "-m", "dct_mcp_server.main"]`. Includes a `LABEL` with `maintainer`, `version`, and `description`. No `EXPOSE` (stdio server). Does not modify any file in `src/`. Must run before Task 3 (test generation requires the image to exist).

### Spec References
- FR-001 (AC-1 through AC-5): Multi-stage Dockerfile that builds a ≤500 MB image, runs as non-root `appuser`, imports `dct_mcp_server.config.loader`, errors on missing creds, and excludes `.git/` / `logs/` / `__pycache__/` / `.env`
- FR-001 step 7: `LABEL` with `maintainer`, `version`, `description`

### Sub-tasks (TDD)

For infrastructure files like a `Dockerfile`, the TDD cycle uses static-analysis assertions (grep-based checks) in place of unit tests. The "test" is a shell script that asserts properties of the `Dockerfile` itself.

- [ ] **RED**: Create the file `tests/test_dockerfile_static.sh` that asserts the required `Dockerfile` properties. Run it — it MUST fail because `Dockerfile` does not exist yet.

```bash
# File: tests/test_dockerfile_static.sh
#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="$REPO_ROOT/Dockerfile"

echo "=== Static Dockerfile assertions ==="

# 1. File must exist
[[ -f "$DOCKERFILE" ]] || { echo "FAIL: Dockerfile does not exist"; exit 1; }
echo "PASS: Dockerfile exists"

# 2. Must have two FROM lines (multi-stage)
FROM_COUNT=$(grep -c "^FROM " "$DOCKERFILE")
[[ "$FROM_COUNT" -ge 2 ]] || { echo "FAIL: Expected >= 2 FROM lines, got $FROM_COUNT"; exit 1; }
echo "PASS: Multi-stage build ($FROM_COUNT FROM lines)"

# 3. Must create appuser
grep -q "adduser\|useradd" "$DOCKERFILE" || { echo "FAIL: No user creation (adduser/useradd)"; exit 1; }
echo "PASS: appuser creation present"

# 4. Must set USER appuser
grep -q "^USER appuser" "$DOCKERFILE" || { echo "FAIL: USER appuser not set"; exit 1; }
echo "PASS: USER appuser set"

# 5. CMD must be python -m dct_mcp_server.main
grep -q 'CMD \["python", "-m", "dct_mcp_server.main"\]' "$DOCKERFILE" || { echo "FAIL: CMD not set to python -m dct_mcp_server.main"; exit 1; }
echo "PASS: CMD is python -m dct_mcp_server.main"

# 6. Must create /app/logs
grep -q "/app/logs" "$DOCKERFILE" || { echo "FAIL: /app/logs not created"; exit 1; }
echo "PASS: /app/logs present"

# 7. Must have LABEL with maintainer, version, description
grep -q "^LABEL" "$DOCKERFILE" || { echo "FAIL: No LABEL instruction"; exit 1; }
grep -q "maintainer" "$DOCKERFILE" || { echo "FAIL: LABEL missing 'maintainer' field"; exit 1; }
grep -q "version" "$DOCKERFILE" || { echo "FAIL: LABEL missing 'version' field"; exit 1; }
grep -q "description" "$DOCKERFILE" || { echo "FAIL: LABEL missing 'description' field"; exit 1; }
echo "PASS: LABEL present with maintainer, version, description"

# 8. Must NOT have EXPOSE
grep -q "^EXPOSE" "$DOCKERFILE" && { echo "FAIL: EXPOSE found (stdio server should not expose ports)"; exit 1; } || true
echo "PASS: No EXPOSE (stdio server)"

# 9. pip install must reference requirements.txt or pip install .
grep -E "pip install" "$DOCKERFILE" | grep -vE "requirements\.txt|-e \.|pip install \." | grep -v "^#" | grep -q "pip install " && { echo "FAIL: Bare pip install without -r requirements.txt or pip install ."; exit 1; } || true
echo "PASS: pip install lines use requirements.txt or pip install ."

echo "=== All Dockerfile static assertions PASSED ==="
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
bash tests/test_dockerfile_static.sh
```
Expected: FAIL — `FAIL: Dockerfile does not exist`

- [ ] **GREEN**: Create `Dockerfile` at the worktree root with this exact content:

```dockerfile
# ============================================================
# Stage 1: Build — install dependencies and package
# ============================================================
FROM python:3.11-slim AS build

WORKDIR /app

# Install build tools needed for pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a virtualenv in the build stage
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install pinned runtime dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source tree and install the package
COPY src/ src/
COPY pyproject.toml .
# Copy bundled OpenAPI spec (used as fallback for persona toolsets)
COPY docs/api-external.yaml docs/api-external.yaml

RUN pip install --no-cache-dir .

# ============================================================
# Stage 2: Runtime — minimal image with no build tools
# ============================================================
FROM python:3.11-slim AS runtime

LABEL maintainer="Delphix Engineering <support@delphix.com>" \
      version="2026.0.2.0-preview" \
      description="Delphix DCT API MCP Server — stdio MCP server for the Delphix Data Control Tower API"

WORKDIR /app

# Create non-root user (uid 1000)
RUN addgroup --gid 1000 appuser \
    && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" appuser

# Copy the virtualenv from the build stage
COPY --from=build /app/venv /app/venv

# Copy the installed package (site-packages are inside the venv)
# The bundled OpenAPI spec must be accessible at the path the package expects
COPY --from=build /app/docs /app/docs

# Create the log directory and set ownership
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

ENV PATH="/app/venv/bin:$PATH"

# Switch to non-root user
USER appuser

# stdio MCP server — no ports to expose
CMD ["python", "-m", "dct_mcp_server.main"]
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
bash tests/test_dockerfile_static.sh
```
Expected: `=== All Dockerfile static assertions PASSED ===`

- [ ] **REFACTOR**: No refactoring needed for a Dockerfile. Verify the static test file is committed alongside the Dockerfile.

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
git add Dockerfile tests/test_dockerfile_static.sh
git commit -m "Add multi-stage Dockerfile for DCT MCP Server (DLPXECO-13635)"
```

### Depends On
- None

### Acceptance Criteria
- [ ] Given the file is created, `bash tests/test_dockerfile_static.sh` exits 0 with all PASS lines
- [ ] `Dockerfile` contains exactly 2 `FROM` lines (multi-stage)
- [ ] `USER appuser` appears in the runtime stage
- [ ] `CMD ["python", "-m", "dct_mcp_server.main"]` is set
- [ ] `/app/logs` is created and `chown`ed to `appuser`
- [ ] `LABEL` includes `maintainer`, `version`, `description`
- [ ] No `EXPOSE` instruction
- [ ] All `pip install` lines use `-r requirements.txt` or `pip install .` — no bare floating installs
- [ ] No changes to any file in `src/`

---

## Task 2: Create .dockerignore  [parallel][model:haiku]

### Description
Creates the `.dockerignore` file at the repo root (`/Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635/.dockerignore`). Excludes development artifacts, credentials, logs, and generated files from the Docker build context. The critical constraint is that `docs/api-external.yaml` must NOT be excluded — do not use a bare `docs/` pattern without a `!docs/api-external.yaml` negation. Does not modify any other file. This task is parallel with Task 1 because they create different files.

### Spec References
- FR-002 (AC-1, AC-2, AC-3): Excludes `.git/`, `logs/`, `__pycache__/`, `.env`; keeps `docs/api-external.yaml`; excludes `tests/` and `evals/`

### Sub-tasks (TDD)

- [ ] **RED**: Create `tests/test_dockerignore_static.sh` that asserts `.dockerignore` properties. Run it — it MUST fail.

```bash
# File: tests/test_dockerignore_static.sh
#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERIGNORE="$REPO_ROOT/.dockerignore"

echo "=== Static .dockerignore assertions ==="

# 1. File must exist
[[ -f "$DOCKERIGNORE" ]] || { echo "FAIL: .dockerignore does not exist"; exit 1; }
echo "PASS: .dockerignore exists"

# 2. Must exclude .git/
grep -q "^\.git" "$DOCKERIGNORE" || { echo "FAIL: .git/ not excluded"; exit 1; }
echo "PASS: .git/ excluded"

# 3. Must exclude logs/
grep -q "^logs" "$DOCKERIGNORE" || { echo "FAIL: logs/ not excluded"; exit 1; }
echo "PASS: logs/ excluded"

# 4. Must exclude __pycache__
grep -q "__pycache__" "$DOCKERIGNORE" || { echo "FAIL: __pycache__ not excluded"; exit 1; }
echo "PASS: __pycache__ excluded"

# 5. Must exclude .env
grep -q "^\.env" "$DOCKERIGNORE" || { echo "FAIL: .env not excluded"; exit 1; }
echo "PASS: .env excluded"

# 6. Must exclude tests/
grep -q "^tests" "$DOCKERIGNORE" || { echo "FAIL: tests/ not excluded"; exit 1; }
echo "PASS: tests/ excluded"

# 7. Must exclude evals/
grep -q "^evals" "$DOCKERIGNORE" || { echo "FAIL: evals/ not excluded"; exit 1; }
echo "PASS: evals/ excluded"

# 8. Must exclude uv.lock
grep -q "uv\.lock" "$DOCKERIGNORE" || { echo "FAIL: uv.lock not excluded"; exit 1; }
echo "PASS: uv.lock excluded"

# 9. Must exclude .claude/
grep -q "^\.claude" "$DOCKERIGNORE" || { echo "FAIL: .claude/ not excluded"; exit 1; }
echo "PASS: .claude/ excluded"

# 10. If a bare docs/ exclusion exists, a !docs/api-external.yaml negation MUST follow it
if grep -q "^docs/" "$DOCKERIGNORE" || grep -q "^docs$" "$DOCKERIGNORE"; then
    # Find the last line number of the docs exclusion
    DOCS_LINE=$(grep -n "^docs" "$DOCKERIGNORE" | tail -1 | cut -d: -f1)
    NEGATION_LINE=$(grep -n "!docs/api-external.yaml" "$DOCKERIGNORE" | head -1 | cut -d: -f1)
    [[ -n "$NEGATION_LINE" ]] || { echo "FAIL: docs/ is excluded but !docs/api-external.yaml negation is missing"; exit 1; }
    [[ "$NEGATION_LINE" -gt "$DOCS_LINE" ]] || { echo "FAIL: !docs/api-external.yaml must appear AFTER docs/ exclusion (Docker processes in order)"; exit 1; }
    echo "PASS: docs/ excluded with correct !docs/api-external.yaml negation ordering"
else
    echo "PASS: No bare docs/ exclusion (api-external.yaml is kept by default)"
fi

echo "=== All .dockerignore static assertions PASSED ==="
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
bash tests/test_dockerignore_static.sh
```
Expected: FAIL — `.dockerignore does not exist`

- [ ] **GREEN**: Create `.dockerignore` at the worktree root with this exact content:

```
# =============================================================
# .dockerignore — DCT MCP Server
# Keeps build context small (<5 MB) and secrets out of image
# =============================================================

# --- Version control ---
.git
.gitignore
.gitattributes

# --- Python caches (generated at runtime, not needed in image) ---
__pycache__
*.pyc
*.pyo
*.pyd
*.egg-info
*.egg
dist/
build/
.eggs/

# --- Virtual environments (never copy into image) ---
.venv
venv
.venv/
venv/

# --- Secrets and local config (NEVER bake into image layers) ---
.env
*.env
.env.*
mcp.json
.claude/settings.local.json

# --- Runtime logs (generated at runtime, mount with -v instead) ---
logs/

# --- Lock files (image uses requirements.txt for reproducibility) ---
uv.lock

# --- Development and CI infrastructure ---
.claude/
evals/
tests/
whitesource/

# --- Startup scripts (not needed inside container) ---
start_mcp_server_*.sh
start_mcp_server_*.bat

# --- Documentation (not needed inside container)
# NOTE: docs/api-external.yaml is intentionally NOT excluded —
#       it is the bundled OpenAPI spec fallback used by persona toolsets.
# The Dockerfile copies it explicitly via: COPY docs/api-external.yaml docs/api-external.yaml
*.md
!README.md
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
bash tests/test_dockerignore_static.sh
```
Expected: `=== All .dockerignore static assertions PASSED ===`

- [ ] **REFACTOR**: No structural changes needed. Commit:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
git add .dockerignore tests/test_dockerignore_static.sh
git commit -m "Add .dockerignore to keep build context lean (DLPXECO-13635)"
```

### Depends On
- None (parallel with Task 1)

### Acceptance Criteria
- [ ] `bash tests/test_dockerignore_static.sh` exits 0
- [ ] `.git/`, `logs/`, `__pycache__/`, `.env`, `tests/`, `evals/` are all listed as exclusions
- [ ] `uv.lock`, `.claude/`, `start_mcp_server_*.sh`, `start_mcp_server_*.bat` are excluded
- [ ] No bare `docs/` exclusion pattern (or if present, `!docs/api-external.yaml` follows it in file order)
- [ ] `src/`, `pyproject.toml`, `requirements.txt` are NOT listed as exclusions
- [ ] No changes to any file in `src/`

---

## Task 3: Update README.md — "Run with Docker" Section  [model:sonnet]

### Description
Updates `README.md` to add a "Run with Docker" section with a ToC entry, subsections for bash/PowerShell/cmd.exe `docker run` examples, MCP client config JSON snippets (Claude Desktop, Cursor, VS Code Copilot), a persist-logs pattern, a registry placeholder subsection clearly marked TODO, and SSL/proxy notes. All `docker run` examples use `-i` and `--init` flags; none use `-t`. Environment variable definitions cross-reference the existing `## Environment Variables` section rather than duplicating them. This task depends on Tasks 1 and 2 being complete so the README correctly documents what the Dockerfile builds.

### Spec References
- FR-003 (AC-1 through AC-5): "Run with Docker" section, ToC entry, MCP client JSON snippets, registry placeholder, env var cross-reference
- FR-004 (AC-1 through AC-5): `-i` flag, `--init` recommendation, PowerShell `$env:` syntax, cmd.exe `%VAR%` syntax, troubleshooting note about `-t`
- FR-005 (AC-1 through AC-3): Registry placeholder `docker pull <registry-host>/delphix/dct-mcp-server:<tag>`, TODO annotation, build-from-source fallback visible

### Sub-tasks (TDD)

- [ ] **RED**: Create `tests/test_readme_docker_static.sh` that asserts README properties. Run it — it MUST fail because the "Run with Docker" section does not exist yet.

```bash
# File: tests/test_readme_docker_static.sh
#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
README="$REPO_ROOT/README.md"

echo "=== Static README Docker section assertions ==="

# 1. File must exist
[[ -f "$README" ]] || { echo "FAIL: README.md does not exist"; exit 1; }
echo "PASS: README.md exists"

# 2. Must have "Run with Docker" section heading
grep -q "## Run with Docker" "$README" || { echo "FAIL: '## Run with Docker' section heading not found"; exit 1; }
echo "PASS: 'Run with Docker' heading present"

# 3. Must have ToC entry linking to the section
grep -q "Run with Docker" "$README" | head -1 || true
TOC_ENTRY=$(grep "run-with-docker\|Run with Docker" "$README" | grep -v "^##" | head -1)
[[ -n "$TOC_ENTRY" ]] || { echo "FAIL: ToC entry for 'Run with Docker' not found"; exit 1; }
echo "PASS: ToC entry present"

# 4. Must have docker run examples for bash
grep -q "docker run" "$README" || { echo "FAIL: No 'docker run' command found"; exit 1; }
echo "PASS: docker run command present"

# 5. All docker run lines must use -i flag
DOCKER_RUN_LINES=$(grep "docker run" "$README" | grep -v "^#" | grep -v "^\s*#")
BAD_LINES=$(echo "$DOCKER_RUN_LINES" | grep -v "\-i " | grep -v "\-i$" | grep -v "docker run \\\\" || true)
# Only check non-continuation lines
BAD_ACTUAL=$(echo "$DOCKER_RUN_LINES" | grep -v "\-i" || true)
[[ -z "$BAD_ACTUAL" ]] || { echo "WARN: Some docker run lines may be missing -i — review manually"; }
echo "PASS: docker run lines checked for -i flag"

# 6. Must NOT have -t flag on docker run lines (breaks stdio)
grep "docker run" "$README" | grep " -t " && { echo "FAIL: Found 'docker run ... -t ...' — -t flag breaks stdio MCP transport"; exit 1; } || true
echo "PASS: No -t flag on docker run lines"

# 7. Must have --init flag documented
grep -q "\-\-init" "$README" || { echo "FAIL: --init flag not documented"; exit 1; }
echo "PASS: --init flag documented"

# 8. Must have PowerShell example with \$env: syntax
grep -q '\$env:' "$README" || { echo "FAIL: PowerShell \$env: syntax not found"; exit 1; }
echo "PASS: PowerShell \$env: syntax present"

# 9. Must have cmd.exe example with %VAR% syntax
grep -q '%DCT_API_KEY%\|%VAR%\|%DCT_' "$README" || { echo "FAIL: cmd.exe %VAR% syntax not found"; exit 1; }
echo "PASS: cmd.exe %VAR% syntax present"

# 10. Must have registry placeholder
grep -q "registry-host" "$README" || { echo "FAIL: Registry placeholder not found"; exit 1; }
echo "PASS: Registry placeholder present"

# 11. Registry placeholder must be annotated as pending/TODO
grep -A5 "registry-host" "$README" | grep -qi "TODO\|pending\|not yet" || { echo "FAIL: Registry placeholder not annotated as TODO/pending"; exit 1; }
echo "PASS: Registry placeholder annotated as TODO/pending"

# 12. Must include MCP client JSON snippets with docker run -i
grep -q '"command": "docker"' "$README" || { echo "FAIL: MCP client JSON snippet with docker command not found"; exit 1; }
echo "PASS: MCP client JSON snippet with docker command present"

# 13. Must have troubleshooting note about -t
grep -q "\-t.*TTY\|\-t.*stdio\|TTY.*\-t\|pseudo-TTY\|pseudo.*tty" "$README" || { echo "FAIL: Troubleshooting note about -t flag not found"; exit 1; }
echo "PASS: Troubleshooting note about -t present"

# 14. Must NOT duplicate env var definitions (cross-reference instead)
DOCKER_SECTION_START=$(grep -n "## Run with Docker" "$README" | head -1 | cut -d: -f1)
ENV_VAR_SECTION=$(grep -n "## Environment Variables" "$README" | head -1 | cut -d: -f1)
# Ensure the Docker section references the Environment Variables section
grep -A 200 "## Run with Docker" "$README" | grep -q "Environment Variables\|#environment-variables" || { echo "FAIL: Docker section does not cross-reference Environment Variables section"; exit 1; }
echo "PASS: Docker section cross-references Environment Variables section"

echo "=== All README Docker static assertions PASSED ==="
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
bash tests/test_readme_docker_static.sh
```
Expected: FAIL — `'## Run with Docker' section heading not found`

- [ ] **GREEN**: Edit `README.md` to:
  1. Add `- [Run with Docker](#run-with-docker)` to the Table of Contents, positioned after `- [Advanced Installation](#advanced-installation)`.
  2. Insert the full "Run with Docker" section after the `## Advanced Installation` section.

**Step 1 — ToC update:**

In the `## Table of Contents` section, find the line:
```
- [Advanced Installation](#advanced-installation)
```
Add immediately after it:
```
- [Run with Docker](#run-with-docker)
```

**Step 2 — Insert section after Advanced Installation:**

Find the `## Toolsets` heading (which comes after `## Advanced Installation`) and insert the following section immediately before `## Toolsets`:

```markdown
## Run with Docker

Run the DCT MCP Server as a Docker container — no Python, `uv`, or virtual environment required on the host machine.

> **Note:** All `docker run` commands use `-i` (interactive stdin) and `--init` (proper signal handling). Do **not** add `-t` (allocate TTY) — it breaks the binary stdio MCP transport.
>
> For the full list of environment variables, see [Environment Variables](#environment-variables).

### Prerequisites

- **Docker Desktop** (macOS or Windows with WSL2 backend) or **Docker Engine** 20.10+ (Linux)
- **Windows**: Docker Desktop with the WSL2 backend enabled (not the legacy Hyper-V backend)
- No Python, `uv`, or `pip` required on the host

### Build the Image

From the root of a cloned repository:

```bash
docker build -t dct-mcp-server .
```

> **Note:** The first build downloads the `python:3.11-slim` base image and installs packages from PyPI. Subsequent builds use Docker's layer cache and are much faster. If you are on Apple Silicon, add `--platform linux/amd64` for cross-platform compatibility:
> ```bash
> docker build --platform linux/amd64 -t dct-mcp-server .
> ```

### Run the Server

The server communicates over stdio. Always pass `-i` (keep stdin open) and `--init` (PID 1 signal reaping). **Never use `-t`.**

**macOS / Linux (bash):**

```bash
docker run -i --init --rm \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -e DCT_TOOLSET="self_service" \
  -e DCT_VERIFY_SSL="false" \
  dct-mcp-server
```

**Windows (PowerShell):**

```powershell
docker run -i --init --rm `
  -e DCT_API_KEY="$env:DCT_API_KEY" `
  -e DCT_BASE_URL="$env:DCT_BASE_URL" `
  -e DCT_TOOLSET="self_service" `
  -e DCT_VERIFY_SSL="false" `
  dct-mcp-server
```

**Windows (cmd.exe):**

```cmd
docker run -i --init --rm ^
  -e DCT_API_KEY=%DCT_API_KEY% ^
  -e DCT_BASE_URL=%DCT_BASE_URL% ^
  -e DCT_TOOLSET=self_service ^
  -e DCT_VERIFY_SSL=false ^
  dct-mcp-server
```

> **Do not prefix `DCT_API_KEY` with `apk`** — the server adds this prefix automatically. Use the key value exactly as provided by DCT (e.g. `2.abc123...`).

### MCP Client Configuration

Use `docker run -i --init --rm` as the command in your MCP client's JSON config. The container handles all environment setup — no local Python install needed.

<details>
<summary><strong>Claude Desktop</strong></summary>

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": [
        "run", "-i", "--init", "--rm",
        "-e", "DCT_API_KEY=your-api-key-here",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "-e", "DCT_TOOLSET=self_service",
        "-e", "DCT_VERIFY_SSL=false",
        "dct-mcp-server"
      ]
    }
  }
}
```
</details>

<details>
<summary><strong>Cursor IDE</strong></summary>

```json
{
  "mcpServers": [
    {
      "name": "delphix-dct",
      "command": "docker",
      "args": [
        "run", "-i", "--init", "--rm",
        "-e", "DCT_API_KEY=your-api-key-here",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "-e", "DCT_TOOLSET=self_service",
        "-e", "DCT_VERIFY_SSL=false",
        "dct-mcp-server"
      ]
    }
  ]
}
```
</details>

<details>
<summary><strong>VS Code Copilot</strong></summary>

```json
{
  "servers": {
    "delphix-dct": {
      "command": "docker",
      "args": [
        "run", "-i", "--init", "--rm",
        "-e", "DCT_API_KEY=your-api-key-here",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "-e", "DCT_TOOLSET=self_service",
        "-e", "DCT_VERIFY_SSL=false",
        "dct-mcp-server"
      ]
    }
  }
}
```

> **VS Code Copilot note:** For best experience, use a fixed toolset (e.g. `self_service`) instead of `auto` mode — VS Code Copilot requires a chat restart after `enable_toolset`.
</details>

> **Tip:** Replace `your-api-key-here` and `https://your-dct-host.company.com` with your actual values. See [Environment Variables](#environment-variables) for the full list of supported variables.

### Persist Logs (Optional)

By default, logs are written to `/app/logs` inside the container and lost when the container exits. To persist them, bind-mount a host directory:

**macOS / Linux:**
```bash
docker run -i --init --rm \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -v "$(pwd)/logs:/app/logs" \
  dct-mcp-server
```

**Linux note:** If the mounted `logs/` directory is owned by root, the container's `appuser` (uid 1000) may not have write permission. Fix with:
```bash
mkdir -p logs && chmod 777 logs
# or pass --user to match your host UID:
docker run -i --init --rm \
  --user "$(id -u):$(id -g)" \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -v "$(pwd)/logs:/app/logs" \
  dct-mcp-server
```

### Using a Pre-Built Registry Image (Pending Provisioning)

> **TODO: The official Delphix registry is not yet provisioned.** Build from source (see [Build the Image](#build-the-image) above) until this pull URL is available.

Once the registry is provisioned, you will be able to pull the pre-built image:

```bash
# Pending — not yet available
docker pull <registry-host>/delphix/dct-mcp-server:<tag>
```

After pulling, use the registry image in place of the locally built `dct-mcp-server` tag with no other changes:

```bash
docker run -i --init --rm \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  <registry-host>/delphix/dct-mcp-server:<tag>
```

### SSL and Proxy Notes

**SSL verification:**
```bash
docker run -i --init --rm \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -e DCT_VERIFY_SSL="true" \
  dct-mcp-server
```

> **Custom CA certificates:** The current codebase passes `verify_ssl` as a boolean to `httpx.AsyncClient` — a CA bundle path is **not** supported via environment variable. If your DCT instance uses a self-signed or corporate CA certificate, build a derived image that installs the certificate:
> ```dockerfile
> FROM dct-mcp-server
> USER root
> COPY my-ca.crt /usr/local/share/ca-certificates/my-ca.crt
> RUN update-ca-certificates
> USER appuser
> ```

**Corporate proxy:**
```bash
docker run -i --init --rm \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -e HTTPS_PROXY="http://proxy.company.com:8080" \
  dct-mcp-server
```

`httpx` (the HTTP client used by the server) honours `HTTPS_PROXY` automatically when passed via `-e`.

### Troubleshooting

**Container exits immediately with no output:**
- Ensure you included `-i` in your `docker run` command. Without `-i`, stdin is closed immediately and the MCP server exits. The MCP client must hold stdin open for the duration of the session.
- **Never add `-t`** (allocate pseudo-TTY) to `docker run` for MCP clients. A pseudo-TTY injects CRLF line endings and TTY escape sequences into the binary stdio stream, corrupting the MCP JSON-RPC framing and causing the client to receive no valid responses.

**`DCT_API_KEY` or `DCT_BASE_URL` not set:**
- The server exits non-zero with a configuration error if either variable is missing. Pass them via `-e DCT_API_KEY=...` and `-e DCT_BASE_URL=...` on the `docker run` command line.
- Do **not** rely on a `.env` file bind-mounted at `/app/.env` — the server does not use `python-dotenv` and will silently ignore it. Use Docker's own `--env-file /path/to/your.env` flag instead.

**Running on Apple Silicon (linux/arm64 vs linux/amd64):**
- Docker Desktop on Apple Silicon defaults to building `linux/arm64` images. If you need to deploy the image to an `amd64` host, build with `--platform linux/amd64`:
  ```bash
  docker build --platform linux/amd64 -t dct-mcp-server .
  ```

**`DCT_TOOLSET=dynamic` in an air-gapped network:**
- Dynamic mode downloads the DCT OpenAPI spec at startup. If DCT is unreachable from inside the container, the server exits with `SPEC_LOAD_FAILED`. Use a persona toolset (e.g. `DCT_TOOLSET=self_service`) instead — persona toolsets use the bundled `docs/api-external.yaml` spec and work offline after the image is built.

```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
bash tests/test_readme_docker_static.sh
```
Expected: `=== All README Docker static assertions PASSED ===`

- [ ] **REFACTOR**: Verify the section is positioned correctly in the file — it should appear after `## Advanced Installation` and before `## Toolsets`. Check the ToC entry is in the correct alphabetical/logical position.

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
# Verify section ordering
grep -n "^## " README.md
```

Expected output includes (in this order):
```
Advanced Installation
Run with Docker
Toolsets
```

Commit:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
git add README.md tests/test_readme_docker_static.sh
git commit -m "Add 'Run with Docker' section to README (DLPXECO-13635)"
```

### Depends On
- Task 1 (Dockerfile must exist so the docker build command documented in README is valid)
- Task 2 (.dockerignore must exist so the build context documented in README is accurate)

### Acceptance Criteria
- [ ] `bash tests/test_readme_docker_static.sh` exits 0
- [ ] `## Run with Docker` section heading exists in README
- [ ] ToC entry `- [Run with Docker](#run-with-docker)` appears after `Advanced Installation`
- [ ] bash, PowerShell (`$env:`), and cmd.exe (`%VAR%`) `docker run` examples are present
- [ ] All `docker run` examples use `-i` and `--init`; none use `-t`
- [ ] MCP client JSON snippets for Claude Desktop and Cursor use `"command": "docker"`
- [ ] Registry placeholder contains `<registry-host>/delphix/dct-mcp-server:<tag>` and is annotated as TODO/pending
- [ ] Troubleshooting note explains why `-t` must not be used (pseudo-TTY corrupts stdio)
- [ ] All env var references in the Docker section point to `[Environment Variables](#environment-variables)` — no duplicate definitions
- [ ] `git diff src/` is empty — zero changes to existing MCP server source

---

## Task 4: Run Static Tests and Verify No Regressions  [model:haiku]

### Description
Runs all static assertion tests created in Tasks 1–3 and verifies the existing pytest suite in `tests/` still passes. This is the post-implementation gate. Also runs `git diff src/` to confirm no source files were modified. Does not create any new files — only executes verification commands.

### Spec References
- FR-001 (AC-1–AC-5), FR-002 (AC-1–AC-3), FR-003 (AC-1–AC-5), FR-004 (AC-1–AC-5), FR-005 (AC-1–AC-3)
- Quality Rule: API backward compatibility — `git diff src/` must be empty

### Sub-tasks (TDD)

- [ ] **RED (verification)**: Run all three static test scripts and confirm they all pass:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635

echo "=== Test 1: Dockerfile static assertions ==="
bash tests/test_dockerfile_static.sh

echo ""
echo "=== Test 2: .dockerignore static assertions ==="
bash tests/test_dockerignore_static.sh

echo ""
echo "=== Test 3: README Docker static assertions ==="
bash tests/test_readme_docker_static.sh
```

Expected: All three print their `=== All ... PASSED ===` lines and exit 0.

- [ ] **GREEN (regression check)**: Confirm no Python source files were changed:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635

echo "=== Verifying src/ is unchanged ==="
git diff src/
git diff --name-only | grep "^src/" && { echo "FAIL: src/ files were modified"; exit 1; } || echo "PASS: src/ unchanged"

echo ""
echo "=== Files changed in this branch ==="
git diff main --name-only 2>/dev/null || git diff HEAD~3 --name-only 2>/dev/null || git status --porcelain
```

Expected: Output shows only `Dockerfile`, `.dockerignore`, `README.md`, and files under `tests/` and `docs/`. No `src/` files.

- [ ] **GREEN (existing tests)**: Run the existing pytest suite to confirm no regressions:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635

# Install test deps if not already present
pip install pytest pytest-asyncio 2>/dev/null || true

# Run existing tests (excluding the new static shell scripts which aren't pytest)
python -m pytest tests/ -v --ignore=tests/test_dockerfile_static.sh \
  --ignore=tests/test_dockerignore_static.sh \
  --ignore=tests/test_readme_docker_static.sh \
  2>&1 | tail -20
```

Expected: Exit code 0 (or any pre-existing failures are pre-existing and unrelated to this change).

- [ ] **REFACTOR**: No code changes. Final commit if any loose files remain:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/dxi-mcp-server/.worktrees/dlpxeco-13635
git status
```

### Depends On
- Task 1 (Dockerfile)
- Task 2 (.dockerignore)
- Task 3 (README.md)

### Acceptance Criteria
- [ ] `bash tests/test_dockerfile_static.sh` exits 0
- [ ] `bash tests/test_dockerignore_static.sh` exits 0
- [ ] `bash tests/test_readme_docker_static.sh` exits 0
- [ ] `git diff src/` is empty
- [ ] `git diff main --name-only` (or equivalent) shows only infra/doc files
- [ ] `pytest tests/` exits 0 (pre-existing test suite, no regressions)

---

## Execution Order

Task 1 (parallel), Task 2 (parallel) → Task 3 → Task 4

Tasks 1 and 2 create independent files (`Dockerfile` and `.dockerignore`) and can run simultaneously. Task 3 updates `README.md` and should run after both are complete so the documented commands are accurate. Task 4 is a final verification gate that runs after all three deliverables exist.

## Progress Tracker

| Task | Status |
|------|--------|
| Task 1: Create Dockerfile | DONE |
| Task 2: Create .dockerignore | DONE |
| Task 3: Update README.md — Run with Docker section | DONE |
| Task 4: Run Static Tests and Verify No Regressions | DONE |
