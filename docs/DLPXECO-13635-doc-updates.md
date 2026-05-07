# Documentation Updates: Docker Support for the DCT MCP Server

**Jira**: [DLPXECO-13635](https://perforce.atlassian.net/browse/DLPXECO-13635) — Support for Hosting MCP Server in docker container
**Affects**:
- `README.md` — new "Run with Docker" subsection under "Advanced Installation"
- Internal contributor rules (`.claude/rules/build-and-execution.md`) — added a "Run with Docker" subsection so future CLAUDE.md regeneration stays accurate

## Summary of Change

Users can now run the DCT MCP Server from a Docker container instead of installing Python, `uv`, or `pip` on the host. A Dockerfile and `.dockerignore` ship in the repository so anyone with Docker installed can build a slim, deterministic image and run the server end-to-end on macOS, Linux, or Windows (Linux containers via Docker Desktop with the WSL2 backend). All existing install paths (`uvx`, `pip install`, local clone start scripts) continue to work unchanged — Docker is an additional option, not a replacement.

## Pages to Update

### Run with Docker — README.md "Advanced Installation" section

| Section | What to change |
|---------|----------------|
| Table of Contents | Already updated — confirm the "Run with Docker" entry links to the new subsection. |
| Advanced Installation | Already extended — confirm the new "Run with Docker" subsection sits between "Developer Setup" and "Connecting a Client to a Running Server" so the install paths read in increasing complexity. |
| Run with Docker | Already drafted with: prerequisites, build-from-source command, registry-pull placeholder (clearly marked as pending registry provisioning), required env vars, optional env vars (cross-referenced — not duplicated), MCP client wiring example, log persistence example, and shell variants for bash/zsh, PowerShell, and cmd.exe. |

Suggested writer review for the "Run with Docker" subsection (in the tone of the existing README):

> The DCT MCP Server can be run in a Docker container as an alternative to installing Python locally. This is the recommended path for Windows users who do not already have Python and `uv` set up, for users in environments where installing global tooling is restricted, and for anyone who wants a hermetic, reproducible runtime.
>
> The image is `linux/amd64`, runs as a non-root user, uses `tini` as PID 1 for clean signal handling, and starts the server on stdio — the same transport used by the local-clone install. MCP clients launch the container per session with `docker run -i --rm`.
>
> A registry pull URL is documented as a placeholder (`<registry-host>/delphix/dct-mcp-server:<tag>`) and will be replaced once the official registry is provisioned. Until then, build from source.

### Run with Docker — `.claude/rules/build-and-execution.md`

| Section | What to change |
|---------|----------------|
| Run with Docker | Already added with build/run snippets, image facts (base, size, non-root user, PID 1, no `EXPOSE`, no `HEALTHCHECK`), log-persistence pattern, and a note that the host-only `start_mcp_server_*` scripts are not invoked inside the container. |
| Logs | Already extended with the `-v $(pwd)/logs:/app/logs` example so users know where container logs land on the host. |

## New Configuration Parameters

No new configuration parameters. The container honours the existing environment-variable contract exactly.

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| (none) | All `DCT_*` env vars listed in the existing "Environment Variables" table apply unchanged inside the container. Pass them with `-e VAR=value` on the `docker run` command line. | — | — |

## Release Notes Entry

The DCT MCP Server now ships with first-class Docker support. A `Dockerfile` and `.dockerignore` at the repo root produce a slim, non-root, deterministic Linux image that runs the server on stdio with the same environment-variable contract as the local-clone install. Users on macOS, Linux, and Windows (Docker Desktop + WSL2) can build and run the server with two commands and wire it into their MCP client without installing Python or `uv` on the host. Existing install paths (`uvx`, `pip install`, `start_mcp_server_*.sh`) are unchanged.

---

## Runbook

### What changed and why users may notice it

- **New install path**: A "Run with Docker" subsection now appears in the README under "Advanced Installation". Users who previously had to install Python 3.11+ and `uv` (especially on Windows) can now run the server from a single `docker run` command.
- **No behaviour change for existing installs**: Anyone running the server via `uvx`, `pip install`, or one of the `start_mcp_server_*` scripts will see no difference. Their commands, env vars, log locations, and MCP client wiring all continue to work as before.
- **MCP client config form is slightly different for the Docker path**: clients launch `docker run -i --rm ...` per session instead of pointing at a local Python entry point. Per-session container lifetime is the standard MCP-over-Docker pattern for stdio transport.

### How to verify the change is working correctly

1. **Build the image** from a fresh clone:
   ```
   docker build -t dct-mcp-server:dev .
   ```
   Expected: build completes in a few minutes; final image size around 250 MB uncompressed (closer to 80 MB compressed).

2. **Run the container manually** with a real DCT API key and base URL:
   ```
   docker run --rm -i \
     -e DCT_API_KEY=<your-api-key> \
     -e DCT_BASE_URL=<your-dct-host> \
     dct-mcp-server:dev
   ```
   Expected: the server starts, prints its startup log lines to stderr, and waits for MCP requests on stdin. Press Ctrl-C to stop.

3. **Wire into an MCP client** (Claude Desktop, Cursor, or VS Code) using the Docker `command` form documented in the README. Run a read-only action (e.g. list VDBs via `vdb_tool` with `DCT_TOOLSET=self_service`). The response shape should match what the same call returns when the server is run via `uvx` or a local clone.

4. **Confirm log persistence** if the user is mounting a host volume:
   ```
   docker run --rm -i \
     -e DCT_API_KEY=... -e DCT_BASE_URL=... \
     -v "$(pwd)/logs:/app/logs" \
     dct-mcp-server:dev
   ```
   Expected: `logs/dct_mcp_server.log` appears on the host; rotation behaviour matches the local-clone install.

5. **Verify the existing install paths are unchanged**: run the server via `./start_mcp_server_uv.sh` (or `uvx --from git+... dct-mcp-server`) and confirm no regression from the pre-Docker behaviour.

### What to check if something appears broken after deployment

| Symptom | What to check |
|---------|---------------|
| `docker build` fails on a fresh machine | Public network access to Docker Hub and PyPI. The build must not require any private mirror. Re-run with `--no-cache` to rule out a stale layer. |
| Image larger than ~250 MB uncompressed | The `.dockerignore` may have been edited to allow build artefacts back in. Verify `docs/`, `.git/`, `logs/`, `.venv/`, and `__pycache__/` are still excluded. |
| Container exits immediately on `docker run -i` | `DCT_API_KEY` or `DCT_BASE_URL` likely missing. Check the container's stderr for the validation error. |
| MCP client cannot reach the server | The client must launch the container with `-i` (interactive, no TTY) — not `-it`. A pseudo-TTY breaks the stdio framing the MCP protocol expects. Verify the client config uses `-i`. |
| Garbled output / CRLF issues on Windows | Confirm Docker Desktop is on the WSL2 backend (Linux containers, not Windows containers). The image is `linux/amd64` only. |
| `docker stop <id>` hangs | `tini` is PID 1 and forwards SIGTERM correctly; if signal handling looks broken, verify the running image is the one built from this repository's Dockerfile (the `STOPSIGNAL SIGTERM` directive should be present). |
| Logs not appearing on the host | The mount must be `-v <host-path>:/app/logs` and the host directory must be writable by UID 1000 (the in-container `appuser`). On Windows, use Docker Desktop's "File sharing" settings to grant access to the host path. |
| `tools/list` shows fewer tools than expected | `DCT_TOOLSET` may be unset (defaults to `self_service`). Pass `-e DCT_TOOLSET=continuous_data_admin` (or another toolset) to enable the full set. |
| "Pull from registry" command fails | The registry URL in the README is currently a **placeholder pending registry provisioning**. Build from source is the supported path until the registry is published — this is expected, not a bug. |

### Rollback

Removing the Dockerfile and `.dockerignore`, and reverting the README and `.claude/rules/build-and-execution.md` Docker subsections, fully removes the feature with zero impact on the existing install paths. The runtime code in `src/dct_mcp_server/` is untouched by this change, so rollback does not affect server behaviour for any other install method.
