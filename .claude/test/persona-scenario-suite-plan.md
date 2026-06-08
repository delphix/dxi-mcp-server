# Persona Scenario Suite — Plan (Claude-driven, real DCT, all toolsets)

> **End goal:** for EVERY toolset/persona under `config/toolsets/`, drive the dct-mcp-server
> with a natural-language prompt through the **Claude Code CLI** against a **real DCT**, and
> **verify the output**. I should be able to hand any persona any prompt and get a pass/fail.
> This is "Layer 5 at full scale across all personas."
>
> **Start date:** building begins 2026-06-04. This doc is the build plan + the inputs needed.
> Read the STATUS section first when resuming.

---

## STATUS

**State:** ✅ **S0–S5 ALL DONE 2026-06-08 — persona scenario suite COMPLETE.** Any persona's prompts run
live via Claude against the real DCT with verified output. Totals: self_service 23P/9S, CDA 157P/10S/3xf,
platform/reporting/provision/auto 199P/12S/11xf. Tier-2 act→verify validated (self_service vdb-tag, admin
engine-tag). Runner shipped. FINDINGS: discoverability gaps for vault_tool / admin_platform_tool /
diagnostic_tool (names don't match prompt language) — see `_KNOWN_ISSUES` + [[tool-discoverability-findings]].

### Run it (the S5 runner — use the safe-run venv for live layers)
```bash
set -a; source .env.local; set +a
.venv-live/bin/dct-mcp-test --layer scenarios --persona continuous_data_admin           # read-only
.venv-live/bin/dct-mcp-test --layer scenarios --persona self_service --mutations         # incl. mutations
.venv-live/bin/dct-mcp-test --layer scenarios --persona platform_admin --scenario-limit 10 \
    --report report.xml                                                                  # capped + JUnit report
```
`--persona` (csv) → SCENARIO_PERSONAS · `--mutations` → SCENARIO_MUTATIONS=1 · `--scenario-limit N` ·
`--report file.xml` (JUnit). Cleanup (tests/e2e/cleanup) runs automatically after.

### How to run the scenario suite (the S1 framework)
```bash
set -a; source .env.local; set +a
SCENARIO_PERSONAS=self_service SCENARIO_LIMIT=5 \
  .venv-live/bin/python -m pytest tests/llm_local/test_scenarios.py -m scenario -v
# knobs: SCENARIO_PERSONAS (csv, required) · SCENARIO_MUTATIONS=1 · SCENARIO_LIMIT=N · SCENARIO_IDS=csv
```
Catalog: `tests/_support/scenarios.py` (parses `.claude/test/testing/<persona>.md` → 904 prompts across
6 personas; read/mutation classified). Harness: `tests/llm_local/test_scenarios.py` (Tier-1 verify =
expected tool used + license-skip). KNOWN LIMITATIONS to address in S2+: (a) first-verb tier
classification mis-labels compound prompts like "List … then refresh" as read — refine per-scenario or
smarter classifier before enabling mutations broadly; (b) chained "that VDB"/"previous result" prompts
run as independent calls (Tier-1 still holds since Claude re-discovers; true session replay is future work).

### SAFE-RUN RECIPE (use this for ALL live runs — no more commit/restore)
The repo is an editable install, so booting the server live regenerates tools into `src/`. Avoid that
by running live tests from the **non-editable venv** (`.venv-live`, gitignored), which installs the
package into site-packages → generation goes to `$TEMP/dct_mcp_tools`, `src/` untouched.
```bash
# one-time (or after src/ changes — reinstall to refresh the snapshot):
python3 -m venv .venv-live && .venv-live/bin/pip install ".[test]"
# run any live layer (sources gitignored creds):
set -a; source .env.local; set +a
.venv-live/bin/python -m pytest tests/llm_local -m llm_driven -q     # or tests/e2e, etc.
```
VERIFIED 2026-06-08: a live `claude`-driven case ran via the venv and `git status src/` stayed clean;
generated modules landed in `/tmp/.../dct_mcp_tools/`.

| Phase | What | State |
|---|---|---|
| S0 | Safe-run venv + `llm_driver_for(toolset)` factory + `license_blocked()` helper | ☑ DONE 2026-06-08 |
| S1 | Scenario catalog (904 prompts) + Tier-1 verifier + env-selected harness | ☑ DONE 2026-06-08 |
| S2 | self_service scenario suite (live) | ☑ DONE 2026-06-08 — read catalog 23 passed / 9 skipped(license) / 0 failed; Tier-2 vdb-tag act→verify passed |
| S3 | continuous_data_admin scenario suite (live) — **priority persona** | ☑ DONE 2026-06-08 — read 157 passed / 10 skipped(license) / 3 xfail; engine-tag act→verify passed |
| S4 | platform_admin, reporting_insights, self_service_provision, auto | ☑ DONE 2026-06-08 — 199 passed / 12 skipped / 11 xfail (9 discoverability gaps, 2 chained) |
| S5 | runner (`dct-mcp-test --layer scenarios`) + cleanup + JUnit report | ☑ DONE 2026-06-08 |

---

## WHAT ALREADY EXISTS (reuse — don't rebuild)

- **Claude driver:** `tests/llm_local/conftest.py` — `_write_mcp_config(toolset)`, `_make_driver(config_path)`,
  `llm_driver` (self_service), `llm_driver_cda` (CDA). Drives `claude -p … --output-format stream-json`
  with the job-completion pre-prompt, parses the tool-call trace (`DriverResult.tool_calls / tools_used / actions_for`).
  **Pipeline live-validated** (CDA engine discoverability passed against the real DCT).
- **Job-completion pre-prompt:** `.claude/test/llm-driver-preprompt.md` (poll job to terminal before success).
- **Prompt catalogs already authored:** `.claude/test/testing/<toolset>.md` — the per-persona prompt lists
  (self_service 70, self_service_provision 139, continuous_data_admin 431, platform_admin 198,
  reporting_insights 79, auto 57). **These are the scenario source of truth.**
- **License tolerance (pytest side):** `tests/e2e/_helpers.py:call_tool_tolerant` (skip on "License does not permit").
- **Config oracle:** `tests/_support/config_cases.py` (tools/actions per toolset).
- **`claude` CLI authenticated** on this machine ✓. **DCT creds** in `.env.local` (gitignored) ✓.

## KNOWN CONSTRAINTS (from the live runs)

- **EDITABLE INSTALL FOOTGUN:** booting the server against a real DCT regenerates tool files into
  `src/dct_mcp_server/tools/` (deletes existing `*_tool.py` first). A big live suite that boots the
  server hundreds of times CANNOT use the commit/restore loop sustainably → **S0 must fix this.**
- **This DCT's license blocks VDB_GROUP and BOOKMARK** (401). Scenarios touching unlicensed resources
  must be SKIPPED, not failed. A fully-exercised self_service needs those features licensed, or we
  accept skips. (Confirm which features the test DCT licenses.)

---

## THE KEY DESIGN DECISION — "verify the output"

For ~970 prompts we cannot hand-author an expected result per prompt. Three verification tiers
(use a HYBRID — recommended):

1. **Tool-trace + no-error (generic, all scenarios).** Assert Claude called the expected tool/action(s)
   for the scenario and the run had no unhandled error. Cheap, scales to every prompt. Expected
   tool/action derived from `config_cases` by matching the scenario to its domain. License-blocked → skip.
2. **Act → independent verify (mutations).** After a create/modify/delete, do an INDEPENDENT read
   (second Claude call or a direct tool call) and assert the real effect (object exists / status changed
   / tag present / gone). This is the strong signal. Reuse the job-completion pre-prompt for async waits.
3. **LLM-judge (reasoning/synthesis prompts, optional).** A second `claude -p` call judges whether the
   final answer satisfies the prompt (structured yes/no + reason). Powerful for "how many X / which engine
   has most Y" prompts; costs an extra call and is advisory.

**Recommendation:** Tier 1 for every scenario (baseline), Tier 2 for all mutating scenarios (the real
proof), Tier 3 only where a deterministic assertion isn't possible. Each scenario in the catalog declares
its tier + (for Tier 2) its verification read + cleanup.

---

## PHASES

### S0 — Safe-run foundation  ✓ DONE 2026-06-08
Delivered: `.venv-live` non-editable install (generation → `$TEMP`, src untouched — proven live);
`llm_driver_for()` factory fixture (per-toolset driver) + `license_blocked(result)` helper in
`tests/llm_local/conftest.py`; `.venv-live/` gitignored. See SAFE-RUN RECIPE above. Original notes:
- **Fix the src-regeneration footgun.** Recommended: run the server from a **non-editable install** —
  `python -m venv .venv-live && .venv-live/bin/pip install ".[test]"` (NO `-e`). Then `'site-packages' in
  __file__` is true → generation writes to `$TEMP/dct_mcp_tools` and the loader loads from there; `src/`
  is never touched. Run the live suite with `.venv-live/bin/python -m pytest …` (the test subprocess uses
  `sys.executable`). (Alternative: add a `DCT_TOOLS_OUTPUT_DIR` env hook to driver.py + loader — bigger,
  touches src.)
- **Generalize the Claude driver to ANY toolset:** a `llm_driver_for(toolset)` factory fixture (params:
  toolset) built on the existing `_write_mcp_config` / `_make_driver`. Replace the two hardcoded fixtures.
- **License tolerance on the Claude side:** helper that detects "License does not permit" / tool-error in
  the `DriverResult` and marks the scenario skipped (resource not licensed), not failed.
- **Exit:** can run `llm_driver_for("<any toolset>")("<prompt>")` against the real DCT with `src/` untouched.

### S1 — Scenario catalog + verification model  (~1 day)
- Parse `.claude/test/testing/<toolset>.md` into a structured catalog: `Scenario(persona, id, prompt,
  expected_tools, tier, verify_read?, cleanup?)`. Start by auto-deriving `expected_tools` from the domain
  headers in those files (they're grouped by tool).
- Implement the Tier-1 verifier (tool-trace + no-error + license-skip) and the Tier-2 act→verify helper
  (independent re-read; reuse pre-prompt for job waits). Optionally the Tier-3 LLM-judge.
- **Exit:** a parametrized test can run any catalog scenario for any persona and produce pass/skip/fail.

### S2 — self_service suite (live)  ✓ DONE 2026-06-08
- Read catalog (32 read-tier prompts) run live: **23 passed / 9 skipped (license: vdb_group, bookmark) /
  0 failed** (~15 min). Every license-permitted read scenario: Claude drove the right tool.
- Compound-prompt classifier fix (scenarios.py): "List … then refresh" now → mutation.
- Tier-2 act→verify (`tests/llm_local/test_act_verify.py`): added a **vdb-tag** scenario (licensed) —
  Claude tags a VDB, an INDEPENDENT re-read (key not in the prompt) confirms it, then cleanup. PASSED live.
  Bookmark scenario now skips on license (guard added). Hardened verifications against echoed-identifier
  false passes; don't over-constrain which read action Claude picks.
- LEARNINGS for later personas: (a) verify prompts must NOT contain the identifier being checked;
  (b) assert the OUTCOME (key present in a full listing) not the mechanism (which action).

### S3 — continuous_data_admin suite (live) — PRIORITY  ✓ DONE 2026-06-08
- Read catalog (170 read-tier prompts) run live: **157 passed / 10 skipped (license) / 3 xfail**
  (~98% of non-skipped). Run took ~1h40m.
- Tier-1 robustness fix: assert Claude used a tool BELONGING to the persona (config_cases), not the
  imperfect .md-header tool. (Root cause: "VDB groups" prompts filed under data_tool, but DCT exposes
  them via group_tool — Claude is right.)
- Admin Tier-2 act→verify (`test_act_verify_cda.py`): engine-tag PASSED live (tag→independent verify→
  cleanup). engine register→verify→unregister gated on `E2E_ENGINE_JSON` (skips until provided).
- **FINDINGS (real, recorded as xfail in test_scenarios.py `_KNOWN_ISSUES`):**
  1. **Discoverability gap — `vault_tool`** (#407/#408): `vault_tool` exists + generates with
     `list/search_hashicorp_vaults`, but Claude's tool-search did NOT surface/select it for "Hashicorp
     vaults" (with 22 CDA tools, Claude Code defers tools + uses ToolSearch). Actionable: improve
     vault_tool name/description discoverability. ← the kind of signal Layer 5 exists to catch.
  2. **Chained prompt** (#161 "that vCDB"): no antecedent in isolated execution → Claude asks. Known
     limitation of independent-prompt execution; true session replay is future work.

### S4 — remaining personas (live)  ✓ DONE 2026-06-08
- Read catalogs for platform_admin / reporting_insights / self_service_provision / auto (222 read-tier)
  run live: **199 passed / 12 skipped (license) / 11 xfail** (~1h53m). self_service_provision + auto:
  clean (no failures). auto verified leniently (meta-tool mode; assert Claude drove some tool).
- The 11 xfail = documented findings (in `_KNOWN_ISSUES`), same two classes as S3:
  * **DISCOVERABILITY GAPS (9):** Claude's tool-search did not surface a tool whose NAME doesn't match
    the prompt's domain language — even though the tool exists + generates:
      - `vault_tool` (Hashicorp vaults #174-176; **also owns kerberos-configs** #182-184)
      - `admin_platform_tool` ("LLM models" #155)
      - `diagnostic_tool` ("NetBackup connectivity" #187, "DSP network test" #192)
  * **CHAINED (2):** reporting_insights #78/#79 "that tag" — no antecedent in isolation.
- **ACTIONABLE PRODUCT THEME (across S3+S4):** several tools are unreachable via natural language because
  their names/descriptions don't reflect what they do (vault_tool→kerberos, admin_platform_tool→AI/LLM,
  diagnostic_tool→NetBackup/DSP). With 13-22 tools per persona, Claude Code defers them behind ToolSearch,
  so name/description quality directly gates usability. Recommend improving these tool descriptions.

### S5 — runner + cleanup + report  ✓ DONE 2026-06-08
- `dct-mcp-test` gained a **`scenarios`** layer + `--persona` (csv), `--mutations`, `--scenario-limit`,
  `--report` (JUnit-XML). Cleanup (`tests/e2e/cleanup`, E2E_RUN_TAG purge) runs automatically after
  (scenarios is in `_LAYERS_NEEDING_DCT`). Run via the `.venv-live` console script so generation stays
  in `$TEMP` (safe-run). Smoke-verified end-to-end: 1 scenario passed, cleanup ran, JUnit report written,
  src clean.

---

## EVERYTHING NEEDED TO START (inputs + decisions)

**From you / the environment:**
1. **A disposable DCT licensed for the features you want to test.** This one blocks VDB_GROUP + BOOKMARK —
   confirm whether the test DCT can be licensed for them, or we accept those scenarios as skipped.
2. **`claude` CLI authenticated** ✓ (done) and **DCT creds in `.env.local`** ✓ (done).
3. **Engine connection details** (`E2E_ENGINE_JSON`: hostname, type, username, password) for engine
   register/unregister scenarios.
4. **Provisioning inputs** for provision scenarios (a provisionable dSource id + any required provision
   params) — environment-specific.
5. **Priority order of personas** (default: self_service → continuous_data_admin → platform_admin →
   reporting_insights → self_service_provision → auto).

**Decisions to lock tomorrow:**
6. **Safe-run mechanism:** non-editable venv (recommended) vs. a driver.py env hook.
7. **Verification depth:** Tier-1+2 (recommended) vs. add Tier-3 LLM-judge.
8. **Mutation policy:** which mutating scenarios are OK to run on the disposable DCT (provisioning,
   engine register, deletes) and which to leave gated/skipped.

**Build artifacts (what we'll create):**
- `.venv-live` (or driver hook) — safe-run.
- Generalized `llm_driver_for(toolset)` fixture + Claude-side license tolerance.
- `tests/scenarios/` (or `tests/llm_local/scenarios/`) — catalog loader + per-persona scenario tests.
- Per-persona cleanup/purge.
- `dct-mcp-test --layer scenarios` runner + report.

## EFFORT
~8–11 working days total for all personas. self_service+CDA (the priority) ~4–5 days. Inherently
live + iterative (each scenario tuned against the real DCT).

## RELATED
- Existing layered suite + status: `.claude/test/test-implementation-plan.md`
- Strategy/rationale: `.claude/test/test-strategy.md`; pre-prompt: `.claude/test/llm-driver-preprompt.md`
