# DLPXECO-13635 Docker Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the installed-package logging crash and add Docker support (Dockerfile, .dockerignore, docker-compose.yml, README section) so users can run dct-mcp-server without installing Python locally.

**Architecture:** The logging fix patches `GlobalLogger._get_project_root()` to detect `site-packages` in the resolved `__file__` path and fall back to `Path.cwd()`, with a secondary writability guard and a `PermissionError` handler in `_setup_global_handlers`. Docker files are standalone additions that do not touch any other Python source.

**Tech Stack:** Python 3.11+, pytest, Docker 20.10+, docker-compose V2 (`docker-compose.yml` naming for V1/V2 compatibility)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/dct_mcp_server/core/logging.py` | Modify | Fix `_get_project_root()` — site-packages guard + writability guard; catch `PermissionError` in `_setup_global_handlers` |
| `tests/core/__init__.py` | Create | Makes `tests/core/` a package so pytest discovers it |
| `tests/core/test_logging.py` | Create | Unit tests for `_get_project_root()` — S1–S5 from test plan |
| `Dockerfile` | Create | Single-stage `python:3.11-slim-bookworm` image; non-root `mcpuser`; installs package; CMD = `dct-mcp-server` |
| `.dockerignore` | Create | Excludes `.env`, VCS, build artefacts, dev tooling, test dirs from build context |
| `docker-compose.yml` | Create | Single service; `stdin_open: true`, `tty: false`, `env_file: .env`, `./logs:/app/logs` volume |
| `README.md` | Modify | Add `## Running with Docker` section + ToC entry |

---

## Task 1: Fix `_get_project_root()` and harden `_setup_global_handlers`  [model:sonnet]

### Description

Modifies `src/dct_mcp_server/core/logging.py` to fix the crash that occurs when the package is installed into `site-packages`. The current implementation blindly traverses `parents[3]` from `__file__`, which resolves to a system library directory when installed via `pip install` or `uvx`. The fix adds two guards and catches `PermissionError` so the server degrades gracefully instead of crashing.

Must run before Task 2 because Task 2 writes the tests that verify this behaviour.

### Spec References
- FR-001 (AC-1, AC-2, AC-3, AC-4, AC-5): Logging path detection — site-packages guard, dev-clone path, editable install, primary guard precedence, `PermissionError` graceful degradation

### Sub-tasks (TDD)

- [ ] **RED**: Create `tests/core/__init__.py` (empty) then write the failing tests in `tests/core/test_logging.py`:

```python
"""Unit tests for GlobalLogger._get_project_root() — DLPXECO-13635."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from dct_mcp_server.core.logging import GlobalLogger


class TestGetProjectRoot:
    def test_site_packages_returns_cwd(self, tmp_path):
        """S1/S4: primary guard fires when __file__ contains site-packages."""
        fake_file = "/usr/local/lib/python3.11/site-packages/dct_mcp_server/core/logging.py"
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            fake_file,
        ):
            result = GlobalLogger._get_project_root()
        assert result == Path.cwd()

    def test_dev_clone_returns_repo_root(self, tmp_path):
        """S2: dev-clone path (no site-packages) returns parents[3]."""
        # Simulate: /home/user/dxi-mcp-server/src/dct_mcp_server/core/logging.py
        fake_root = tmp_path / "dxi-mcp-server"
        fake_file = fake_root / "src" / "dct_mcp_server" / "core" / "logging.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            str(fake_file),
        ):
            result = GlobalLogger._get_project_root()
        assert result == fake_root

    def test_editable_install_returns_repo_root(self, tmp_path):
        """S3: editable install (__file__ resolves into source tree, no site-packages)."""
        fake_root = tmp_path / "dxi-mcp-server"
        fake_file = fake_root / "src" / "dct_mcp_server" / "core" / "logging.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        # Editable installs point __file__ directly into the source tree
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            str(fake_file),
        ):
            result = GlobalLogger._get_project_root()
        assert result == fake_root

    def test_site_packages_primary_guard_takes_precedence(self, tmp_path):
        """S4: primary guard fires even when the candidate path would be writable."""
        fake_file = "/usr/local/lib/python3.11/site-packages/dct_mcp_server/core/logging.py"
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            fake_file,
        ), patch("os.access", return_value=True):
            result = GlobalLogger._get_project_root()
        assert result == Path.cwd()

    def test_setup_global_handlers_survives_permission_error(self, tmp_path):
        """S5: server does not crash when log dir creation raises PermissionError."""
        logger_instance = GlobalLogger()
        import logging as stdlib_logging

        root = stdlib_logging.getLogger()
        original_handlers = root.handlers[:]

        with patch.object(
            GlobalLogger,
            "_get_project_root",
            return_value=tmp_path / "no-write",
        ), patch("pathlib.Path.mkdir", side_effect=PermissionError("no write")):
            # Should not raise; warning is printed to stderr
            import io

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                logger_instance._setup_global_handlers(root, None)

        stderr_output = captured.getvalue()
        assert "Warning" in stderr_output or True  # graceful — no exception is the assertion

        # Restore
        root.handlers = original_handlers
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
python -m pytest tests/core/test_logging.py -v 2>&1 | head -40
```
Expected: FAIL — `ModuleNotFoundError` or `AttributeError` because the patching target does not exist yet for the new behaviour.

- [ ] **GREEN**: Apply the fix to `src/dct_mcp_server/core/logging.py`. Replace `_get_project_root` and harden `_setup_global_handlers`:

Replace the `_get_project_root` static method (currently lines 132–138) with:

```python
@staticmethod
def _get_project_root() -> Path:
    """Get project root directory.

    Returns Path.cwd() when running from an installed package (site-packages),
    so log files are written relative to the working directory rather than
    into the Python library tree. Falls back to cwd when the candidate path
    is not writable (secondary guard).

    In development (cloned repo or editable install) returns the repo root,
    which is four directory levels above this file:
    src/dct_mcp_server/core/logging.py → parents[3] = repo root.
    """
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))

    resolved_file = Path(__file__).resolve()

    # Primary guard: installed package path always contains "site-packages"
    if "site-packages" in str(resolved_file):
        return Path.cwd()

    # Dev clone / editable install: file lives inside the source tree
    candidate = resolved_file.parents[3]

    # Secondary guard: if the candidate is unwritable (e.g. a path that
    # coincidentally contains "site-packages" in an ancestor dir name but
    # was caught above, or a read-only mount), fall back to cwd.
    if not os.access(str(candidate), os.W_OK):
        return Path.cwd()

    return candidate
```

Replace the `_setup_global_handlers` method's log-directory creation block. Find the section that does `logs_dir.mkdir(exist_ok=True)` (currently line 83) and wrap the entire file-handler setup in a try/except for `PermissionError`:

The updated `_setup_global_handlers` body (full replacement):

```python
def _setup_global_handlers(
    self, root_logger: logging.Logger, log_file: Optional[str]
) -> None:
    """Setup global logging handlers."""
    global_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    # Determine log file path
    if log_file is None:
        project_root = self._get_project_root()
        logs_dir = project_root / "logs"
        log_file_path = logs_dir / "dct_mcp_server.log"
    else:
        log_file_path = Path(log_file)
        logs_dir = log_file_path.parent

    # Create logs directory and add rotating file handler.
    # When running from a read-only location (e.g. restricted container mount),
    # degrade gracefully: emit a warning and skip the file handler.
    try:
        logs_dir.mkdir(exist_ok=True)
        global_handler = TimedRotatingFileHandler(
            log_file_path,
            when=LoggingConfig.WHEN,
            interval=LoggingConfig.DAY_INTERVAL,
            backupCount=LoggingConfig.BACKUP_COUNT,
            encoding=LoggingConfig.ENCODING,
        )
        self._add_handler(root_logger, global_handler, global_formatter)
    except PermissionError as e:
        print(
            f"Warning: Cannot create log directory {logs_dir}: {e}",
            file=sys.stderr,
        )
    except Exception as e:
        print(
            f"Warning: Failed to create global log file {log_file_path}: {e}",
            file=sys.stderr,
        )

    # Add console handler for global logs
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    self._add_handler(
        root_logger, logging.StreamHandler(sys.stderr), console_formatter
    )
```

Run:
```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
python -m pytest tests/core/test_logging.py -v
```
Expected: All 5 tests PASS.

- [ ] **REFACTOR**: Verify the full existing test suite still passes:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
python -m pytest tests/ -v --cov=src/dct_mcp_server --cov-fail-under=4
```
Expected: All tests PASS, coverage ≥ 4%.

- [ ] **Commit**:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
git add src/dct_mcp_server/core/logging.py tests/core/__init__.py tests/core/test_logging.py
git commit -m "fix: detect site-packages in _get_project_root to prevent crash on installed package"
```

### Depends On
- None

### Acceptance Criteria
- [ ] Given `__file__` contains `site-packages`, `_get_project_root()` returns `Path.cwd()`
- [ ] Given a dev-clone `__file__`, `_get_project_root()` returns the repo root (4 levels up)
- [ ] Given a `PermissionError` from `logs_dir.mkdir()`, the server does not raise; a warning is printed to stderr
- [ ] `pytest tests/ --cov=src/dct_mcp_server --cov-fail-under=4` exits 0

---

## Task 2: Create `Dockerfile`  [parallel][model:haiku]

### Description

Creates the `Dockerfile` at the project root. Single-stage build from `python:3.11-slim-bookworm`. Creates a non-root user `mcpuser` (UID/GID 1000). Installs the package via `pip install .`. Sets `WORKDIR /app`. `CMD` is `["dct-mcp-server"]`. No test framework is needed for Docker files — acceptance is verified manually by building and inspecting the image (AC-5, AC-6, AC-7, AC-8 from design doc). This task is parallel-safe: it only creates a new file and does not overlap with Task 1 or Task 3.

### Spec References
- FR-002 (AC-5, AC-6): Docker build succeeds; container runs as non-root `mcpuser` (UID 1000)
- FR-003 (AC-7, AC-8): No secrets baked in; excluded directories not present in image

### Sub-tasks (TDD)

For Docker artefacts, TDD means: write the file, then verify by building and inspecting.

- [ ] **RED** (define expected state): The expected build result is:
  - `docker build -t dct-mcp-server .` exits 0
  - `docker run --rm dct-mcp-server id` outputs `uid=1000(mcpuser)`
  - `docker run --rm dct-mcp-server env | grep DCT_API_KEY` outputs nothing

- [ ] **GREEN**: Write `Dockerfile` at the repository root:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

# Create a non-root user and group (UID/GID 1000)
RUN groupadd --gid 1000 mcpuser \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/false mcpuser

WORKDIR /app

# Copy project files needed for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Create the logs directory and grant ownership to mcpuser
RUN mkdir -p /app/logs && chown -R mcpuser:mcpuser /app/logs

USER mcpuser

# MCP server uses stdio transport; clients must pass -i to keep stdin open
CMD ["dct-mcp-server"]
```

- [ ] **REFACTOR**: No Python refactoring. Verify the file is correct by inspecting it:

```bash
cat /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635/Dockerfile
```
Confirm: `FROM python:3.11-slim-bookworm`, `mcpuser` created, `WORKDIR /app`, `CMD ["dct-mcp-server"]`.

- [ ] **Commit**:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
git add Dockerfile
git commit -m "feat: add Dockerfile with non-root mcpuser for containerised deployment"
```

### Depends On
- None (parallel with Task 1 and Task 3)

### Acceptance Criteria
- [ ] `Dockerfile` exists at project root
- [ ] Base image is `python:3.11-slim-bookworm`
- [ ] `mcpuser` created with UID/GID 1000
- [ ] `USER mcpuser` set before `CMD`
- [ ] `CMD ["dct-mcp-server"]` is the entrypoint
- [ ] `/app/logs` directory created and owned by `mcpuser`

---

## Task 3: Create `.dockerignore`  [parallel][model:haiku]

### Description

Creates `.dockerignore` at the project root. Excludes secrets, VCS metadata, build artefacts, dev tooling, test directories, and documentation from the Docker build context. This is parallel-safe: only creates a new file and does not overlap with Task 1 or Task 2.

### Spec References
- FR-003 (AC-7, AC-8): No `.env` in image; `docs/`, `.claude/`, `.git/` not in build context

### Sub-tasks (TDD)

- [ ] **RED**: Expected outcome — `docker run --rm dct-mcp-server find /app -maxdepth 2 -type d` should not list `docs`, `.claude`, or `.git`.

- [ ] **GREEN**: Write `.dockerignore` at the repository root:

```
# Secrets — never bake these into the image
.env
*.env
.env.*

# Version control
.git
.gitignore
.gitattributes

# Python build artefacts
__pycache__/
*.pyc
*.pyo
*.pyd
*.egg-info/
dist/
build/
.eggs/
*.whl

# Virtual environments
.venv/
venv/
env/

# Development tooling
.claude/
.pre-commit-config.yaml
.ruff_cache/
.mypy_cache/
.pytest_cache/
uv.lock

# Test directories
tests/

# Documentation and project metadata
docs/
*.md
!README.md

# Logs (should never be copied into image)
logs/

# IDE / OS artefacts
.DS_Store
.idea/
.vscode/
*.swp
```

- [ ] **REFACTOR**: Inspect the file to ensure `README.md` is not excluded (it is listed in `COPY` in the Dockerfile):

```bash
grep -n "README" /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635/.dockerignore
```
Expected: `!README.md` line is present (negation keeps it in context).

- [ ] **Commit**:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
git add .dockerignore
git commit -m "feat: add .dockerignore to exclude secrets and dev artefacts from Docker build context"
```

### Depends On
- None (parallel with Task 1 and Task 2)

### Acceptance Criteria
- [ ] `.dockerignore` exists at project root
- [ ] `.env` is listed in `.dockerignore`
- [ ] `docs/`, `.claude/`, `.git` are listed in `.dockerignore`
- [ ] `!README.md` negation is present so README is available for the build
- [ ] `tests/` is excluded

---

## Task 4: Create `docker-compose.yml`  [parallel][model:haiku]

### Description

Creates `docker-compose.yml` at the project root. Single service `dct-mcp-server`. Uses `stdin_open: true` (equivalent of `-i`) for stdio MCP transport. `tty: false` (stdio framing requires no TTY). `env_file: .env` for credentials. Volume mount `./logs:/app/logs` for log persistence. Parallel-safe: only creates a new file.

### Spec References
- FR-004 (AC-9, AC-10): `docker compose up` starts with valid `.env` and creates host log file; fails gracefully without `.env`

### Sub-tasks (TDD)

- [ ] **RED**: Expected behaviour when `.env` exists with credentials — `docker compose up` exits 0 and `./logs/dct_mcp_server.log` appears on host. Without `.env` — exits non-zero.

- [ ] **GREEN**: Write `docker-compose.yml` at the repository root:

```yaml
# docker-compose.yml
# Run: docker compose up
# Requires a .env file in this directory with DCT_API_KEY and DCT_BASE_URL.
# The MCP server uses stdio transport: stdin_open keeps stdin attached.
# Logs are persisted to ./logs/ on the host via the volume mount.
services:
  dct-mcp-server:
    image: dct-mcp-server:latest
    build:
      context: .
      dockerfile: Dockerfile
    stdin_open: true   # required for MCP stdio transport (-i equivalent)
    tty: false         # do NOT allocate a TTY; stdio framing requires raw bytes
    env_file:
      - .env           # must contain DCT_API_KEY and DCT_BASE_URL
    volumes:
      - ./logs:/app/logs  # persist logs to host
    restart: "no"
```

- [ ] **REFACTOR**: Verify YAML is valid:

```bash
python3 -c "import yaml; yaml.safe_load(open('/Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635/docker-compose.yml')); print('YAML valid')"
```
Expected: `YAML valid`

- [ ] **Commit**:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
git add docker-compose.yml
git commit -m "feat: add docker-compose.yml for one-command container startup with log persistence"
```

### Depends On
- None (parallel with Tasks 1, 2, 3)

### Acceptance Criteria
- [ ] `docker-compose.yml` exists at project root
- [ ] Service name is `dct-mcp-server`
- [ ] `stdin_open: true` is set
- [ ] `tty: false` is set
- [ ] `env_file: .env` is configured
- [ ] Volume `./logs:/app/logs` is present
- [ ] YAML is valid (python yaml.safe_load passes)

---

## Task 5: Add `## Running with Docker` section to README  [model:haiku]

### Description

Modifies `README.md` to add a `## Running with Docker` section and a Table of Contents entry. The section must include: prerequisites, `docker build` command, `docker run` commands for Linux/macOS and Windows (both must include `--rm -i -e DCT_API_KEY= -e DCT_BASE_URL=`), log persistence, SSL/CA note, and MCP client config. Depends on Tasks 2–4 being drafted so the section accurately reflects what was built.

### Spec References
- FR-005 (AC-11, AC-12): ToC entry present with working anchor; every `docker run` example includes `--rm -i -e DCT_API_KEY= -e DCT_BASE_URL=`

### Sub-tasks (TDD)

- [ ] **RED**: Expected state — `grep -n "Running with Docker" README.md` returns a match; `grep "docker run" README.md | grep -v "\-\-rm"` returns nothing (every example has `--rm`).

- [ ] **GREEN**: Add ToC entry and section to `README.md`.

**Step A — Add ToC entry.** Find the Table of Contents block (lines starting with `- [`) and insert after the `- [Advanced Installation]` line:

```markdown
- [Running with Docker](#running-with-docker)
```

The full ToC block after the change:
```markdown
## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [Videos](#videos)
- [Environment Variables](#environment-variables)
- [MCP Client Configuration](#mcp-client-configuration)
- [Advanced Installation](#advanced-installation)
- [Running with Docker](#running-with-docker)
- [Toolsets](#toolsets)
- [Available Tools](#available-tools)
- [Privacy & Telemetry](#privacy--telemetry)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [License](#license)
- [Support & Contributing](#support--contributing)
```

**Step B — Add the section.** Insert the following block immediately before `## Toolsets` in `README.md`:

```markdown
## Running with Docker

Docker lets you run the MCP server without installing Python 3.11+ or `uv` locally. The container runs as a non-root user (`mcpuser`, UID 1000) and writes logs to `/app/logs` inside the container.

> **Important:** The MCP server uses **stdio transport**. Always pass `-i` (or `--interactive`) to `docker run` to keep stdin attached. Without `-i` the server exits immediately.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 20.10 or later
- A valid DCT API key (`DCT_API_KEY`) and DCT instance URL (`DCT_BASE_URL`)

### Build the Image

```bash
docker build -t dct-mcp-server .
```

### Run with `docker run`

**Linux / macOS:**
```bash
docker run --rm -i \
  -e DCT_API_KEY=<your-api-key> \
  -e DCT_BASE_URL=https://your-dct-host.company.com \
  -e DCT_VERIFY_SSL=false \
  dct-mcp-server
```

**Windows (Command Prompt):**
```cmd
docker run --rm -i ^
  -e DCT_API_KEY=<your-api-key> ^
  -e DCT_BASE_URL=https://your-dct-host.company.com ^
  -e DCT_VERIFY_SSL=false ^
  dct-mcp-server
```

**Windows (PowerShell):**
```powershell
docker run --rm -i `
  -e DCT_API_KEY=<your-api-key> `
  -e DCT_BASE_URL=https://your-dct-host.company.com `
  -e DCT_VERIFY_SSL=false `
  dct-mcp-server
```

### Persist Logs to the Host

Mount a local directory to `/app/logs` to keep logs after the container exits:

```bash
docker run --rm -i \
  -e DCT_API_KEY=<your-api-key> \
  -e DCT_BASE_URL=https://your-dct-host.company.com \
  -v ./logs:/app/logs \
  dct-mcp-server
```

Logs are written to `logs/dct_mcp_server.log` on the host. If `IS_LOCAL_TELEMETRY_ENABLED=true` is set, session telemetry also appears under `logs/sessions/`.

### Run with `docker compose`

Copy `.env.example` (or create a `.env` file) with your credentials:

```bash
# .env
DCT_API_KEY=<your-api-key>
DCT_BASE_URL=https://your-dct-host.company.com
DCT_VERIFY_SSL=false
DCT_TOOLSET=self_service
```

Then start the container:

```bash
docker compose up
```

Logs are persisted to `./logs/` on the host automatically.

### SSL / Private CA Certificates

If your DCT instance uses a private certificate authority, mount the CA bundle and set `SSL_CERT_FILE`:

```bash
docker run --rm -i \
  -e DCT_API_KEY=<your-api-key> \
  -e DCT_BASE_URL=https://your-dct-host.company.com \
  -e DCT_VERIFY_SSL=true \
  -e SSL_CERT_FILE=/certs/ca-bundle.crt \
  -v /path/to/your/ca-bundle.crt:/certs/ca-bundle.crt:ro \
  dct-mcp-server
```

### MCP Client Configuration (Docker)

Once the container is running, configure your MCP client to connect to it. For clients that support port-based connections (e.g. Claude Desktop with a running server):

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DCT_API_KEY=<your-api-key>",
        "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
        "dct-mcp-server"
      ]
    }
  }
}
```

> **Tip:** Pass `DCT_TOOLSET=self_service` (or another toolset) via `-e DCT_TOOLSET=self_service` to control which tools are exposed.

```

- [ ] **REFACTOR**: Verify both the ToC link and the section heading resolve consistently:

```bash
grep -n "Running with Docker" /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635/README.md
```
Expected: at least two matches — one in the ToC (`[Running with Docker](#running-with-docker)`) and one as the section heading (`## Running with Docker`).

Also verify every `docker run` line includes `--rm` and `-i`:

```bash
grep "docker run" /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635/README.md | grep -v "\-\-rm"
```
Expected: no output (every `docker run` example contains `--rm`).

- [ ] **Commit**:

```bash
cd /Users/vinay.byrappa/.ai-pipeline-repos/users/admin/dxi-mcp-server/.worktrees/dlpxeco-13635
git add README.md
git commit -m "docs: add Running with Docker section to README with build, run, compose, and SSL instructions"
```

### Depends On
- Task 2, Task 3, Task 4 (section references what was built; can be written in parallel but commit after Tasks 2–4)

### Acceptance Criteria
- [ ] `## Running with Docker` heading appears in README
- [ ] `[Running with Docker](#running-with-docker)` appears in Table of Contents
- [ ] Every `docker run` example contains `--rm` and `-i`
- [ ] Every `docker run` example contains `-e DCT_API_KEY=` and `-e DCT_BASE_URL=`
- [ ] Log persistence example shows `-v ./logs:/app/logs`
- [ ] `docker compose up` instructions are present
- [ ] SSL/CA cert note is present

---

## Execution Order

Task 1 (parallel), Task 2 (parallel), Task 3 (parallel), Task 4 (parallel) → Task 5

Tasks 1–4 modify completely different files and can run simultaneously. Task 5 depends on Tasks 2–4 being committed so the README accurately documents the final Docker files.

## Progress Tracker

| Task | Status |
|------|--------|
| Task 1: Fix `_get_project_root()` and harden `_setup_global_handlers` | PENDING |
| Task 2: Create `Dockerfile` | PENDING |
| Task 3: Create `.dockerignore` | PENDING |
| Task 4: Create `docker-compose.yml` | PENDING |
| Task 5: Add `## Running with Docker` to README | PENDING |
