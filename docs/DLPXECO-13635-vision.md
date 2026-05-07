# DLPXECO-13635 — Docker Support for DCT MCP Server: Vision

> **Ticket**: [DLPXECO-13635](https://perforce.atlassian.net/browse/DLPXECO-13635) — Support for Hosting MCP Server in docker container
> **Issue type**: Feature Request
> **Domain**: feature
> **Assignee**: Vinay Byrappa

---

## 1. Problem

Today the Delphix DCT MCP Server (`dct-mcp-server`) can be installed in three ways:

1. **`uvx` from GitHub** — recommended for end users; requires `uv` on the host.
2. **`pip install` from GitHub** — requires Python 3.11+ on the host.
3. **Local clone + `start_mcp_server_uv.sh` / `start_mcp_server_python.sh`** — for developers; requires Python and shell access.

All three paths place the burden of toolchain provisioning on the user: they must install `uv` or `pip`, ensure Python 3.11+, manage virtualenvs, and (on Windows) navigate the differences between the `.bat` and `.sh` startup scripts. There is no portable, OS-neutral way to:

- Run the server with **zero host-side Python/uv setup**.
- Pin a known-good runtime + dependency set in a way that survives across user machines (hermetic execution).
- Distribute the server through corporate registries / air-gapped environments where `pip` and `uvx` to public PyPI/GitHub are not reachable.
- Stand up a reproducible **Windows** dev or test environment for the server (the existing `start_mcp_server_windows_*.bat` files are tied to the host Python install).

This creates friction in three contexts:

| Audience | Friction today |
|---|---|
| End users on Windows | Must install Python + uv + correct shell; PowerShell vs. cmd differences; PATH issues |
| Internal QA / demo environments | Cannot trivially spin up a fresh, isolated server per test run |
| Field engineers in restricted networks | No way to ship the server as an immutable image to an air-gapped host |

## 2. Goals

This feature adds a **first-class Docker distribution path** for the MCP server so the four ticket-stated requirements are met:

1. **G1 — Hosting in a Docker container**: A `Dockerfile` at the repo root that builds an image running `dct-mcp-server` as PID 1, configurable entirely through the documented `DCT_*` environment variables.
2. **G2 — README documentation**: A new "Run with Docker" section in the README covering build, run, env-var configuration, and MCP client wiring — with copy-pasteable commands.
3. **G3 — Windows support**: The published image runs unmodified on **Windows hosts via Docker Desktop with the WSL2 backend** (Linux containers). PowerShell and `cmd` examples are provided alongside macOS/Linux examples in the docs.
4. **G4 — Registry placeholder URL**: A documented placeholder of the form `<registry-host>/delphix/dct-mcp-server:<tag>` (with a clearly-marked TODO note) that future releases will swap in once the registry is provisioned. End users can `docker pull` from this placeholder and substitute in their own internal mirror until the official registry exists.

Beyond the explicit ticket requirements, two implicit goals follow from the project's existing conventions:

5. **G5 — Match existing runtime semantics**: The container must behave identically to `python -m dct_mcp_server.main` invoked from a clone — same stdio transport, same env-var contract, same logging behavior. No Docker-specific divergence in tool registration or DCT API client behavior.
6. **G6 — Image hygiene**: The image must use a non-root user at runtime, pin the Python base image to a specific minor version, and avoid copying `.git`, `logs/`, `__pycache__`, virtualenvs, or local credentials into the image (enforced via `.dockerignore`).

## 3. Non-Goals

This feature explicitly does **not** address:

- **Kubernetes / Helm packaging**. A Helm chart or k8s manifests are out of scope; we only ship a Dockerfile and `docker run` examples.
- **HTTP / SSE transport**. The MCP server uses stdio. Running stdio inside a long-lived detached container is the standard MCP-over-Docker pattern (the client launches `docker run -i --rm ...` per session). We do not introduce a new HTTP transport.
- **Multi-arch image publishing**. Initial image is `linux/amd64`. `linux/arm64` may be added later but is not a blocker for this ticket.
- **CI/CD pipeline for image publishing**. Wiring up GitHub Actions to build/push to a registry is a follow-up. This ticket adds the `Dockerfile` + docs only; the registry URL is a placeholder per ticket requirement #4.
- **Windows containers (Server Core / Nano Server)**. We support Windows *hosts* running Linux containers (via Docker Desktop / WSL2). Native Windows containers would require a separate base image and build pipeline.
- **`docker-compose.yml`**. Not required by the ticket; the server has no companion services. May be added as a documentation example only if it clarifies the wiring.
- **Changes to existing startup scripts** (`start_mcp_server_*.sh` / `.bat`). These remain the path for local-clone developers. Docker is added alongside, not replacing them.

## 4. Constraints

- **MCP transport is stdio.** The container's entrypoint must keep stdin/stdout open and unmuxed for the MCP client to drive the server. This rules out background `daemon`-style containers and dictates the use of `docker run -i` (interactive without TTY) or equivalent.
- **No code changes to `main.py` or `dct_client/`.** Goal G5 requires behavioral parity. Any deviation breaks the existing `start_mcp_server_*.sh` and the published `uvx` / `pip` install paths.
- **Python 3.11+ minimum** (per `pyproject.toml requires-python = ">=3.11"`). The base image must satisfy this.
- **No telemetry or credentials baked into the image.** `DCT_API_KEY` and `DCT_BASE_URL` must be passed at `docker run` time via `-e`. `IS_LOCAL_TELEMETRY_ENABLED` defaults to `false` and remains opt-in.
- **The image must work behind corporate proxies.** Build steps must not require interactive prompts; runtime must respect `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` env vars (httpx already honors these).
- **Reproducibility.** The image must build deterministically from `requirements.txt` or `uv.lock` — no unpinned `pip install` of latest.

## 5. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | stdio transport doesn't survive `docker run` cleanly on some Windows / PowerShell shells (line-buffering, CRLF translation, TTY allocation) | Medium | High — server unusable on Windows | Explicit `-i` (no `-t`) flag in docs; PowerShell vs. cmd command examples; document `--init` for proper signal handling; smoke-test from PowerShell on Windows in test plan |
| R2 | Image bloat — naive `python:3.11` base + `pip install` produces a ~1 GB image | High | Medium — slow pulls, registry cost | Use `python:3.11-slim` base; multi-stage build separating build deps from runtime; rely on `requirements.txt` (already pinned); `.dockerignore` excludes dev artifacts |
| R3 | Tool generation step (`generate_tools_from_openapi()`) writes to `$TEMP/dct_mcp_tools/` at startup. In a container, `$TEMP` (`/tmp`) is ephemeral — the regen runs on every container start | Low | Low — adds ~1–2s to startup | Acceptable; the bundled `docs/api-external.yaml` fallback ensures the server still starts if the OpenAPI download fails. Document this as expected behavior. |
| R4 | Running as root inside the container is a security smell; running as non-root may break `logs/` write permissions if the user mounts a host volume | Medium | Medium | Create `appuser` in the Dockerfile; `chown` `/app/logs` to `appuser`; document the volume-mount pattern (`-v $(pwd)/logs:/app/logs`) and the `--user` override for users who need root for debugging |
| R5 | Registry URL is a placeholder — users may `docker pull` and get nothing | Low (until publish) | High once published incorrectly | Ticket explicitly calls for a placeholder. README must mark it as **TODO: pending registry provisioning** and provide a build-from-source fallback so users are never blocked. |
| R6 | `urllib3>=2.6.3` and the `apk ` API key prefix behavior must work identically inside the container | Low | High — silently broken auth | Validation phase will run a smoke-test invoking `dct_client/client.py` against a live DCT to confirm. Covered in test plan. |
| R7 | The `start_mcp_server_*.sh` scripts auto-install Python and `uv` if absent. Container has neither — entrypoint must `exec` directly into the Python module, not run those scripts | Medium | High — container hangs / fails | `Dockerfile` `CMD` is `python -m dct_mcp_server.main`. Do not invoke `start_mcp_server_*.sh` from the container. Document this distinction. |
| R8 | Toolset config files (`config/toolsets/*.txt`) may be missed if `COPY src/ /app/src/` is not exhaustive | Low | High — server starts with empty toolset | Use `COPY . /app/` with a thorough `.dockerignore`, and add a build-time smoke test that asserts `import dct_mcp_server.config.loader` succeeds and at least one toolset is parseable. |

## 6. Out-of-band considerations

- The ticket description explicitly says "Have a placeholder of url where the docker image can be hosted" — interpreted as "document a placeholder pull URL in the README, not provision a real registry." Confirmed scope: docs-only placeholder, no actual publish step.
- The ticket title says "Hosting MCP Server in docker container" (singular "Hosting") — interpreted as packaging/distribution support, not as introducing a long-lived server-style hosting model. Stdio per-session container launch is the correct MCP pattern.
- No mention of multi-tenancy, secrets management, or TLS termination — out of scope.

## 7. Success criteria (informal — formalised in the functional spec)

The feature is successful if:

- A user with only Docker installed (no Python, no uv) can run the server end-to-end on macOS, Linux, and Windows from a single set of documented commands.
- The README's new "Run with Docker" section answers the questions a first-time user has, in order: build / pull → set env vars → wire into the MCP client.
- Existing `uvx` / `pip` / `start_mcp_server_*.sh` users see no behavioral change.
- The image builds in under 3 minutes on a typical developer laptop and is under 250 MB compressed.

---

*See [DLPXECO-13635-functional.md](DLPXECO-13635-functional.md) for the FR-* breakdown and acceptance criteria.*
