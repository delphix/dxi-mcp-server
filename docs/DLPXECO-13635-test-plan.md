# Test Plan: DLPXECO-13635 — Docker Support for DCT MCP Server

**Derived from**: `docs/DLPXECO-13635-design.md` — Affected Components and Version Compatibility sections
**FR References**: FR-001 (Dockerfile), FR-002 (.dockerignore), FR-003 (README Docker section), FR-004 (Windows compatibility)

---

## Environment Requirements

- Docker Engine 20.10+ installed (Linux host, or Docker Desktop on macOS/Windows)
- Docker Desktop (Windows) configured in Linux container mode for Windows platform tests
- No active DCT instance required for build and startup tests (env vars can be fake for banner test)
- Network access to pull `python:3.11-slim` from Docker Hub

---

## Scenarios

### FR-001: Dockerfile — Build and Run

| ID | Scenario | Version / Platform | Expected Outcome |
|----|----------|--------------------|-----------------|
| T-001 | `docker build -t dct-mcp-server .` from project root | Docker 20.10+ / Linux | Exit code 0; no errors during build |
| T-002 | Layer caching — re-run `docker build` after touching only `src/` file | Docker 20.10+ / Linux | `pip install` layer is cached (no re-download); build completes fast |
| T-003 | `docker run -e DCT_API_KEY=test -e DCT_BASE_URL=https://fake.dct dct-mcp-server` | Docker 20.10+ / Linux | Server starts; startup banner appears in stdout within 10 seconds |
| T-004 | `docker run dct-mcp-server` (no env vars) | Docker 20.10+ / Linux | Container exits with informative error naming the missing env var(s); no Python traceback |
| T-005 | `docker inspect dct-mcp-server` (or inspect image layers) | Any | `DCT_API_KEY` and `DCT_BASE_URL` not present as `ENV` or `ARG` values in image manifest |
| T-006 | `docker run -e DCT_API_KEY=... -e DCT_BASE_URL=... -e DCT_LOG_LEVEL=DEBUG dct-mcp-server` | Docker 20.10+ / Linux | DEBUG log output visible in stdout |

### FR-002: .dockerignore

| ID | Scenario | Version / Platform | Expected Outcome |
|----|----------|--------------------|-----------------|
| T-007 | Build context size — verify `.git/` and `docs/` are excluded | Docker 20.10+ / Linux | `docker build` output shows reduced context size; no `.git/` transfer |
| T-008 | Verify `logs/` is absent from final image | Docker 20.10+ / Linux | `docker run --entrypoint ls dct-mcp-server /app` does not show `logs/` directory |
| T-009 | Verify `.claude/` is absent from final image | Docker 20.10+ / Linux | `docker run --entrypoint ls dct-mcp-server /app` does not show `.claude/` directory |
| T-010 | Verify `.env` files are excluded from context | Docker 20.10+ / Linux | Create a test `.env` file; build; exec into container and confirm file not present |

### FR-003: README.md Docker section

| ID | Scenario | Version / Platform | Expected Outcome |
|----|----------|--------------------|-----------------|
| T-011 | README contains `## Docker` heading | Any (file inspection) | `grep "^## Docker" README.md` returns a match |
| T-012 | Table of Contents contains Docker entry | Any (file inspection) | `grep "\[Docker\]" README.md` returns a match with correct anchor |
| T-013 | Docker section contains placeholder registry command | Any (file inspection) | `grep "docker pull" README.md` returns a line clearly marked as a placeholder |
| T-014 | Docker section contains `docker build` example | Any (file inspection) | `grep "docker build" README.md` returns `docker build -t dct-mcp-server .` |
| T-015 | Docker section contains `docker run` example with env vars | Any (file inspection) | `grep "docker run" README.md` returns a line with `-e DCT_API_KEY` and `-e DCT_BASE_URL` |
| T-016 | Docker section contains MCP client connection snippet | Any (file inspection) | JSON or config example for connecting Claude Desktop / Cursor to containerised server is present |
| T-017 | Existing README sections intact | Any (diff inspection) | `git diff README.md` shows no deletions from existing sections; only additions |

### FR-004: Windows compatibility

| ID | Scenario | Version / Platform | Expected Outcome |
|----|----------|--------------------|-----------------|
| T-018 | Dockerfile `FROM` uses Linux base | Any (file inspection) | `grep "^FROM" Dockerfile` returns `FROM python:3.11-slim` |
| T-019 | ENTRYPOINT is JSON array form | Any (file inspection) | `grep "^ENTRYPOINT" Dockerfile` returns `ENTRYPOINT ["dct-mcp-server"]` (not shell form) |
| T-020 | README contains Windows PowerShell example or equivalent guidance | Any (file inspection) | README Docker section contains PowerShell env var syntax or explicit note that Linux `docker run` command works unchanged on Docker Desktop for Windows |
| T-021 | (Optional, if Windows host available) `docker build` on Docker Desktop for Windows | Docker Desktop 4.0+ / Windows (Linux containers mode) | Build succeeds; same result as T-001 |
| T-022 | (Optional, if Windows host available) `docker run` on Docker Desktop for Windows | Docker Desktop 4.0+ / Windows (Linux containers mode) | Server starts; same result as T-003 |

### Quality Rules

| ID | Scenario | Expected Outcome |
|----|----------|-----------------|
| T-023 | No credentials in Dockerfile | `grep -E "DCT_API_KEY|DCT_BASE_URL" Dockerfile` returns no line that sets a value |
| T-024 | `python:3.11-slim` base used | `grep "^FROM" Dockerfile` returns `python:3.11-slim` (not `python:3.11` full) |
| T-025 | Only Docker/README files changed | `git diff --name-only` shows only `Dockerfile`, `.dockerignore`, `README.md`, and `docs/` paths |

---

## Version Coverage

| Platform | Covered | How |
|----------|---------|-----|
| Linux (Docker 20.10+) | Yes | T-001 through T-010 |
| macOS (Docker Desktop 4.0+) | Best-effort | Same Linux container execution as Linux host |
| Windows (Docker Desktop 4.0+, Linux containers) | Documentation tests only (T-018 to T-020); optional live tests (T-021, T-022) | |
| Python 3.11 | Yes | Implicit — base image is `python:3.11-slim` |

---

## Skip Justifications

- T-021, T-022 (Windows live tests): skippable if no Windows host is available. The Dockerfile uses a Linux base image which is identical under Docker Desktop for Windows in Linux container mode — the difference is only in how env vars are passed via PowerShell vs bash, and the README documents both.
- E2E DCT API calls: out of scope for this feature (NG3 in vision — Docker packaging must not alter functionality). Functional correctness of DCT tools is covered by existing integration tests against a live engine.
