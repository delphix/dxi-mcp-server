# Test Infrastructure

Instructions for Claude to bring up the DCT MCP Server before running tests.

## Credentials

Read credentials from `.claude/settings.local.json` — the `mcpServers.dct.env` block contains:
- `DCT_API_KEY` — API key for the DCT instance
- `DCT_BASE_URL` — Base URL of the DCT instance
- `DCT_TOOLSET` — Toolset to enable (e.g. `self_service`)
- `DCT_VERIFY_SSL` — SSL verification flag

Export them at runtime like this (never hardcode or log values):
```bash
export DCT_API_KEY=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_API_KEY'])")
export DCT_BASE_URL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_BASE_URL'])")
export DCT_TOOLSET=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_TOOLSET'])")
export DCT_VERIFY_SSL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_VERIFY_SSL'])")
export DCT_LOG_LEVEL=DEBUG
```

## Choosing the Startup Path

**Check whether the current change is Docker-related before starting the server.**

A change is Docker-related if any of the following are true:
- A `Dockerfile` exists in the repo root
- The design doc's `## Source Files to Modify` or `## New Files` mentions `Dockerfile`, `docker-compose`, or container configuration
- The change being tested is specifically about Docker image build, container startup, or container environment

**If Docker-related → use Path A (Docker)**
**Otherwise → use Path B (uv)**

---

## Path A — Docker

Use this path when the change involves the Dockerfile or container runtime.

1. Export credentials (see above)

2. Build the Docker image using the ticket ID as the tag:
```bash
docker build -t dct-mcp-server:$NAME .
```
If the build fails, stop and report the error — do not fall back to uv.

3. Start the container:
```bash
docker run -d --name dct-mcp-test \
  -e DCT_API_KEY="$DCT_API_KEY" \
  -e DCT_BASE_URL="$DCT_BASE_URL" \
  -e DCT_TOOLSET="$DCT_TOOLSET" \
  -e DCT_VERIFY_SSL="$DCT_VERIFY_SSL" \
  -e DCT_LOG_LEVEL=DEBUG \
  dct-mcp-server:$NAME
sleep 3
```

4. Verify the container is running:
```bash
docker ps --filter "name=dct-mcp-test" --format "{{.Status}}"
```
Expected: `Up N seconds`

5. Verify the DCT endpoint is reachable:
```bash
curl -sk -H "Authorization: ApiKey $DCT_API_KEY" "$DCT_BASE_URL/v3/management/version" | python3 -m json.tool
```
Expected: JSON response with a `version` field.

### Docker Teardown
```bash
docker stop dct-mcp-test && docker rm dct-mcp-test
```

---

## Path B — uv (direct)

Use this path for all non-Docker changes.

1. Export credentials (see above), then also set:
```bash
export PYTHONPATH=src
```

2. Start the server in the background:
```bash
bash start_mcp_server_uv.sh &
sleep 3
```

3. Verify it started:
```bash
tail -20 logs/mcp_server_setup.log
```
Expected: last lines confirm the server started without errors.

4. Verify the DCT endpoint is reachable:
```bash
curl -sk -H "Authorization: ApiKey $DCT_API_KEY" "$DCT_BASE_URL/v3/management/version" | python3 -m json.tool
```
Expected: JSON response with a `version` field.

### uv Teardown
```bash
kill %1 2>/dev/null || true
```
