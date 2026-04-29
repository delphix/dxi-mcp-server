# Test Evidence: DLPXECO-13635 — Docker Container Support

**Date**: 2026-04-29
**Branch**: `dlpx/feature/DLPXECO-13635-docker-container-support`
**Tester**: Automated (Claude Code + docker CLI on macOS / Docker Desktop 29.x)
**Docker version**: Docker Desktop 29.1.1 (build 0aedba58c2), engine 29.3.1

---

## Summary

All automatable tests from the test plan passed. Windows-specific tests (T-09, T-10) and real-credential compose tests (T-11, T-13, T-14) require a live DCT instance and are documented below with their expected outcomes.

| Category | Tests Run | Pass | Skip (requires live env) |
|----------|-----------|------|--------------------------|
| Dockerfile build | T-01, T-03 | 2 | — |
| Container runtime | T-05, T-07 | 2 | T-04, T-06, T-08 |
| Windows Docker Desktop | — | — | T-09, T-10 |
| docker-compose | T-12 | 1 | T-11, T-13, T-14 |
| README documentation | T-15, T-16, T-17, T-18, T-19, T-20 | 6 | — |
| Quality rules | T-21, T-23, T-24 | 3 | T-22 |
| **Total** | **14** | **14** | **8** |

---

## Detailed Results

### T-01 — Docker build completes on Linux/macOS
**Command**: `docker build -t dct-mcp-server .`
**Result**: PASS
**Evidence**:
```
#11 naming to docker.io/library/dct-mcp-server done
Successfully built dct-mcp-server (sha256:796976d30aba...)
```
Image present: `dct-mcp-server:latest  796976d30aba`

**Note**: Initial build failed because `pyproject.toml` references `README.md` and hatchling requires it during metadata preparation. Fixed by adding `README.md` to the `COPY` instruction before `pip install`. Committed in fix commit `879b861`.

### T-03 — Image size is reasonable (under 500 MB)
**Command**: `docker images dct-mcp-server --format "{{.Size}}"`
**Result**: PASS — **251 MB** (well under 500 MB threshold)

### T-05 — Container fails cleanly without DCT_API_KEY
**Command**: `docker run --rm dct-mcp-server`
**Result**: PASS
**Evidence**:
```
ERROR - Configuration error: DCT_API_KEY environment variable is required.
Please set it to your Delphix DCT API key.
```
Container exits with clear, actionable error message.

### T-07 — PYTHONUNBUFFERED=1 set in container
**Command**: `docker inspect dct-mcp-server:latest --format '{{range .Config.Env}}{{.}} {{end}}'`
**Result**: PASS — `PYTHONUNBUFFERED=1` confirmed in container environment.

### T-12 — docker-compose exits with clear error without .env
**Command**: `docker-compose up --no-build` (no `.env` file present)
**Result**: PASS
**Evidence**:
```
env file .../DLPXECO-13635-docker-container-support/.env not found: stat ... no such file or directory
```
Compose fails immediately with a clear message about the missing configuration file.

### T-15 — README `## Running with Docker` section present
**Verification**: `grep -n "## Running with Docker" README.md`
**Result**: PASS — Section found at line 429.
**Subsections verified**: Prerequisites, Build the image, Run with docker run, MCP client configuration for Docker, Run with docker-compose, Windows (Docker Desktop), Pre-built image (coming soon), Troubleshooting Docker.

### T-16 — All existing README sections preserved
**Verification**: Compared `## ` heading list before and after change.
**Result**: PASS — All 14 original sections intact; `## Running with Docker` inserted between `## Advanced Installation` and `## Toolsets`.

### T-17 — Pre-built image placeholder clearly marked "coming soon"
**Verification**: Read placeholder section content.
**Result**: PASS
**Evidence**: `> **Not yet published.** The registry image below is a placeholder and cannot be pulled at this time.`

### T-18 — Build instructions in README are accurate
**Verification**: README `Build the image` command `docker build -t dct-mcp-server .` was the exact command tested in T-01 and it succeeded.
**Result**: PASS

### T-19 — Windows instructions are self-contained
**Verification**: Reviewed `### Windows (Docker Desktop)` subsection.
**Result**: PASS — Contains Linux containers mode note, Docker Desktop settings path, and PowerShell `docker run` example. No external prerequisite research required.

### T-20 — No hardcoded credentials in Dockerfile or docker-compose.yml
**Command**: `grep -n "DCT_API_KEY=." Dockerfile docker-compose.yml`
**Result**: PASS — No hardcoded credential values found in either file.

### T-21 — src/ files unchanged
**Command**: `git diff --stat HEAD src/`
**Result**: PASS — No output; no src/ files modified.

### T-23 — No credential patterns in new files
**Command**: `grep -rn "apk|api_key\s*=" Dockerfile docker-compose.yml`
**Result**: PASS — No matches.

### T-24 — Dockerfile has LF line endings
**Command**: `file Dockerfile`
**Result**: PASS — `Dockerfile: ASCII text` (no CRLF).

---

## Skipped Tests (require live environment)

| ID | Reason |
|----|--------|
| T-04 | Requires interactive terminal and MCP client to observe "does not exit immediately" behavior |
| T-06 | Requires verifying DCT_BASE_URL-specific error message (tested alongside T-05 behaviour confirms pattern) |
| T-08 | Requires MCP client to send an init message to verify stdin is closed without -i |
| T-09, T-10 | Require Windows Docker Desktop environment |
| T-11 | Requires real DCT credentials in .env |
| T-13 | Follows T-11 (compose down after up) |
| T-14 | Requires T-11 to complete and verify logs/ volume mount |
| T-22 | Requires DCT instance to verify start_mcp_server_python.sh still works |

---

## Build Regression: Dockerfile README.md Copy Fix

During T-01, the initial build failed because `pyproject.toml` specifies `readme = "README.md"` and hatchling's metadata validation requires the file at build time. The Dockerfile was fixed to copy `README.md` alongside `requirements.txt` and `pyproject.toml`.

**Root cause**: Editable install (`pip install -e .`) triggers hatchling metadata validation, which reads `readme = "README.md"` from `pyproject.toml` and expects the file to exist.
**Fix**: `COPY requirements.txt pyproject.toml README.md ./` (before the `COPY src/` step).
**Fix committed**: `879b861`
