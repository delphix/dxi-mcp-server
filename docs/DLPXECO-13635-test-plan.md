# Test Plan: DLPXECO-13635 — Docker Container Support

**Derived from**: `docs/DLPXECO-13635-design.md` — Affected Components, Version Compatibility, and Acceptance Criteria.

---

## Scope

This test plan covers the three new artifacts: `Dockerfile`, `docker-compose.yml`, and the `README.md` Docker section. No runtime code in `src/` is modified, so existing server unit tests are not within scope. All tests verify container build, startup, and operator workflow.

---

## Environments Required

| Environment | Required For |
|-------------|-------------|
| Linux (amd64) — Docker Engine 20.10+ | Primary build and run tests (FR-001, FR-002) |
| Windows — Docker Desktop 4.x+ in Linux containers mode | Windows compatibility test (FR-001 AC-4, FR-003 AC-2) |
| macOS (Apple Silicon) — optional | ARM64 build test with `--platform linux/amd64` |

---

## Scenarios

### Category 1: Dockerfile Build (FR-001)

| ID | Scenario | Command | Expected Outcome | AC |
|----|----------|---------|------------------|----|
| T-01 | Docker build completes on Linux | `docker build -t dct-mcp-server .` | Exit code 0; image `dct-mcp-server` present in `docker images` | FR-001 AC-1 |
| T-02 | Docker build fails gracefully with missing Python dep | Modify `requirements.txt` to include a non-existent package; build | Non-zero exit code with pip error message; revert change | FR-001 ERR-1 |
| T-03 | Image size is reasonable | `docker images dct-mcp-server --format "{{.Size}}"` | Under 500 MB (slim base + deps) | FR-001 Quality |

### Category 2: Container Runtime — docker run (FR-001)

| ID | Scenario | Command | Expected Outcome | AC |
|----|----------|---------|------------------|----|
| T-04 | Container starts with valid env vars | `docker run --rm -i -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost dct-mcp-server` | Container starts (server process runs); no immediate exit; Ctrl+C stops it | FR-001 AC-2 |
| T-05 | Container fails cleanly without DCT_API_KEY | `docker run --rm dct-mcp-server` | Non-zero exit; error message references missing `DCT_API_KEY` | FR-001 AC-3 |
| T-06 | Container fails cleanly without DCT_BASE_URL | `docker run --rm -e DCT_API_KEY=test dct-mcp-server` | Non-zero exit; error message references missing `DCT_BASE_URL` | FR-001 AC-3 |
| T-07 | PYTHONUNBUFFERED is set | `docker inspect dct-mcp-server --format '{{.Config.Env}}'` (on built image) | `PYTHONUNBUFFERED=1` present in env | FR-001 Platform |
| T-08 | `-i` flag required for stdin | Without `-i`: `docker run --rm -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost dct-mcp-server`; send MCP init message | MCP message not processed (stdin closed); documented in README | FR-001 Platform |

### Category 3: Windows Docker Desktop (FR-001 AC-4)

| ID | Scenario | Expected Outcome | AC |
|----|----------|------------------|----|
| T-09 | `docker build` on Windows Docker Desktop (Linux containers mode) | Build succeeds; no CRLF or path errors | FR-001 AC-4 |
| T-10 | `docker run -i ...` on Windows PowerShell | Container starts; server process runs | FR-001 AC-4 |

### Category 4: docker-compose (FR-002)

| ID | Scenario | Command | Expected Outcome | AC |
|----|----------|---------|------------------|----|
| T-11 | `docker-compose up --build` with valid `.env` | Copy `.env.example` to `.env`, fill real creds, `docker-compose up --build` | Build and startup succeed; logs visible | FR-002 AC-1 |
| T-12 | `docker-compose up` without `.env` and without inline env | Remove `.env`; `docker-compose up` | Container exits with clear error about missing `DCT_API_KEY` or `DCT_BASE_URL` | FR-002 AC-2 |
| T-13 | `docker-compose down` stops cleanly | `docker-compose down` after T-11 | Container stopped and removed; `docker ps` shows no running containers for this service | FR-002 AC-3 |
| T-14 | Log file persists on host after container stop | After T-11, check `./logs/dct_mcp_server.log` | File exists on host; contains server startup logs | FR-002 (volume mount) |

### Category 5: README Documentation (FR-003)

| ID | Scenario | Verification Method | Expected Outcome | AC |
|----|----------|---------------------|------------------|----|
| T-15 | `## Running with Docker` section exists | Read `README.md`; grep for heading | Section present; subsections: Prerequisites, Build, Run, Compose, Windows, Pre-built image | FR-003 AC-1 |
| T-16 | Existing README sections preserved | Compare heading list before and after | All existing TOC entries still present; no sections removed or reordered | FR-003 AC-4 |
| T-17 | Placeholder URL clearly marked | Read placeholder section | Text contains "coming soon" or equivalent; not presented as a live pullable image | FR-003 AC-3 |
| T-18 | Build instructions in README are accurate | Follow README `Build the image` steps verbatim on Linux | `docker build` succeeds following only README instructions | FR-003 AC-1 |
| T-19 | Windows instructions are self-contained | Review Windows subsection | Linux containers mode note present; no external prerequisite research required | FR-003 AC-2 |
| T-20 | No credentials hardcoded in Dockerfile or compose | `grep -rn "DCT_API_KEY=." Dockerfile docker-compose.yml` (for non-placeholder patterns) | No hardcoded key values found | Quality Rule |

### Category 6: Quality Rules

| ID | Scenario | Verification | Expected Outcome |
|----|----------|-------------|-----------------|
| T-21 | `src/` files unchanged | `git diff --stat HEAD src/` | No files in `src/` modified |
| T-22 | Existing startup scripts still work | Run `./start_mcp_server_python.sh` with env vars set | Server starts normally outside Docker |
| T-23 | No credentials in new files | `grep -rn "apk\|api_key\s*=" Dockerfile docker-compose.yml` | No hardcoded credential patterns |
| T-24 | Dockerfile has LF line endings | `file Dockerfile` | Reports "ASCII text" (not "CRLF"); or verify with `cat -A` |

---

## Version Coverage

| Version | Coverage |
|---------|---------|
| Python 3.11 | Primary (pinned in `python:3.11-slim` base image) |
| Docker Engine 20.10+ (Linux) | Primary build/run target |
| Docker Desktop 4.x+ (Windows, Linux containers) | Windows compatibility |
| Compose v2 (no `version:` key) | Primary compose format |

---

## Test Execution Order

1. T-01 (build) must pass before any runtime tests (T-04 through T-08).
2. T-11 (compose up) must pass before T-13 (compose down) and T-14 (logs).
3. T-15 through T-20 (README) can be run in any order, independently of Docker tests.
4. T-21 through T-24 (quality) can be run immediately after file creation, without a Docker build.

---

## Out of Scope

- CI/CD automation to build and push Docker image to registry (tracked as NG1 in vision doc)
- Multi-arch image builds (ARM64 + amd64 manifest) — `--platform` flag documented in README is sufficient
- Performance benchmarking of containerised vs non-containerised server startup time
- Testing with real DCT credentials / live DCT instance (smoke test only; integration tests are a separate activity)
