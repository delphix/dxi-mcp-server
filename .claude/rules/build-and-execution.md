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
| `DCT_LOG_DIR` | No | auto-detected | Override the log directory; useful when running as pip-installed package (e.g. Docker) to write logs to a mounted volume |

## Logs

- Application log: `logs/dct_mcp_server.log` (daily rotation)
- Session telemetry: `logs/sessions/{session_id}.log` (JSON, opt-in only)
