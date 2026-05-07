# DLPXECO-13635 — Docker Support: Design

> **Vision**: see [DLPXECO-13635-vision.md](DLPXECO-13635-vision.md)
> **Functional spec**: see [DLPXECO-13635-functional.md](DLPXECO-13635-functional.md)
> **Domain**: feature
> **Status**: ready for implementation

---

## 1. Overview

This design realises FR-1..FR-8 with a single **Dockerfile** + **`.dockerignore`** at the repo root, a new **"Run with Docker"** subsection in `README.md`, and a manual **test plan** suitable for the project's MCP-client-driven test process. There are **no source-code changes** to `src/dct_mcp_server/`, no changes to existing startup scripts, and no changes to `pyproject.toml` or `requirements.txt`.

**Decision on FR-9 (`docker-compose.yml`)**: see §7. Short answer: **drop FR-9 from this implementation**.

---

## 2. Architecture Changes

The Docker artifacts are **purely a packaging/distribution layer wrapping the existing `dct_mcp_server.main:main` entrypoint**. The runtime call graph (`main.py` → `tools/__init__.py` → `dct_client/client.py`) is unchanged. The container is conceptually equivalent to running `python -m dct_mcp_server.main` inside a hermetic Python 3.11 environment.

```
┌──────────────────────── Host (macOS / Linux / Windows + WSL2) ────────────────────────┐
│                                                                                       │
│   MCP client (Claude Desktop / Cursor / VS Code)                                      │
│           │                                                                           │
│           │  spawns: docker run -i --rm -e DCT_API_KEY=... -e DCT_BASE_URL=...        │
│           │                          dct-mcp-server:dev                               │
│           ▼                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐    │
│   │   Container (linux/amd64, python:3.11.x-slim base)                          │    │
│   │                                                                             │    │
│   │     PID 1 = tini  (signal forwarding)                                       │    │
│   │           │                                                                 │    │
│   │           ▼                                                                 │    │
│   │     PID 2 = python -m dct_mcp_server.main   (USER appuser, UID 1000)        │    │
│   │           │                                                                 │    │
│   │           │  ── reads stdin (MCP requests) / writes stdout (responses)      │    │
│   │           │  ── reads DCT_* env vars                                        │    │
│   │           │  ── HTTPS → DCT_BASE_URL (via httpx, retry/backoff)             │    │
│   │           │  ── writes /app/logs/dct_mcp_server.log (rotating)              │    │
│   │           │     (mountable as `-v $(pwd)/logs:/app/logs`)                   │    │
│   │           ▼                                                                 │    │
│   │     dct_mcp_server source at /app/src/dct_mcp_server/                       │    │
│   └─────────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

### Source Files to Modify

| Path | Change | Notes |
|------|--------|-------|
| `Dockerfile` | **CREATE** | Multi-stage; see §3 for full layout. |
| `.dockerignore` | **CREATE** | See §4 for exact contents. |
| `README.md` | **MODIFY** | Add "Run with Docker" as a new `###` subsection of `## Advanced Installation` (insert between `### Developer Setup` (L375) and `### Connecting a Client to a Running Server` (L409)); add link entry to `## Table of Contents` (L9). See §5 for placement and content. |
| `.claude/rules/build-and-execution.md` | **MODIFY (small)** | Add a "Run with Docker" subsection mirroring the existing "Running the Server" structure. Source-of-truth for future CLAUDE.md regeneration. |

### Source Files NOT Modified

| Path | Reason |
|------|--------|
| `src/dct_mcp_server/**` | FR-2 / G5 require behavioral parity. No code changes. |
| `pyproject.toml` | FR-8 (AC-8.4) — no new dependencies needed. |
| `requirements.txt` | Existing pins are sufficient. The Dockerfile installs from this file as-is. |
| `start_mcp_server_*.sh`, `start_mcp_server_*.bat` | Out-of-scope per vision §3 and FR-* out-of-scope list. The container's entrypoint is `python -m dct_mcp_server.main` directly — these scripts are not invoked from the container. |
| `.gitignore` | The existing `.gitignore` already excludes `logs/`, `.env`, `__pycache__/`, `.venv`, `docs/`, `.worktrees/`. No change needed for git hygiene. The new `.dockerignore` is a separate file with overlapping but distinct purpose (build context vs. git history). |

---

## 3. Dockerfile — Multi-stage layout

### 3.1 Base image choice

Pin to **`python:3.11-slim-bookworm`** with a **specific patch version** (e.g. `python:3.11.9-slim-bookworm`) per AC-1.2.

Rationale (decision matrix):

| Candidate | Image size | Wheel availability | apt ergonomics | Verdict |
|-----------|-----------|--------------------|---------------- |---------|
| `python:3.11.9` (full) | ~1 GB | All | Native | Bloated. Reject. |
| `python:3.11.9-slim-bookworm` | ~125 MB | Manylinux wheels work | `apt-get` available if needed | **Selected**. Best size/compat tradeoff for our deps (no compiled extensions of our own; httpx + pyyaml + pydantic ship manylinux wheels). |
| `python:3.11.9-alpine` | ~50 MB | musl — pyyaml/pydantic require build-from-source on musl | `apk add` — but QR-3 forbids Alpine | Rejected by QR-3 (explicit). |
| `gcr.io/distroless/python3-debian12` | ~50 MB | All | No shell; no `apt` | Tempting but breaks AC-1.10 verification step (`docker run --entrypoint sh`) and complicates debugging. Reject. |
| `python:3.11.9-bookworm` | ~1 GB | All | Full Debian | Bloat. Reject. |

The exact patch version (`3.11.9`) will be pinned at implementation time to whatever is the **latest 3.11.x slim-bookworm tag with a published manifest digest** at the time of writing the Dockerfile, and the digest itself is also pinned (`FROM python:3.11.9-slim-bookworm@sha256:...`) to give a fully deterministic build per FR-7 / vision constraint #6.

### 3.2 Stage layout

Two stages: `builder` and `runtime`.

```dockerfile
# syntax=docker/dockerfile:1.7

# -----------------------------------------------------------------------------
# Stage 1: builder — installs Python deps into a venv we copy into runtime
# -----------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm@sha256:<DIGEST> AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for any wheel that needs compilation (currently none of our pinned
# deps require it on slim-bookworm + amd64, but keep this minimal set staged
# here so a future dep that needs compilation does not break the build).
# Pinning to bookworm package versions is deliberate (FR-7).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy ONLY dependency manifests first → maximises Docker layer cache reuse.
# Source changes will not bust this layer.
COPY requirements.txt ./

# Create a dedicated venv we will copy verbatim into the runtime stage.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: runtime — slim image with only the venv + source + tini + non-root user
# -----------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm@sha256:<DIGEST> AS runtime

# OCI labels (FR-6 / AC-6.8). Version is updated by hand or via a build arg
# at release time; the placeholder below is replaced by the implement phase
# from the actual pyproject.toml value.
LABEL org.opencontainers.image.title="dct-mcp-server" \
      org.opencontainers.image.source="https://github.com/delphix/dxi-mcp-server" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="2026.0.1.0-preview" \
      org.opencontainers.image.description="Delphix DCT API MCP Server" \
      org.opencontainers.image.documentation="https://github.com/delphix/dxi-mcp-server#run-with-docker"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1

# tini for proper PID-1 signal forwarding (AC-3.4 / R1 / R7 mitigation).
# Pinned via apt; this is the only runtime apt dep.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (FR-6 / AC-1.7 / AC-6.1). UID/GID 1000 is conventional and
# matches typical host-user UID on Linux, which keeps `-v` mounts of `logs/`
# writable without `--user` overrides on Linux hosts.
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 --home-dir /app --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy the venv from builder (no compilers, no caches, no apt lists).
COPY --from=builder /opt/venv /opt/venv

# Copy source. .dockerignore filters out everything we don't need.
# The COPY is a single layer for the source so it changes together.
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser docs/api-external.yaml /app/docs/api-external.yaml
COPY --chown=appuser:appuser pyproject.toml requirements.txt /app/

# Pre-create the writable directory for logs and chown to appuser so a
# bind-mount on Linux works without manual chown on the host.
RUN mkdir -p /app/logs/sessions \
    && chown -R appuser:appuser /app

USER appuser

# PYTHONPATH so `python -m dct_mcp_server.main` finds the src layout without
# needing an editable install. (We did not pip-install the package itself in
# the venv — only its deps — to keep the image small and deterministic.)
ENV PYTHONPATH=/app/src

# stdio transport: no EXPOSE, no HEALTHCHECK (AC-6.7 — intentional).
# tini handles SIGTERM/SIGINT correctly so docker stop triggers the existing
# lifespan shutdown path in main.py (AC-3.4 / R1).
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "dct_mcp_server.main"]

STOPSIGNAL SIGTERM
```

### 3.3 Layer-cache strategy

Layers from least-to-most-frequently-changing:

1. Base image (changes only when we bump the pinned digest).
2. apt install of `tini` + cleanup.
3. Non-root user creation.
4. `COPY --from=builder /opt/venv` — busted only when `requirements.txt` changes.
5. `COPY src/` — busted on every code change (expected and isolated).
6. `mkdir logs && chown` — small, late.

Source changes only invalidate steps 5+, leaving the dependency install (the slow part) cached.

### 3.4 Why we don't `pip install .` of the project itself

`pyproject.toml` declares the `dct-mcp-server` console script entry point. We could `pip install .` to get that script. We deliberately **don't**, because:

- It would require `hatchling` build backend in the image (extra build deps).
- The container's invocation form is `python -m dct_mcp_server.main` (matches AC-1.4 verbatim).
- `PYTHONPATH=/app/src` + the existing `if __name__ == "__main__"` in `main.py` is sufficient.
- Smaller image, fewer layers, no build backend in the runtime path.

Trade-off: a user who `docker run`s the image and tries `dct-mcp-server` (the console-script form) will get "command not found". This is acceptable because the documented invocation is `docker run dct-mcp-server:dev` (the image name carries the role of the command). README will make this explicit.

### 3.5 `linux/amd64` only for v1

Per vision §3 ("Multi-arch image publishing — out of scope"). The Dockerfile itself is arch-agnostic; the implementer builds with `--platform=linux/amd64` (or omits the flag on amd64 hosts). Apple Silicon Macs run via Rosetta emulation through Docker Desktop. arm64 native is a follow-up.

### 3.6 What the Dockerfile does NOT have

| Feature | Why omitted |
|---------|-------------|
| `EXPOSE` | stdio transport — no listening port. |
| `HEALTHCHECK` | AC-6.7 — no useful liveness probe for stdio. |
| `VOLUME` | Adds noise without benefit — we recommend `-v` at run time, but declaring `VOLUME /app/logs` would force anonymous-volume creation on every `docker run` even when the user doesn't mount one. |
| `ARG VERSION=...` build arg + dynamic `LABEL` | Future enhancement once a CI pipeline exists. v1 hardcodes the version label from `pyproject.toml`. The implement phase MAY introduce a build arg if it can be done without complicating the README; otherwise hardcode + add a `<!-- TODO -->` comment. |
| `--mount=type=cache,target=...` (BuildKit pip cache) | Adds non-determinism and requires BuildKit. v1 keeps the build portable. |

---

## 4. `.dockerignore`

### 4.1 Contents (final)

```dockerignore
# VCS
.git/
.gitignore
.gitattributes
.github/

# Python
__pycache__/
*.py[cod]
*.pyo
*.egg-info/
build/
dist/
wheels/
.venv/
venv/
env/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# OS / IDE noise
.DS_Store
.DS_Store?
._*
Thumbs.db
ehthumbs.db
.idea/
.vscode/
*.swp
*.swo
*~

# Project-local secrets and local-only state
.env
.env.*
!.env.example
*.log
logs/
mcp_server_setup_logfile.txt

# Claude Code workspace (NOT runtime — purely dev tooling)
.claude/
.worktrees/

# Docs are dev artifacts, NOT runtime — except api-external.yaml, which is
# COPIed explicitly in the Dockerfile from docs/api-external.yaml.
docs/

# Host-only startup scripts (the container does not invoke these)
start_mcp_server_python.sh
start_mcp_server_uv.sh
start_mcp_server_windows_python.bat
start_mcp_server_windows_uv.bat

# Misc
node_modules/
.coverage
htmlcov/
*.cover

# Don't ship the Dockerfile itself or this file into the image
Dockerfile
.dockerignore
```

### 4.2 Rationale per AC

- **AC-5.1** — file present at repo root.
- **AC-5.2** — every required pattern listed.
- **AC-5.3** — with `docs/` (≈10 MB of YAML/MD), `logs/`, `.git/` (large), `.venv/` excluded, the build context drops well under 5 MB. Empirically validated during implement phase using `docker build --no-cache .` and reading the "Sending build context" line.
- **AC-5.4** — `src/` is **not** excluded, and the patterns `*.txt` / `config/` are **not** in the ignore file. The toolset `.txt` files and `manual_confirmation.txt` will copy through with `COPY src/`. **Note**: a single `*.txt` exclusion would silently break the toolsets — explicitly verified by the test plan (T-IMG-3).
- **AC-5.5** — `pyproject.toml`, `requirements.txt`, `README.md` are **not** in the ignore file. They are copied explicitly by the Dockerfile.
- **Special case — `docs/`**: `docs/` is in the ignore file (for context speed and to keep workflow `*.md` artefacts out), but `docs/api-external.yaml` is required at runtime as the bundled fallback for `tool_factory.py` (see vision R3). The `.dockerignore` syntax `docs/` blanket-excludes the directory; the Dockerfile uses an explicit `COPY docs/api-external.yaml /app/docs/api-external.yaml`. Docker honors `.dockerignore` first, so we use a re-include pattern: `!docs/api-external.yaml` — but Docker's `.dockerignore` re-include for a file inside an excluded directory only works if **the directory itself is not excluded by a more specific pattern**. The reliable form, therefore:

```
docs/**
!docs/api-external.yaml
```

(replacing the bare `docs/` line above — the implement phase will use the `docs/**` + `!docs/api-external.yaml` form to make the re-include work).

### 4.3 Consistency with `.gitignore`

`.gitignore` already excludes `logs/`, `.env`, `.venv`, `docs/`, `.worktrees/`, `.vscode/`, `.idea/`, `__pycache__/`. The `.dockerignore` is a strict superset of these plus IDE/OS noise plus the host-only startup scripts. They serve different purposes (one filters git history, the other filters build context) but using consistent patterns prevents drift (QR-7).

---

## 5. README integration plan

### 5.1 Insertion points

1. **`## Table of Contents` (currently L9–22)**: insert `- [Run with Docker](#run-with-docker)` between `- [Advanced Installation](#advanced-installation)` (L15) and `- [Toolsets](#toolsets)` (L16). Anchor matches the section heading slug.

2. **New `### Run with Docker` subsection**: insert as a new `###` subsection of `## Advanced Installation`, between `### Developer Setup` (currently L375) and `### Connecting a Client to a Running Server` (currently L409). Rationale: Docker is "another way to run it as a standalone tool", so it belongs alongside `Quick Start (Command-Line Tool)` and `Developer Setup`.

   Heading depth `###` matches sibling subsections. `## Run with Docker` (top-level) was considered but breaks the existing "everything that's not the recommended client-config method lives under Advanced Installation" structure.

### 5.2 Section content (skeleton)

The implementer writes the prose; this skeleton enumerates exactly what must appear (mapped to FR-4 ACs).

```
### Run with Docker

Run the MCP server inside a Docker container — useful when you don't want to
install Python or `uv` on the host, or when you need a hermetic, reproducible
runtime (for example on Windows hosts via Docker Desktop + WSL2 backend, or
in air-gapped environments after building the image once).

> **Note**: this image is for **local-development MCP usage**. The MCP transport
> is stdio, so the container is launched per-session by the MCP client — it is
> not a long-lived hosted service. (AC-4.5)

#### Prerequisites
- Docker (Linux, macOS, or Windows with Docker Desktop + WSL2 backend, Linux containers mode).
- Network access to your DCT instance from the host.
- A valid `DCT_API_KEY`.

(AC-4.2 step 1)

#### Build from source

bash / zsh:
    git clone https://github.com/delphix/dxi-mcp-server.git
    cd dxi-mcp-server
    docker build -t dct-mcp-server:dev .

PowerShell:
    git clone https://github.com/delphix/dxi-mcp-server.git
    cd dxi-mcp-server
    docker build -t dct-mcp-server:dev .

(AC-4.2 step 2)

#### Pull from registry  *(placeholder — pending registry provisioning)*

<!-- TODO(DLPXECO-13635): swap placeholder for real registry URL once provisioned -->

The image will be published to a registry in a future release. The intended
form is:

    docker pull <registry-host>/delphix/dct-mcp-server:<tag>

For now, build from source as shown above.

(AC-4.2 step 3, AC-4.3, AC-4.6 mark, QR-6 — uses fake-looking `<registry-host>`)

#### Run the server (interactive)

bash / zsh:
    docker run --rm -i \
      -e DCT_API_KEY="your-api-key" \
      -e DCT_BASE_URL="https://your-dct-host.company.com" \
      dct-mcp-server:dev

PowerShell:
    docker run --rm -i `
      -e DCT_API_KEY="your-api-key" `
      -e DCT_BASE_URL="https://your-dct-host.company.com" `
      dct-mcp-server:dev

cmd.exe:
    docker run --rm -i ^
      -e DCT_API_KEY=your-api-key ^
      -e DCT_BASE_URL=https://your-dct-host.company.com ^
      dct-mcp-server:dev

> Use `-i` (no `-t`). MCP is a JSON-RPC stream over stdio — a TTY would
> mangle line buffering on Windows and is not needed.

(AC-4.2 step 4, AC-4.4 — three shells)

#### Optional environment variables

The container honours every env var documented in
[Environment Variables](#environment-variables) — pass each with `-e VAR=value`.

(AC-4.2 step 5 — references existing table; no duplication, satisfies AC-4.6)

#### Persisting logs (optional)

Mount the host `logs/` directory:

    docker run --rm -i \
      -e DCT_API_KEY="..." -e DCT_BASE_URL="..." \
      -v "$(pwd)/logs:/app/logs" \
      dct-mcp-server:dev

(satisfies AC-2.6 documentation; PowerShell variant inline using ${PWD})

#### Wire into MCP clients

Claude Desktop (`claude_desktop_config.json`):

    {
      "mcpServers": {
        "delphix-dct": {
          "command": "docker",
          "args": [
            "run", "--rm", "-i",
            "-e", "DCT_API_KEY=your-api-key",
            "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
            "dct-mcp-server:dev"
          ]
        }
      }
    }

> The MCP client launches a fresh container per session; the container exits
> when the client closes the connection.

(AC-4.2 step 6)
```

### 5.3 What does NOT change in README

- All existing `uvx` / `pip install` / startup-script content (AC-4.6 — additive only).
- The existing `Environment Variables` table — referenced, not duplicated.

### 5.4 Heading-anchor verification

The slug for `### Run with Docker` is `run-with-docker`. The TOC link `[Run with Docker](#run-with-docker)` resolves correctly under GitHub's heading-anchor algorithm. The implement phase verifies by rendering the README locally (or pushing to a branch and checking the GitHub web UI).

---

## 6. Test plan

The functional spec generates the requirements; this section maps each FR/AC to a verifiable test step. Per `.claude/rules/testing.md`, automated unit tests are not part of this project — verification is **build-time** (Docker build / `docker history` / file presence) and **runtime** (live MCP-client connection against a real DCT). The Test phase will collect and write evidence into `docs/DLPXECO-13635-test-evidence.md`.

### 6.1 Test categories

| ID prefix | Category | Performed by |
|-----------|----------|--------------|
| **T-BLD-*** | Build-time checks (`docker build`, `docker images`, `docker history`, file inspection) | Implementer at end of `implement` phase |
| **T-IMG-*** | Container introspection (`docker run --entrypoint sh`) | Implementer at end of `implement` phase |
| **T-RUN-*** | Runtime against live DCT — one MCP client + one toolset per FR-2/FR-3 path | Tester during `test` phase |
| **T-DOC-*** | README / docs lint | Implementer + reviewer in `validate` phase |

### 6.2 Test matrix

| ID | What to verify | How | Maps to |
|----|----------------|-----|---------|
| **T-BLD-1** | Image builds clean on a host with no prior Docker cache | `docker build --no-cache --pull -t dct-mcp-server:dev .` exits 0 | FR-1 / AC-1.1, FR-7 / AC-7.4 |
| **T-BLD-2** | Build context size < 5 MB | Read "Sending build context to Docker daemon" line from build output | AC-5.3 |
| **T-BLD-3** | Final image ≤ 250 MB compressed | `docker save dct-mcp-server:dev | gzip -c | wc -c` | AC-1.9 |
| **T-BLD-4** | No `pip` cache, no `apt` lists, no build deps in runtime layer | `docker history --no-trunc dct-mcp-server:dev` — confirm `gcc` / `build-essential` not in any runtime-stage layer; `/var/lib/apt/lists` absent | AC-6.4 / AC-6.5 / AC-6.6 |
| **T-BLD-5** | OCI labels present | `docker inspect dct-mcp-server:dev | jq '.[0].Config.Labels'` | AC-6.8 |
| **T-BLD-6** | No `HEALTHCHECK` directive | `docker inspect dct-mcp-server:dev | jq '.[0].Config.Healthcheck'` returns null | AC-6.7 |
| **T-BLD-7** | `STOPSIGNAL` is `SIGTERM` | `docker inspect dct-mcp-server:dev | jq '.[0].Config.StopSignal'` returns `"SIGTERM"` | AC-3.4 mitigation |
| **T-BLD-8** | Build succeeds with `--platform=linux/amd64` from arm64 host (Apple Silicon) | Run `docker build --platform=linux/amd64 -t dct-mcp-server:dev .` on Mac M-series | AC-3.1 |
| **T-BLD-9** | Hadolint clean (errors only — warnings acceptable per AC-8.1) | `docker run --rm -i hadolint/hadolint < Dockerfile` returns no error-level findings; any warnings are explained inline with `# hadolint ignore=...` comments | AC-8.1 |
| **T-IMG-1** | Image runs as non-root | `docker run --rm dct-mcp-server:dev id` — UID/GID = 1000 | AC-1.7, AC-6.1, AC-6.2 |
| **T-IMG-2** | No `.git/`, `.claude/`, `.venv/`, `logs/`, `docs/DLPXECO-13635-*.md` in image | `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls -la /app && ls -la /app/.git 2>/dev/null; ls /app/.claude 2>/dev/null; ls /app/logs 2>/dev/null'` — first ls shows expected files; the others either error out or show only the runtime-created `logs/` dir (empty/owned by appuser) | AC-1.10, AC-5.2 |
| **T-IMG-3** | Toolset `.txt` files and `manual_confirmation.txt` present | `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls /app/src/dct_mcp_server/config/toolsets && ls /app/src/dct_mcp_server/config/mappings'` — all 6 toolset files + the confirmation mappings file present | AC-5.4, R8 mitigation |
| **T-IMG-4** | `docs/api-external.yaml` present at `/app/docs/api-external.yaml` | `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'ls -la /app/docs/api-external.yaml'` | R3 mitigation |
| **T-IMG-5** | No credentials, `.env`, or API key fragments in any layer | `docker history --no-trunc dct-mcp-server:dev | grep -iE '(api[_-]?key|password|secret|\.env)'` returns no matches; `docker run --rm --entrypoint sh dct-mcp-server:dev -c 'find / -name "*.env" -o -name "*api*key*" 2>/dev/null'` returns nothing | AC-6.3 |
| **T-IMG-6** | Python module import smoke test | `docker run --rm --entrypoint python dct-mcp-server:dev -c "import dct_mcp_server.config.loader as l; toolsets = ['self_service','self_service_provision','continuous_data_admin','platform_admin','reporting_insights']; [print(t, len(l.parse_toolset_file(t)) if hasattr(l,'parse_toolset_file') else 'ok') for t in toolsets]"` — succeeds without exceptions; each toolset name prints | R8, FR-2 |
| **T-RUN-1** | Container starts MCP server on stdio and accepts `initialize` | Wire into Claude Desktop using the README config; open a new Claude Desktop conversation; verify the server connects and `tools/list` returns at least the `self_service` tool set | AC-2.1, AC-2.2 |
| **T-RUN-2** | All `DCT_*` env vars take effect | Set `DCT_LOG_LEVEL=DEBUG` and `DCT_TOOLSET=continuous_data_admin` via `-e`; verify the running tool count matches `continuous_data_admin` (22 tools) and DEBUG logs appear in mounted `logs/dct_mcp_server.log` | AC-2.3 |
| **T-RUN-3** | Live DCT API call parity | Run `vdb_tool(action="search")` from Claude Desktop against the containerised server, then against a host-clone server pointing at the same DCT instance — compare JSON shapes and tool counts | AC-2.4 |
| **T-RUN-4** | `DCT_TOOLSET=auto` works end-to-end | Configure with `-e DCT_TOOLSET=auto`; in Claude Desktop run `list_available_toolsets`, `enable_toolset(name="self_service")`, `vdb_tool(action="search")`, `disable_toolset()` — all succeed; tool list updates between calls | AC-2.5 |
| **T-RUN-5** | Logs mounted to host | Run with `-v $(pwd)/logs:/app/logs`; after a session, host `./logs/dct_mcp_server.log` contains entries owned by UID 1000 | AC-2.6 |
| **T-RUN-6** | Telemetry mount works when opted in | Add `-e IS_LOCAL_TELEMETRY_ENABLED=true` to T-RUN-5 setup; host `./logs/sessions/<session_id>.log` appears | AC-2.7 |
| **T-RUN-7** | Windows host (Docker Desktop + WSL2) | Repeat T-RUN-1 from a Windows 11 host with Docker Desktop in Linux-containers mode, using PowerShell `docker run` form from README | AC-3.1, AC-3.2, AC-3.3 |
| **T-RUN-8** | `docker stop` triggers clean shutdown | Start the container, then `docker stop <id>` from a second terminal; in mounted log, observe the existing `handle_shutdown` lifespan-finally output | AC-3.4 |
| **T-RUN-9** | Confirmation flow works inside container | From Claude Desktop, run a destructive action against a test target (e.g. `bookmark_tool` delete on a throwaway bookmark) — first call returns `confirmation_required`; "yes, go ahead and confirm" executes | functional parity, exercises sample from `.claude/rules/testing/self_service.md` step 56 |
| **T-DOC-1** | "Run with Docker" section exists, is in TOC, uses correct heading depth | Manual review of `README.md`; render preview on a branch | AC-4.1, AC-4.7 |
| **T-DOC-2** | Section answers the 6 FR-4 questions in order | Manual review of section content vs. AC-4.2 list | AC-4.2 |
| **T-DOC-3** | Registry placeholder is grep-able and uses fake host | `grep -n 'TODO(DLPXECO-13635)' README.md` finds the marker; placeholder host is `<registry-host>` (not a real-looking domain) | AC-4.3, QR-6 |
| **T-DOC-4** | bash + PowerShell + cmd forms are all present where they differ | Manual review of section examples | AC-4.4 |
| **T-DOC-5** | Docker section warns it's local-development MCP usage | Search for the exact warning sentence | AC-4.5 |
| **T-DOC-6** | Existing install instructions are unchanged | `git diff main..HEAD -- README.md` — only additions; no edits to `## Quick Start`, `## MCP Client Configuration`, `### Setting Environment Variables`, `### Quick Start (Command-Line Tool)`, `### Developer Setup` | AC-4.6 |
| **T-DOC-7** | LF line endings on new files | `file Dockerfile .dockerignore` reports "ASCII text" (no CRLF) | QR-1 |
| **T-DOC-8** | No trailing whitespace, terminal newline present | `git diff --check` clean | QR-2 |
| **T-DOC-9** | `.claude/rules/build-and-execution.md` updated with Docker subsection | Manual review | AC-8.3 |

### 6.3 Coverage table (FR/AC → tests)

| FR | ACs | Tests |
|----|-----|-------|
| FR-1 | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10 | T-BLD-1, T-BLD-3, T-IMG-1, T-IMG-2; AC-1.2..1.6 / 1.8 verified by Dockerfile review |
| FR-2 | 2.1..2.7 | T-RUN-1, T-RUN-2, T-RUN-3, T-RUN-4, T-RUN-5, T-RUN-6, T-IMG-6 |
| FR-3 | 3.1..3.5 | T-BLD-8, T-RUN-7, T-RUN-8 |
| FR-4 | 4.1..4.7 | T-DOC-1, T-DOC-2, T-DOC-3, T-DOC-4, T-DOC-5, T-DOC-6 |
| FR-5 | 5.1..5.5 | T-BLD-2, T-IMG-3 (negative — verify .txt config files NOT excluded) |
| FR-6 | 6.1..6.8 | T-IMG-1, T-IMG-5, T-BLD-4, T-BLD-5, T-BLD-6 |
| FR-7 | 7.1..7.4 | T-BLD-1 (with `--no-cache --pull`) |
| FR-8 | 8.1..8.4 | T-BLD-9, T-DOC-1, T-DOC-9, design-doc verification (no `pyproject.toml` change) |
| QR-1..QR-7 | — | T-DOC-7, T-DOC-8, T-DOC-3 (QR-6), pattern review |

Every FR-* and quality rule has at least one test. Every test has at least one mapped AC (no orphan tests).

### 6.4 DCT toolset coverage for T-RUN-* (per `.claude/rules/testing.md`)

The change is a packaging / distribution layer — it does not modify any toolset, tool implementation, confirmation rule, or auto-mode behavior. Per the testing rules table, this fits the "Dynamic tool generation change" / general functional-parity category. The minimum live-DCT coverage:

- **`self_service`** (default, smallest) — proves the happy path (T-RUN-1).
- **`continuous_data_admin`** (largest pre-built toolset, 22 tools) — proves no regression on the high-end tool count and that all `*_endpoints_tool.py` modules import correctly inside the container (T-RUN-2).
- **`auto`** — proves dynamic-toolset behavior survives containerization (T-RUN-4); uses Claude Desktop per `.claude/rules/testing/auto.md` guidance.

Other toolsets (`self_service_provision`, `platform_admin`, `reporting_insights`) are out of scope for this ticket's runtime testing but covered transitively because the Dockerfile makes no toolset-specific decisions.

### 6.5 MCP client coverage for T-RUN-*

- **Claude Desktop** is the primary client for T-RUN-1, T-RUN-2, T-RUN-4, T-RUN-7. It supports stdio + dynamic tool switching, matching the project's existing test guidance.
- **VS Code Copilot** smoke test: launch with `DCT_TOOLSET=self_service` (fixed mode) per `.claude/rules/testing.md` recommendation. Verifies stdio over Docker works in a different MCP client implementation (catches CRLF / line-buffer issues per R1).
- **Cursor** is optional — covered transitively if Claude Desktop and VS Code Copilot both pass.

### 6.6 Test evidence template

`docs/DLPXECO-13635-test-evidence.md` (produced in the `test` phase) must contain:

- Docker version (`docker version`).
- Host OS for each T-RUN-* execution (macOS / Linux / Windows host).
- DCT version that the live API calls were made against.
- Per-test row: ID, status (pass/fail), evidence (command output snippet or screenshot reference).
- Aggregate pass/fail summary.

---

## 7. FR-9 decision: drop `docker-compose.yml`

**Decision: do NOT ship `docker-compose.yml` in this implementation.**

### 7.1 Why FR-9 was optional

The functional spec marks FR-9 as "optional", to be decided at design time. The vision §3 already lists `docker-compose.yml` as a non-goal, with the carve-out "may be added as a documentation example only if it clarifies the wiring."

### 7.2 Reasons to drop it

1. **No companion services**. Compose's value is orchestrating multiple services (a server + a database + a cache). The MCP server has none — it talks to a remote DCT over HTTPS. A single-service compose file is just a wordier `docker run`.

2. **Stdio doesn't compose**. MCP uses stdio. `docker compose up` runs containers detached and **does not attach the MCP client to stdin/stdout** — the client launches the container itself per session, so compose adds zero value to the actual MCP wiring path. Demonstrating compose risks teaching users a pattern that doesn't work for their real use case.

3. **Adds new failure surface**. A compose file introduces a `.env` example, the question of whether to include the API key in it, and version-pinning of the compose schema — all noise for a feature whose ticket goal is "run the server in a container."

4. **README story stays cleaner**. Adding compose forces a "use compose vs. use docker run" decision into the README; users would have to read two paths and pick one. AC-4.2 already covers the docker-run path completely.

5. **YAGNI**. There is no concrete user request for compose. The ticket asks for a Dockerfile, README, Windows support, and a placeholder URL. All four are met without compose.

### 7.3 Consequence

- Functional spec scope is reduced: AC-9.1..AC-9.4 are not evaluated. The implement phase does not create `docker-compose.yml` or `.env.example`.
- If a user later asks for compose, it can be added as a follow-up — the Dockerfile is already designed to be the building block (FR-9 / AC-9.2 was already going to require it). No future redesign needed.

---

## 8. Risks revisited (from vision §5)

| # | Mitigation in this design |
|---|---------------------------|
| R1 — Windows stdio | tini as PID 1; `-i` (no `-t`) documented; PowerShell + cmd examples; T-RUN-7 explicitly tests on Windows. |
| R2 — Image bloat | `python:3.11-slim-bookworm` + multi-stage; `--no-install-recommends`; `rm -rf /var/lib/apt/lists/*`; `--no-cache-dir`; build-essential confined to builder stage; T-BLD-3 enforces ≤ 250 MB. |
| R3 — `$TEMP` ephemerality on every container start | Accepted. Bundled `docs/api-external.yaml` is `COPY`ed into the image (T-IMG-4) so generation always has a fallback. README documents the ~1–2s startup cost. |
| R4 — Non-root + log volume permissions | UID 1000 matches typical host user on Linux; `chown -R appuser:appuser /app`; README's volume-mount example tested in T-RUN-5. Document `--user` override for debugging. |
| R5 — Placeholder registry URL | Marked with `<!-- TODO(DLPXECO-13635): ... -->` (AC-4.3); placeholder host is `<registry-host>` (QR-6); T-DOC-3 verifies. |
| R6 — `urllib3>=2.6.3` + `apk ` API-key prefix | Honored unchanged — no source code change, requirements.txt unchanged. T-RUN-3 verifies via live API call parity. |
| R7 — Container must not invoke startup scripts | Dockerfile `CMD` is `python -m dct_mcp_server.main` directly; startup scripts are excluded by `.dockerignore` so they're not even in the image. |
| R8 — Toolset config files might be missed | `.dockerignore` does NOT exclude `*.txt`; `COPY src/` is the single comprehensive copy of the package; T-IMG-3 enforces toolset files are present; T-IMG-6 imports the loader as a smoke test. |

---

## 9. Implementation order

The implementer should produce changes in this order to keep each commit reviewable:

1. **Commit 1** — `Dockerfile` + `.dockerignore`.
   - Build locally; run T-BLD-1..T-BLD-9 + T-IMG-1..T-IMG-6.
   - Smallest reviewable unit; no docs noise.

2. **Commit 2** — `README.md` "Run with Docker" subsection + TOC entry.
   - Run T-DOC-1..T-DOC-8.
   - Separate from commit 1 per `.claude/rules/git-workflow.md` guidance: "Separate toolset config changes from code changes where possible" — analogous principle for docs vs. infra.

3. **Commit 3** — `.claude/rules/build-and-execution.md` Docker subsection (AC-8.3 / T-DOC-9).
   - Trivial; gives future automation (CLAUDE.md regeneration) a source of truth for Docker as a run path.

The `test` and `validate` phases run T-RUN-* and the doc-coverage / lint pass against the merged result.

---

## 10. Open items deferred to implement / test phases

- Exact pinned digest for `python:3.11.x-slim-bookworm` — implementer pulls the latest 3.11.x slim-bookworm and records the digest at the time of writing the Dockerfile.
- Exact pinned `tini` version from Debian bookworm `apt` — captured by the `apt-get install` invocation; reproducibility is governed by the base image digest.
- Whether to keep `pyproject.toml` + `requirements.txt` both inside the image (currently both are copied) or trim to just `requirements.txt`. Decision: keep both — total cost is ~1 KB and `pyproject.toml` is needed if anyone ever runs `pip install /app` from inside the container for debugging.
- Whether to ship `arm64` natively in v1. Decision (per vision §3): **no**. Implementer builds `linux/amd64` only; arm64 is a follow-up.

---

## 11. Out of scope (reaffirmed)

Per functional spec §"Out of scope (explicit)" and vision §3:

1. CI / image publishing.
2. Helm / k8s manifests.
3. HTTP / SSE transport.
4. arm64 / Windows-container variants.
5. Source code changes in `src/dct_mcp_server/`.
6. Changes to `start_mcp_server_*.sh` / `.bat`.
7. `docker-compose.yml` and `.env.example` (FR-9 — see §7).

---

## Cross-references

- Vision: [DLPXECO-13635-vision.md](DLPXECO-13635-vision.md)
- Functional spec: [DLPXECO-13635-functional.md](DLPXECO-13635-functional.md)
- Project rules: `.claude/rules/build-and-execution.md`, `.claude/rules/code-style.md`, `.claude/rules/git-workflow.md`, `.claude/rules/testing.md`
- Architecture map: `.claude/architecture.md`
- MCP server entry point: `src/dct_mcp_server/main.py`
- Existing startup scripts (preserved, not invoked from container): `start_mcp_server_uv.sh`, `start_mcp_server_python.sh`, `start_mcp_server_windows_uv.bat`, `start_mcp_server_windows_python.bat`
