# Test Evidence: DLPXECO-13635

## Landscape / Environment
- macOS (Darwin 23.6.0)
- Docker Desktop (20.10+, buildx capable)
- Branch: `mcpondockercontainer`
- Startup path: Docker (Path A) — change involves Dockerfile

## Versions Tested
- Base image: `python:3.11-slim`
- DCT instance: `dct-sho.dlpxdc.co`
- Toolset: `self_service`

## Scenarios Exercised

| Scenario | Outcome |
|----------|---------|
| `docker build -t dct-mcp-server:DLPXECO-13635 .` | Pass — built cleanly, no errors |
| Non-root user: `docker run --rm ... whoami` → `mcpuser` | Pass |
| Server starts and loads tools from DCT OpenAPI spec | Pass — 46 APIs grouped into 6 unified tools |
| Graceful logging fix: mkdir fails with PermissionError, warning printed to stderr, server continues running | Pass — `Warning: Failed to create global log file /usr/local/lib/python3.11/logs/dct_mcp_server.log: [Errno 13] Permission denied` observed, server proceeded normally |
| All 46 APIs loaded across 6 tools (self_service toolset) | Pass |
| `.dockerignore` excludes secrets, dev files, Python artifacts | Pass — verified by file inspection |
| README `## Docker` section present with build/run/logs/client-config examples | Pass |
