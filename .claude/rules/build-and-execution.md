# Build and Execution Rules

## Running the Server

**Recommended (uvx — no install needed):**
```bash
uvx --from git+https://github.com/delphix/dxi-mcp-server.git dct-mcp-server
```

**From a local clone:**
```bash
export DCT_API_KEY="your-api-key"
export DCT_BASE_URL="https://your-dct-host.company.com"

./start_mcp_server_uv.sh      # uv (recommended)
./start_mcp_server_python.sh  # venv fallback
```

**Install via pip:**
```bash
pip install git+https://github.com/delphix/dxi-mcp-server.git
dct-mcp-server
```

## Run with Docker

A `Dockerfile` and `.dockerignore` at the repo root produce a slim, non-root, deterministic runtime image. See `README.md` "Run with Docker" for the full client-config recipe and Windows variants.

**Build:**
```bash
docker build -t dct-mcp-server:dev .
```

**Run (stdio transport — `-i`, no `-t`):**
```bash
docker run --rm -i \
  -e DCT_API_KEY="your-api-key" \
  -e DCT_BASE_URL="https://your-dct-host.company.com" \
  dct-mcp-server:dev
```

**Image facts:**
- Base: `python:3.11-slim-bookworm` (digest-pinned)
- Multi-stage build; final image ≈ 244 MB uncompressed (≈ 80 MB compressed)
- Runs as non-root `appuser` (UID/GID 1000)
- PID 1 is `tini` for clean signal forwarding (`docker stop` triggers FastMCP lifespan shutdown)
- No `EXPOSE`, no `HEALTHCHECK` — stdio transport only
- OCI labels populated (`org.opencontainers.image.*`)
- `STOPSIGNAL` is `SIGTERM`

**Persisting logs to the host (optional):**
```bash
docker run --rm -i \
  -e DCT_API_KEY="..." -e DCT_BASE_URL="..." \
  -v "$(pwd)/logs:/app/logs" \
  dct-mcp-server:dev
```

**Notes:**
- The container's entrypoint is `python -m dct_mcp_server.main` — the host-only `start_mcp_server_*.sh` and `start_mcp_server_*.bat` scripts are excluded from the image and never invoked from the container.
- All `DCT_*` env vars listed below work identically inside the container — pass them with `-e VAR=value`.
- The bundled OpenAPI fallback `docs/api-external.yaml` is excluded from the image; the server downloads the spec from `${DCT_BASE_URL}/dct/static/api-external.yaml` on every container start (the existing `tool_factory.py` fallback path no-ops gracefully when the bundled file is absent).

## Development Connection

When running from a local clone, the server prints the port it listens on (e.g. `http://127.0.0.1:6790`). Connect your MCP client using just the port — no env vars needed in the client:

```json
{ "mcpServers": { "delphix-dct": { "port": 6790 } } }
```

This allows server restarts without reconfiguring the client.

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DCT_API_KEY` | Yes | — | Do not prefix with `apk` |
| `DCT_BASE_URL` | Yes | — | No `/dct` suffix |
| `DCT_TOOLSET` | No | `self_service` | `auto`, `self_service`, `self_service_provision`, `continuous_data_admin`, `platform_admin`, `reporting_insights` |
| `DCT_VERIFY_SSL` | No | `false` | Set `true` in production |
| `DCT_LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `DCT_TIMEOUT` | No | `30` | Seconds |
| `DCT_MAX_RETRIES` | No | `3` | |
| `IS_LOCAL_TELEMETRY_ENABLED` | No | `false` | Opt-in telemetry |

## Logs

- Application log: `logs/dct_mcp_server.log` (daily rotation)
- Session telemetry: `logs/sessions/{session_id}.log` (JSON, opt-in only)
- In Docker: `logs/` lives at `/app/logs` inside the container; mount it with `-v $(pwd)/logs:/app/logs` to surface to the host.
