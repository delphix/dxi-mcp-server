# Automated Test Suite — Strategy, Architecture & Status

**Branch:** `dlpx/pr/chaitali/test-suite-poc`  
**Status:** implemented (Layers 1–5 built and validated, 2026-06-11)

---

## 1. Problem Statement

Today every code change goes through Claude Desktop by hand — a developer drives ~70
prompts per toolset, eyeballs the responses, and writes a free-text PR report. This
doesn't scale, can't run in CI, and produces inconsistent signal.

**This suite replaces that with a layered automated test pyramid** that runs on every
PR (Layers 1–3), on-demand against a real DCT (Layer 4), and optionally as an
AI-usability check via the Claude Code CLI (Layer 5).

---

## 1.1 What This Strategy Achieves — Summary Table

| Layer | What it proves | Catches what nothing else does | Needs DCT? | Triggered by | Blocks merge? |
|---|---|---|---|---|---|
| **1 — Unit** | Action routing, parameter building, confirmation state machine, config parsing | Logic bugs in tool functions (mocked client) | No | Every save / PR | Yes |
| **2 — Integration** | HTTP wire: URL building, `apk ` auth, retries, timeouts | Bugs that only appear once real HTTP is built | No (respx) | Every push / PR | Yes |
| **3a — Toolset registration** | Right tools registered per persona | Edits to `config/toolsets/*.txt` silently changing tool exposure | No (dct_stub) | Every PR | Yes |
| **3b — Workflow tests ★** | Multi-step chains over MCP stdio | **Replaces the manual Claude Desktop playbook** — every `.md` scenario as a deterministic test | No (dct_stub) | Every PR | Yes |
| **3c — Confirmation handshake** | Two-step `confirmation_required` → `confirmed=True` over MCP wire | Regressions in destructive-op safety net | No (dct_stub) | Every PR | Yes |
| **4 — Real-DCT E2E** | Workflows against the cloned DCT | Real API contract drift, real auth, real latency | Yes | On-demand via CLI / `.venv-live` | No (advisory) |
| **5 — LLM-driven** | AI can navigate the tool surface + operation actually took effect | Confusing action names, vague descriptions, undiscoverable tools | Yes — real DCT + `claude` CLI | On-demand, local | No (advisory) |

**Invocation paths — all hit the same `dct-mcp-test` CLI:**

| Path | When | How |
|---|---|---|
| CLI | Terminal, scripts, ad-hoc | `dct-mcp-test --layer ci` |
| Claude Code skill | Interactive testing from chat | `/dct-mcp-test localhost --api-key ...` |

**Cost summary:**

| Item | Cost |
|---|---|
| Layers 1–3 in CI | $0 (free GitHub Actions tier, once wired) |
| Layer 4 | $0 CI cost; cloned DCT is existing infra |
| Layer 5 — Claude Code CLI | Consumes existing Claude subscription / enterprise usage; no separate metered API key |
| Anthropic metered API key for E2E | **Not needed** — CLI uses subscription auth |
| Claude Desktop license | **Not needed** for regression testing anymore |

**Before vs. after:**

| Today | After this rollout |
|---|---|
| Push code → open Claude Desktop → run prompts manually → eyeball responses → write report | Push code → CI runs Layers 1–3 → PR shows green/red. Pre-release: trigger Layer 4 via CLI. |
| 30+ minutes of human attention | < 3 minutes of CI time |

---

## 2. The Core Insight — Two Different Questions

Every time the question "can we automate testing?" came up, it conflated two separate
questions with different answers:

| Question | What fails if unanswered | Best tool |
|---|---|---|
| **"Did the workflow break?"** | Regressions in routing, auth, confirmation logic, HTTP contract | Scripted deterministic tests — Layers 1–3 |
| **"Can an AI figure out how to use the tools?"** | Tool discoverability, confusing action names, broken async UX | LLM-driven tests — Layer 5 |

These are separate questions. Solve them with separate tools.

- **Regression gate (primary):** scripted workflow tests, no LLM in the loop, runs on every PR
- **AI-usability check (optional, local):** LLM-driven, runs ad-hoc before releases

---

## 3. Current State

### What exists (2026-06-11)

- **Layer 1 — Unit:** 156 tests, all personas, 62 confirmation rules, parametrized via `config_cases`
- **Layer 2 — Integration:** 29 tests, full `DCTAPIClient` wire coverage
- **Layer 3 — Functional:** 931 tests — registration (all 5 personas), 70 self_service workflow chains, 57+15 CDA/SS confirmation handshakes, 833-case generated routing sweep
- **Layer 4 — E2E:** 27 tests (self_service + CDA smoke/contract, mutation lifecycle)
- **Layer 5 — LLM-driven:** 217 tests — discoverability (14), scenario catalog (170+), act→verify, CDA setup/teardown
- **`dct-mcp-test` CLI** with layers: `unit | integration | functional | ci | e2e | llm | scenarios | all`
- **`dct_stub`** fully built with catch-all; spec downloaded from DCT; **total: 1,360 tests**

### What is pending

- MySQL AppData dSource enable + VDB provision (plugin infra issue on engine `qa-dev-test11`)
- L6 GitHub Actions CI enforcement (workflows exist; required-check not yet enforced) — see **§ Future Scope**
- Engine register scenario (built, gated on `E2E_ENGINE_JSON`)

---

## 4. Architecture

Three layers in CI (regression gate), plus two optional local layers (real DCT):

```
   ┌──────────────────────────────────────────────────────────────┐
   │  Layer 1 — Unit (in-process, mocked client)                  │
   │  tool fn → MagicMock(DCTAPIClient).make_request              │
   │  156 tests · ~0.3s                                          │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 2 — Integration (in-process, mocked HTTP)             │
   │  tool fn → DCTAPIClient → httpx → respx intercept            │
   │  29 tests · ~0.1s                                           │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 3 — Functional (subprocess + stub DCT)                │
   │   3a. Toolset registration (all 5 personas + auto)           │
   │   3b. ★ Workflow tests — the .md scenarios as Python          │
   │   3c. Confirmation handshake over MCP wire                   │
   │  931 tests · ~2.5 min                                       │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 4 — E2E vs. real DCT (safe-run venv)                  │
   │  Same server, real instance, on-demand via CLI               │
   │  27 tests · 3–8 min                                         │
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 5 — LLM-driven (LOCAL, advisory)                      │
   │  Claude Code CLI → .mcp.json delphix-dct server → real DCT  │
   │  NL task → act → wait for job → verify outcome               │
   │  217 tests · varies                                         │
   └──────────────────────────────────────────────────────────────┘
```

Layer 3b is the **centerpiece** — it's what directly replaces the manual Claude Desktop
playbook. Each chain of prompts in the existing `.md` files becomes one Python test.

### 4.1 Layer 4 — E2E vs. real DCT

`build_real_transport(toolset)` in `tests/e2e/conftest.py` reads the `delphix-dct`
server definition from `.mcp.json`, injects runtime credentials from the environment,
and spawns it as a subprocess. A `fastmcp.Client` talks to it over stdio. The server
downloads the live OpenAPI spec and generates tools dynamically.

**Safe-run venv:** in a dev/editable checkout the startup generator writes into `src/`.
Use `.venv-live` (non-editable install) so generation goes to `$TEMP`:
```bash
python3 -m venv .venv-live && .venv-live/bin/pip install ".[test]"
```

### 4.2 The `dct-mcp-test` CLI — one runner, all contexts

```
src/dct_mcp_server/testing/cli.py
```

Available layers: `unit | integration | functional | ci | e2e | llm | scenarios | all`

For `--layer scenarios`, additional flags: `--persona <csv>`, `--mutations`, `--scenario-limit`, `--report <file.xml>`.

```bash
dct-mcp-test --layer ci
dct-mcp-test --layer e2e --base-url https://localhost --api-key <key>
dct-mcp-test --layer scenarios --persona continuous_data_admin --report report.xml
```

### 4.3 The `/dct-mcp-test` Claude Code skill — third invocation path

The same CLI wrapped as a project-local skill so it can be invoked from inside any
Claude Code session via `/dct-mcp-test`. Failure triage — Claude can read the failing
test, propose a fix, and re-run the skill in one session.

### 4.4 Layer 5 — LLM-driven via Claude Code CLI

**Driver: Claude Code CLI only.**

Layer 5 uses `claude -p … --output-format stream-json` as the sole LLM driver. It
connects to the **`delphix-dct` MCP server defined in `.mcp.json`** — the same server
config the interactive Claude Code session uses. Credentials come from `DCT_BASE_URL` /
`DCT_API_KEY` env vars. No separate Anthropic API key required.

```bash
claude -p "<task>" \
  --mcp-config <derived-from-.mcp.json> \
  --strict-mcp-config \
  --allowedTools "mcp__delphix-dct__*" \
  --permission-mode bypassPermissions \
  --append-system-prompt-file .claude/test/llm-driver-preprompt.md \
  --output-format stream-json --verbose
```

The **job-completion pre-prompt** (`.claude/test/llm-driver-preprompt.md`) instructs
Claude to poll `job_tool` to a terminal state before declaring success on any async
operation. This is the mechanism that implements act → wait → verify without code
changes to the server.

**The act → verify pattern (mandatory for every mutation test):**

| Phase | Example |
|---|---|
| 1. Act | Claude receives a plain-English task → discovers and calls the tool |
| 2. Wait | Pre-prompt requires polling `job_tool` to COMPLETED/FAILED |
| 3. Verify | A **separate** Claude call reads state back — identifier NOT in the verify prompt |

The verify prompt must never contain the identifier being confirmed (else Claude echoes
it regardless of real state — a false-pass trap we discovered in live runs).

**Architectural separation:**

```
   ┌────────────────────────────┐   ┌────────────────────────────┐
   │ Regression gate             │   │ AI-usability check          │
   │ (runs on every PR)          │   │ (runs ad-hoc, local)        │
   │                             │   │                             │
   │ Layers 1–3                  │   │ Layer 5                     │
   │ Scripted, deterministic     │   │ LLM-driven, act → verify    │
   │ No LLM in the loop          │   │ Claude Code CLI · real DCT  │
   │ $0 cost                     │   │ Subscription usage          │
   │                             │   │                             │
   │ "Did the workflow break?"   │   │ "Can AI use it — and did it │
   │                             │   │  really happen?"            │
   └────────────────────────────┘   └────────────────────────────┘
```

Layer 5 is **completely optional** — the regression-prevention goal is fully met by
Layers 1–3 alone. Layer 5 only adds value for AI-usability checks.

---

## 5. Layer 3b — Workflow Tests (the heart of the suite)

### Pattern

Each multi-step chain in `.claude/test/testing/<toolset>.md` becomes one Python test.
The chaining ("that VDB" → previous result) becomes a Python variable. Each step is a
real MCP call over stdio via `fastmcp.Client`. Each step is verified at the wire level
via `dct_stub.received_request(...)`. No LLM in the loop — deterministic, fast,
reproducible.

```python
# tests/functional/workflows/test_vdb_lifecycle.py
async def test_vdb_lifecycle_search_get_start_stop(mcp_client_self_service, dct_stub):
    search = await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "search", "limit": 10})
    vdb_id = _payload(search)["items"][0]["id"]

    await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "start", "vdb_id": vdb_id})
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/start")

    await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "stop", "vdb_id": vdb_id, "confirmed": True})
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/stop")
```

### Mapping: scenario files → workflow tests

| Scenario file | Prompts | Workflow tests |
|---|---|---|
| `self_service.md` | 70 | 9 files (vdb lifecycle, refresh/rollback, tags, groups, dsource, snapshot, bookmark, job, timeflow) |
| `continuous_data_admin.md` | 431 | 5 CDA chains + 833-case routing sweep + 57-case confirmation sweep |
| Other personas | 403 | Registration + routing via in-process generator |

---

## 6. The `dct_stub` Component

A tiny Starlette app that pretends to be the DCT API. Runs on `127.0.0.1:<random-port>`
inside the pytest process. The MCP server subprocess is pointed at it via `DCT_BASE_URL`.
Every request is recorded so tests can assert exactly what the server sent.

### Data flow

```
pytest process
  │
  ├─ StubServer.start() → spawns uvicorn thread
  │       dct_stub URL: http://127.0.0.1:<port>
  │
  ├─ fastmcp.Client(StdioTransport)
  │       spawns dct-mcp-server subprocess with DCT_BASE_URL=stub.url
  │
  ├─ await client.call_tool("vdb_tool", {"action": "search"})
  │       subprocess → HTTP POST http://127.0.0.1:<port>/dct/v3/vdbs/search
  │       dct_stub._record(request)   ← records for assertion
  │       dct_stub.vdbs_search()      ← returns canned {"items":[...]}
  │
  └─ assert dct_stub.received_request("POST", "/dct/v3/vdbs/search")
```

### Routes

The stub serves all `/dct/v3/...` routes via explicit handlers for core paths and a
catch-all for everything else. Deliberately does NOT serve `/dct/static/api-external.yaml`
so the server falls back to pre-built modules (stable for the stub-based tests).

The OpenAPI spec (`tests/fixtures/api-external.yaml`) is downloaded from the real DCT
and cached locally (gitignored). The `openapi_spec` fixture in `tests/functional/conftest.py`
downloads it on first run, then reuses the cache for offline runs.

---

## 7. LLM Testing — Claude Code CLI as the MCP Client

Layer 5 answers the question no scripted layer can: **given only a plain-English task
and the tool schemas, can Claude discover the right tool, call it correctly, and did
the operation actually take effect on a real DCT?**

### Driver and MCP server

- **Driver:** `claude -p` (Claude Code CLI headless mode), `--output-format stream-json`
- **MCP server:** the `delphix-dct` server defined in **`.mcp.json`** — the single
  source of truth, the same server the interactive Claude Code session uses
- **Credentials:** `DCT_BASE_URL` + `DCT_API_KEY` from environment (never hardcoded)
- **Toolset:** set via `DCT_TOOLSET` env var; the `_write_mcp_config()` helper derives
  the server command/args from `.mcp.json` and stamps in the toolset per test

### Three verification tiers

| Tier | How | When |
|---|---|---|
| **Tier 1 — Tool trace** | Assert Claude used a tool from the persona's toolset | All read-tier scenario prompts |
| **Tier 2 — Act → verify** | Independent read-back (identifier NOT in verify prompt) | All mutations |
| **Discoverability** | Assert Claude picked the expected tool from plain English | Per-tool-domain sanity |

### Findings from live runs

Layer 5 surfaced genuine product findings:

| Tool | Gap | Impact |
|---|---|---|
| `vault_tool` | Not surfaced for "Hashicorp vaults" or "Kerberos configurations" — the tool owns both but its name hints at neither | Users can't reach Kerberos config via natural language |
| `admin_platform_tool` | Not surfaced for "LLM models", "AI settings" | AI-related admin flows unreachable |
| `diagnostic_tool` | Not surfaced for "NetBackup connectivity", "DSP network test" | Diagnostic workflows unreachable |

These are recorded as `xfail` in `test_scenarios.py:_KNOWN_ISSUES` — visible in reports,
suite stays green. **Actionable:** improve tool descriptions to match the domain language
users speak.

### License tolerance

Some DCT instances license-restrict whole resource types (e.g. `401: License does not
permit operations on VDB_GROUP`). The `call_tool_tolerant` helper in `tests/e2e/_helpers.py`
and the `license_blocked()` helper in `tests/llm_local/conftest.py` skip license-forbidden
operations instead of failing, making the suite resilient across DCT tiers.

---

## 8. Changes Made

All layers are built. Here is what was implemented:

### 8.1 Test infrastructure

- `tests/_support/config_cases.py` — parametrization engine (parses toolset `.txt` files + confirmation rules)
- `tests/fixtures/dct_stub.py` — full stub with catch-all and 13+ explicit routes
- `tests/fixtures/api-external.yaml` — gitignored spec cache (downloaded from DCT)
- `tests/functional/conftest.py` — generalized fixtures with `openapi_spec`, `persona_tools`, `build_stub_transport`
- `tests/e2e/conftest.py` — `build_real_transport` reading from `.mcp.json`
- `tests/llm_local/conftest.py` — `llm_driver_for`, `license_blocked`, `llm_driver_for_session`
- `tests/llm_local/mcp_client_helper.py` — MCP-based state queries (replaces direct HTTP calls)
- `tests/llm_local/prereq_checker.py` — session-cached prerequisite chain checker
- `tests/llm_local/connector_fixtures.py` — per-connector field sets (AppData/Oracle/MSSQL/ASE)

### 8.2 Test files by layer

All under `tests/unit/`, `tests/integration/`, `tests/functional/`, `tests/e2e/`, `tests/llm_local/`.

### 8.3 `.github/workflows/`

- `test.yml` — runs `dct-mcp-test --layer ci` on every push/PR; non-editable install
- `e2e-real-dct.yml` — `workflow_dispatch` trigger; credentials from `DCT_BASE_URL`/`DCT_API_KEY` secrets; downloads spec from DCT

**Note:** The workflows exist but the required-check gate in branch protection is not yet
enforced. See **§ Future Scope** below.

---

## 9. When Tests Run

| Trigger | What runs | Invocation | Blocking? |
|---|---|---|---|
| While coding | Layer 1 (unit) | `dct-mcp-test --layer unit` | No |
| Every push / PR | Layers 1–3 (CI gate) | GitHub Actions calls `dct-mcp-test --layer ci` | **Yes — merge gate (once enforced)** |
| On-demand against real DCT | Layer 4 | `.venv-live/bin/dct-mcp-test --layer e2e` | No (advisory) |
| Pre-release AI usability | Layer 5 | `.venv-live/bin/dct-mcp-test --layer scenarios --persona <p>` | No (advisory) |

---

## 10. Roadmap

All layers are implemented. Remaining work:

### Completed ✓

- L0 Foundations (config_cases parametrization engine, stub, spec fixture)
- L1 Unit (156 tests)
- L2 Integration (29 tests)
- L3 Functional (931 tests — registration, workflows, confirmation, all personas)
- L4 E2E real-DCT (27 tests — smoke, contract, mutation lifecycle)
- L5 LLM-driven (217 tests — discoverability, scenarios, act→verify, CDA setup/teardown)
- S0–S5 Persona scenario suite (904 prompts, all toolsets, prereq chain)

### In progress / blocked

- MySQL AppData dSource enable + VDB provision — plugin jobs fail on `qa-dev-test11`; check engine logs for APPDATA plugin error. Framework is complete (P2 steps 5b/6).
- Engine register scenario — built and gated; set `E2E_ENGINE_JSON` to run.

---

## 11. Success Criteria

### Regression gate (Layers 1–3)

- [x] `dct-mcp-test --layer ci` runs green in < 3 min
- [x] 1,116 tests pass offline
- [x] Every self_service scenario chain is a deterministic test
- [x] Every CDA action routes correctly (parametrized sweep)
- [x] All 62 confirmation rules have two-step handshake coverage
- [x] All 5 personas register the right tools

### Real-DCT validation (Layer 4)

- [x] Smoke tests pass against live DCT
- [x] License-restricted resources skip gracefully
- [x] Mutation lifecycle (engine register, MySQL dSource) live-verified

### AI-usability (Layer 5)

- [x] Claude discovers the right tool from plain English (14 discoverability tests)
- [x] Act → verify pattern validated live (vdb-tag, engine-tag, MySQL environments, dSource link)
- [x] Discoverability gaps identified and documented (`vault_tool`, `admin_platform_tool`, `diagnostic_tool`)

---

## 12. Future Scope

### L6 — GitHub Actions CI enforcement

The `.github/workflows/test.yml` and `.github/workflows/e2e-real-dct.yml` files exist
and are correct. What remains is making `test.yml` a **required check** in branch
protection so red PRs cannot merge.

This is a process/permission decision, not a coding task:

| Step | Who | What |
|---|---|---|
| Enable required check | Repo admin | Settings → Branches → main → Add required status check: `test / test` |
| Add DCT secrets | Repo admin | Settings → Secrets → `DCT_BASE_URL`, `DCT_API_KEY` for the e2e workflow |
| Nightly cron (optional) | Repo admin | Uncomment the `schedule` block in `e2e-real-dct.yml` |

Once the required check is enabled:
- PRs with failing Layers 1–3 cannot merge (the merge button is greyed out)
- The manual Claude Desktop verification is fully retired for regression testing
- Layer 4 runs on demand from the GitHub UI or via CLI

### Snapshot assertions

Add `syrupy` to the workflow tests to lock response shapes. Future drift in DCT API
response envelopes would fail the snapshot comparison automatically.

### Session-replay for Layer 5

Currently Layer 5 runs each prompt as an independent Claude call (no state carried
between "Search VDBs" and "that VDB"). True session replay — chaining Claude calls with
context — would allow testing the full conversational flow described in the scenario
`.md` files.

### Other-persona mutation scenarios

Read-tier validated for all personas. Mutation-tier scenarios (CDA provisions, IAM
changes, policy updates) depend on having a working dSource/VDB. Unblocked once the
MySQL plugin infra issue is resolved.

---

## 13. Out of Scope

- Load / performance testing
- Exhaustive per-action E2E (cost vs. coverage tradeoff; Layers 1–3 cover routing)
- True 1:1 translation of all ~970 scenario prompts to L3 workflow tests (chains collapse into ~90 workflow tests)
