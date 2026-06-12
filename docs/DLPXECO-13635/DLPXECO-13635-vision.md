# Vision: DLPXECO-13635 — Docker Support for DCT MCP Server

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Issue type**: Feature Request
**Domain**: feature
**Assignee**: Vinay Byrappa

## Problem Statement

The Delphix DCT MCP Server can currently be installed only via `uvx` from GitHub, `pip install` from GitHub, or a local clone with startup scripts — all three paths require the user to provision Python 3.11+, `uv`, or a virtual environment on the host. There is no OS-neutral, hermetic distribution path: Windows users must navigate PowerShell/cmd/PATH differences, QA teams cannot spin up isolated server instances per test run, and field engineers in restricted networks cannot ship the server to air-gapped hosts where GitHub and PyPI are unreachable. This toolchain friction blocks adoption among the target audiences who most need the MCP server (Windows dev machines, corporate restricted networks, repeatable demo environments).

## Goals

- G1: Deliver a `Dockerfile` at the repo root that builds a functional, minimal-footprint image running `dct-mcp-server` as PID 1, configurable entirely through the documented `DCT_*` environment variables
- G2: Document Docker usage in the README with a dedicated "Run with Docker" section covering build, run, env-var wiring, MCP client configuration, and a copy-pasteable `docker run` command for Claude Desktop / Cursor / VS Code Copilot
- G3: Ensure the container runs unmodified on **Windows hosts** via Docker Desktop with the WSL2 backend (Linux containers); provide PowerShell and `cmd.exe` command examples alongside macOS/Linux examples
- G4: Include a documented registry placeholder URL (`<registry-host>/delphix/dct-mcp-server:<tag>`) marked as pending registry provisioning (not yet available), with a build-from-source fallback so users are never blocked
- G5: Match existing runtime semantics exactly — the container must behave identically to `python -m dct_mcp_server.main` invoked from a clone (same stdio transport, same env-var contract, same tool registration, same logging behavior)
- G6: Apply image hygiene standards — non-root runtime user, pinned Python base image minor version, `.dockerignore` excluding `.git`, `logs/`, `__pycache__`, virtualenvs, and credentials

## Non-Goals

- NG1: Kubernetes/Helm packaging — no Helm charts or k8s manifests are in scope; `docker run` examples only
- NG2: HTTP/SSE transport — the server uses stdio; no new transport is introduced in this feature
- NG3: Multi-arch image publishing (`linux/arm64`) — initial image targets `linux/amd64` only; arm64 support is a follow-up
- NG4: CI/CD pipeline for image push to a registry — `Dockerfile` and docs only; GitHub Actions wiring for publish is a follow-up ticket
- NG5: Native Windows containers (Server Core / Nano Server) — we support Windows *hosts* running Linux containers via Docker Desktop/WSL2 only
- NG6: Changes to existing startup scripts (`start_mcp_server_*.sh` / `.bat`) — Docker is added alongside, not replacing, the existing paths
- NG7: `docker-compose.yml` as a production configuration — may be included as a convenience example only if it clarifies the wiring; the server has no companion services

## Success Criteria

- SC1: `docker build -t dct-mcp-server .` completes successfully from a clean clone with no internet access to PyPI beyond what `requirements.txt` pins
- SC2: `docker run -i --rm -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server` starts the server in stdio mode, responds to MCP initialize, and successfully calls at least one DCT API endpoint
- SC3: The container runs as a non-root user; no credentials or secret values appear in the image layers or in `docker inspect`
- SC4: The README "Run with Docker" section contains working copy-pasteable commands for macOS/Linux (bash) and Windows (PowerShell and cmd.exe), and an MCP client JSON snippet for Claude Desktop / Cursor / VS Code Copilot
- SC5: The container image size is ≤ 500 MB (compressed) when built from `python:3.11-slim`
- SC6: Existing `uvx` / `pip install` / local-clone paths are unaffected — all existing tests pass with no changes to `main.py` or `dct_client/`

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Vinay Byrappa (Assignee) | Technical delivery: Dockerfile, `.dockerignore`, README documentation, Windows smoke-test |
| Windows end users (developers, field engineers) | Zero host-side Python/uv setup; copy-pasteable Docker commands that work on PowerShell and cmd.exe |
| QA / demo environment teams | Hermetic, isolated server instances per test run without Python environment management |
| Field engineers in restricted networks | Ability to distribute the server as an immutable image to air-gapped hosts |
| Delphix OCTO / product team | Registry placeholder documented for future image publishing pipeline (PPM follow-up) |

## Constraints

- MCP transport is stdio — the container entrypoint must keep stdin/stdout open for the MCP client; `-i` (interactive, no TTY) is required; daemon-style containers are not applicable
- No code changes to `main.py` or `dct_client/` — behavioral parity with the existing startup paths is mandatory (G5)
- Python 3.11+ minimum per `pyproject.toml`; the base image must satisfy this
- No credentials baked into the image — `DCT_API_KEY` and `DCT_BASE_URL` must be supplied at `docker run` time via `-e`; `IS_LOCAL_TELEMETRY_ENABLED` defaults to `false`
- The image must work behind corporate proxies; runtime must honor `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` env vars (httpx already honors these)
- Dependencies must be pinned reproducibly from `requirements.txt` or `uv.lock`; no unpinned `pip install` of latest packages
- The `Dockerfile` CMD must invoke `python -m dct_mcp_server.main` directly — the container must not call `start_mcp_server_*.sh`, which installs Python/uv on a bare host
- **No `DCT_LOG_DIR` env var exists** — `core/logging.py` derives the log directory from `Path(__file__).resolve().parents[3]` inside the installed package (resolves to `/app/logs` when the package is installed at `/app`). There is no runtime env var to relocate logs; users who need a different log path must mount a volume at `/app/logs` or override with the internal `log_file` argument (not exposed as an env var). This is a codebase fact, not something the Docker feature changes.
- **No `python-dotenv` in the dependency tree** — `pyproject.toml` does not declare `python-dotenv`; the server reads configuration exclusively from `os.getenv()`. A `.env` file mounted into the container will not be auto-loaded. Users must pass variables explicitly via `-e` flags or `--env-file`. Any `.env` file mounted at `/app/.env` is silently ignored by the application.
- **`DCT_VERIFY_SSL` accepts `true`/`false` only — not a CA bundle path** — `dct_client/client.py` calls `httpx.AsyncClient(verify=self.verify_ssl)` where `verify_ssl` is a bool. There is no `DCT_SSL_CERT_FILE` or CA bundle path env var in the current codebase. Users requiring a custom CA bundle must extend `DCTAPIClient` or use system-level CA injection (`update-ca-certificates` in a custom image layer) — this is out of scope for this feature but must not be falsely documented.
- **Spec cache writes to `/tmp/dct_mcp_tools/` inside the container** — `tempfile.gettempdir()` returns `/tmp` in a Linux container; the directory is writable by `appuser` as long as `/tmp` has `1777` permissions (standard on `python:3.11-slim`). The spec cache path can be overridden via `DCT_SPEC_CACHE_PATH`. In `dynamic` mode the cache is re-populated on each container start when the on-disk file is absent or stale (controlled by `DCT_SPEC_MAX_AGE_HOURS`, default 24h).
- **`DCT_TOOLSET=dynamic` has no bundled-spec fallback** — unlike the persona-based toolsets, dynamic mode calls `spec_cache.load_and_cache_spec()` at startup and raises `MCPError("SPEC_LOAD_FAILED")` if the DCT spec cannot be downloaded and no fresh on-disk cache exists. There is no bundled `docs/api-external.yaml` fallback in this code path. Users running in `dynamic` mode must ensure DCT is reachable at container startup.
- **`DCT_API_KEY` must not include the `apk ` prefix** — `client.py` prepends `apk ` automatically in the `Authorization` header. Passing `apk <key>` as the env var value results in a double-prefix authentication failure.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| stdio transport fails on Windows PowerShell due to line-buffering, CRLF translation, or TTY allocation | Medium | High — server unusable on Windows | Use `-i` (not `-t`) explicitly in all docs; provide both PowerShell and cmd.exe examples; document `--init` for proper signal handling; smoke-test from PowerShell on Windows |
| Image bloat — `python:3.11` base + pip install produces >1 GB image | High | Medium — slow pulls, registry cost | Use `python:3.11-slim` base; exclude dev artifacts via `.dockerignore`; multi-stage build separates build deps from runtime; verify with `docker image inspect --format '{{.Size}}'` in CI |
| Tool generation (`generate_tools_from_openapi()`) writes to `$TEMP/dct_mcp_tools/` — ephemeral in a container; regen runs on every container start | Low | Low — adds ~1–2s startup overhead | Acceptable behavior; `$TEMP` resolves to `/tmp` (writable by `appuser`); document as expected. Note: for `dynamic` toolset there is NO bundled-spec fallback — if DCT is unreachable at start, the container exits with `MCPError("SPEC_LOAD_FAILED")` |
| Non-root user breaks `logs/` write permissions when user mounts a host volume | Medium | Medium — logs silently lost or container crashes | Create `appuser` in Dockerfile; `chown /app/logs` to `appuser`; document volume-mount pattern and `--user $(id -u):$(id -g)` override for Linux; verify with `docker run --rm -v $(pwd)/logs:/app/logs dct-mcp-server ls -la /app/logs` |
| Registry URL placeholder misleads users into `docker pull` before registry is provisioned | Low | Medium — confusing UX | README marks placeholder as "pending registry provisioning — not yet available" with build-from-source fallback prominently displayed; use `> [!NOTE]` GitHub admonition markup to make the callout visually distinct |
| `apk ` API key prefix double-applied — user passes `apk <key>` in `DCT_API_KEY`; `client.py` prepends `apk ` again, causing a 401 | Low | High — silently broken auth | Smoke-test `dct_client/client.py` against a live DCT instance as part of validation; README and all examples explicitly state "do not include the `apk ` prefix" |
| Toolset config files (`config/toolsets/*.txt`) are missed by `COPY` if paths are wrong | Low | High — server starts with empty toolset | Use `COPY . /app/` with a thorough `.dockerignore`; add a build-time smoke test asserting `import dct_mcp_server.config.loader` succeeds and at least one toolset is parseable; FR-001 AC-3 enforces this |
| `start_mcp_server_*.sh` scripts are accidentally used as the container entrypoint, causing the container to hang trying to install uv/Python | Medium | High — container never starts | Dockerfile CMD is `python -m dct_mcp_server.main` exclusively; `.sh` scripts are not referenced in the Dockerfile; README clearly distinguishes the two paths |
| User mounts a `.env` file into the container at `/app/.env` expecting auto-loading | Medium | High — silent misconfiguration; credentials may be committed alongside the image if the file is baked in | The server has no `python-dotenv` dependency and will silently ignore a mounted `.env` file; README must document that variables must be passed via `-e` or `--env-file`; `.dockerignore` must exclude `.env`; warn explicitly against bind-mounting `.env` files |
| Platform mismatch — image built on Apple Silicon (`linux/arm64`) is deployed on `linux/amd64` CI or production host | Medium | High — container refuses to start or crashes with SIGILL on incompatible binaries | README notes that the image built locally on Apple Silicon is natively `arm64`; explicitly document `--platform linux/amd64` flag for cross-platform builds; NG3 defers multi-arch publishing to a follow-up |
| `DCT_TOOLSET=dynamic` container fails to start in air-gapped environments because spec download is mandatory with no bundled fallback | High | High — entire dynamic mode unusable offline | Document this hard requirement prominently; recommend `self_service` or other persona toolsets for air-gapped or restricted-network deployments where DCT spec endpoint may be blocked |

## Assumptions

The following assumptions were made during spec generation. If any prove false, the affected FRs should be re-evaluated.

- A1: **`python:3.11-slim` is available on Docker Hub** (or the user's configured registry mirror) at build time. The base image is not mirrored to an internal registry for this feature; that is a follow-up concern.
- A2: **The host Docker daemon is version 20.10 or later** (supports multi-stage builds, BuildKit by default). Older Docker versions on Windows Docker Desktop are not supported.
- A3: **`requirements.txt` is kept in sync with `pyproject.toml` dependencies** by the maintainer. The Dockerfile depends on `requirements.txt` for reproducible installs; if `requirements.txt` is absent or stale, the build will fail or produce an image with wrong dependency versions. No automated sync is assumed.
- A4: **The DCT instance is reachable from inside the container at runtime** — the container's network stack uses the host's default Docker network (`bridge` mode). Users in environments where DCT requires VPN access must ensure VPN connectivity is present before starting the container; VPN integration is out of scope.
- A5: **`/tmp` is writable by `appuser` (uid 1000) inside the container** — `python:3.11-slim` sets `/tmp` to `1777` permissions. If the base image ever changes this, the spec cache write will fail; this is caught by a non-fatal OSError path in `spec_cache.py` (the server continues with an in-memory-only cache).
- A6: **No `python-dotenv` auto-loading occurs** — the server uses `os.getenv()` exclusively; `.env` files are not read by the application. Documentation must not suggest `--env-file .env` as a security-conscious pattern without also warning that the file's contents travel as plaintext Docker build context if present.
- A7: **The MCP client (Claude Desktop, Cursor, VS Code Copilot) launches a new `docker run` process per session** — there is no persistent sidecar container model. Each MCP initialize/terminate cycle corresponds to one container lifetime.
- A8: **`DCT_TOOLSET=dynamic` requires live DCT connectivity at container startup** — unlike persona toolsets, dynamic mode has no bundled spec fallback. This assumption is a deliberate codebase constraint (see `spec_cache.py`) and is treated as a documentation requirement, not a feature gap to close in this ticket.
- A9: **The `docs/api-external.yaml` bundled spec is committed to the repository** and will be present in the Docker build context for non-dynamic toolsets. If it is removed from the repo, persona-based toolsets that fall back to it will start without dynamic tool generation, which is an existing behavior unrelated to this feature.
- A10: **Log output to `stderr` from inside the container does not break the MCP stdio protocol** — `logging.py` routes all console log output to `sys.stderr` (not `stdout`), preserving the MCP JSON-RPC channel on `stdout`. This assumption holds for the current codebase and must not be changed.

---
<!-- Cross-reference: Goals (G1–G6) map to FR descriptions in the functional spec.
     Success Criteria (SC1–SC6) map to Acceptance Criteria in FR-* entries.
     Constraints and Risks inform the Quality Rules and Edge Cases sections. -->
