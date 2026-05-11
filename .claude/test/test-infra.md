# Test Infrastructure — DCT MCP Server

Sets up the MCP server for local testing. Three installation methods are supported — choose
based on what is available in the environment.

## Context Detection — Which Method to Use

Run this check first:

```bash
command -v uvx > /dev/null 2>&1 && echo "uvx=yes" || echo "uvx=no"
command -v uv  > /dev/null 2>&1 && echo "uv=yes"  || echo "uv=no"
```

| Result | Use |
|--------|-----|
| `uvx=yes` and you don't need a local clone | [Option A: uvx (no clone)](#option-a-uvx-no-clone) |
| `uvx=no` but pip available, no clone needed | [Option B: pip from git (no clone)](#option-b-pip-from-git-no-clone) |
| Local clone, `uv=yes` | [Option C: Local clone (uv)](#option-c-local-clone-uv) |
| Local clone, `uv=no` | [Option C: Local clone (pip)](#option-c-local-clone-pip) |

For development on the server itself, use Option C — only that method picks up local code
edits. Options A and B are good for testing a published version against a DCT instance.

---

## Prerequisites (all options)

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

### Supported environment variables

The server reads these (see `src/dct_mcp_server/config/config.py`):

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DCT_API_KEY` | Yes | — | Do not prefix with `apk` — the client adds it |
| `DCT_BASE_URL` | Yes | `https://localhost:8083` | No `/dct` suffix |
| `DCT_TOOLSET` | No | `self_service` | See [Switching toolsets](#switching-toolsets) |
| `DCT_VERIFY_SSL` | No | `false` | Set `true` in production |
| `DCT_LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `DCT_TIMEOUT` | No | `30` | Seconds |
| `DCT_MAX_RETRIES` | No | `3` | Retry attempts on failure |
| `IS_LOCAL_TELEMETRY_ENABLED` | No | `false` | Opt-in JSON session telemetry under `logs/sessions/` |

---

## Option A: uvx (no clone)

### Step A1 — Smoke test

```bash
DCT_API_KEY=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_API_KEY'])")
DCT_BASE_URL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_BASE_URL'])")

DCT_API_KEY="$DCT_API_KEY" DCT_BASE_URL="$DCT_BASE_URL" DCT_TOOLSET=self_service \
  DCT_LOG_LEVEL=DEBUG \
  uvx --from git+https://github.com/delphix/dxi-mcp-server.git dct-mcp-server &
SERVER_PID=$!
# Poll for the success line (up to 60s — first uvx run downloads); break early on success.
for i in $(seq 1 60); do
  grep -q "All available tools have been registered." logs/dct_mcp_server.log 2>/dev/null && break
  sleep 1
done
kill $SERVER_PID 2>/dev/null
head -20 logs/dct_mcp_server.log
```

**Expected outcome**: Log shows `DCT MCP Server initialized` and
`All available tools have been registered.` First run takes longer while uvx downloads.

### Step A2 — Configure .mcp.json for uvx

```bash
python3 -c "
import json, pathlib

src = json.load(open('.claude/settings.local.json'))
env = src['mcpServers']['dct']['env']

mcp_path = pathlib.Path('.mcp.json')
mcp = json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
mcp.setdefault('mcpServers', {})

mcp['mcpServers']['delphix-dct'] = {
    'command': 'uvx',
    'args': ['--from', 'git+https://github.com/delphix/dxi-mcp-server.git', 'dct-mcp-server'],
    'env': {
        'DCT_API_KEY':                env['DCT_API_KEY'],
        'DCT_BASE_URL':               env['DCT_BASE_URL'],
        'DCT_TOOLSET':                env.get('DCT_TOOLSET', 'self_service'),
        'DCT_VERIFY_SSL':             env.get('DCT_VERIFY_SSL', 'false'),
        'DCT_LOG_LEVEL':              env.get('DCT_LOG_LEVEL', 'INFO'),
        'DCT_TIMEOUT':                env.get('DCT_TIMEOUT', '30'),
        'DCT_MAX_RETRIES':            env.get('DCT_MAX_RETRIES', '3'),
        'IS_LOCAL_TELEMETRY_ENABLED': env.get('IS_LOCAL_TELEMETRY_ENABLED', 'false'),
    }
}

mcp_path.write_text(json.dumps(mcp, indent=2))
print('Written .mcp.json with delphix-dct (uvx)')
"
```

**Expected outcome**: `.mcp.json` updated. After restarting Claude Code, run `/mcp` to
confirm the server is connected.

---

## Option B: pip from git (no clone)

### Step B1 — Install

```bash
python3 -m venv .venv-dct
source .venv-dct/bin/activate
pip install git+https://github.com/delphix/dxi-mcp-server.git
which dct-mcp-server
```

**Expected outcome**: `Successfully installed dct-mcp-server` and `which` prints a path
inside `.venv-dct/bin/`.

### Step B2 — Smoke test

```bash
DCT_API_KEY=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_API_KEY'])")
DCT_BASE_URL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_BASE_URL'])")

DCT_API_KEY="$DCT_API_KEY" DCT_BASE_URL="$DCT_BASE_URL" DCT_TOOLSET=self_service \
  DCT_LOG_LEVEL=DEBUG dct-mcp-server &
SERVER_PID=$!
for i in $(seq 1 30); do
  grep -q "All available tools have been registered." logs/dct_mcp_server.log 2>/dev/null && break
  sleep 1
done
kill $SERVER_PID 2>/dev/null
head -20 logs/dct_mcp_server.log
```

**Expected outcome**: Log shows `DCT MCP Server initialized` and
`All available tools have been registered.`

### Step B3 — Configure .mcp.json for the pip-installed CLI

```bash
python3 -c "
import json, pathlib, shutil

src = json.load(open('.claude/settings.local.json'))
env = src['mcpServers']['dct']['env']

cli = shutil.which('dct-mcp-server') or 'dct-mcp-server'

mcp_path = pathlib.Path('.mcp.json')
mcp = json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
mcp.setdefault('mcpServers', {})

mcp['mcpServers']['delphix-dct'] = {
    'command': cli,
    'env': {
        'DCT_API_KEY':                env['DCT_API_KEY'],
        'DCT_BASE_URL':               env['DCT_BASE_URL'],
        'DCT_TOOLSET':                env.get('DCT_TOOLSET', 'self_service'),
        'DCT_VERIFY_SSL':             env.get('DCT_VERIFY_SSL', 'false'),
        'DCT_LOG_LEVEL':              env.get('DCT_LOG_LEVEL', 'INFO'),
        'DCT_TIMEOUT':                env.get('DCT_TIMEOUT', '30'),
        'DCT_MAX_RETRIES':            env.get('DCT_MAX_RETRIES', '3'),
        'IS_LOCAL_TELEMETRY_ENABLED': env.get('IS_LOCAL_TELEMETRY_ENABLED', 'false'),
    }
}

mcp_path.write_text(json.dumps(mcp, indent=2))
print('Written .mcp.json with delphix-dct (pip CLI at', cli + ')')
"
```

**Expected outcome**: `.mcp.json` updated. After restarting Claude Code, run `/mcp` to
confirm the server is connected.

---

## Option C: Local clone (uv)

### Step C1 — Install dependencies

```bash
uv sync
```

**Expected outcome**: Dependencies resolved and installed into `.venv/`. No error output.

## Option C: Local clone (pip)

### Step C1 — Install dependencies (pip variant)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

**Expected outcome**: `Successfully installed dct-mcp-server` and dependencies. `.venv/`
directory exists.

### Step C2 — Smoke test the local server

```bash
DCT_API_KEY=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_API_KEY'])")
DCT_BASE_URL=$(python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print(d['mcpServers']['dct']['env']['DCT_BASE_URL'])")

DCT_API_KEY="$DCT_API_KEY" DCT_BASE_URL="$DCT_BASE_URL" DCT_TOOLSET=self_service \
  DCT_LOG_LEVEL=DEBUG .venv/bin/python -m dct_mcp_server.main &
SERVER_PID=$!
for i in $(seq 1 30); do
  grep -q "All available tools have been registered." logs/dct_mcp_server.log 2>/dev/null && break
  sleep 1
done
kill $SERVER_PID 2>/dev/null
head -20 logs/dct_mcp_server.log
```

**Expected outcome**: Log shows `DCT MCP Server initialized` and
`All available tools have been registered.` No `Configuration error` lines.

### Step C3 — Configure .mcp.json for local launch

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
        'DCT_API_KEY':                env['DCT_API_KEY'],
        'DCT_BASE_URL':               env['DCT_BASE_URL'],
        'DCT_TOOLSET':                env.get('DCT_TOOLSET', 'self_service'),
        'DCT_VERIFY_SSL':             env.get('DCT_VERIFY_SSL', 'false'),
        'DCT_LOG_LEVEL':              env.get('DCT_LOG_LEVEL', 'INFO'),
        'DCT_TIMEOUT':                env.get('DCT_TIMEOUT', '30'),
        'DCT_MAX_RETRIES':            env.get('DCT_MAX_RETRIES', '3'),
        'IS_LOCAL_TELEMETRY_ENABLED': env.get('IS_LOCAL_TELEMETRY_ENABLED', 'false'),
    }
}

mcp_path.write_text(json.dumps(mcp, indent=2))
print('Written .mcp.json with delphix-dct (local,', script + ')')
"
```

**Expected outcome**: `.mcp.json` updated and `delphix-dct` entry present with real
credentials. After restarting Claude Code, run `/mcp` to confirm the server is connected.

---

## Verify DCT connectivity (all options)

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

- `logs/dct_mcp_server.log` — application log (daily rotation)
- `logs/sessions/{session_id}.log` — per-session JSON telemetry, only when
  `IS_LOCAL_TELEMETRY_ENABLED=true`

---

## Next: run the tests

With the server wired up, follow [`testing.md`](testing.md) for what to verify per change
type and how to drive the automated pytest suite.
