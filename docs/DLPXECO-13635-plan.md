# DLPXECO-13635: Docker Container Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Docker container support so the DCT MCP Server can be run without Python or `uv` on the host.

**Architecture:** A `Dockerfile` builds a multi-arch, non-root image using `python:3.11-slim`. A `.dockerignore` keeps secrets and dev files out of the image. `README.md` gets a `## Docker` section with build/run/log/client-config examples. A one-line fix to `core/logging.py` moves `logs_dir.mkdir()` inside the `try` block so log-dir creation failures are handled gracefully (needed when running as a non-root installed package).

**Tech Stack:** Docker 20.10+ (buildx for multi-arch), Python 3.11-slim, pip, FastMCP stdio transport.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `src/dct_mcp_server/core/logging.py` | Graceful mkdir — move inside try block |
| Create | `.dockerignore` | Exclude artifacts, secrets, dev files from image |
| Create | `Dockerfile` | Multi-arch, non-root, stdio-transport image |
| Modify | `README.md` | Add TOC entry + `## Docker` section |

---

### Task 1: Fix `logging.py` — graceful log directory creation

**Files:**
- Modify: `src/dct_mcp_server/core/logging.py:82-86`

When the package is installed via `pip` (as in the Docker image), `_get_project_root()` resolves from site-packages, not `/app`. The resulting path for `logs_dir` will be unwritable by the non-root user. Moving `mkdir` inside the `try` block means a permission failure is caught and logged to stderr instead of crashing the server.

- [ ] **Step 1: Verify the current state**

```bash
grep -n "mkdir\|try:" src/dct_mcp_server/core/logging.py
```

Expected output shows `logs_dir.mkdir(exist_ok=True)` on a line **before** the `try:` line:
```
82:        # Create logs directory
83:        logs_dir.mkdir(exist_ok=True)
84:
85:        # Add rotating file handler for global logs
86:        try:
```

- [ ] **Step 2: Move `mkdir` inside the `try` block**

In `src/dct_mcp_server/core/logging.py`, replace the block at lines 82–87 from:

```python
        # Create logs directory
        logs_dir.mkdir(exist_ok=True)

        # Add rotating file handler for global logs
        try:
            global_handler = TimedRotatingFileHandler(
```

to:

```python
        # Add rotating file handler for global logs
        try:
            logs_dir.mkdir(exist_ok=True)
            global_handler = TimedRotatingFileHandler(
```

- [ ] **Step 3: Verify the change looks correct**

```bash
grep -n -A 3 "rotating file handler" src/dct_mcp_server/core/logging.py
```

Expected:
```
85:        # Add rotating file handler for global logs
86:        try:
87:            logs_dir.mkdir(exist_ok=True)
88:            global_handler = TimedRotatingFileHandler(
```

- [ ] **Step 4: Confirm the server still imports cleanly**

```bash
python3 -c "from dct_mcp_server.core.logging import setup_logging, get_logger; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/dct_mcp_server/core/logging.py
git commit -m "Fix log directory creation to be graceful in installed package environments"
```

---

### Task 2: Create `.dockerignore`

**Files:**
- Create: `.dockerignore`

Keeps Python artifacts, secrets, logs, `.mcp.json`, git state, dev tooling, and startup scripts out of the Docker build context.

- [ ] **Step 1: Create `.dockerignore`**

Create the file `.dockerignore` at the repo root with this exact content:

```
# Python artifacts
.venv/
__pycache__/
*.pyc
*.pyo
*.pyd
*.egg-info/
dist/
build/

# Secrets and local config
.env
.env.*
.mcp.json

# Logs (ephemeral; mount a volume to persist)
logs/

# Version control
.git/
.github/

# Dev tooling
.claude/
docs/

# Startup scripts (not needed inside the image)
*.sh
*.bat
```

- [ ] **Step 2: Verify it was created**

```bash
cat .dockerignore
```

Expected: file content as above.

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "Add .dockerignore for Docker container support"
```

---

### Task 3: Create `Dockerfile`

**Files:**
- Create: `Dockerfile`

Multi-arch (`linux/amd64`, `linux/arm64`), non-root user (`mcpuser`, uid/gid 1000), stdio transport, no exposed port, no HEALTHCHECK.

- [ ] **Step 1: Create `Dockerfile`**

Create the file `Dockerfile` at the repo root with this exact content:

```dockerfile
# syntax=docker/dockerfile:1
# Supports linux/amd64 and linux/arm64 via docker buildx.
# Build: docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server .
# Run:  docker run --rm -i -e DCT_API_KEY=<key> -e DCT_BASE_URL=<url> dct-mcp-server

FROM python:3.11-slim

# ── Non-root user ────────────────────────────────────────────────────────────
RUN groupadd --gid 1000 mcpuser && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/sh mcpuser

WORKDIR /app

# ── Dependencies (cached layer — only re-runs when pyproject.toml changes) ──
COPY pyproject.toml README.md ./

# ── Source ───────────────────────────────────────────────────────────────────
COPY src/ src/

# ── Install & prepare runtime directories ────────────────────────────────────
RUN pip install --no-cache-dir . && \
    mkdir -p /app/logs && \
    chown -R mcpuser:mcpuser /app

# ── Drop privileges ──────────────────────────────────────────────────────────
USER mcpuser

# stdio transport — no port exposed, no HEALTHCHECK (not applicable)
CMD ["dct-mcp-server"]
```

- [ ] **Step 2: Verify the file exists**

```bash
cat Dockerfile
```

Expected: file content as above.

- [ ] **Step 3: Build the image to verify it builds cleanly**

```bash
docker build -t dct-mcp-server:test .
```

Expected: build completes with `Successfully tagged dct-mcp-server:test` (or equivalent). No errors.

- [ ] **Step 4: Verify the non-root user**

```bash
docker run --rm dct-mcp-server:test whoami
```

Expected: `mcpuser`

- [ ] **Step 5: Clean up test image**

```bash
docker rmi dct-mcp-server:test
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile
git commit -m "Add Dockerfile with multi-arch and non-root user support"
```

---

### Task 4: Update `README.md` — TOC entry and Docker section

**Files:**
- Modify: `README.md` (line 16 — TOC; line 428 — section body)

Add `- [Docker](#docker)` to the Table of Contents between `Advanced Installation` and `Toolsets`, then insert the full `## Docker` section body before `## Toolsets`.

- [ ] **Step 1: Add the TOC entry**

In `README.md`, find the Table of Contents block (lines 9–17). Replace:

```markdown
- [Advanced Installation](#advanced-installation)
- [Toolsets](#toolsets)
```

with:

```markdown
- [Advanced Installation](#advanced-installation)
- [Docker](#docker)
- [Toolsets](#toolsets)
```

- [ ] **Step 2: Add the Docker section body**

In `README.md`, find the line `## Toolsets` (currently at ~line 428). Insert the following block immediately **before** that line (leave one blank line between the inserted block and `## Toolsets`):

```markdown
## Docker

Run the MCP server as a Docker container — no Python or `uv` installation required on the host.

### Build the Image

**Standard build (current platform):**
```bash
docker build -t dct-mcp-server .
```

**Multi-architecture build (linux/amd64 + linux/arm64):**
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server .
```

> Requires Docker 20.10+ with `buildx`. On Apple Silicon (M-series), the standard `docker build` produces an `arm64` image automatically.

### Run the Server

The server uses stdio transport. Pass credentials as environment variables:

**Linux / macOS:**
```bash
docker run --rm -i \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -e DCT_VERIFY_SSL="true" \
  -e DCT_TOOLSET="self_service" \
  dct-mcp-server
```

**Windows (Command Prompt):**
```cmd
docker run --rm -i ^
  -e DCT_API_KEY="your-api-key-here" ^
  -e DCT_BASE_URL="https://your-dct-host.company.com" ^
  -e DCT_VERIFY_SSL="true" ^
  -e DCT_TOOLSET="self_service" ^
  dct-mcp-server
```

**Windows (PowerShell):**
```powershell
docker run --rm -i `
  -e DCT_API_KEY="your-api-key-here" `
  -e DCT_BASE_URL="https://your-dct-host.company.com" `
  -e DCT_VERIFY_SSL="true" `
  -e DCT_TOOLSET="self_service" `
  dct-mcp-server
```

> **Note:** The `-i` flag is required — it keeps stdin open so the MCP stdio protocol can communicate.

### Persist Logs

Container logs are available via `docker logs <container-name>`. To also write logs to a file on your host, mount a directory:

**Linux / macOS:**
```bash
docker run --rm -i \
  -e DCT_API_KEY="your-api-key-here" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  -v "$(pwd)/logs:/app/logs" \
  dct-mcp-server
```

**Windows (Command Prompt):**
```cmd
docker run --rm -i ^
  -e DCT_API_KEY="your-api-key-here" ^
  -e DCT_BASE_URL="https://your-dct-host.company.com" ^
  -v %cd%\logs:/app/logs ^
  dct-mcp-server
```

**Windows (PowerShell):**
```powershell
docker run --rm -i `
  -e DCT_API_KEY="your-api-key-here" `
  -e DCT_BASE_URL="https://your-dct-host.company.com" `
  -v "${PWD}/logs:/app/logs" `
  dct-mcp-server
```

### MCP Client Configuration (Docker)

Use `docker run` as the command in your MCP client config instead of `uvx` or `python`.

<details>
<summary><strong>Claude Desktop — Docker</strong></summary>

**Linux / macOS:**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DCT_API_KEY=your-api-key-here",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "-e", "DCT_VERIFY_SSL=true",
        "-e", "DCT_TOOLSET=self_service",
        "-e", "DCT_LOG_LEVEL=INFO",
        "dct-mcp-server"
      ]
    }
  }
}
```

**Windows (Docker Desktop):**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DCT_API_KEY=your-api-key-here",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "-e", "DCT_VERIFY_SSL=true",
        "-e", "DCT_TOOLSET=self_service",
        "-e", "DCT_LOG_LEVEL=INFO",
        "dct-mcp-server"
      ]
    }
  }
}
```

> The `docker run` argument format is identical on Windows — Docker Desktop handles the platform differences transparently.
</details>

<details>
<summary><strong>Cursor IDE & Windsurf — Docker</strong></summary>

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DCT_API_KEY=your-api-key-here",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "-e", "DCT_VERIFY_SSL=true",
        "-e", "DCT_TOOLSET=self_service",
        "-e", "DCT_LOG_LEVEL=INFO",
        "dct-mcp-server"
      ]
    }
  }
}
```

</details>

<details>
<summary><strong>VS Code Copilot — Docker</strong></summary>

Add to your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "delphix-dct": {
        "command": "docker",
        "args": [
          "run", "--rm", "-i",
          "-e", "DCT_API_KEY=your-api-key-here",
          "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
          "-e", "DCT_VERIFY_SSL=true",
          "-e", "DCT_TOOLSET=self_service",
          "-e", "DCT_LOG_LEVEL=INFO",
          "dct-mcp-server"
        ]
      }
    }
  }
}
```

</details>

```

- [ ] **Step 3: Verify TOC entry was added**

```bash
grep -n "Docker\|Advanced Installation\|Toolsets" README.md | head -6
```

Expected output includes:
```
15:- [Advanced Installation](#advanced-installation)
16:- [Docker](#docker)
17:- [Toolsets](#toolsets)
```

- [ ] **Step 4: Verify the Docker section exists**

```bash
grep -n "^## Docker\|^## Toolsets" README.md
```

Expected:
```
<line N>:## Docker
<line N+K>:## Toolsets
```

Both headings should be present with `## Docker` appearing before `## Toolsets`.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Add Docker section to README with multi-arch build and client config examples"
```
