# Feature Design: DLPXECO-13635

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: DLPXECO-13635". -->

---

## Summary

This feature adds Docker-based distribution support for the Delphix DCT MCP Server (`dct-mcp-server`), enabling OS-neutral, hermetic deployment on Windows, macOS, and Linux hosts without requiring Python, `uv`, or virtual environment setup on the host machine. The change delivers a `Dockerfile` (multi-stage, non-root, `python:3.11-slim`-based), a `.dockerignore` for lean build contexts, and a comprehensive "Run with Docker" section in `README.md` covering bash, PowerShell, and cmd.exe command examples as well as MCP client JSON configuration snippets. No changes are made to any existing source files in `src/`, `main.py`, or `dct_client/` — the container runs `python -m dct_mcp_server.main` directly and replicates the existing startup semantics exactly. The feature targets Windows developers, QA teams needing isolated test instances, and field engineers in restricted networks.

## Affected Components

Based on `.claude/architecture.md` layer map and the scope of this feature (Dockerfile, `.dockerignore`, `README.md` only):

- [ ] `main.py` — Entry point; FastMCP app, lifespan, startup/shutdown
- [ ] `toolsgenerator/driver.py` — Generates tool modules from OpenAPI spec at startup
- [ ] `tools/__init__.py` — Dynamic tool registration
- [ ] `tools/core/meta_tools.py` — Auto-mode meta-tools
- [ ] `tools/core/tool_factory.py` — Runtime tool generation from OpenAPI spec
- [ ] `tools/*_endpoints_tool.py` — Pre-built grouped tools
- [ ] `config/config.py` — Env var loading and validation
- [ ] `config/loader.py` — Toolset + confirmation rule parsing
- [ ] `config/toolsets/*.txt` — Persona toolset definitions
- [ ] `config/mappings/manual_confirmation.txt` — Confirmation rules
- [ ] `dct_client/client.py` — Async httpx client with retry/backoff
- [ ] `core/logging.py` — Logging setup
- [ ] `core/session.py` — Telemetry session management
- [ ] `core/decorators.py` — @log_tool_execution
- [ ] `core/exceptions.py` — DCTClientError, MCPError
- [x] `Dockerfile` (new) — Multi-stage container build definition for the MCP server
- [x] `.dockerignore` (new) — Exclusion rules for lean Docker build context
- [x] `README.md` — "Run with Docker" section with bash/PowerShell/cmd.exe examples

## Architecture Changes

### Schema / Config Changes

None. This feature introduces no changes to schema files, configuration formats, or persisted state shapes. The `Dockerfile` references `requirements.txt` and `src/` at build time but does not modify them. All `DCT_*` environment variables are passed at `docker run` time — no new env vars are introduced.

### Source Files to Modify

| File | Purpose | Maps to FR |
|------|---------|------------|
| `Dockerfile` (new) | Multi-stage build: build stage installs dependencies into `/app/venv` from `requirements.txt`, installs package via `pip install .`; runtime stage copies venv + installed package, creates `appuser` (uid 1000), sets `USER appuser`, sets `CMD ["python", "-m", "dct_mcp_server.main"]`, creates `/app/logs` with correct ownership | FR-001 |
| `.dockerignore` (new) | Excludes `.git/`, `logs/`, `__pycache__/`, `*.pyc`, `*.pyo`, `.venv/`, `venv/`, `.env`, `*.env`, `mcp.json`, `evals/`, `tests/`, `*.md` (except README), `uv.lock`, `.claude/`, `start_mcp_server_*.sh`, `start_mcp_server_*.bat`, `whitesource/`; explicitly keeps `src/`, `pyproject.toml`, `requirements.txt`, `docs/api-external.yaml` | FR-002 |
| `README.md` | Adds "Run with Docker" section (ToC entry + subsections: Prerequisites, Build, Run on bash/PowerShell/cmd.exe, MCP client config, Persist Logs, Registry Placeholder, SSL/Proxy Notes); documents Windows-specific flags (`-i`, `--init`, no `-t`) | FR-003, FR-004, FR-005 |

### New Files (if any)

- `Dockerfile` — Multi-stage Docker build definition for the containerised MCP server runtime
- `.dockerignore` — Build context exclusion rules keeping context transfer under 5 MB

## Version Compatibility

This feature adds infrastructure files only (`Dockerfile`, `.dockerignore`, `README.md`). There are no code changes to the MCP server source. Version compatibility is therefore about which Python versions and base images are used inside the container:

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11 | Yes | No | Minimum per `pyproject.toml`; base image is `python:3.11-slim`; pinned to minor version |
| Python 3.12+ | No (scope) | N/A | Follow-up; initial image targets 3.11 only for determinism |
| Docker Engine < 20.10 | No | N/A | Multi-stage builds require BuildKit (Docker 20.10+); older versions not supported per A2 |
| Docker Desktop (macOS / Windows WSL2) | Yes | No | Primary developer target; WSL2 backend required on Windows |
| linux/amd64 | Yes | No | Default build platform; explicit `--platform linux/amd64` flag documented for cross-platform builds |
| linux/arm64 | No (NG3) | N/A | Multi-arch publishing deferred to follow-up; Apple Silicon users get native arm64 from local builds |
| `DCT_TOOLSET=dynamic` (air-gapped) | Partially | No | Dynamic mode requires live DCT spec download at startup — no bundled fallback; documented as requirement |
| `DCT_TOOLSET=<persona>` | Yes | No | Persona toolsets use bundled `docs/api-external.yaml` — works offline after image build |

## Platform Behavior Notes

Key platform behaviors from `.claude/architecture.md` and how this feature interacts with each:

- **API key prefix** (`client.py` prepends `apk ` automatically): Affects — README and all `docker run` examples must explicitly state "do not include the `apk ` prefix" in `DCT_API_KEY`. EC-7 / ERR-7 in functional spec cover this failure mode.
- **SSL**: Defaults to `verify=false`: Affects — README documents `DCT_VERIFY_SSL=true` and explicitly notes that a CA bundle path is NOT supported via env var (`dct_client/client.py` passes `verify_ssl` as a bool to `httpx.AsyncClient`). EC-11 covers the custom CA pattern (`update-ca-certificates` in a derived image).
- **Retries**: Exponential backoff up to `DCT_MAX_RETRIES`: N/A — retry behavior is unchanged; container adds no overhead to the MCP tool execution path.
- **Toolset config cache** (`loader.py` uses `@lru_cache`): Affects (indirectly) — toolset config files must be included in the Docker build context; `.dockerignore` must NOT exclude `src/dct_mcp_server/config/toolsets/*.txt` or `manual_confirmation.txt`. FR-001 AC-3 validates this at build time.
- **Telemetry** (opt-in, `IS_LOCAL_TELEMETRY_ENABLED=true`): Affects — `logs/sessions/` is under `/app/logs` inside the container; if telemetry is enabled, the volume-mount pattern (`-v $(pwd)/logs:/app/logs`) must be documented. Default is `false` so telemetry is off by default in containers.
- **Spec cache writes to `$TEMP/dct_mcp_tools/`**: Affects — in a container, `$TEMP` is `/tmp`; writable by `appuser` on `python:3.11-slim` (standard `1777` permissions). `DCT_SPEC_CACHE_PATH` can override this. `DCT_TOOLSET=dynamic` requires live DCT connectivity at startup — no bundled spec fallback; this is a hard constraint documented in README (EC-4 / ERR-4).
- **Logging path** (`core/logging.py` derives log path from `Path(__file__).resolve().parents[3]`): Affects — resolves to `/app/logs` when the package is installed at `/app`. Dockerfile must create `/app/logs` and `chown` to `appuser`. No `DCT_LOG_DIR` env var exists — only volume-mounting `/app/logs` changes the persisted log location.
- **MCP stdio transport**: Affects critically — the container entrypoint must keep stdin/stdout open for the MCP client. All `docker run` examples must use `-i` (no `-t`). `--init` is recommended for proper PID 1 signal handling.

## Open Questions / Risks

- R: `python:3.11-slim` base image digest may change between builds if pinned only to minor version tag — Mitigation: pin to `python:3.11-slim` (tag, not digest) for initial delivery; consider digest pinning in a follow-up CI hardening ticket.
- R: `requirements.txt` may be out of sync with `pyproject.toml` — Mitigation: A3 from vision doc assumes maintainer keeps these in sync; add a build validation note in the README referencing this assumption.
- R: `uid 1000` conflict if future base image ships a conflicting user — Mitigation: documented in ERR-2; Dockerfile should check before creating `appuser`; use `--uid 10001` as a fallback.
- Q: Should the `Dockerfile` use `pip install .` (install the package from source) or `pip install -r requirements.txt` + `COPY src/` (copy source without pip-installing the package)? — Resolution: Use `pip install .` in the build stage so the package is properly installed under `site-packages`; this ensures `python -m dct_mcp_server.main` resolves correctly and the log path (`Path(__file__).resolve().parents[3]`) resolves to `/app/logs`. — Owner: Vinay Byrappa.
- Q: What is the authoritative image size threshold — compressed or uncompressed? — Resolution: Align to "compressed ≤ 500 MB" to match the functional spec Quality Rules (`docker save | gzip | wc -c` ≤ 524288000 bytes). AC-1 has been updated accordingly. — Owner: Vinay Byrappa.
- Q: Should `docs/api-external.yaml` be excluded by the `docs/` pattern in `.dockerignore` and explicitly re-added? — Resolution: The `.dockerignore` must NOT include a bare `docs/` exclusion pattern. Instead, list only specific subdirectories or files to exclude from `docs/` (none needed in this case — only `docs/api-external.yaml` is relevant). If a broad `docs/` exclusion pattern is used, it must be followed by a `!docs/api-external.yaml` negation rule; Docker processes patterns in order so the negation must come after the exclusion. FR-002 AC-2 validates the final result. — Owner: Vinay Byrappa.
- R: `LABEL version` in the Dockerfile will drift from `pyproject.toml` on each release if hard-coded — Mitigation: derive version via `ARG VERSION` passed at build time from `pyproject.toml` (e.g. `docker build --build-arg VERSION=$(python -c "import tomllib; ...")`) or omit the version label and rely solely on the image tag. Non-blocking for initial delivery but should be addressed before registry publishing.
- R: `.dockerignore` negation rule `!docs/api-external.yaml` ordering — Docker `.dockerignore` processes patterns in file order; a `docs/` exclusion listed after a `!docs/api-external.yaml` negation will re-exclude the file. The pattern ordering in `.dockerignore` must be: `docs/` exclusion first, then `!docs/api-external.yaml` negation. Verified by FR-002 AC-2.

## Acceptance Criteria

Derived from FR-001 through FR-005 and the Quality Rules in the functional spec:

- [ ] AC-1: `docker build -t dct-mcp-server .` from a clean clone completes without error and the compressed image size is ≤ 500 MB (verified via `docker save dct-mcp-server | gzip | wc -c` ≤ 524288000 bytes) (FR-001, SC1, SC5)
- [ ] AC-2: `docker inspect dct-mcp-server` shows runtime user `appuser`; `docker run --rm dct-mcp-server id` prints `uid=1000(appuser)` (FR-001, SC3)
- [ ] AC-3: `docker run --rm dct-mcp-server python -c "import dct_mcp_server.config.loader; print('ok')"` prints `ok` without error (FR-001 AC-3)
- [ ] AC-4: `docker run` without `DCT_API_KEY` / `DCT_BASE_URL` exits non-zero with a descriptive error message, not a Python traceback (FR-001 AC-4)
- [ ] AC-5: `.git/`, `logs/`, `__pycache__/`, and `.env` files do not appear in the built image (FR-001 AC-5, FR-002 AC-1)
- [ ] AC-6: `docs/api-external.yaml` is present inside the built image (FR-002 AC-2)
- [ ] AC-7: `tests/` and `evals/` do not appear inside the built image (FR-002 AC-3)
- [ ] AC-8: `README.md` contains a "Run with Docker" section with working `docker run` commands for bash, PowerShell, and cmd.exe (FR-003 AC-1)
- [ ] AC-9: `README.md` contains MCP client JSON snippets for at least Claude Desktop and Cursor using `docker run -i --rm ...` (FR-003 AC-2)
- [ ] AC-10: Registry placeholder URL is present and clearly annotated as pending provisioning (not a working pull command) (FR-003 AC-3, FR-005 AC-1, AC-2, AC-3)
- [ ] AC-11: Table of Contents includes a link to the "Run with Docker" section (FR-003 AC-4)
- [ ] AC-12: The `docker run` command in MCP client config snippets uses `-i`, does not use `-t`, and includes `--init` (FR-004 AC-1, AC-2)
- [ ] AC-13: README contains PowerShell `docker run` example with `$env:` syntax (FR-004 AC-3)
- [ ] AC-14: README contains cmd.exe `docker run` example with `%VAR%` syntax (FR-004 AC-4)
- [ ] AC-15: README contains a troubleshooting note explaining why `-t` breaks stdio MCP transport (FR-004 AC-5)
- [ ] AC-16: All existing pytest tests pass with no changes to `main.py`, `dct_client/`, or any `*_endpoints_tool.py` files (SC6, Quality Rule: API backward compatibility)
- [ ] AC-17: `docker run -i --rm -e DCT_API_KEY=... -e DCT_BASE_URL=... dct-mcp-server` starts the server in stdio mode and responds to MCP `initialize` (SC2, Quality Rule: Stdio transport parity)
- [ ] AC-18: All `DCT_*` environment variable references in the new README Docker section cross-reference the canonical `## Environment Variables` section rather than duplicating definitions (FR-003 AC-5)
- [ ] AC-19: `docker history --no-trunc dct-mcp-server | grep -iE 'apk|DCT_API_KEY|DCT_BASE_URL'` returns empty; `docker inspect` Config.Env does not contain secret values (Quality Rule: No credentials in image layers, SC3)
- [ ] AC-20: `docker run --rm -v $(pwd)/test.env:/app/.env -e DCT_API_KEY=override dct-mcp-server python -c "import os; assert os.getenv('DCT_API_KEY')=='override'"` succeeds, confirming `.env` auto-loading does not occur (Quality Rule: No `.env` auto-loading, EC-15)
- [ ] AC-21: `docker inspect --format '{{json .Config.Labels}}' dct-mcp-server` returns JSON with non-empty `maintainer`, `version`, and `description` fields (FR-001 step 7)
- [ ] AC-22: All `pip install` lines in the Dockerfile reference `requirements.txt` with `-r` flag; no bare `pip install <package>` without a version pin; `docker build --no-cache` produces reproducible package set (Quality Rule: Reproducible build)

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/DLPXECO-13635/DLPXECO-13635-functional.md → at least one row in ### Source Files to Modify
       FR-001 → Dockerfile row
       FR-002 → .dockerignore row
       FR-003 → README.md row
       FR-004 → README.md row (Windows-specific content)
       FR-005 → README.md row (registry placeholder subsection)
     - Non-Goals in docs/DLPXECO-13635/DLPXECO-13635-vision.md → MUST NOT appear in Architecture Changes
       NG1 (k8s/Helm) — not present
       NG2 (HTTP/SSE transport) — not present
       NG3 (linux/arm64 publishing) — not present
       NG4 (CI/CD pipeline) — not present
       NG5 (native Windows containers) — not present
       NG6 (changes to startup scripts) — not present
       NG7 (docker-compose production config) — not present
     Run: .claude/evals/check-structure.sh DLPXECO-13635 --step design -->
