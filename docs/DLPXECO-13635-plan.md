# Implementation Tasks: DLPXECO-13635

**Spec**: `docs/DLPXECO-13635-functional.md`
**Design**: `docs/DLPXECO-13635-design.md`

> **Note on TDD adaptation**: This project has no automated test suite (per `CLAUDE.md`). The `RED → GREEN → REFACTOR` cycle in the standard task template is adapted here to **VERIFY-FAIL → IMPLEMENT → VERIFY-PASS** using shell commands, `docker` CLI checks, and manual MCP-client smoke tests. Each task records the exact verification command + expected output.

---

## Task 1: Wire `DCT_LOG_DIR` env var into core logging  [model:sonnet]

### Description
Modify `src/dct_mcp_server/core/logging.py:_setup_global_handlers` so it reads `DCT_LOG_DIR` from the environment and uses it as the logs directory when set. Also add `parents=True` to the `mkdir` call so multi-segment paths work on first run. Update `src/dct_mcp_server/config/config.py:print_config_help()` to document the new env var. Must run **before Task 2** because the Dockerfile relies on `DCT_LOG_DIR=/app/logs` (set as a default ENV) actually being read by the logging code.

### Spec References
- FR-005 (AC-1, AC-2, AC-3, AC-4): Honour `DCT_LOG_DIR` env var.
- QR-4 (backward compat: unset → identical default behaviour).
- QR-8 (no `logging.getLogger` direct usage — preserve existing `get_logger` pattern; this task does not introduce new logger creation).

### Sub-tasks (Verify → Implement → Verify)

- [ ] **VERIFY-FAIL** — run on `main`, no patch yet:
  ```bash
  rm -rf /tmp/dct-log-test && mkdir -p /tmp/dct-log-test
  DCT_LOG_DIR=/tmp/dct-log-test/custom DCT_API_KEY=dummy DCT_BASE_URL=https://example.invalid \
    timeout 3 .venv/bin/python -c "
  from dct_mcp_server.core.logging import setup_logging, get_logger
  setup_logging('INFO')
  get_logger('verify').info('hello')
  " 2>/tmp/dct-log-test/stderr.txt
  ls /tmp/dct-log-test/custom/ 2>&1 || echo "EXPECTED: directory not created"
  ls "$(git rev-parse --show-toplevel)/logs/" 2>&1
  ```
  Expected: `/tmp/dct-log-test/custom/` does **not** exist; instead `<repo>/logs/dct_mcp_server.log` was written. This proves the env var is currently ignored.

- [ ] **IMPLEMENT**:
  - In `src/dct_mcp_server/core/logging.py`, replace the `if log_file is None: …` block (lines 73–80) with the design's "After" snippet (reads `os.getenv("DCT_LOG_DIR")`, falls back to project root).
  - Change `logs_dir.mkdir(exist_ok=True)` → `logs_dir.mkdir(parents=True, exist_ok=True)` (line 83).
  - In `src/dct_mcp_server/config/config.py:print_config_help()`, insert one line after the existing `IS_LOCAL_TELEMETRY_ENABLED` print and before the `DCT_TOOLSET` print (around line 60–61):
    ```python
    print("  DCT_LOG_DIR      Override directory for log files (default: <project_root>/logs)")
    ```
  - Confirm `import os` is already present in `core/logging.py` (it is, at line 6).

- [ ] **VERIFY-PASS**:
  ```bash
  rm -rf /tmp/dct-log-test && mkdir -p /tmp/dct-log-test
  DCT_LOG_DIR=/tmp/dct-log-test/custom DCT_API_KEY=dummy DCT_BASE_URL=https://example.invalid \
    timeout 3 .venv/bin/python -c "
  from dct_mcp_server.core.logging import setup_logging, get_logger
  setup_logging('INFO')
  get_logger('verify').info('hello DCT_LOG_DIR')
  "
  ls /tmp/dct-log-test/custom/dct_mcp_server.log && \
    grep -q 'hello DCT_LOG_DIR' /tmp/dct-log-test/custom/dct_mcp_server.log && \
    echo PASS
  ```
  Expected: prints `PASS`. Then run with `DCT_LOG_DIR` unset and confirm `<repo>/logs/dct_mcp_server.log` still receives writes (regression check).

  Additional verifications:
  - `DCT_LOG_DIR=""` (empty string) → behaves like unset. Confirmed via inspection: `if env_log_dir:` is falsy for empty string.
  - `DCT_LOG_DIR=/proc/cant-create-here` → warning to stderr, no exception. Run the same one-liner with that value; expect stderr to contain `Warning: Failed to create global log file`.

### Depends On
- None — this is the foundation task and must precede Task 2.

### Acceptance Criteria
- [ ] `DCT_LOG_DIR=/tmp/dct-log-test/custom` produces logs at `/tmp/dct-log-test/custom/dct_mcp_server.log` (FR-005 AC-2).
- [ ] `DCT_LOG_DIR` unset → logs at `<project_root>/logs/dct_mcp_server.log` (FR-005 AC-1, no regression).
- [ ] `DCT_LOG_DIR=""` → logs at `<project_root>/logs/dct_mcp_server.log` (FR-005 AC-4).
- [ ] `DCT_LOG_DIR=/proc/forbidden` → warning to stderr, no traceback, server continues (FR-005 AC-3).
- [ ] `dct-mcp-server --help`-style invocation still prints help and now lists `DCT_LOG_DIR` in the optional section.
- [ ] No other lines in `core/logging.py` or `config.py` change beyond what's specified.

---

## Task 2: Create `Dockerfile`  [model:sonnet]

### Description
Create a top-level `Dockerfile` per the FR-001 + FR-004 designs: two-stage build, `python:3.11-slim-bookworm` base, `uv sync --frozen --no-dev`, non-root runtime user (UID 1000), `ENV DCT_LOG_DIR=/app/logs`, OCI labels, `ENTRYPOINT ["dct-mcp-server"]`.

### Spec References
- FR-001 (AC-1, AC-2, AC-3, AC-4): Buildable image, non-root, starts cleanly, < 250 MB.
- FR-004 (AC-1, AC-2, AC-3): Non-root, no secrets, OCI labels.
- QR-1 (non-root), QR-2 (no secrets), QR-6 (size budget), QR-7 (no new deps).

### Sub-tasks (Verify → Implement → Verify)

- [ ] **VERIFY-FAIL**:
  ```bash
  cd <worktree-root>
  ls Dockerfile && echo "Dockerfile already exists, unexpected" || echo "EXPECTED: Dockerfile does not exist yet"
  docker build -t dct-mcp-server:test . 2>&1 | tail -1
  ```
  Expected: file does not exist; `docker build` fails with `Cannot locate specified Dockerfile`.

- [ ] **IMPLEMENT** — write `Dockerfile` to repo root with these stages:

  **Builder stage**:
  ```dockerfile
  # syntax=docker/dockerfile:1.7
  FROM python:3.11-slim-bookworm AS builder

  ENV PIP_NO_CACHE_DIR=1 \
      PIP_DISABLE_PIP_VERSION_CHECK=1 \
      UV_LINK_MODE=copy \
      UV_PYTHON_DOWNLOADS=never

  RUN pip install --no-cache-dir "uv==0.5.31"

  WORKDIR /build

  # Copy dependency manifests first for layer caching
  COPY pyproject.toml uv.lock README.md LICENSE.md ./
  COPY src ./src

  # Install runtime deps + project, frozen against uv.lock, no dev groups
  RUN uv sync --frozen --no-dev
  ```

  **Runtime stage**:
  ```dockerfile
  FROM python:3.11-slim-bookworm AS runtime

  LABEL org.opencontainers.image.title="dct-mcp-server" \
        org.opencontainers.image.description="Delphix DCT API MCP Server (stdio transport)" \
        org.opencontainers.image.source="https://github.com/delphix/dxi-mcp-server" \
        org.opencontainers.image.licenses="MIT" \
        org.opencontainers.image.version="2026.0.1.0-preview"

  ENV PYTHONUNBUFFERED=1 \
      PYTHONDONTWRITEBYTECODE=1 \
      PATH="/app/.venv/bin:$PATH" \
      DCT_LOG_DIR=/app/logs

  RUN groupadd -g 1000 app \
   && useradd  -u 1000 -g 1000 -m -s /bin/false app \
   && mkdir -p /app/logs \
   && chown -R app:app /app

  WORKDIR /app

  COPY --from=builder --chown=app:app /build/.venv /app/.venv
  COPY --chown=app:app pyproject.toml uv.lock README.md LICENSE.md ./
  COPY --chown=app:app src ./src

  USER app

  # Document at-runtime env vars (consumed by the server, not declared here):
  #   DCT_API_KEY           (required)
  #   DCT_BASE_URL          (required)
  #   DCT_TOOLSET           (default: self_service)
  #   DCT_VERIFY_SSL        (default: false)
  #   DCT_LOG_LEVEL         (default: INFO)
  #   DCT_TIMEOUT           (default: 30)
  #   DCT_MAX_RETRIES       (default: 3)
  #   DCT_LOG_DIR           (default: /app/logs — set above)
  #   IS_LOCAL_TELEMETRY_ENABLED  (default: false)

  ENTRYPOINT ["dct-mcp-server"]
  ```

  Pin notes:
  - `uv==0.5.31` is the chosen pin at implement time; if the actual installed `uv` major has shifted, choose the latest 0.5.x release. Do not use unpinned `uv`.
  - `python:3.11-slim-bookworm` is the explicit Debian release. If unavailable, fall back to `python:3.11-slim` and note the substitution in the build evidence.

- [ ] **VERIFY-PASS** — build phase will run B1–B8 from the design's verification table. Inline checks here:
  ```bash
  docker build -t dct-mcp-server:test .   # exit 0
  docker run --rm --entrypoint id dct-mcp-server:test   # uid=1000(app)
  docker run --rm -i -e DCT_API_KEY=dummy -e DCT_BASE_URL=https://example.invalid \
    dct-mcp-server:test < /dev/null  # starts, exits cleanly on EOF
  docker save dct-mcp-server:test | gzip | wc -c   # < 262144000
  ```

### Depends On
- Task 1 — `DCT_LOG_DIR` must be honoured by the code before the Dockerfile sets it as an ENV.

### Acceptance Criteria
- [ ] FR-001 AC-1: `docker build` exits 0.
- [ ] FR-001 AC-2: `id` shows UID 1000 (non-zero).
- [ ] FR-001 AC-3: `docker run … < /dev/null` runs without permission errors / Python tracebacks unrelated to DCT connectivity.
- [ ] FR-001 AC-4: image compressed size < 250 MB; configured user is `app`.
- [ ] FR-004 AC-1: id confirms `app:app`.
- [ ] FR-004 AC-2: `docker history` shows no secret values.
- [ ] FR-004 AC-3: OCI labels present.

---

## Task 3: Create `.dockerignore`  [parallel-after-task-2][model:haiku]

### Description
Add `.dockerignore` at repo root with the FR-002 exclusion list. Trims build context and prevents host noise from entering the image.

### Spec References
- FR-002 (AC-1, AC-2): `.dockerignore` keeps build context small and excludes `.git`, `.venv`, `logs/`, `docs/`, `.claude/`, dev scripts.

### Sub-tasks (Verify → Implement → Verify)

- [ ] **VERIFY-FAIL**:
  ```bash
  ls .dockerignore 2>&1   # expect: No such file or directory
  ```

- [ ] **IMPLEMENT** — write `.dockerignore` at repo root:
  ```
  # Python build artefacts
  __pycache__/
  *.py[oc]
  build/
  dist/
  wheels/
  *.egg-info/

  # Virtualenvs
  .venv/
  venv/
  env/

  # Logs
  logs/
  *.log
  mcp_server_setup_logfile.txt

  # Env / secrets
  .env
  .env.*
  .env.local
  .env.*.local

  # VCS metadata and CI
  .git/
  .gitignore
  .github/
  .whitesource

  # Docs and specs (the Docker section is in README.md, which is re-included below)
  docs/
  *.md
  !README.md
  !LICENSE.md

  # Project-specific
  .claude/
  CLAUDE.md
  .worktrees/
  worktrees/

  # Dev startup scripts
  start_mcp_server_python.sh
  start_mcp_server_uv.sh
  start_mcp_server_windows_python.bat
  start_mcp_server_windows_uv.bat

  # Test files (defensive — no tests today)
  tests/
  test/
  **/test_*.py
  **/*_test.py

  # IDE / editor
  .vscode/
  .idea/
  *.swp
  *.swo
  *~

  # OS junk
  .DS_Store
  .DS_Store?
  ._*
  Thumbs.db
  ehthumbs.db

  # Don't rebuild image into image
  Dockerfile
  .dockerignore
  ```

- [ ] **VERIFY-PASS**:
  ```bash
  # Inspect the runtime image's /app contents
  docker run --rm --entrypoint sh dct-mcp-server:test -c 'ls -A /app'
  # Expect: .venv  LICENSE.md  README.md  logs  pyproject.toml  src  uv.lock
  # Must NOT contain: .git, .claude, docs, CLAUDE.md, start_mcp_server_*.sh, .dockerignore, Dockerfile
  ```
  Also verify the build-context size is small:
  ```bash
  docker build --no-cache -t dct-mcp-server:test . 2>&1 | grep -i "transferring context"
  # Expect: "transferring context" line shows under ~5 MB
  ```

### Depends On
- Task 2 — verification compares against a built image; the image must exist to inspect it.

### Acceptance Criteria
- [ ] FR-002 AC-1: `/app` listing inside the image excludes `.git`, `.claude`, `docs`, `CLAUDE.md`, `start_mcp_server_*.sh`, `Dockerfile`, `.dockerignore`.
- [ ] FR-002 AC-2: build context transfer size < 15 MB.

---

## Task 4: Add Docker section + TOC entry to README.md  [model:sonnet]

### Description
Insert the `## Docker` section between the existing `## Advanced Installation` and `## Toolsets` sections, and add `- [Docker](#docker)` to the TOC. All edits are additive — no existing line content is modified.

### Spec References
- FR-003 (AC-1, AC-2, AC-3): Docker section + TOC entry.
- QR-9 (additive-only README diff).

### Sub-tasks (Verify → Implement → Verify)

- [ ] **VERIFY-FAIL**:
  ```bash
  grep -n "^## Docker" README.md && echo "section already exists" || echo "EXPECTED: no Docker section yet"
  grep -n "Docker.*#docker" README.md && echo "TOC entry exists" || echo "EXPECTED: no TOC entry yet"
  ```

- [ ] **IMPLEMENT**:
  1. **TOC**: in the TOC block (around line 9–22), insert exactly this line between `- [Advanced Installation](#advanced-installation)` and `- [Toolsets](#toolsets)`:
     ```
     - [Docker](#docker)
     ```
  2. **New section**: insert the full `## Docker` section between the closing line of "Advanced Installation" (around line 426: ends after the "Connecting a Client to a Running Server" subsection) and the line `## Toolsets` (around line 428). Section content per the design's "README.md `## Docker` section" component design — including all 8 subsections (Prerequisites, Build, Run, Environment variables table, Persist logs, MCP client config blocks for Claude/Cursor/VS Code, Multi-arch, Common pitfalls).
  3. Use existing README's collapsible `<details>`/`<summary>` style for the per-client config blocks to match the rest of the README's UX.
  4. Use the docker run invocation pattern `"-e", "DCT_API_KEY"` (no `=value`) in the `args` array, with the actual value supplied via the `mcpServers.<name>.env` block — keeps the API key out of the args.

- [ ] **VERIFY-PASS**:
  ```bash
  # TOC entry present
  grep -c '^- \[Docker\](#docker)$' README.md   # expect: 1

  # Section heading present, exactly once
  grep -c '^## Docker$' README.md   # expect: 1

  # Required subsections present
  for sub in '### Prerequisites' '### Build the image' '### Run the server' '### Environment variables' '### Persist logs' '### MCP client configuration' '### Multi-arch' '### Common pitfalls'; do
    grep -q "$sub" README.md && echo "PASS: $sub" || echo "FAIL: missing $sub"
  done

  # Required code patterns present
  grep -q 'docker build -t dct-mcp-server' README.md && echo PASS-build
  grep -q 'docker run --rm -i' README.md && echo PASS-run
  grep -q '"command": "docker"' README.md && echo PASS-client-config
  grep -q '/app/logs' README.md && echo PASS-logs-mount

  # Diff is additive only (no existing line modified)
  git diff origin/main -- README.md | grep -E '^-' | grep -v '^---' | head
  # Expect: empty (no removed lines except the diff header)
  ```

### Depends On
- Task 1 (so the README's mention of `DCT_LOG_DIR` matches actual code behaviour).
- Tasks 2 & 3 (so the README's commands accurately describe a real built image — `--entrypoint id`, `-v $(pwd)/logs:/app/logs`).

### Acceptance Criteria
- [ ] FR-003 AC-1: TOC entry + section heading both present, each exactly once.
- [ ] FR-003 AC-2: required code blocks (`docker build`, `docker run -i`, JSON config, logs mount) all present.
- [ ] FR-003 AC-3: a Docker-only reader can complete the full setup without leaving the section.
- [ ] QR-9: `git diff origin/main -- README.md` shows no removed lines (only additions).

---

## Task 5: Final regression sweep  [model:haiku]

### Description
Confirm that the files listed in the design's "Files **NOT** Modified" list are byte-identical to `origin/main`. This is the QR-3 / QR-7 enforcement.

### Spec References
- QR-3, QR-7: existing host-install flows must continue to work; no new third-party deps.

### Sub-tasks (Verify → Implement → Verify)

- [ ] **VERIFY-FAIL** — N/A (this is a regression check, no code change).

- [ ] **IMPLEMENT** — N/A.

- [ ] **VERIFY-PASS**:
  ```bash
  # Compare the protected file list against main
  git diff --stat origin/main -- \
    pyproject.toml \
    requirements.txt \
    start_mcp_server_uv.sh \
    start_mcp_server_python.sh \
    start_mcp_server_windows_uv.bat \
    start_mcp_server_windows_python.bat \
    src/dct_mcp_server/main.py \
    src/dct_mcp_server/tools/ \
    src/dct_mcp_server/dct_client/ \
    src/dct_mcp_server/toolsgenerator/ \
    src/dct_mcp_server/config/toolsets/ \
    src/dct_mcp_server/config/mappings/ \
    .github/ \
    LICENSE.md \
    .whitesource \
    uv.lock
  # Expect: empty output (no diff)
  ```
  If any file in this list has changed, the offending change must be reverted or moved into a follow-up ticket.

  Also confirm that the existing host flow still works:
  ```bash
  # Smoke test the local script (uses the patched logging code)
  unset DCT_LOG_DIR
  rm -f logs/dct_mcp_server.log
  DCT_API_KEY=dummy DCT_BASE_URL=https://example.invalid timeout 5 ./start_mcp_server_uv.sh || true
  ls logs/dct_mcp_server.log && echo PASS-default-logs-path
  ```

### Depends On
- Tasks 1–4 — runs after all code changes.

### Acceptance Criteria
- [ ] `git diff --stat origin/main -- <protected-list>` is empty.
- [ ] After Task 1 patch, default logs path still resolves to `<repo>/logs/dct_mcp_server.log` when `DCT_LOG_DIR` is unset.

---

## Execution Order

Task 1 → Task 2 → Task 3 → Task 4 → Task 5

Tasks 2 and 3 could be parallelised in principle (different files), but Task 3's verification depends on Task 2's image existing, so they are sequential here. Task 4's verification benefits from the image existing too. Task 5 is the final gate.

## Progress Tracker

| Task   | Status  |
|--------|---------|
| Task 1 | PENDING |
| Task 2 | PENDING |
| Task 3 | PENDING |
| Task 4 | PENDING |
| Task 5 | PENDING |
