# DCT MCP Server Test Suite — Demo Guide

**Branch:** `dlpx/pr/chaitali/test-suite-poc`
**Status:** PoC complete (4 days of work) — ready for approval
**Demo length:** ~10 minutes

This is the field guide for the live demo. It covers exactly what to run, what to show, what to say, and what to look for.

---

## 1. The TL;DR

| | Before | After |
|---|---|---|
| Verify a code change | Open Claude Desktop, manually drive ~70 prompts, eyeball responses, write a free-text PR report | `git push` — CI auto-runs 8 tests in 9 seconds. Pre-release: trigger Layer 4 against real DCT via 1 command. |
| Time per verification | 30+ minutes of human attention | < 10 seconds of CI time |
| Reproducibility | LLM responses vary; "looks right" is the signal | Deterministic assertions; exact failure messages |
| Merge gate | None | Required CI check on `main` |
| Live DCT required? | Yes, every time | Only for Layer 4 (advisory, optional) |

**Cost:** $0/month. No Anthropic API key needed. No Claude Desktop license needed for testing anymore.

---

## 2. What's on the branch

```
e845d53  Strategy design + interactive HTML report
2fc1cfd  Day 1 — Layer 1 (unit) + Layer 2 (integration)
2b1f18c  Day 2 — Layer 3 (functional: registration, workflow, confirmation)
8d0e85a  Day 3 — dct-mcp-test CLI + Claude Code skill + GitHub Actions
26a8c60  Day 4 — Layer 4 real-DCT smoke + on-demand workflow
```

~600 lines of test code. 11 tests total. CI suite (Layers 1–3) runs in 9.3 seconds.

---

## 3. The 10-minute demo script

### 0:00 — Set the stage (30s)

> "Today every code change goes through Claude Desktop by hand — I drive 70 prompts, eyeball responses, write a report. Doesn't scale, doesn't gate merges, can't run in CI. We built a replacement over the past 4 days. Let me walk you through it."

### 0:30 — Show the branch (30s)

```bash
git log --oneline main..HEAD
```

Five commits. Day 1 to Day 4. ~600 lines.

### 1:00 — Layer 1: Unit (60s)

> "Unit tests prove action routing inside our grouped tools. The DCTAPIClient is mocked — no HTTP, no DCT, runs in a second."

```bash
dct-mcp-test --layer unit
```

Expected: **2 tests, ~1s, green.**

Open `tests/unit/test_job_tool.py` while it runs.

> "Each tool function has actions like `search`, `get`, `delete`. We mock the HTTP client, call the function directly, assert it would have hit the right endpoint. This is what catches refactor bugs."

### 2:00 — Layer 2: Integration (90s)

> "Integration tests prove the HTTP wire behavior — URLs, auth headers, retry logic. Unit tests can't see this because they mock above HTTP."

```bash
dct-mcp-test --layer integration
```

Expected: **3 tests, ~3s, green.** (Retry test takes 3s of real sleeps — that's exponential backoff being exercised.)

Open `tests/integration/test_client_retry.py`.

> "This one — `test_client_sends_apk_prefixed_auth_header` — catches a subtle class of bug. Our DCTAPIClient prepends `apk ` to the API key. If someone refactors and accidentally drops the prefix, every auth fails. This test would catch it in 50ms."

### 3:30 — Layer 3: Functional ★ (3 min — the wow)

> "This is what directly replaces Claude Desktop. Full MCP-stdio workflows against an in-process fake DCT. Read this slowly."

```bash
dct-mcp-test --layer functional
```

Expected: **3 tests, ~5s, green.**

Open two files side by side:
- `.claude/test/testing/self_service.md` lines 12–17
- `tests/functional/workflows/test_vdb_lifecycle.py`

> "This `.md` file is what I run by hand today. Search VDBs, get the first one, start it, stop it. The Python file is the same scenario, deterministic. Every step is a real MCP call over stdio to the actual `dct-mcp-server` subprocess. The fake DCT — `dct_stub` — records every HTTP request and we assert the right endpoint got hit."

Then show:
- `tests/functional/test_toolset_registration.py` — proves the right tools register
- `tests/functional/test_confirmation_handshake.py` — proves the two-step destructive-op contract

> "When a workflow test fails, the message tells you exactly which DCT endpoint never got hit. That's a level of precision Claude Desktop can never give us."

### 5:30 — Layer 4: Real DCT (90s)

> "Layer 4 is the same shape — but pointed at a real DCT instead of the stub. I'm running against my localhost DCT right now."

```bash
export DCT_API_KEY=<your-key>
dct-mcp-test --base-url https://localhost --layer e2e
```

Expected: **3 tests (2 smoke + 1 cleanup), ~2–5s, green.**

> "These are read-only smoke tests. They prove the server boots against real DCT and the API contract still matches. When we add destructive workflows in the future, the cleanup pass uses a per-run tag to delete everything we created."

### 7:00 — The Break Demo (90s, the emotional moment)

Edit `src/dct_mcp_server/tools/dataset_endpoints_tool.py` line 2705:

```python
# Change this line:
return make_api_request('POST', '/vdbs/search', params=params, json_body=body)
# To this:
return make_api_request('POST', '/vdbs/search-BROKEN', params=params, json_body=body)
```

```bash
dct-mcp-test --layer functional
```

Expected: **test_vdb_lifecycle FAILS** with `Missing DCT calls: {('POST', '/dct/v3/vdbs/search')}`.

> "One typo. CI catches it. Today this would silently land on main, and somebody would catch it when their workflow stops working. Now the merge button stays grey."

Revert the change, re-run, all green.

### 8:30 — Three invocation paths (60s)

> "Same command works in three places."

```bash
# 1. Terminal (just did)
dct-mcp-test --layer ci

# 2. Show the GitHub Actions yaml
cat .github/workflows/test.yml
```

> "Every PR runs this. Free GitHub-hosted runners, $0/month."

```
# 3. Show the Claude Code skill
/dct-mcp-test localhost --api-key <key> --layer e2e
```

> "Same command from inside Claude Code. URL aliasing, results stream into chat, Claude can read the failing test and propose a fix."

### 9:30 — Wrap (30s)

> "PoC ready. If approved, the full rollout — translating all ~30 workflows from the manual `.md` files into deterministic tests — is roughly 3 working weeks. After that, manual Claude Desktop testing is for exploration, not regression."

---

## 4. What each layer covers

### Layer 1 — Unit (`tests/unit/`)

| Field | Value |
|---|---|
| Tests | 2 |
| Runtime | ~1 second |
| Needs DCT? | No |
| Needs network? | No |
| What it proves | Action routing logic, parameter validation, missing-param guards |
| What it catches | "I refactored the action dispatch and broke a path" |
| How it's built | `MagicMock(spec=DCTAPIClient)` with `AsyncMock` on `make_request`; set as module global; call tool function directly |
| Value | Fastest feedback. Run every save. |

### Layer 2 — Integration (`tests/integration/`)

| Field | Value |
|---|---|
| Tests | 3 |
| Runtime | ~3 seconds (real backoff sleeps) |
| Needs DCT? | No |
| Needs network? | No (respx intercepts) |
| What it proves | URL construction, auth header `apk ` prefix, 4xx vs 5xx vs connection error behavior |
| What it catches | "URL has double slashes", "auth header missing prefix", "retry logic doesn't actually retry" |
| How it's built | `respx.mock` decorator + real `DCTAPIClient` + canned `httpx.Response` objects |
| Value | Wire-level safety net. Things unit tests can't see. |

### Layer 3 — Functional ★ (`tests/functional/`)

| Field | Value |
|---|---|
| Tests | 3 (1 registration + 1 workflow + 1 confirmation) |
| Runtime | ~5 seconds |
| Needs DCT? | No (`dct_stub`) |
| Needs network? | No (loopback HTTP) |
| What it proves | Full MCP stdio works; toolsets register correctly per persona; multi-step workflows succeed end-to-end; confirmation handshake survives the wire |
| What it catches | "I edited config/toolsets/*.txt and broke a persona", "delete_vdb skips the confirmation step", "the workflow chain has a regression" |
| How it's built | `Starlette` stub on `127.0.0.1` + `uvicorn` threaded + `fastmcp.Client` with `StdioTransport` subprocess + `dct_stub.received_request(method, path)` assertions |
| Value | **This is what replaces Claude Desktop.** Highest-impact layer. |

### Layer 4 — Real DCT (`tests/e2e/`)

| Field | Value |
|---|---|
| Tests | 2 smoke + 1 cleanup |
| Runtime | ~2–5 seconds against localhost |
| Needs DCT? | Yes |
| Needs network? | Yes (real HTTP to real DCT) |
| What it proves | Server can boot against real DCT, API contract still matches expected envelope shapes |
| What it catches | "Real DCT API drifted from our spec", "real auth doesn't work despite the test key working", "real network/timeout behavior" |
| How it's built | Same subprocess pattern as Layer 3, no stub — points `DCT_BASE_URL` at the real instance |
| Value | Periodic confidence check against real DCT. NOT on the PR critical path. |

---

## 5. Three invocation paths — all hit the same CLI

```
            ┌──────────────────────────────────────────┐
            │  src/dct_mcp_server/testing/cli.py       │
            │  (the actual implementation)             │
            └──────────────┬───────────────────────────┘
                           │
       ┌───────────────────┼───────────────────────────┐
       │                   │                            │
       ▼                   ▼                            ▼
  Terminal CLI       GitHub Actions             Claude Code skill
  $ dct-mcp-test     - run: dct-mcp-test        /dct-mcp-test
  --layer ci           --layer ci                 localhost --api-key ...
```

| Path | When | Trigger |
|---|---|---|
| Terminal CLI | Local dev, ad-hoc debugging | `dct-mcp-test ...` |
| GitHub Actions (CI) | Every PR + push to main | Auto on `push`/`pull_request` |
| GitHub Actions (E2E) | On-demand, pre-release | `workflow_dispatch` from GitHub UI |
| Claude Code skill | Interactive testing from chat | `/dct-mcp-test ...` |

Change behavior once in `cli.py`. Every path follows. No drift between local and CI.

---

## 6. What this catches — by bug class

| Bug class | Caught by | Real example |
|---|---|---|
| Tool action routing wrong | Unit | `vdb_tool(action="search")` calls `/vdbs/list` instead of `/vdbs/search` |
| `build_params` drops a field | Unit | `limit=10` not forwarded to the HTTP call |
| Confirmation rule bypassed | Unit + Functional | Destructive op executes without the two-step |
| URL has double slash | Integration | `https://dct//dct/v3/vdbs` from a stray trailing `/` |
| Auth header missing `apk ` | Integration | Plain key sent, every call gets 401 |
| 5xx not retried | Integration | Transient DCT blip causes whole workflow to fail |
| 4xx incorrectly retried | Integration | 401s burning DCT rate limit |
| Edited `.txt` broke a persona | Functional 3a | Removing a `# TOOL` header silently drops a tool |
| Multi-step workflow regression | Functional 3b | `start_vdb` no longer reaches DCT |
| Two-step confirmation broken | Functional 3c | `delete_vdb` skips confirmation |
| Server doesn't boot for a persona | Functional 3a | Bad config in `self_service.txt` |
| Real DCT API contract drift | Real DCT | Delphix changes the response envelope |
| Real auth doesn't work | Real DCT | API key format changed |
| AI can't navigate tool schema | (Out of scope — future Layer 5 with LM Studio) | |

---

## 7. Production bug Layer 3 already caught

While building Day 2, the workflow test surfaced a real issue: `async_to_sync` in the tool modules calls `asyncio.run()` in a per-call thread, which closes the event loop between MCP calls. The `httpx.AsyncClient` cached on the dead loop fails on the next call. The retry loop recovers, but each call ends up on the wire twice.

> This is the kind of latent fragility manual Claude Desktop testing would never have surfaced. The workflow test sees it immediately via duplicate request recordings in `dct_stub`. Worth a follow-up PR after the demo.

---

## 8. Cheat sheet (every command in one place)

```bash
# === Setup (once) ===
pip install -e ".[test]"

# === Verify what's on the branch ===
git log --oneline main..HEAD       # 5 commits since strategy doc

# === Fast feedback (while coding) ===
dct-mcp-test --layer unit          # ~1s, 2 tests
dct-mcp-test --layer integration   # ~3s, 3 tests
dct-mcp-test --layer functional    # ~5s, 3 tests

# === CI gate (Layers 1-3, no DCT needed) ===
dct-mcp-test --layer ci            # ~9s, 8 tests — what GitHub runs

# === Real DCT (Layer 4) ===
export DCT_API_KEY=<your-apk-key>
dct-mcp-test --base-url https://localhost --layer e2e

# === Via Claude Code skill ===
/dct-mcp-test https://localhost --api-key <key> --layer e2e

# === The break demo ===
# 1. Edit src/dct_mcp_server/tools/dataset_endpoints_tool.py line 2705:
#    change '/vdbs/search' to '/vdbs/search-BROKEN'
# 2. Run:
dct-mcp-test --layer functional    # FAILS — clear error message
# 3. Revert, re-run — green
```

---

## 9. What's next (if approved)

The PoC is the first 4 days of a roughly 3-week full rollout:

| Phase | Duration | Deliverable |
|---|---|---|
| ✓ 1–4 (done) | 4 days | PoC: one test per layer + CLI + skill + 2 workflows |
| 5 | 5 days | Translate all ~30 workflows from `.claude/test/testing/*.md` |
| 6 | 3 days | Backfill unit tests for each `*_endpoints_tool.py` |
| 7 | 1 day | Add snapshot assertions on tool response shapes |
| 8 | done in PoC | CLI + skill |
| 9 | 2 days | Wire `e2e-real-dct.yml` to a network-reachable DCT |
| 10 (optional) | later | LM Studio local AI-usability check |

After phase 5, manual Claude Desktop testing is reduced to exploratory use only.

---

## 10. Open questions for the team

- **Is the cloned DCT reachable from GitHub-hosted runners?** Determines whether Layer 4 can run in CI.
- **Who owns test data hygiene on the cloned DCT?** Cleanup is bulletproof, but someone needs to monitor for accumulation.
- **Do we want nightly Layer 4 cron, or workflow_dispatch only?** Nightly catches drift early; on-demand is cheaper.
- **Is the production async_to_sync event-loop bug a follow-up PR?** Caught by Layer 3 — easy fix, separate change.
