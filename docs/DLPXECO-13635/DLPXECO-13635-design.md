# Feature Design: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: DLPXECO-13635" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

---

## Summary

This feature re-implements Docker support for the DCT MCP Server (`dct-mcp-server`) after a prior implementation was reverted due to a startup crash caused by incorrect log-directory path detection when the package runs from `site-packages`. The change fixes `GlobalLogger._get_project_root()` in `src/dct_mcp_server/core/logging.py` so that installed-package environments (Docker, `pip install`, `uvx`) write logs to `Path.cwd()` instead of traversing up into the Python library path. Alongside the logging fix, a `Dockerfile`, `.dockerignore`, `docker-compose.yml`, and a `## Running with Docker` section in `README.md` are added, enabling users who cannot or prefer not to install Python 3.11+ or `uv` locally to run the MCP server as a minimal non-root container. No new Python dependencies are introduced and all existing installation paths remain unaffected.

## Affected Components

<!-- Component checklist derived from .claude/architecture.md layer map. -->
- [x] `core/logging.py` — `_get_project_root()` logic changed (FR-001)
- [ ] `main.py` — no changes; entry point is unaffected
- [ ] `tools/__init__.py` — no changes
- [ ] `tools/*_endpoints_tool.py` — no changes
- [ ] `tools/core/meta_tools.py` — no changes
- [ ] `tools/core/tool_factory.py` — no changes
- [ ] `config/config.py` — no changes
- [ ] `config/loader.py` — no changes
- [ ] `config/toolsets/*.txt` — no changes
- [ ] `config/mappings/manual_confirmation.txt` — no changes
- [ ] `dct_client/client.py` — no changes
- [ ] `core/session.py` — no changes
- [ ] `core/decorators.py` — no changes
- [ ] `core/exceptions.py` — no changes
- [x] `Dockerfile` — new file (FR-002)
- [x] `.dockerignore` — new file (FR-003)
- [x] `docker-compose.yml` — new file (FR-004)
- [x] `README.md` — new Docker section added (FR-005)
- [x] `tests/core/test_logging.py` — new/updated unit tests for `_get_project_root()` (FR-001, QR-1)

## Architecture Changes

### Schema / Config Changes

None. No schema files, database models, or persisted state shapes change. Environment variables consumed by the server (`DCT_API_KEY`, `DCT_BASE_URL`, etc.) are unchanged. The `docker-compose.yml` references an `.env` file on the developer's local machine — this file is never committed and is already git-ignored.

### Source Files to Modify

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/core/logging.py` | Fix `_get_project_root()`: add primary guard checking `"site-packages" in str(resolved_file)` and secondary guard checking `not os.access(str(candidate), os.W_OK)`. Add `PermissionError` handling in `_setup_global_handlers` for unwritable CWD. | FR-001 |
| `tests/core/test_logging.py` | Add `TestGetProjectRoot` test class with `test_site_packages_returns_cwd`, `test_dev_clone_returns_repo_root`, and `test_editable_install_returns_repo_root` test methods. | FR-001 |
| `README.md` | Add `## Running with Docker` section (prerequisites, build, run on Linux/macOS and Windows, log persistence, SSL/CA note, MCP client config subsections); update Table of Contents. | FR-005 |

### New Files (if any)

- `Dockerfile` — single-stage `python:3.11-slim` image; creates `mcpuser` (UID/GID 1000), installs package, sets `WORKDIR /app`, exposes `dct-mcp-server` as `CMD`
- `.dockerignore` — excludes secrets (`.env`), VCS metadata, build artefacts, dev tooling, and test directories from the Docker build context
- `docker-compose.yml` — single `dct-mcp-server` service; `stdin_open: true`, `tty: false`, `env_file: .env`, log volume mount `./logs:/app/logs`

## Version Compatibility

<!-- This project is a Python package, not a versioned API server. The version axis here refers to the Python version and Docker compatibility matrix, not DCT API versions. -->

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11 | Yes | No | Minimum supported Python version; `python:3.11-slim` base image |
| Python 3.12 | Yes | No | Tested in CI; no code path differences |
| Python 3.13 | Yes | No | Compatible; `python:3.11-slim` image pins to 3.11 in Docker, but local dev with 3.13 is unaffected |
| Docker 20.10+ | Yes | No | Minimum Docker version for reliable `--init` and BuildKit support |
| Docker Buildx (multi-arch) | Optional | No | Required only for `--platform linux/amd64,linux/arm64`; single-arch `docker build` works without it |

## Platform Behavior Notes

<!-- Flagging key platform behaviors from .claude/architecture.md that this feature interacts with. -->

- **API key prefix** (`DCTAPIClient` prepends `apk ` automatically — do not prefix in env vars) — **Affects**: README Docker examples must show `DCT_API_KEY=<raw key>` without the `apk` prefix; environment variables passed via `-e` flags or `.env` file are raw values exactly as with non-Docker usage.
- **SSL defaults to `verify=false`** — **Affects**: Docker run examples include `DCT_VERIFY_SSL=false` (default) as a comment; the SSL/CA cert note in README documents how to set `SSL_CERT_FILE` for private CA environments.
- **Retries: exponential backoff up to `DCT_MAX_RETRIES`** — **N/A**: retry behavior is unchanged inside Docker; the network topology (container → DCT) is transparent to the client layer.
- **Toolset config cache (`@lru_cache`)** — **N/A**: the cache is per-process; container restarts are a clean process start, so cache invalidation is not a concern.
- **Telemetry opt-in (`IS_LOCAL_TELEMETRY_ENABLED`)** — **Affects**: telemetry session logs are written to `logs/sessions/{id}.log`; if the `./logs` volume is mounted, these are persisted to the host. README notes this behavior.
- **Transport: stdio** — **Affects**: `docker run` must always include `-i` to keep stdin open for MCP stdio framing. `docker-compose.yml` sets `stdin_open: true`. README includes a prominent callout that `-i` is required.

## Open Questions / Risks

- R: The logging fix (`site-packages` string check) could theoretically misfire on a repo cloned into a path that contains a directory named `site-packages` (e.g. `/home/user/site-packages/dxi-mcp-server/src/...`). — Mitigation: the secondary guard (`os.access` check) catches this edge case; additionally AC-2 of FR-001 covers the dev-clone path test. Documented in FR-001 EC-9/EC-10.
- R: `python:3.11-slim` base image may receive a security patch between project builds, causing non-reproducible builds. — Mitigation: pin to `python:3.11-slim-bookworm` (stable Debian bookworm variant) in `Dockerfile` for reproducibility. A future task can pin to a specific digest if SBOM requirements arise.
- R: Windows Docker Desktop volume-mount path format differs between Command Prompt (`%cd%`) and PowerShell (`${PWD}`). — Mitigation: README provides both variants; no code change needed.
- Q: Should `docker-compose.yml` use `docker compose` V2 syntax (`compose.yml`) or the legacy `docker-compose.yml` name? — Current decision: `docker-compose.yml` for V1/V2 compatibility (see Functional spec A2). No change anticipated.
- Q: Future CI integration (Docker build job in `ci.yml`) is explicitly out of scope (NG2), but the `Dockerfile` should be authored such that it can be added to CI without modification. — Owner: Vinay Byrappa. Non-blocking for this ticket.

## Acceptance Criteria

<!-- Derived from FR Acceptance Criteria and vision Success Criteria (SC1–SC6). -->

- [ ] AC-1 (FR-001/SC2): `docker run --rm -i -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost dct-mcp-server` starts without a Python traceback; a connection-refused or MCP handshake message is acceptable output.
- [ ] AC-2 (FR-001): Given `_get_project_root()` with `__file__` containing `site-packages`, the return value equals `Path.cwd()` (unit test `test_site_packages_returns_cwd` passes).
- [ ] AC-3 (FR-001): Given `_get_project_root()` with a dev-clone `__file__`, the return value is the repo root (unit test `test_dev_clone_returns_repo_root` passes).
- [ ] AC-4 (FR-001/SC3): `docker run --rm -i -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost -v ./logs:/app/logs dct-mcp-server` writes `logs/dct_mcp_server.log` to the mounted host directory.
- [ ] AC-5 (FR-002/SC1): `docker build -t dct-mcp-server .` completes without errors.
- [ ] AC-6 (FR-002/SC4): `docker run --rm dct-mcp-server id` returns `uid=1000(mcpuser)` — not root.
- [ ] AC-7 (FR-003): `docker run --rm dct-mcp-server env | grep DCT_API_KEY` returns nothing when `-e DCT_API_KEY=` is not passed (no secret baked into image).
- [ ] AC-8 (FR-003): Image does not contain `docs/`, `.claude/`, `.git/` directories (inspected via `docker run --rm dct-mcp-server find /app -maxdepth 2 -type d`).
- [ ] AC-9 (FR-004): Given a `.env` file with valid credentials, `docker compose up` starts the container and creates `./logs/dct_mcp_server.log` on the host.
- [ ] AC-10 (FR-004): Given no `.env` file, `docker compose up` exits non-zero with `env file .env not found`.
- [ ] AC-11 (FR-005/SC5): `## Running with Docker` section appears in the README Table of Contents and links correctly.
- [ ] AC-12 (FR-005): Each `docker run` example includes `--rm -i` and at minimum `-e DCT_API_KEY=` and `-e DCT_BASE_URL=`.
- [ ] AC-13 (FR-001/SC6): All existing unit tests pass after the logging fix: `pytest --cov=src/dct_mcp_server --cov-fail-under=4` (regression guard — see FR-001 AC-4 in functional spec).

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/DLPXECO-13635/DLPXECO-13635-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/DLPXECO-13635/DLPXECO-13635-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh DLPXECO-13635 --step design -->
