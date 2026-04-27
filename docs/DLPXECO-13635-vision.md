# Vision: DLPXECO-13635

**Jira**: DLPXECO-13635 — Support for Hosting MCP Server in docker container
**Type**: Task
**Domain**: feature

## Problem Statement

Today, the `dct-mcp-server` can only be run as a host-installed CLI (`uvx`, `pip install`, or local clone scripts). Users who prefer container-based isolation — for example operators running on shared workstations, CI environments, or deployments that standardise on container runtimes — have no supported path. They must either install Python 3.11+ and `uv` on the host or maintain their own unofficial Dockerfile, fragmenting how the server is deployed and making the project harder to adopt.

## Goals

- **G1**: Ship a first-party `Dockerfile` and `.dockerignore` at the repo root that produce a working `dct-mcp-server` image in a single `docker build` command, so users can run the server without any host Python/uv installation.
- **G2**: Document, in `README.md`, the complete user journey for Docker — build, run, configure (env vars), connect from supported MCP clients (Claude Desktop, Cursor, VS Code) — at the same level of polish as the existing `uvx` and `pip` sections.
- **G3**: Make the image safe by default — non-root runtime user, minimal base, no secrets baked into layers — and small enough that pulls are fast (target: < 250 MB compressed for the slim variant).
- **G4**: Make logs reachable from the host. Wire the `DCT_LOG_DIR` env var (currently documented but unimplemented in `core/logging.py`) so users can mount a host directory to capture logs without rebuilding the image.

## Non-Goals

- **NG1**: No HTTP / SSE transport server in this release — the existing stdio transport is preserved as-is. Container is invoked by the MCP client via `docker run -i`, not run as a long-lived background daemon.
- **NG2**: No publishing pipeline to a public registry (Docker Hub, GHCR) in this PR. The Dockerfile builds locally; registry publishing is a follow-up Jira if and when the team decides on a registry strategy.
- **NG3**: No `docker-compose.yml`, no Kubernetes manifests, no Helm chart — those are deployment-flavour decisions outside the scope of "support hosting in a container".
- **NG4**: No refactor of the existing `start_mcp_server_*.sh` scripts, the `pyproject.toml`, or any tool implementations under `src/dct_mcp_server/tools/`. The only Python change is the minimal one needed to honour `DCT_LOG_DIR` (G4).
- **NG5**: No changes to telemetry behaviour. `IS_LOCAL_TELEMETRY_ENABLED` remains opt-in and off by default, matching host behaviour.

## Success Criteria

- **SC1**: `docker build -t dct-mcp-server .` from a fresh clone of `main` produces an image successfully on `linux/amd64` and `linux/arm64` without manual buildx setup beyond the standard `docker buildx create --use` instruction documented in the README.
- **SC2**: Given a built image, running `docker run --rm -i -e DCT_API_KEY=… -e DCT_BASE_URL=… dct-mcp-server` starts the MCP server, completes startup logging, and accepts an MCP `initialize` request on stdin within 10 seconds on a typical developer laptop.
- **SC3**: An MCP client (Claude Desktop) configured per the new README section connects to the container, lists tools for the configured `DCT_TOOLSET`, and successfully executes at least one read-only tool call (e.g. `vdb_tool(action="search")`) end-to-end against a live DCT instance.
- **SC4**: When `DCT_LOG_DIR=/var/log/dct-mcp` is set and `/var/log/dct-mcp` is bind-mounted from the host, after a server session the host directory contains `dct_mcp_server.log` with non-empty content.
- **SC5**: The running container's process inside the namespace has a non-root effective UID, verifiable via `docker exec` or `docker run … id`.
- **SC6**: The final image size is under 250 MB compressed (≤ ~600 MB uncompressed) and contains no `__pycache__/`, `.venv/`, `logs/`, `.git/`, `tests/`, or `docs/` directories — verified by inspecting the image with `docker image inspect` and `docker run --rm --entrypoint sh dct-mcp-server -c 'ls -la /app'`.

## Stakeholders

| Stakeholder              | Interest                                                                |
|--------------------------|-------------------------------------------------------------------------|
| MCP server end users     | A no-host-install path to run the server; consistent setup across OSes. |
| Platform / SRE consumers | Container-native deployment, predictable image, non-root execution.     |
| Maintainers (Delphix)    | A simple, supported Docker story so user issues converge on one image.  |
| Security reviewers       | No secrets in image layers; non-root runtime; minimal attack surface.   |
| CI / release engineers   | Reproducible build; multi-arch ready when registry publishing arrives.  |

## Constraints

- **C1**: Python ≥ 3.11 (current floor in `pyproject.toml`); base image must include or install a 3.11+ interpreter.
- **C2**: The server uses `stdio` transport (`app.run_stdio_async()` in `src/dct_mcp_server/main.py`). Container must therefore run with stdin attached and not background — the entrypoint must `exec` into the Python process so signals reach it as PID 1's child.
- **C3**: Dependencies are managed by `uv` and pinned in `uv.lock`. The image must build deterministically from `uv.lock` (or `requirements.txt` as a backup); no unpinned `pip install` in the runtime layer.
- **C4**: No automated test suite exists in this repo (per `CLAUDE.md`). Verification is via `docker build`, `docker run`, image inspection, and a live MCP-client smoke test.
- **C5**: Docker support must not break the existing `uvx`, `pip`, or local-clone flows. No edits to `start_mcp_server_*.sh`, `pyproject.toml` `dependencies`, or `requirements.txt`.
- **C6**: Logs from inside the container must be retrievable from the host without `docker cp`. This requires honouring `DCT_LOG_DIR` (currently a CLAUDE.md-documented env var that is **not** read by the code) so a bind-mount works.
- **C7**: Reimplemented from scratch per task instructions — no copying from the existing `dlpx/pr/vinaybyrappa/02e1b67e-…` branch. Branch must be created off `origin/main`.

## Risks

| Risk                                                                                                       | Likelihood | Impact | Mitigation                                                                                                                                                  |
|------------------------------------------------------------------------------------------------------------|------------|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| stdio transport doesn't survive container PID-1 signal handling, causing zombies on client disconnect      | Medium     | High   | Use a multi-stage Dockerfile with `exec uv run` (or `exec python -m`) so the Python process becomes PID 1; document `--init` flag if signal proxy needed.   |
| Log file handler crashes inside container because logs dir is read-only or default path is non-writable   | High       | High   | Wire `DCT_LOG_DIR` env var; in Dockerfile, set `WORKDIR /app`, create writable `/app/logs` owned by app user; document mount option.                        |
| Image bloat from including dev/test files, `.git`, `__pycache__`, `logs/` from host                        | High       | Medium | Provide a comprehensive `.dockerignore`; verify final image size during build phase; use multi-stage build to drop build-time artefacts.                    |
| User runs `docker run` without `-i` and the server appears to start then exits immediately                 | Medium     | Medium | README explicitly documents `-i` requirement; provide a "common pitfalls" subsection in the Docker readme.                                                  |
| Multi-arch build fails for a transitive dep with no `arm64` wheel                                          | Low        | Medium | Build on `linux/amd64` first as the primary supported arch; mark `linux/arm64` as best-effort in README; capture build evidence in PR description.          |
| Wiring `DCT_LOG_DIR` regresses existing host behaviour (default logs path)                                 | Low        | High   | Default path unchanged when `DCT_LOG_DIR` is unset; only override when explicitly set; verify by running `start_mcp_server_uv.sh` after the change.         |
| Reviewer asks for `docker-compose.yml` or a published image — scope creep                                  | Medium     | Low    | NG2 / NG3 explicitly stated; PR description references vision doc; defer to follow-up tickets.                                                              |

---

<!-- Cross-reference:
- G1 maps to FR-001 (Dockerfile), FR-002 (.dockerignore).
- G2 maps to FR-003 (README Docker section).
- G3 maps to FR-004 (non-root user, minimal base, image size budget).
- G4 maps to FR-005 (DCT_LOG_DIR env var support).
- SC1, SC2, SC5, SC6 are verified by FR-001 and FR-004 acceptance criteria.
- SC3 is verified by manual MCP-client smoke test recorded in test-evidence and PR description.
- SC4 is verified by FR-005 acceptance criteria.
- C2 is enforced by FR-001 entrypoint design.
- C5 is enforced by validation phase comparing untouched files vs. diff.
- C6 is enforced by FR-005. -->
