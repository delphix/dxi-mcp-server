# DCT MCP Server — Test Suite Implementation Plan

> **Purpose:** the canonical, resumable plan for building the full automated test suite.
> Built **layer by layer**, targeting **full coverage achieved efficiently** (data-driven /
> parametrized from the config files — not hundreds of hand-written near-duplicates).
> If a session is interrupted, **start by reading the STATUS TRACKER below**, then continue
> from the first unchecked item.

---

## STATUS TRACKER  ← read this first when resuming

**Last updated:** 2026-06-03
**Current phase:** ALL TEST CODE BUILT (L0–L5), now incl. **continuous_data_admin L4/L5** (admin persona
is the priority test target). CI layer (L1–L3) = **1053 passed ~29s**; whole suite collects 1109.
L4 (self_service 11 + CDA smoke/engine) + L5 (self_service 8 + CDA discoverability) skip w/o creds —
**LIVE DCT RUN PENDING**. ⚠ See LIVE-RUN SAFETY below before running. Remaining: live verify, **L6 (CI)**.

**⚠ LIVE-RUN SAFETY (must handle before any live run):** this is an EDITABLE install, so when the
server boots against a REAL DCT it regenerates tool files INTO `src/dct_mcp_server/tools/` (deletes
existing `*_tool.py` first). A live run will overwrite the refactored dataset/job files and recreate
the deleted persona files. Safe options: (A) commit the working tree first, run live, then
`git checkout -- src/ && git clean -fd src/dct_mcp_server/tools/` to restore; or (B) run from a
NON-editable install (`pip install .` into a throwaway venv → generation goes to $TEMP, src untouched).
Spec fixture: `tests/fixtures/api-external.yaml` (DCT API v3.29.0).
**Branch:** `dlpx/pr/chaitali/test-suite-poc`
**Spec-fixture approach (resolved for registration):** non-self_service personas are tested via the
in-memory generator `tool_factory.generate_tools_for_toolset()` seeded from the fixture (offline, NO
disk writes). NOTE: the dev-mode FILE generator (driver.py) writes into `src/dct_mcp_server/tools/`
and deletes existing `*_tool.py` — so never let a fixed-mode subprocess run generation in dev. 3b
workflows for non-self_service will reuse the in-process/seeded approach (or auto-mode), TBD in 3b.

| Phase | Layer | State |
|---|---|---|
| L0 | Foundations (cleanup + scaffolding + param helpers) | ☑ done |
| L1 | Layer 1 — Unit | ☑ done (156 tests, 0 xfail/skip) |
| L2 | Layer 2 — Integration | ☑ done (29 tests, ~0.09s) |
| L3 | Layer 3 — Functional (3a reg, 3b workflows, 3c confirm) | ☑ done — all personas (CI layer 1053 passed) |
| L4 | Layer 4 — E2E (real DCT) | ◑ code-complete (11 tests); live run pending |
| L5 | Layer 5 — LLM-driven (Claude Code CLI) | ◑ code-complete (8 tests); live run pending |
| L6 | CI & enforcement (CI runs tests; required-check optional/deferred) | ☐ not started — **LAST**, after all test layers |

> **Focus for now: building tests (L0–L5).** All CI / GitHub-Actions wiring and any
> required merge-gate is deferred to **L6** and done last.

Update the checkbox (☐ → ◑ in-progress → ☑ done) and the per-phase "Exit criteria"
checklist as work lands. Keep "Current phase" accurate.

---

## CONTEXT SNAPSHOT (so a fresh session is grounded)

**Decisions already locked:**
- The uncommitted tool refactor is **KEPT.** Canonical surface = async per-resource tools:
  `vdb_tool, vdb_group_tool, dsource_tool, snapshot_tool, bookmark_tool, timeflow_tool, job_tool`
  (replaced the old `data_tool`/`snapshot_bookmark_tool`/`data_connection_tool`).
- Single-VDB param is named **`vdb_id`** in the function signatures (NOT `vdbId`).
- Tools are **async**; unit tests must `await` them. `@log_tool_execution` handles async.
- **Demo tests are separate and must not be touched:** `tests/demo/` under the `demo` marker,
  run via `dct-mcp-test --layer demo`. They stay green independently.

**Where things live:**
- Shared fixtures: `tests/conftest.py` (`mock_dct_client`, autouse `_set_test_env`).
- Shared stub: `tests/fixtures/dct_stub.py` (`DctStub`, `StubServer`) — ~24 routes today.
- Runner CLI: `src/dct_mcp_server/testing/cli.py` (`_LAYER_PATHS`, `_LAYER_MARKERS`,
  `_LAYERS_NEEDING_DCT`). Markers registered in `pyproject.toml`.
- The full suite is built FRESH in `tests/unit`, `tests/integration`, `tests/functional`,
  `tests/e2e`, `tests/llm_local` (currently empty / removed — L0 recreates them).
- Config that drives coverage: `src/dct_mcp_server/config/toolsets/*.txt`,
  `src/dct_mcp_server/config/mappings/manual_confirmation.txt`.

**Surface to cover (source of the coverage targets):**
| Toolset | Tools | Action mappings | Scenario prompts |
|---|---|---|---|
| self_service | 7 | 70 | 70 |
| self_service_provision | 10 | 66 | 139 |
| continuous_data_admin | 22 | 434 | 431 |
| platform_admin | 13 | 197 | 198 |
| reporting_insights | 13 | 79 | 79 |
| auto (meta) | 6 meta-tools | — | 57 |

Plus **62 confirmation rules** in `manual_confirmation.txt`.

---

## PRINCIPLES — "full coverage, efficiently"

1. **Data-driven = full coverage, low code.** Every action / confirmation rule / toolset is
   covered, but by **parametrizing over the config files**, not by hand-writing one function
   each. One parametrized test that loads all 70 actions from `self_service.txt` and asserts
   routing = 70 cases, ~1 function to maintain.
2. **Test the pattern + the mechanism, then let parametrization fan it out.** Because tools are
   generated from the toolset `.txt` files, routing is homogeneous — prove the dispatch pattern
   and the generator once, then sweep all actions as data.
3. **Layer by layer.** Finish and green a layer (across all personas) before starting the next.
   Each layer is a milestone.
4. **Exhaustive where risk is high; representative where it's homogeneous.** ALL confirmation
   rules and ALL destructive ops get covered. Routing/param logic is swept by data but asserted
   structurally, not bespoke per action.
5. **Workflows (3b) are the irreducible hand-written bulk** — each scenario chain becomes one
   test. This is where most human effort goes; everything else is largely generated.
6. **Reuse, don't duplicate.** All layers share `tests/conftest.py` + `tests/fixtures/`.
7. **Demo is frozen.** Never edit `tests/demo/`.

---

## LAYER-BY-LAYER PLAN

### Phase L0 — Foundations  (~1 day)  ✓ DONE (2026-06-02)

**Goal:** unblock every later layer; set up the data-driven machinery.

- ~~Clean `loader.py:TOOL_TO_MODULE`~~ → **NOT NEEDED (investigated).** Those entries are NOT
  stale: the OpenAPI generator (`driver.py:_get_module_for_path`) writes modules named exactly
  `dataset_endpoints_tool`, `environment_endpoints_tool`, `compliance_endpoints_tool`,
  `admin_endpoints_tool`, etc. at runtime, and `TOOL_TO_MODULE` correctly points at those
  generated names. Removing entries would BREAK dynamic loading for other personas. Added a
  clarifying comment to `loader.py` instead. (Deleted pre-built files are only the fallback.)
- ☑ Recreated suite dirs with `__init__.py`: `tests/{unit,integration,functional,
  functional/workflows,e2e,e2e/cleanup,llm_local}/`.
- ☑ Added generalized (toolset-parametrizable) conftests: `tests/functional/conftest.py`
  (`dct_stub`, `build_stub_transport(stub, toolset)`, `mcp_client_self_service`) and
  `tests/e2e/conftest.py` (`build_real_transport(toolset)`, `real_mcp_client`). Unit/integration
  reuse the root `tests/conftest.py`; `tests/llm_local/conftest.py` is added in L5.
- ☑ Added **`tests/_support/config_cases.py`** — parses the toolset `.txt` files (with
  `@inherit`) and `manual_confirmation.txt` into pytest params. API: `toolset_names()`,
  `tools_for(ts)`, `action_cases(ts=None)`, `confirmation_rules()`, `action_id`/`rule_id`.
  Verified: 5 toolsets, 902 action cases (all personas), 62 confirmation rules, inheritance works.

**Exit criteria:** ☑ loader consistent (no change needed; comment added) · ☑ dirs+conftests exist ·
☑ `config_cases` returns all actions+rules · ☑ `pytest --collect-only` clean · ☑ demo still green.

---

### Phase L1 — Layer 1: Unit  ✓ DONE (2026-06-02)  → 156 tests across 6 files, runtime ~0.3s

**Delivered:** `tests/unit/test_action_routing.py` (70 self_service action cases, all route to correct
method+endpoint, 0 xfail — config↔impl fully agree), `test_confirmation.py` (62 rules + 2 negatives),
`test_param_building.py`, `test_loader.py` (loader vs config_cases oracle + inheritance),
`test_config.py` (env defaults/coercion/validation), `test_tool_factory.py` (offline toolset→grouped
mapping). No `src/` changes; demo still green. Scope note: routing is exhaustive for the pre-built
self_service surface; other-persona routing is covered structurally via the generator/mapping test and
will be exercised through L3 functional + the generator. Original target below for reference:

> target ~12–15 functions, ~250 cases, runtime ~10s

**Coverage target (full):** every action across all toolsets is routed to the correct
method+endpoint; every confirmation rule's gating is exercised; param building, missing-param
guards, None-stripping, path-substitution; `loader.py` (parse, inheritance, mapping) and
`config.py` (env validation); the dynamic generator (`tool_factory`) once.

**Efficient approach:**
- `test_action_routing.py` — **parametrized over `config_cases`**: for each `(tool, method,
  path, action)`, set the module `client` to `mock_dct_client`, `await tool(action=…, <required
  ids>)`, assert `make_request` got the right method+endpoint. Sweeps all actions in ~1 function.
- `test_confirmation.py` — **parametrized over the 62 rules**: assert un-confirmed call returns
  `confirmation_required` at the right level; confirmed call proceeds. Plus negative cases.
- `test_param_building.py` — `build_params` None/empty stripping, path-param substitution,
  `_SafeDict` behavior. ~10 cases.
- `test_loader.py` / `test_config.py` — toolset parse + `@inherit` + `TOOL_TO_MODULE`; env var
  validation + defaults. ~25 cases.
- `test_tool_factory.py` — generator produces expected grouped tool names/actions from a toolset
  file. ~5–8 cases.

**Exit criteria:** ☐ all actions routed · ☐ all 62 rules covered · ☐ loader/config/generator ·
☐ `dct-mcp-test --layer unit` green.

---

### Phase L2 — Layer 2: Integration  ✓ DONE (2026-06-02)  → 29 tests, ~0.09s

**Delivered:** `tests/integration/test_client_request.py` (15 — URL/`/dct/v3` building, `apk ` auth +
default headers, JSON body & query-param passthrough, methods, json-vs-non-json parsing) and
`test_client_retry.py` (14 — 5xx retry, all-5xx→DCTClientError after max_retries, 4xx fail-fast,
connection-error retry, error-message content, backoff counts). `tests/integration/conftest.py` adds a
`no_backoff` autouse fixture (patches the client's `asyncio.sleep`) so retries are instant + assertable,
plus a `client` fixture. No `src/` changes; demo green. Original estimate below:

> ~25–35 cases (fixed, doesn't scale per-action)

**Coverage target (full):** the `DCTAPIClient` wire behaviors — these are per-CLIENT, not
per-action, so the count is small and fixed.

**Approach (respx):**
- URL construction incl. `/dct` prefix and no double slashes.
- `apk ` auth-header prefix (the classic silent-break bug).
- Retry/backoff on 5xx up to `DCT_MAX_RETRIES`; no-retry on 4xx; connection-error handling →
  `DCTClientError`.
- Timeout behavior; cursor pagination; JSON body passthrough.

**Exit criteria:** ☐ auth/url/retry/timeout/error-mapping covered · ☐ `--layer integration` green.

---

### Phase L3 — Layer 3: Functional  (~9–13 days)  → the bulk (tests only; CI moved to L6)

Subprocess MCP server over stdio + `dct_stub`. Three parts:

**3a Registration (~6–8 cases, parametrized):** for each toolset (+auto), boot the server and
assert the expected tool set registers. Parametrize over toolsets. Include `TOOL_TO_MODULE`
correctness and auto-mode enable/disable.

**3b Workflows ★ (the irreducible bulk, ~60–90 tests):** translate each scenario chain in
`.claude/test/testing/<toolset>.md` into one deterministic Python test (search→get→act chains,
"that VDB" → Python variable, wire-level `dct_stub.received_request` assertions). Requires
**expanding `dct_stub` from ~24 → ~120 routes** incrementally as workflows demand. Start with
self_service (~12–15), then provision, then the admin personas (continuous_data_admin is largest).

**3c Confirmation handshake over the wire (~15–20, parametrized over destructive ops):** first
call → `confirmation_required` + no DCT request; second call `confirmed=True` → request issued.

> CI wiring (running these in GitHub Actions) and any required-check / branch-protection gate
> are intentionally deferred to **Phase L6** — we build tests first. End of L3 = full functional
> coverage, so the suite *can* replace the manual playbook in practice (enforcement comes in L6).

**Exit criteria:** ☑ all personas register (3a: 7 tests — self_service over stdio + auto meta-tools +
all 5 personas generate exactly their config tools) · ☑ all self_service scenario chains translated
(3b: 9 workflows = all 70 self_service prompts over stdio) · ☑ non-self_service covered (3b: 832
generated-action routing cases + 4 per-persona in-process chains) · ☑ all destructive ops
handshake-tested (3c: 15) · ☑ stub covers needed routes (catch-all + explicit). **CI layer = 1053
passed, ~29s.** Done 2026-06-03.

---

### Phase L4 — Layer 4: E2E real DCT  (~3–4 days)  → ~20–30 tests (representative, advisory)

**Coverage target:** representative real lifecycles per major domain (NOT every action). Real API
contract, auth, latency. Mutations gated + cleaned up.

**Approach:** mirror key 3b chains with `@pytest.mark.real_dct` against real DCT; provision/
refresh/snapshot/delete, dsource link, bookmark, job. Tag created objects with `E2E_RUN_TAG`;
`tests/e2e/cleanup/test_purge.py` deletes them. Runnable locally via
`dct-mcp-test --layer e2e`. (The `e2e-real-dct.yml` GitHub Actions trigger is deferred to L6.)

**Exit criteria:** ☐ key lifecycles pass vs real DCT · ☐ purge works (run-tag teardown).

---

### Phase L5 — Layer 5: LLM-driven  (~3 days)  → ~15–25 tests (advisory, Claude Code CLI)

**Coverage target:** discoverability for each tool domain (can Claude pick the right tool from a
plain-English task) + act→verify for the key mutating flows. Already scaffolded in the demo; here
it's productionized for the full toolset surface.

**Approach:** reuse the `llm_driver` pattern (`claude -p … --output-format stream-json`,
job-completion pre-prompt). One discoverability test per tool domain; act→verify for provision/
refresh/snapshot/delete. Harden stream-json parsing. Gate mutations behind `LLM_ALLOW_MUTATION=1`.

**Exit criteria:** ☑ discoverability per domain (7, parametrized) · ☑ act→verify lifecycle (bookmark,
gated LLM_ALLOW_MUTATION) · ☐ runs vs real DCT (LIVE RUN PENDING). Code at `tests/llm_local/`
(conftest `llm_driver` + test_discoverability.py + test_act_verify.py). Skips w/o `claude` CLI / creds.

---

### Phase L6 — CI & enforcement  (~1 day; LAST — after all test layers)

**Goal:** automate running the suite, and (optionally) enforce it. Deferred deliberately: while
building, the suite is run locally / via `dct-mcp-test`. This phase is NOT a test-writing phase.

Two independent steps — do the first; the second is optional and gated on permissions/buy-in:
1. **CI runs the tests (non-blocking).** Add `.github/workflows/test.yml` running Layers 1–3 on
   every push/PR; add `.github/workflows/e2e-real-dct.yml` (`workflow_dispatch` + optional
   nightly) for Layer 4. Gives a red/green signal on every PR. Needs no special permissions.
2. **Make it a required merge gate (OPTIONAL / deferred).** Mark the `test.yml` check as required
   in branch protection on `main` so red PRs cannot merge. Needs repo-admin rights + team buy-in;
   promote only once the suite is trusted and non-flaky.

**Exit criteria:** ☐ test.yml runs Layers 1–3 on PRs · ☐ e2e `workflow_dispatch` exists ·
☐ (optional) required check enabled on `main`.

---

## BUILD ORDER, MILESTONES, RUNTIMES

- **Order:** L0 → L1 → L2 → L3 → L4 → L5 → **L6 (CI, last)**. (L1 and L2 may overlap.)
- **Focus now: building tests (L0–L5).** ALL CI / GitHub-Actions wiring and any required-check
  gate are deferred to L6.
- **Milestone @ end of L3:** full functional coverage — the suite *can* replace the manual
  playbook in practice (machine enforcement comes in L6).
- **Per-PR runtime (once CI is wired in L6) ~1.5–2.5 min** (Layers 1–3). L4 (~3–8 min) and L5
  (~10–30 min) are on-demand only.
- **Effort total:** ~22–30 working days for full coverage across all personas, dominated by 3b.

## OPEN ITEMS / RISKS

- **OpenAPI spec fixture — ADDED** at `tests/fixtures/api-external.yaml` (DCT API v3.29.0, 2.1MB,
  794 paths). RESOLVED for registration (3a): non-self_service personas are tested via the
  in-memory generator (`tool_factory.generate_tools_for_toolset` seeded from the fixture, offline,
  no disk writes). Two caveats for 3b: (1) the dev-mode FILE generator (driver.py) writes into
  `src/tools/` and deletes existing `*_tool.py` — NEVER run fixed-mode subprocess generation in
  dev; use the in-process/seeded generator or auto-mode. (2) Optionally bundling the spec to
  `docs/api-external.yaml` would also make `tool_factory._load_bundled_spec` work in production
  (offline fallback) + enable auto-mode subprocess fidelity — separate decision, not done.
  Also note: several toolset tools have no `TOOL_TO_MODULE` entry (cdb_dsource_tool,
  diagnostic_tool, group_tool, staging_cdb_tool, staging_source_tool, vault_tool) — fine under
  dynamic generation (path-based naming), dropped only in the (now-unused) fallback path.
- `loader.py:TOOL_TO_MODULE` — NOT stale, no cleanup needed (see L0 / loader.py comment).
- `dct_stub` expansion is the pacing item for 3b — grow it per-workflow, don't front-load.
- 3b for continuous_data_admin (431 prompts) is the single biggest chunk — schedule it last
  within L3 and group prompts into lifecycle chains rather than 1:1 with prompts.
- Layer 5 needs the `claude` CLI authenticated + a disposable DCT; otherwise it skips.

## RELATED DOCS

- Strategy & rationale: `.claude/test/test-strategy.md` (+ `.html`)
- Testing rules + job-completion pre-prompt: `.claude/test/testing.md`,
  `.claude/test/llm-driver-preprompt.md`
- Demo (frozen, separate): `tests/demo/`, `.claude/test/demo-guide.md` (+ `.html`)
