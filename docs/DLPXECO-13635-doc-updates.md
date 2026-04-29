# Release Notes: DLPXECO-13635 — Docker Support

## What's New

### Docker Support for DCT MCP Server

The DCT MCP Server can now be packaged and run as a Docker container. This enables:

- **CI/CD integration**: deploy the server as a container in automated pipelines
- **Team deployments**: share a reproducible server image without requiring Python on every machine
- **Isolated environments**: run the server without affecting the host Python installation

### New Files

| File | Description |
|------|-------------|
| `Dockerfile` | Builds a `python:3.11-slim`-based image with `dct-mcp-server` as the entry point |
| `.dockerignore` | Excludes dev artefacts (`logs/`, `.claude/`, `.git/`, `.env`, `venv/`, `docs/`) from the build context |

### Build the Image

```bash
docker build -t dct-mcp-server .
```

### Run the Container

```bash
docker run -e DCT_API_KEY=<your-key> -e DCT_BASE_URL=https://your-dct-instance dct-mcp-server
```

For HTTP/SSE mode (port-based MCP client connection):

```bash
docker run -p 6790:6790 -e DCT_API_KEY=<your-key> -e DCT_BASE_URL=https://your-dct-instance dct-mcp-server
```

### Windows Compatibility

The image uses a Linux base and runs on Docker Desktop for Windows in Linux container mode (the default). See `README.md` for PowerShell examples.

## What Hasn't Changed

- All MCP tools and their behaviour are identical inside and outside Docker
- All environment variables behave the same — `DCT_API_KEY`, `DCT_BASE_URL`, `DCT_TOOLSET`, etc.
- No Python source code was modified

## Known Limitations

- The registry image (`ghcr.io/delphix/dct-mcp-server:latest`) is a placeholder — the CI publishing pipeline is a separate work item
- Log files are ephemeral inside the container; use `-v $(pwd)/logs:/app/logs` to persist them
- stdio MCP transport does not cross container boundaries; use port-based (`-p 6790:6790`) connection for containerised deployments
