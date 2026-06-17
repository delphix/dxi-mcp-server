# Vision: DLPXECO-13635

## Problem Statement

Users who cannot or prefer not to install Python 3.11+ or `uv` on their local machine have no supported path to run the DCT MCP Server today. The only published installation methods require a Python runtime (`uvx`, `pip`, or a local virtualenv). Organisations with strict environment policies, Windows users who find Python environment management complex, or teams who want a reproducible, dependency-isolated deployment unit are blocked from adopting the MCP Server. A previous Docker implementation (commits 3bfa45f–f1942e5) was fully reverted because the `logging.py` log-directory detection logic produced an unwritable path when running inside a container (the `site-packages` check inspected the wrong path component), causing a startup crash. This ticket re-implements Docker support correctly with the logging fix included.

## Goals

- G1: Deliver a working, minimal `Dockerfile` (single-stage `python:3.11-slim`) that builds and runs the `dct-mcp-server` entry point correctly, including a non-root `mcpuser` runtime identity
- G2: Fix `src/dct_mcp_server/core/logging.py:_get_project_root()` so that when the package runs from `site-packages` (as it does inside a Docker image), log files are written to `Path.cwd()` (`/app/logs`) instead of an unwritable Python library path
- G3: Provide a `.dockerignore` that prevents secrets (`.env`), VCS metadata (`.git`), generated artefacts (`dist/`, `build/`, `__pycache__/`), and development-only files (`.claude/`, `docs/`) from entering the build context
- G4: Provide a `docker-compose.yml` for local development convenience (build, pass env from `.env` file, mount `./logs` volume)
- G5: Add a `## Running with Docker` section to `README.md` covering build, run (Linux/macOS and Windows), log-volume mount, and per-client MCP configuration examples (Claude Desktop, Cursor/Windsurf, VS Code/IntelliJ)
- G6: Verify the image builds and the server starts cleanly (`dct-mcp-server` exits with MCP handshake output, not a Python traceback) in both amd64 and arm64 environments

## Non-Goals

- NG1: Publishing the image to Docker Hub or GitHub Container Registry is not in scope — this is a local-build-only workflow (Docker Hub publish is tracked as a separate PPM ticket)
- NG2: No CI job is added to build or push the Docker image in this PR — the existing CI pipeline (`ci.yml`) covers lint, test, and sdist/wheel only
- NG3: No Kubernetes or Helm chart is provided
- NG4: Multi-stage builds (builder + runtime stages) to reduce final image size are not required — a single `python:3.11-slim` stage is sufficient for this iteration
- NG5: Container signing or SBOM generation is out of scope
- NG6: Windows Container (LTSC) variants are out of scope; Docker Desktop on Windows runs Linux containers, which is sufficient

## Success Criteria

- SC1: `docker build -t dct-mcp-server .` completes without errors from the project root on a machine with Docker 20.10+
- SC2: `docker run --rm -i -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost dct-mcp-server` starts without a Python traceback (a connection-refused error from the DCT client is acceptable — the crash on startup due to the logging path must not occur)
- SC3: `docker run --rm -i -e DCT_API_KEY=test -e DCT_BASE_URL=https://localhost -v ./logs:/app/logs dct-mcp-server` writes `logs/dct_mcp_server.log` to the mounted host directory
- SC4: The running container identity is not root (`id` returns uid=1000/mcpuser)
- SC5: The README Docker section renders correctly on GitHub and each MCP client configuration example is accurate and copy-pasteable
- SC6: All existing unit tests pass before and after the change (`pytest --cov=src/dct_mcp_server --cov-fail-under=4`)

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| End users (Windows / no-Python environments) | A zero-dependency installation path that doesn't require Python or uv on the host |
| DevOps / platform teams | A reproducible, environment-isolated container image they can deploy without touching host Python versions |
| Delphix Developer Experience team | Reduced support burden — Docker removes "Python version mismatch" and "uv not found" issues from the support queue |
| MCP Server contributors | A clean, correct baseline Dockerfile to extend for future CI/CD or image-push work |
| Vinay Byrappa (Assignee) | Correct re-delivery of a feature that was previously reverted due to a logging path bug |

## Constraints

- Must target `python:3.11-slim` base image — this matches the project's minimum supported Python version (3.11+) and keeps the image lean
- The logging fix must be backward-compatible: when running from a local clone (dev mode), `_get_project_root()` must continue to return the repo root, not CWD
- No new Python dependencies may be introduced — the image installs the package with `pip install --no-cache-dir .` using the existing `pyproject.toml`
- The Docker files must not interfere with the existing `uvx`, `pip`, and `venv` installation paths described in `CLAUDE.md`
- The `docker-compose.yml` must not commit secrets — it must reference an `.env` file that is git-ignored
- Must comply with Delphix security baseline: non-root container user is required

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| The logging fix regresses dev-mode path detection (repo root becomes CWD in dev) | Low | Medium | Unit test `_get_project_root()` under both installed-package and dev-clone conditions before merging; verify manually with `python -c "from dct_mcp_server.core.logging import GlobalLogger; print(GlobalLogger._get_project_root())"` from repo root |
| `python:3.11-slim` base image receives a breaking update between build and deployment | Low | Low | Pin the base image to a specific digest or patch version (e.g. `python:3.11-slim-bookworm`) in `Dockerfile` to make builds reproducible |
| Users forget the `-i` flag, breaking MCP stdio communication silently | Medium | Medium | README prominently notes that `-i` is required with a callout block; README examples always include `--rm -i` together |
| SSL certificate trust fails inside the container for private DCT instances with custom CA certs | Medium | Medium | Document the `SSL_CERT_FILE` environment variable workaround and a `COPY` snippet for injecting CA bundles in the README Docker section |
| Windows Docker Desktop path-mounting differences cause volume mount failures for log directory | Low | Low | Provide tested Windows log-mount examples (both `%cd%` and `${PWD}` variants) in README; note Docker Desktop WSL2 backend handles this transparently for most users |
| Image size becomes large due to unnecessary build artefacts leaking through `.dockerignore` | Low | Low | Verify final image size with `docker image ls` — target < 300 MB; `docker inspect` confirms `tests/` and `evals/` directories are excluded; add a `docker image ls --format '{{.Size}}'` assertion to the manual smoke test |

---

## Assumptions

_The following assumptions were made autonomously (interview mode active but no user context was provided):_

- A1: The reason for the revert was specifically the logging path bug (incorrect `site-packages` detection in `_get_project_root()`), not a policy or security concern about Docker support itself. The re-implementation should restore all reverted content plus the logging fix.
- A2: The branch naming convention `feat/admin/dlpxeco-13635` uses "admin" to reflect the person (Vinay/admin user), not the platform_admin toolset.
- A3: `docker-compose.yml` is desirable for developer convenience but is not a hard requirement for the acceptance criteria — the Dockerfile and README are the primary deliverables.
- A4: The CI workflow (`ci.yml`) is not extended to include a Docker build job in this ticket.
- A5: The target Docker Hub namespace/image name for future publishing will be `delphix/dct-mcp-server` but is not configured here.

---
<!-- Cross-reference: Goals (G1–G6) map to FR descriptions in the functional spec.
     Success Criteria (SC1–SC6) map to Acceptance Criteria in FR-* entries.
     Constraints and Risks inform the Quality Rules and Edge Cases sections. -->
