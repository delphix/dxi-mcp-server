---
name: dct-mcp-test
description: Run the DCT MCP Server test suite from within Claude Code. Wraps the dct-mcp-test CLI with URL aliasing (localhost/remote) and interactive failure triage. Usage — /dct-mcp-test <localhost|remote|URL> [--api-key <key>] [--layer ci|unit|integration|functional|e2e|all] [--workflow <pattern>]
---

# /dct-mcp-test — Run the DCT MCP Server test suite

This skill is the conversational front door for the `dct-mcp-test` CLI. The CLI itself is the canonical implementation; this skill just translates chat-friendly invocations into shell calls and helps triage failures.

## When the user invokes `/dct-mcp-test`

### 1. Parse args

- **First positional arg** — `localhost`, `remote`, or a literal URL
- `--api-key <key>` — required for `e2e` and `all` layers; otherwise optional
- `--layer <name>` — one of `unit`, `integration`, `functional`, `ci`, `e2e`, `all`. Defaults to `ci` (Layers 1–3, no DCT needed).
- `--workflow <pattern>` — filter to workflows whose name matches (passed to pytest as `-k`)
- `--no-cleanup` — only meaningful for `e2e`/`all`; ask the user to confirm if they pass this against a persistent DCT

### 2. Resolve the base URL

Map the first positional arg:
- `localhost` → `http://localhost:8443` (or `DCT_LOCAL_URL` env var if set)
- `remote` → ask the user for the URL, OR read `DCT_REMOTE_URL` env var if set
- Any string starting with `http://` or `https://` → use as-is

If the user runs `--layer ci` (or any layer that doesn't need DCT) and does not pass a URL, **don't ask for one** — the CI layer doesn't need it.

### 3. Invoke the CLI via Bash

Build the command:

```bash
dct-mcp-test \
  --layer <layer> \
  [--base-url <resolved-url>] \
  [--api-key <key>] \
  [--workflow <pattern>] \
  [--no-cleanup]
```

Run it with the `Bash` tool. Stream the output back to the user.

### 4. On failure, offer triage

If pytest exits non-zero:

- Read the failing test file referenced in the output
- Identify the failed assertion or error
- Propose a fix and offer to edit the file
- After the user accepts a fix, re-run the skill with the same args

If the failure is in cleanup (`tests/e2e/cleanup`) and the layer was `e2e`, alert the user clearly — there may be orphaned resources on the persistent DCT that need manual cleanup, and surface the `E2E_RUN_TAG` value from the output so they can find them.

## Usage examples

```text
# Layers 1-3 against the in-process stub (no creds needed) — default
/dct-mcp-test

# Same, explicit layer
/dct-mcp-test --layer ci

# Just the unit tests
/dct-mcp-test --layer unit

# Full E2E against a localhost DCT
/dct-mcp-test localhost --api-key abc123 --layer e2e

# Named remote instance
/dct-mcp-test remote --api-key xyz789 --layer e2e

# One specific workflow
/dct-mcp-test localhost --api-key abc --layer functional --workflow vdb_lifecycle

# Everything (CI + E2E)
/dct-mcp-test remote --api-key xyz --layer all
```

## Why this skill exists

The bare CLI works perfectly well from a terminal. The skill adds value when you're already in Claude Code:

- **URL aliasing** — `localhost`/`remote` are shorter than typing URLs
- **No context switch** — results stream into the chat
- **Interactive triage** — Claude can read the failing test, propose a fix, edit it, and re-run in one session
- **Discoverability** — appears in slash-command autocomplete

CI workflows (`.github/workflows/test.yml`) call the CLI directly. The skill is for human, interactive use.
