# Release Notes and Doc Updates: DLPXECO-13635 — Docker Container Support

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13635
**PR**: https://github.com/delphix/dxi-mcp-server/pull/68
**Branch**: `dlpx/feature/DLPXECO-13635-docker-container-support`

---

## Release Notes (End-User Facing)

### New Feature: Docker Container Support

The DCT MCP Server can now be built and run as a Docker container on Linux and Windows (Docker Desktop with Linux containers). This provides a fully isolated, reproducible runtime that does not require a local Python installation.

**Quick start:**

```bash
# Build the image
docker build -t dct-mcp-server .

# Run (the -i flag is required for MCP stdio transport)
docker run -i --rm \
  -e DCT_API_KEY=your-api-key \
  -e DCT_BASE_URL=https://your-dct-host.company.com \
  dct-mcp-server
```

**MCP client configuration (Claude Desktop, Cursor, VS Code):**

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-e", "DCT_API_KEY=your-api-key",
               "-e", "DCT_BASE_URL=https://your-dct-host.company.com",
               "dct-mcp-server"]
    }
  }
}
```

**docker-compose support:** Copy `.env.example` to `.env`, fill in credentials, and run `docker-compose up --build`.

See `## Running with Docker` in `README.md` for full instructions including Windows setup and troubleshooting.

---

## Files Added

| File | Purpose |
|------|---------|
| `Dockerfile` | Docker image build instructions using `python:3.11-slim` |
| `docker-compose.yml` | Single-command startup with `.env` credential management |
| `.env.example` | Environment variable template (safe to commit) |

## Files Modified

| File | Change |
|------|--------|
| `README.md` | Added `## Running with Docker` section (8 subsections); ToC and Project Structure updated |

## Files Not Changed

All files in `src/`, `pyproject.toml`, `requirements.txt`, startup scripts — no runtime behavior changes.

---

## Runbook

### Building the Docker image

```bash
# Standard build
docker build -t dct-mcp-server .

# For deployment to amd64 from Apple Silicon (ARM64)
docker build --platform linux/amd64 -t dct-mcp-server .
```

### Running with docker-compose

```bash
cp .env.example .env          # Copy template
# Edit .env: set DCT_API_KEY and DCT_BASE_URL
docker-compose up --build     # Build and start
docker-compose down           # Stop and clean up
```

### MCP client integration

The server uses stdio transport. The MCP client must launch the container as a subprocess:

```json
{
  "command": "docker",
  "args": ["run", "-i", "--rm", "-e", "DCT_API_KEY=...", "-e", "DCT_BASE_URL=...", "dct-mcp-server"]
}
```

The `-i` flag is mandatory — it keeps stdin open for MCP communication.

### Windows (Docker Desktop)

1. Open Docker Desktop → Settings → General
2. Ensure "Use the WSL 2 based engine" is selected (Linux containers mode)
3. Build and run using the same commands as Linux

### Troubleshooting

- **Container exits immediately**: Check `-i` flag is present; check `DCT_API_KEY` and `DCT_BASE_URL` are set
- **View logs**: `docker logs <container-id>` or `tail -f logs/dct_mcp_server.log` (with volume mount)
- **SSL errors**: Set `DCT_VERIFY_SSL=false` or inject custom CA via `REQUESTS_CA_BUNDLE` env var and volume mount
