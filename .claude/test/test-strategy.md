# Automated Test Suite — Research, Architecture & Migration Plan

**Status:** Proposal
**Author:** Generated from research session (2026-05-22)
**Goal:** Replace manual Claude Desktop verification with an automated test suite that runs on every code change.

---

## 1. Problem Statement

Today, every code change to `dxi-mcp-server` is verified by hand through Claude Desktop. A developer manually drives prompts from `.claude/test/testing/<toolset>.md`, visually inspects responses, and writes a free-text report into the PR.

This is unsustainable because it:

- **Doesn't scale** — five personas × ~70 prompts each = hours of human time per change
- **Isn't reproducible** — Claude's responses vary; "looks right" is not a regression signal
- **Doesn't gate merges** — a broken `vdb_tool` can land on `main` and nobody knows until someone tries it
- **Requires a live DCT instance** — credentials, network, state-dependent results

We want: a test suite that runs on every push/PR, fails fast on regressions, requires no live DCT, and does not need a human in the loop.

---

## 1.1 What This Strategy Achieves — Summary Table

| Layer | What it proves | Catches what nothing else does | Needs DCT? | Triggered by | Blocks merge? |
|---|---|---|---|---|---|
| **1 — Unit** | Action routing, parameter building, confirmation state machine, config parsing | Logic bugs in tool functions (mocked client) | No | Every save / PR | Yes |
| **2 — Integration** | HTTP wire: URL building, `apk ` auth, retries, timeouts | Bugs that only appear once real HTTP is built | No (respx) | Every push / PR | Yes |
| **3a — Toolset registration** | Right tools registered per persona | Edits to `config/toolsets/*.txt` silently changing tool exposure | No (dct_stub) | Every PR | Yes |
| **3b — Workflow tests ★** | Multi-step chains over MCP stdio | **Replaces the manual Claude Desktop playbook** — every `.md` scenario as a deterministic test | No (dct_stub) | Every PR | Yes |
| **3c — Confirmation handshake** | Two-step `confirmation_required` → `confirmed=True` over MCP wire | Regressions in destructive-op safety net | No (dct_stub) | Every PR | Yes |
| **4 — Real-DCT E2E** | Workflows against the cloned DCT | Real API contract drift, real auth, real latency | Yes | Manual via GitHub UI / Claude Code skill / CLI | No (advisory) |
| **5 — LLM-driven (optional)** | AI can navigate the tool surface | Confusing action names, vague descriptions | No (dct_stub) | LM Studio, local-only | No (advisory) |

**Invocation paths — all hit the same `dct-mcp-test` CLI:**

| Path | When | How |
|---|---|---|
| CLI | Terminal, scripts, ad-hoc | `dct-mcp-test --base-url ... --api-key ...` |
| GitHub Actions | Every PR (Layers 1–3) + on-demand (Layer 4) | Workflow yaml calls `dct-mcp-test` |
| Claude Code skill | Interactive testing from chat | `/dct-mcp-test localhost --api-key ...` |

**Cost summary:**

| Item | Cost |
|---|---|
| Layers 1–3 in CI | $0 (free GitHub Actions tier) |
| Layer 4 in CI | $0 CI cost; cloned DCT is your existing infra |
| Layer 5 (LM Studio) | $0 (local hardware) |
| Anthropic API key for E2E | **Not needed** — explicitly designed around this constraint |
| Claude Desktop license | **Not needed** for testing anymore (only exploratory use) |

**Before vs. after:**

| Today | After this rollout |
|---|---|
| Push code → open Claude Desktop → run prompts manually → eyeball responses → write report | Push code → CI runs Layers 1–3 → PR shows green/red automatically. Pre-release: trigger Layer 4 via GitHub UI or `/dct-mcp-test` skill. |

---

## 2. The Core Insight — Two Different Questions

The manual Claude Desktop check is actually answering **two different questions** at once:

| Question | What it measures | How to automate |
|---|---|---|
| **Does the workflow still work?** | Functional regression — given input X, does the chain produce Y? | Deterministic scripted tests |
| **Can an AI figure out how to use the tools?** | Tool discoverability / schema clarity | LLM-driven tests |

These are fundamentally different testing problems and need different solutions. Conflating them is what makes the current manual process so heavy. The strategy below separates them:

- **Regression gate (primary):** scripted workflow tests, no LLM in the loop, runs on every PR
- **AI-usability check (optional, local):** LLM-driven, runs ad-hoc before releases

---

## 3. Current State

### What exists
- `.claude/test/testing.md` — manual playbook
- `.claude/test/test-infra.md` — setup guide; Track 2 specs automated suite that was never built
- `.claude/test/testing/*.md` — 6 prompt-driven scenario files containing the workflows
- `requirements.txt:33-34` — `pytest` and `pytest-asyncio` listed but **commented out**

### What doesn't exist
- `tests/` directory
- `conftest.py`, `pytest.ini`, or pytest configuration in `pyproject.toml`
- `.github/workflows/` — no CI at all
- Any mocking infrastructure for the DCT API

### Test seams already present in the code

| Seam | Location | Use |
|---|---|---|
| HTTP chokepoint | `src/dct_mcp_server/dct_client/client.py:77` (`make_request`) | Mock for unit tests |
| Config loading | `src/dct_mcp_server/config/config.py:9` | Env var injection |
| Toolset parser | `src/dct_mcp_server/config/loader.py` | `@lru_cache` — clear between tests |
| Tool registration | `src/dct_mcp_server/tools/__init__.py:50` | Test with fresh FastMCP app |
| MCP transport | FastMCP stdio | Drive via `fastmcp.Client` subprocess |

---

## 4. Architecture

Three layers in CI (regression gate), plus one optional local layer (AI usability).

```
   ┌──────────────────────────────────────────────────────────────┐
   │  Layer 1 — Unit (in-process, mocked client)                  │
   │  tool fn → MagicMock(DCTAPIClient).make_request              │
   │  ~60% of tests · seconds                                     │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 2 — Integration (in-process, mocked HTTP)             │
   │  tool fn → DCTAPIClient → httpx → respx intercept            │
   │  ~25% of tests · seconds                                     │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 3 — Functional (subprocess + stub DCT)                │
   │   3a. Toolset registration (5 cases, parametrized)           │
   │   3b. ★ Workflow tests — the .md scenarios as Python          │
   │   3c. Confirmation handshake over MCP wire                   │
   │  ~15% of tests · ~60 seconds                                 │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 4 — E2E vs. real cloned DCT                           │
   │  Same workflows, real instance, on-demand via GitHub UI      │
   │  Manual trigger primary; nightly cron optional               │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 5 — LLM-driven (LOCAL ONLY, optional)                 │
   │  LM Studio → MCP server → dct_stub                           │
   │  AI-usability check · not in CI · not blocking               │
   └──────────────────────────────────────────────────────────────┘
```

Layer 3b is the **centerpiece** — it's what directly replaces the manual Claude Desktop playbook. Each chain of prompts in the existing `.md` files becomes one Python test.

### 4.1 Layer 4 — E2E vs. real cloned DCT

You have a persistent cloned DCT instance with a stable API key, so Layer 4 is buildable. The right shape is **GitHub Secrets + `workflow_dispatch` (primary trigger) + optional nightly cron** — not always-on infra.

**Prerequisite check.** Before this runs in CI, confirm the cloned DCT is reachable from GitHub-hosted runner IPs (i.e., on the public internet). If it's VPN-only, the options are:
- Expose it via a tunnel (e.g. Cloudflare Tunnel, ngrok) for tests
- Use a self-hosted GitHub runner inside the network that hosts the DCT
- Fall back to local-only execution (developer runs `pytest tests/e2e` on a machine with VPN access)

The rest of this section assumes the clone is reachable from GitHub.

**One-time setup.**

1. In repo settings → Secrets → add:
   - `DCT_TEST_BASE_URL` — the clone's base URL (no `/dct` suffix)
   - `DCT_TEST_API_KEY` — the API key (without the `apk ` prefix; the client adds it)
2. Confirm the cloned DCT has stable known fixture data (at least one env, dSource, snapshot)

**One runner, two contexts.** Both local and CI invoke the same CLI entry point — `dct-mcp-test` — installed when you run `pip install -e ".[test]"`. See section 4.2 for the CLI design.

**Workflow file.**

```yaml
# .github/workflows/e2e-real-dct.yml
name: e2e-real-dct
on:
  workflow_dispatch:             # primary: run on demand from GitHub UI
  schedule:
    - cron: "0 6 * * *"          # optional: passive drift detection

jobs:
  e2e:
    runs-on: ubuntu-latest
    env:
      DCT_BASE_URL: ${{ secrets.DCT_TEST_BASE_URL }}
      DCT_API_KEY: ${{ secrets.DCT_TEST_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[test]"
      - run: dct-mcp-test --layer e2e    # same command devs run locally
      - name: Notify on failure
        if: failure()
        run: # post to Slack/email — does NOT fail any PR
```

**Cleanup strategy (critical for persistent DCT).**

Because the DCT clone persists between runs, anything tests create must be cleaned up — even on failure. Strategy:

- Every test tags everything it creates with `E2E_RUN_TAG` (`e2e-{github_run_id}`)
- A separate cleanup module (`tests/e2e/cleanup/test_purge.py`) runs as an `if: always()` step
- Cleanup searches for everything tagged with the current run ID and deletes it
- Crashed runs still get cleaned up because the cleanup step is forced to run

This is much simpler than per-test finalizers because there's one bulk cleanup pass instead of many granular ones.

**Test file shape.**

```python
# tests/e2e/test_vdb_smoke.py
import os
RUN_TAG = os.environ["E2E_RUN_TAG"]

@pytest.mark.real_dct
async def test_vdb_search_returns_results(real_mcp_client):
    result = await real_mcp_client.call_tool("vdb_tool", {"action": "search"})
    assert result["items"]

@pytest.mark.real_dct
async def test_create_bookmark_with_cleanup_tag(real_mcp_client):
    vdb_id = (await real_mcp_client.call_tool("vdb_tool", {"action": "search"}))["items"][0]["id"]
    bookmark = await real_mcp_client.call_tool("bookmark_tool", {
        "action": "create",
        "name": f"{RUN_TAG}-bookmark-1",  # tag in the name
        "vdbId": vdb_id,
    })
    # No need to delete here — cleanup step handles it
```

**Triggering it.**

- **Manual via GitHub UI (primary):** GitHub → Actions → `e2e-real-dct` → "Run workflow"
- **Nightly cron (optional):** turn on the schedule line for passive drift detection
- **Local dev (same CLI):** `dct-mcp-test --base-url <url> --api-key <key>` on your machine

**What Layer 4 catches that Layer 3 doesn't.**

- Real DCT API contract drift (Delphix changes an endpoint shape, the spec we use becomes stale)
- Real auth/permission issues (your API key actually works against real ACLs)
- Network/timeout behavior under real latency (the stub is fast; real DCT isn't)
- State that only exists on a real engine (real snapshots, real timeflows)

It does **not** catch new regressions faster than Layer 3 — Layer 3 still runs on every PR. Layer 4 is a periodic confidence check, not a per-commit gate.

### 4.2 The `dct-mcp-test` CLI — one runner, both contexts

A single CLI tool wraps pytest with the right flags, env vars, run-tag generation, and cleanup. It's registered as a `[project.scripts]` entry point in `pyproject.toml`, so `pip install -e ".[test]"` puts `dct-mcp-test` on your `$PATH`. **Local invocation and CI invocation are identical.**

**Usage.**

```bash
# Provide credentials via flags
dct-mcp-test --base-url https://my-cloned-dct.example.com --api-key abc123

# Or via env vars (preferred for CI)
export DCT_BASE_URL=https://my-cloned-dct.example.com
export DCT_API_KEY=abc123
dct-mcp-test

# Pick a specific layer (defaults to e2e)
dct-mcp-test --layer unit                # no credentials needed
dct-mcp-test --layer integration         # no credentials needed
dct-mcp-test --layer functional          # uses dct_stub, no real DCT needed
dct-mcp-test --layer e2e                 # real DCT, needs credentials
dct-mcp-test --layer all                 # everything in sequence

# Run a single workflow
dct-mcp-test --workflow vdb_lifecycle

# Skip cleanup (DANGER on persistent DCT — only for local debugging)
dct-mcp-test --no-cleanup
```

**What it does internally.**

1. Resolves credentials from flags or `DCT_BASE_URL` / `DCT_API_KEY` env vars
2. Generates a unique `E2E_RUN_TAG=e2e-{uuid8}-{timestamp}` for this run
3. Maps `--layer` to the right pytest paths and markers
4. Runs pytest
5. Always runs the cleanup pass at the end (unless `--no-cleanup`)
6. Exits with pytest's exit code

**Implementation.** About 50 lines at `src/dct_mcp_server/testing/cli.py`:

```python
import os, subprocess, sys, time, uuid
import click

@click.command()
@click.option("--base-url", envvar="DCT_BASE_URL", help="DCT base URL")
@click.option("--api-key", envvar="DCT_API_KEY", help="DCT API key")
@click.option("--layer",
    type=click.Choice(["unit", "integration", "functional", "e2e", "all"]),
    default="e2e", help="Test layer to run")
@click.option("--workflow", help="Filter to workflows matching this name")
@click.option("--no-cleanup", is_flag=True, help="Skip cleanup (DANGER on persistent DCT)")
def main(base_url, api_key, layer, workflow, no_cleanup):
    """Run the DCT MCP Server test suite."""
    env = os.environ.copy()

    if layer in ("e2e", "functional", "all"):
        if not base_url or not api_key:
            click.echo("--base-url and --api-key required for this layer", err=True)
            sys.exit(2)
        env["DCT_BASE_URL"] = base_url
        env["DCT_API_KEY"] = api_key
        env["E2E_RUN_TAG"] = f"e2e-{uuid.uuid4().hex[:8]}-{int(time.time())}"

    paths_by_layer = {
        "unit": ["tests/unit"],
        "integration": ["tests/integration"],
        "functional": ["tests/functional"],
        "e2e": ["tests/e2e"],
        "all": ["tests/unit", "tests/integration", "tests/functional", "tests/e2e"],
    }
    args = ["pytest", *paths_by_layer[layer], "-v"]
    if layer == "e2e":
        args.extend(["-m", "real_dct"])
    if workflow:
        args.extend(["-k", workflow])

    result = subprocess.run(args, env=env)

    if layer in ("e2e", "all") and not no_cleanup:
        click.echo("\n--- Running cleanup ---")
        subprocess.run(["pytest", "tests/e2e/cleanup", "-v"], env=env)

    sys.exit(result.returncode)
```

**Registration in `pyproject.toml`.**

```toml
[project.scripts]
dct-mcp-test = "dct_mcp_server.testing.cli:main"

[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "respx>=0.20",
    "starlette>=0.30",
    "uvicorn>=0.27",
    "syrupy>=4.0",
    "click>=8.0",        # for the CLI
]
```

**Why this design.**

| Property | Benefit |
|---|---|
| Single entry point | Same command works locally and in CI — no drift between environments |
| Env-var fallback | CI uses GitHub Secrets via env; local can use either env or flags |
| Layer selection | Devs can run just unit tests fast, or e2e when validating against real DCT |
| Forced cleanup | Even if tests crash, the CLI runs the cleanup pass before exiting |
| Standard pytest under the hood | All pytest features (`-k`, `-x`, `--pdb`, etc.) still accessible via the CLI's pass-through |

### 4.3 The `/dct-mcp-test` Claude Code skill — third invocation path

The same CLI is wrapped by a project-local Claude Code skill so it can be invoked from inside any Claude Code session via `/dct-mcp-test`. **Three invocation paths, one implementation:**

```
                  ┌──────────────────────────────────┐
                  │   src/dct_mcp_server/testing/    │
                  │   cli.py  (the actual logic)     │
                  └──────────────┬───────────────────┘
                                 │
        ┌────────────────────────┼───────────────────────────┐
        │                        │                            │
        ▼                        ▼                            ▼
   ┌──────────┐         ┌─────────────────┐         ┌──────────────────┐
   │   CLI    │         │ GitHub Actions  │         │ Claude Code skill│
   │ (terminal│         │  workflow yaml  │         │ /dct-mcp-test    │
   └──────────┘         └─────────────────┘         └──────────────────┘
```

**Location:** `.claude/skills/dct-mcp-test/SKILL.md`

```yaml
---
name: dct-mcp-test
description: Run the DCT MCP Server test suite against a DCT instance. Args: <localhost|remote|URL> [--name <label>] [--api-key <key>] [--layer e2e|unit|integration|functional|all] [--workflow <name>]
---

When the user invokes /dct-mcp-test:

## 1. Parse args
- First positional: "localhost", "remote", or a literal URL
- --name: optional, descriptive label for the run
- --api-key: required for e2e/functional layers (or read DCT_API_KEY env)
- --layer: default "e2e"
- --workflow: optional, filters to one workflow

## 2. Resolve base URL
- "localhost" → http://localhost:8443 (or DCT_LOCAL_URL env)
- "remote" → ask user for URL, or read DCT_REMOTE_URL env
- URL string → use as-is

## 3. Invoke via Bash
   dct-mcp-test --base-url <resolved-url> --api-key <key> --layer <layer> [--workflow <name>]

## 4. Stream output
- Show pytest output as it runs
- On test failure, offer to help debug: read the failing test file,
  identify what assertion failed, suggest fixes
- On cleanup failure, alert clearly (orphaned resources on persistent DCT)
```

**Usage examples.**

```text
/dct-mcp-test localhost --api-key abc123
/dct-mcp-test remote --name staging-clone-1 --api-key xyz789
/dct-mcp-test https://my-dct.example.com --api-key xyz789
/dct-mcp-test localhost --api-key abc123 --workflow vdb_lifecycle
/dct-mcp-test remote --api-key xyz --layer all
```

**Why this layering matters.**

| Concern | Where it lives |
|---|---|
| Pytest invocation, env vars, cleanup pass | CLI (one place to maintain) |
| GitHub Actions yaml | Calls CLI |
| Chat-based invocation, URL aliasing, interactive debug | Skill |

If you change how the test suite runs, you change the CLI. CI yaml and the skill follow automatically.

**What the skill adds beyond just typing the CLI command.**

- URL aliasing — `localhost`/`remote` shortcuts instead of memorizing URLs
- Stays in Claude Code — no terminal context switch; results in chat
- Failure triage — Claude can read the failing test, propose a fix, edit it, and re-run the skill in one session
- Discoverability — `/dct-mcp-test` shows up in slash-command autocomplete

CI still uses the bare CLI because workflows aren't conversational. Local + interactive use prefers the skill.

---

## 5. Layer 3b — Workflow Tests (the heart of the suite)

### Pattern

Each multi-step chain in `.claude/test/testing/<toolset>.md` translates to one test function. The chaining ("that VDB" → previous result) becomes a Python variable. Each step is a real MCP call over stdio. Each step is verified at the wire level via `dct_stub`.

```python
# tests/functional/workflows/test_vdb_lifecycle.py
async def test_vdb_lifecycle_start_stop(mcp_client, dct_stub):
    # Step 1 — Search for all VDBs
    vdbs = await mcp_client.call_tool("vdb_tool", {"action": "search"})
    assert vdbs["items"], "search returned no VDBs"
    vdb_id = vdbs["items"][0]["id"]

    # Step 2 — Get details of the first one
    details = await mcp_client.call_tool("vdb_tool", {"action": "get", "vdbId": vdb_id})
    assert details["id"] == vdb_id

    # Step 3 — Start that VDB
    await mcp_client.call_tool("vdb_tool", {"action": "start", "vdbId": vdb_id})
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/start")

    # Step 4 — Stop that VDB
    await mcp_client.call_tool("vdb_tool", {"action": "stop", "vdbId": vdb_id})
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/stop")
```

### Mapping: scenario files → workflow tests

```
.claude/test/testing/self_service.md
├── lines 12–17  (vdb_tool: search→get→start→stop)    → test_vdb_lifecycle.py
├── lines 18–23  (vdb_tool: refresh variants)          → test_vdb_refresh.py
├── lines 24–28  (vdb_tool: rollback variants)         → test_vdb_rollback.py
├── lines 30–47  (vdb_group_tool full lifecycle)       → test_vdb_group_lifecycle.py
├── lines 49–53  (dsource_tool)                        → test_dsource.py
├── lines 55–64  (snapshot_tool)                       → test_snapshot.py
├── lines 66–75  (bookmark_tool + delete confirmation) → test_bookmark_lifecycle.py
├── lines 77–81  (job_tool + abandon confirmation)     → test_job.py
└── lines 83–93  (timeflow_tool + delete confirmation) → test_timeflow.py
```

Same shape for the other 4 toolset scenario files. Roughly **30–40 workflow tests** replace the entire manual playbook.

---

## 6. The `dct_stub` Component

A fake DCT server that runs inside the pytest process so functional and workflow tests don't need a real DCT instance.

### Data flow

```
   pytest process                       subprocess (MCP server)
   ┌──────────────────────┐            ┌─────────────────────┐
   │ test function        │            │ vdb_tool(...)       │
   │  │                   │  stdio     │  │                  │
   │  ▼                   │ ◀────────▶ │  ▼                  │
   │ fastmcp.Client       │            │ DCTAPIClient        │
   │                      │            │  │  httpx →         │
   │ dct_stub ◀───────────┼── HTTP ────┤  DCT_BASE_URL       │
   │ (Starlette, port=0)  │            │  http://127.0.0.1   │
   └──────────────────────┘            └─────────────────────┘
```

### What it needs to support (for workflow tests)

- **Stateful canned data** — `vdbs/search` returns the same fixture every time, so "the first VDB" is always `v-1`. No randomness.
- **Endpoint coverage matching the workflows** — every endpoint the chains touch: search, get, start, stop, refresh variants, snapshots list, bookmarks list, tag operations, etc. ~30–40 routes total across all toolsets.
- **Request recorder** — so tests can assert "the server *did* send `POST /vdbs/v-1/start` to DCT", not just "the call returned without error."
- **Response overrides per test** — for negative cases ("what if start returns 503?") a fixture can override the default response.
- **`/dct/static/api-external.yaml`** — so the OpenAPI bootstrap doesn't fail.

Total size: ~200 lines.

---

## 7. Why Not Claude Desktop / LLM-Driven for the Regression Gate

The question keeps coming up: "can we just automate Claude Desktop?" The honest answer is no, and the reasons are worth recording so we don't relitigate them later.

### Claude Desktop GUI automation — rejected

| Concern | Detail |
|---|---|
| Closed Electron app | No official automation API; Playwright/AppleScript driving relies on DOM that changes between releases |
| Slow | ~10s per click; full scenario file would take 15+ minutes |
| Zero new signal | Claude Desktop's only unique behavior is the LLM picking tools — and Desktop's LLM is the same Claude you'd hit via API more cleanly |
| Brittle in CI | Headless GUI in GitHub Actions is its own infrastructure project |

### Claude API as the driver — blocked by license + cost

| Concern | Detail |
|---|---|
| **Requires explicit API key** | Anthropic API (console.anthropic.com) is a separate product from Claude Enterprise (claude.ai with SSO). The Enterprise license covers humans using the UI; it does **not** include programmatic API access by default. |
| **No key currently available** | An API key would need to be provisioned by IT/admin under the enterprise contract, or set up via AWS Bedrock / GCP Vertex AI if those exist in the org |
| **Real cost** | Per scenario run: ~$2.40 without prompt caching, ~$0.50–$0.80 with caching. Full nightly run (5 toolsets): ~$12 uncached, ~$3–4 cached. Monthly: $30–$360 depending on cadence and caching strategy |
| **Noisy signal for regression testing** | An LLM driver can fail a test because *it* got confused, not because the code regressed. This blurs the failure attribution and makes flake triage expensive |

### LM Studio (local LLM) — useful, but for a different purpose

LM Studio exposes an OpenAI-compatible HTTP API on `localhost:1234/v1`. Any code that talks to OpenAI talks to LM Studio with a base-URL swap.

**Pros**

- $0 monetary cost
- No API key required
- Runs offline, fully private
- Free for unlimited runs

**Cons / tradeoffs**

| Concern | Detail |
|---|---|
| Model quality dictates tool-use reliability | Qwen 2.5 Coder 32B = good. Llama 3.3 70B = very good. Llama 3.1 8B default = marginal. Anything <7B = unreliable. |
| Hardware bound | 32B model needs ~20GB RAM; 70B needs ~40GB+. On 16GB you're stuck with smaller models that misfire on multi-step chains. |
| Cannot run in GitHub Actions | GitHub-hosted runners have no GPU and limited RAM. Would require a self-hosted runner with LM Studio always running — that's real infra work. |
| Slower than hosted APIs | 5–30 tok/s on a Mac vs 50–100 tok/s for the Claude API |
| Noisier signal | Same failure-attribution problem as Claude API — was it the code, or the model? |

### What LM Studio is good for (and what it's not)

**Good for:**

- **Pre-release exploratory testing.** A developer fires it up before a release, runs the workflows, sees whether the AI can navigate the toolsurface naturally. Catches things like confusing action names, vague parameter descriptions, ambiguous tool overlap.
- **Local sanity check after refactoring tool schemas.** If you renamed actions or changed descriptions, LM Studio tells you if you broke discoverability.
- **Demo / showcasing without cloud dependencies.**

**Not good for:**

- The CI regression gate. Use scripted workflow tests for that — deterministic, fast, free, runs anywhere.
- Replacing the manual Claude Desktop playbook on a per-PR basis. The signal is too noisy and the infra to run it in CI is too heavy.

### The architectural separation

```
   ┌────────────────────────────┐   ┌────────────────────────────┐
   │ Regression gate             │   │ AI-usability check          │
   │ (runs on every PR)          │   │ (runs ad-hoc, local)        │
   │                             │   │                             │
   │ Layers 1–3                  │   │ Layer 5                     │
   │ Scripted, deterministic     │   │ LLM-driven, exploratory     │
   │ No LLM in the loop          │   │ LM Studio (no API key)      │
   │ $0 cost                     │   │ $0 cost                     │
   │                             │   │                             │
   │ Answers:                    │   │ Answers:                    │
   │  "did the workflow break?"  │   │  "can an AI use this tool?" │
   └────────────────────────────┘   └────────────────────────────┘
```

These are separate questions. Solve them with separate tools. Layer 5 is **completely optional** — the regression-prevention goal is fully met by Layers 1–3 alone.

---

## 8. Concrete Changes Required

### 8.1 `pyproject.toml`

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "respx>=0.20",
    "starlette>=0.30",
    "uvicorn>=0.27",
    "syrupy>=4.0",       # snapshot testing for response shapes
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

### 8.2 `requirements.txt`

Uncomment lines 33–34, or rely on the `pyproject.toml` test extra.

### 8.3 New directory: `tests/`

```
tests/
├── conftest.py                              # shared fixtures, cache clearing
├── unit/
│   ├── test_vdb_tool.py
│   ├── test_job_tool.py
│   ├── ... (one per *_endpoints_tool.py)
│   ├── test_loader.py
│   └── test_confirmation.py
├── integration/
│   ├── conftest.py
│   ├── test_client_transport.py
│   ├── test_client_retry.py
│   ├── test_client_timeout.py
│   └── test_tool_to_wire.py
├── functional/
│   ├── conftest.py
│   ├── test_server_starts.py
│   ├── test_toolset_registration.py         # Layer 3a
│   ├── test_confirmation_handshake.py       # Layer 3c
│   └── workflows/                            # Layer 3b — the centerpiece
│       ├── test_vdb_lifecycle.py
│       ├── test_vdb_refresh.py
│       ├── test_vdb_rollback.py
│       ├── test_vdb_group_lifecycle.py
│       ├── test_dsource.py
│       ├── test_snapshot.py
│       ├── test_bookmark_lifecycle.py
│       ├── test_job.py
│       ├── test_timeflow.py
│       └── ... (one per scenario chain across all toolset .md files)
├── llm_local/                                # Layer 5 — optional, local-only
│   ├── README.md                             # how to run with LM Studio
│   └── test_ai_usability_smoke.py
└── fixtures/
    ├── dct_stub.py                          # stateful stub server
    └── responses/
        ├── vdbs_search.json
        ├── vdbs_v1.json
        ├── jobs_search.json
        └── ...
```

### 8.4 `.github/workflows/test.yml`

```yaml
name: tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[test]"
      - run: pytest tests/unit tests/integration -v
      - run: pytest tests/functional -v
```

Mark as required check in branch protection. Layer 5 tests are explicitly excluded from CI.

### 8.5 Optional Layer 5 runner script

`scripts/run-llm-local-tests.sh`:

```bash
#!/usr/bin/env bash
# Run LLM-driven AI-usability checks against a local LM Studio instance.
# Requires LM Studio running with a tool-use-capable model loaded.
export OPENAI_API_BASE="http://localhost:1234/v1"
export OPENAI_API_KEY="lm-studio"
pytest tests/llm_local -v "$@"
```

Run manually before releases. Not part of CI.

### 8.6 Documentation updates

- `.claude/test/testing.md` — point to this strategy doc; mark manual playbook as exploratory only
- `README.md` — add a Testing section

---

## 9. When Tests Run

| Trigger | What runs | Invocation | Blocking? |
|---|---|---|---|
| While coding | Layer 1 (unit) | `dct-mcp-test --layer unit` | No |
| Pre-push hook (optional) | Layer 1 (unit) | `dct-mcp-test --layer unit` | Yes (local) |
| Every push / PR | Layers 1–3 (unit + integration + functional incl. workflows) | GitHub Actions calls `dct-mcp-test` | **Yes — merge gate** |
| On-demand against real DCT | Layer 4 (real cloned DCT) | GitHub Actions `workflow_dispatch`, or `/dct-mcp-test localhost --api-key ...` from Claude Code, or CLI direct | No (advisory) |
| Optional nightly | Layer 4 | GitHub Actions cron | No (advisory) |
| Pre-release AI usability | Layer 5 (LM Studio) | `scripts/run-llm-local-tests.sh` | No (advisory) |

The PR merge gate (line 3) is what replaces manual Claude Desktop verification. Layer 4 covers the real-DCT validation you currently do by hand.

---

## 10. Migration Plan

Phased so workflow coverage lands as early as possible. Each phase is independently shippable.

### Phase 1 — Foundation (day 1)
- Add test extra to `pyproject.toml`
- Create `tests/conftest.py` with the mock-client + FastMCP app fixtures
- Write one unit test for `vdb_tool` to prove the pattern
- **Deliverable:** `pytest tests/unit` runs green

### Phase 2 — `dct_stub` + first workflow (days 2–3)
- Build `tests/fixtures/dct_stub.py` with stateful canned responses, request recorder, ~10 routes
- Write `tests/functional/workflows/test_vdb_lifecycle.py` — the highest-traffic chain
- Write `test_toolset_registration.py` (5 personas, parametrized)
- **Deliverable:** one workflow + persona registration verified end-to-end without DCT

### Phase 3 — CI wiring (day 4)
- Add `.github/workflows/test.yml`
- Enable branch protection requiring the `tests` check
- **Deliverable:** PRs cannot merge with failing tests

### Phase 4 — Integration coverage (day 5)
- Add `respx` retry/auth/timeout tests against `DCTAPIClient`
- **Deliverable:** wire-level regressions can no longer slip through

### Phase 5 — Workflow translation (days 6–10)
- One PR per scenario `.md` file, translating each chain into a workflow test
- Expand `dct_stub` route coverage as new workflows demand
- **Deliverable:** every workflow in `.claude/test/testing/*.md` is now a passing test

### Phase 6 — Backfill unit tests (days 11–13)
- One test file per `*_endpoints_tool.py` (9 files)
- Cover action routing + confirmation flow per tool
- Add `test_loader.py`, `test_confirmation.py`

### Phase 7 — Snapshot assertions (day 14)
- Wire `syrupy` into workflow tests
- Capture response-shape snapshots; future drift breaks tests
- **Deliverable:** response-contract regressions caught automatically

### Phase 8 — `dct-mcp-test` CLI + skill (day 15)
- Build `src/dct_mcp_server/testing/cli.py` (click-based)
- Register as `[project.scripts]` entry point in `pyproject.toml`
- Create `.claude/skills/dct-mcp-test/SKILL.md`
- Update CI workflow to invoke `dct-mcp-test` instead of raw `pytest`
- **Deliverable:** three invocation paths (CLI / CI / skill) all hit the same runner

### Phase 9 — Layer 4 wiring (days 16–17)
- Confirm cloned DCT reachability from GitHub-hosted runners (or set up tunnel/self-hosted runner if VPN-only)
- Add `DCT_TEST_BASE_URL` and `DCT_TEST_API_KEY` to GitHub Secrets
- Create `tests/e2e/` directory; mirror selected workflows from `tests/functional/workflows/` with `@pytest.mark.real_dct` markers
- Build `tests/e2e/cleanup/test_purge.py` — uses `E2E_RUN_TAG` to delete anything created
- Add `.github/workflows/e2e-real-dct.yml` with `workflow_dispatch` trigger
- **Deliverable:** real-DCT validation runnable from GitHub UI, Claude Code skill, or CLI

### Phase 10 — Optional Layer 5 (later)
- Wire `tests/llm_local/` against LM Studio
- Document the recommended model + RAM requirements
- Use pre-release, not pre-merge

Total realistic budget: **~3 working weeks** to fully replace manual verification. Phases 1–3 alone deliver the merge gate in 4 days. Phase 9 closes the real-DCT gap that Claude Desktop currently fills.

---

## 11. Success Criteria

### After Phase 5 (merge gate replaces manual playbook)

1. `pytest` runs locally with no DCT credentials and no network
2. Every PR shows a CI status check; merges to `main` require it to pass
3. Every chain in `.claude/test/testing/*.md` has an equivalent Python workflow test
4. Each persona toolset has at least one functional test verifying tool registration
5. The confirmation two-step contract has one functional test per confirmation level
6. The `.claude/test/testing.md` manual playbook is reduced to exploratory testing only — never a regression check

### After Phase 8 (unified runner)

7. `dct-mcp-test` is on the `$PATH` after `pip install -e ".[test]"`
8. `/dct-mcp-test` works from any Claude Code session
9. CI workflow yaml uses the same `dct-mcp-test` command developers use locally

### After Phase 9 (real-DCT validation)

10. Real-DCT E2E runnable from GitHub UI `workflow_dispatch`
11. Same suite runnable locally via `dct-mcp-test --base-url ... --api-key ...`
12. Same suite runnable via `/dct-mcp-test localhost --api-key ...` from Claude Code
13. Cleanup pass deletes everything tagged with the run ID, even on test failure
14. Tool response shapes captured as syrupy snapshots; drift breaks CI

---

## 12. Out of Scope

- Performance / load testing
- Testing against multiple DCT versions in parallel
- Property-based / fuzz testing of tool inputs
- Visual regression of MCP client UIs
- Claude Desktop GUI automation (see section 7)
- Claude API as a CI test driver (see section 7)

These are reasonable future additions but not part of replacing the manual verification loop.
