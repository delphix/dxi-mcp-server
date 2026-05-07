# Test Infrastructure — DCT MCP Server

Sets up the MCP server for local testing. Two installation methods are supported — choose
based on what is available in the environment.

## Context Detection — Which Method to Use

Run this check first:

```bash
docker info > /dev/null 2>&1 && echo "docker=yes" || echo "docker=no"
command -v uv > /dev/null 2>&1 && echo "uv=yes" || echo "uv=no"
```

| Result | Use |
|--------|-----|
| `docker=yes` | [Option A: Docker](#option-a-docker) |
| `docker=no`, `uv=yes` | [Option B: Local (uv)](#option-b-local-uv) |
| `docker=no`, `uv=no` | [Option B: Local (pip)](#option-b-local-pip) |

Docker is preferred when available — it avoids Python environment conflicts and gives a
clean, reproducible setup. Local is faster to iterate on during development.

---

## Prerequisites (both options)

Credentials must be present in `.claude/settings.local.json` under `mcpServers.dct.env`.
Verify they are set:

```bash
python3 -c "
import json
d = json.load(open('.claude/settings.local.json'))
env = d['mcpServers']['dct']['env']
assert env.get('DCT_API_KEY'), 'DCT_API_KEY missing'
assert env.get('DCT_BASE_URL'), 'DCT_BASE_URL missing'
print('Credentials OK')
print('  DCT_BASE_URL =', env['DCT_BASE_URL'])
print('  DCT_TOOLSET  =', env.get('DCT_TOOLSET', 'self_service'))
"
```

**Expected outcome**: Prints `Credentials OK` and the two values. If it errors, populate
`.claude/settings.local.json` with your DCT API key and base URL before continuing.

---

## Option A: Docker

### Step A1 — Build the image

```bash
docker build -t dct-mcp-server:local .
```

**Expected outcome**: `Successfully built` (or equivalent). Image `dct-mcp-server:local`
appears in `docker images`. If the build fails, read the error output — most failures are
network issues pulling the base image or a missing `src/` directory (run from repo root).

### Step A2 — Smoke test the image

```bash
DCT_API_KEY=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_API_KEY'])")
DCT_BASE_URL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_BASE_URL'])")

CID=$(docker run -d \
  -e DCT_API_KEY="$DCT_API_KEY" \
  -e DCT_BASE_URL="$DCT_BASE_URL" \
  -e DCT_TOOLSET=self_service \
  -e DCT_VERIFY_SSL=false \
  -e DCT_LOG_LEVEL=DEBUG \
  dct-mcp-server:local)

sleep 4 && docker logs "$CID" 2>&1 | head -20
docker stop "$CID" > /dev/null
```

**Expected outcome**: Log lines showing `DCT MCP Server initialized` and
`All available tools have been registered.` No `Configuration error` or crash lines.

### Step A3 — Configure .mcp.json to use Docker

Read credentials from `settings.local.json` and write the `delphix-dct` entry into
`.mcp.json` automatically:

```bash
python3 -c "
import json, pathlib

src = json.load(open('.claude/settings.local.json'))
env = src['mcpServers']['dct']['env']

mcp_path = pathlib.Path('.mcp.json')
mcp = json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
mcp.setdefault('mcpServers', {})

mcp['mcpServers']['delphix-dct'] = {
    'command': 'docker',
    'args': [
        'run', '--rm', '-i',
        '-e', 'DCT_API_KEY=' + env['DCT_API_KEY'],
        '-e', 'DCT_BASE_URL=' + env['DCT_BASE_URL'],
        '-e', 'DCT_TOOLSET=' + env.get('DCT_TOOLSET', 'auto'),
        '-e', 'DCT_VERIFY_SSL=' + env.get('DCT_VERIFY_SSL', 'false'),
        '-e', 'DCT_LOG_LEVEL=' + env.get('DCT_LOG_LEVEL', 'INFO'),
        'dct-mcp-server:local'
    ]
}

mcp_path.write_text(json.dumps(mcp, indent=2))
print('Written .mcp.json with delphix-dct (Docker)')
"
```

The `-i` flag is required — it keeps stdin open for the MCP stdio transport.

**Expected outcome**: `.mcp.json` updated and `delphix-dct` entry present with real
credentials. After restarting Claude Code, run `/mcp` to confirm the server is connected.

### Rebuilding after code changes

```bash
docker build -t dct-mcp-server:local . && echo "Rebuild OK"
```

Restart the MCP client after rebuilding — containers are started fresh on each connection.

---

## Option B: Local

### Step B1 (uv) — Install dependencies and run

```bash
uv sync
```

**Expected outcome**: Dependencies resolved and installed into `.venv/`. No error output.

### Step B1 (pip) — Install dependencies and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

**Expected outcome**: `Successfully installed dct-mcp-server` and dependencies. `.venv/`
directory exists.

### Step B2 — Smoke test the local server

```bash
DCT_API_KEY=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_API_KEY'])")
DCT_BASE_URL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_BASE_URL'])")

DCT_API_KEY="$DCT_API_KEY" DCT_BASE_URL="$DCT_BASE_URL" DCT_TOOLSET=self_service \
  DCT_LOG_LEVEL=DEBUG .venv/bin/python -m dct_mcp_server.main &
SERVER_PID=$!
sleep 4
kill $SERVER_PID 2>/dev/null
cat logs/dct_mcp_server.log | head -20
```

**Expected outcome**: Log shows `DCT MCP Server initialized` and
`All available tools have been registered.` No `Configuration error` lines.

### Step B3 — Configure .mcp.json for local launch

Read credentials from `settings.local.json` and write the `delphix-dct` entry into
`.mcp.json` automatically:

```bash
python3 -c "
import json, pathlib, shutil

src = json.load(open('.claude/settings.local.json'))
env = src['mcpServers']['dct']['env']

# Use uv script if uv is available, otherwise fall back to pip script
script = 'start_mcp_server_uv.sh' if shutil.which('uv') else 'start_mcp_server_python.sh'

mcp_path = pathlib.Path('.mcp.json')
mcp = json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
mcp.setdefault('mcpServers', {})

mcp['mcpServers']['delphix-dct'] = {
    'command': 'bash',
    'args': [script],
    'env': {
        'DCT_API_KEY':   env['DCT_API_KEY'],
        'DCT_BASE_URL':  env['DCT_BASE_URL'],
        'DCT_TOOLSET':   env.get('DCT_TOOLSET', 'auto'),
        'DCT_VERIFY_SSL': env.get('DCT_VERIFY_SSL', 'false'),
        'DCT_LOG_LEVEL': env.get('DCT_LOG_LEVEL', 'INFO'),
    }
}

mcp_path.write_text(json.dumps(mcp, indent=2))
print('Written .mcp.json with delphix-dct (local,', script + ')')
"
```

**Expected outcome**: `.mcp.json` updated and `delphix-dct` entry present with real
credentials. After restarting Claude Code, run `/mcp` to confirm the server is connected.

---

## Verify DCT connectivity (both options)

Once the server is connected, confirm it can reach DCT by asking Claude Code:

```
List all VDBs
```

**Expected outcome**: A response from DCT — either a VDB list or an empty result. An
`authentication failed` or `connection refused` response means a credentials or network
issue, not a server problem — recheck `DCT_API_KEY` and `DCT_BASE_URL`.

---

## Switching toolsets

Change `DCT_TOOLSET` in `.mcp.json` and restart the MCP client:

| Value | Description |
|-------|-------------|
| `auto` | 6 meta-tools; dynamic toolset switching at runtime |
| `self_service` | Basic VDB operations (default) |
| `self_service_provision` | Extended self-service with provisioning |
| `continuous_data_admin` | Full DBA operations |
| `platform_admin` | System administration |
| `reporting_insights` | Read-only reporting |

## Logs

- Local: `logs/dct_mcp_server.log`
- Docker: `docker logs <container-id>` (find ID with `docker ps`)
