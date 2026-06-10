## DLPXECO-13984 — 2026-06-02

**Feature**: Phase 1 Two-Tool Architecture (Discovery + Execute) for DCT API MCP Server
**Domain**: feature
**Workflow**: context → vision → design → implement → build → test → validate → pr → release → retrospective

1. What slowed the workflow down or caused rework?

The most significant friction point was the **LLM evaluation harness (FR-005, scenarios S29–S31)** — the test plan required these 3 scenarios to exercise the live LLM harness against a real DCT instance with live API keys, but neither were available during test execution. This forced them to be explicitly skipped with documented rationale, which was acceptable per design intent (developer-time only) but still required rework: the test evidence section needed an additional failure triage row, the validate phase flagged them as warranting a note, and the decision-gate report had to acknowledge that the ≥80% adoption threshold was assessed against a dry-run harness rather than live LLM results.

A secondary slowdown was the **validate phase catching a medium coverage gap** (77% actual vs. 80% target). The gap traced to `register_dynamic_tools()` in `tools/__init__.py` — the integration entry point was not covered because its test would require a full `FastMCP` app fixture, out of scope for unit tests. This was known during design but the coverage threshold in `.claude/test/testing.md` had not been updated to reflect the exception, requiring a manual gate-disable note in the validation report rather than a clean threshold pass.

A third friction point was **Python 3.12 compatibility**: one generated test for FR-003 (S15) initially used `asyncio.coroutine`, removed in Python 3.12. This was caught during the test run and fixed inline, but it indicates that the test-generation phase did not account for the runtime Python version when selecting async mocking patterns.

2. Did the domain auto-detection (`feature`) correctly classify this change?

Yes — `feature` was the correct classification. This ticket delivered net-new capabilities (`spec_cache.py`, `dynamic.py`, `confirmation_resolver.py`, `evals/llm_eval_harness.py`) and new config surface (`DCT_TOOLSET=dynamic`, `DCT_SPEC_CACHE_PATH`, `DCT_SPEC_MAX_AGE_HOURS`) with no changes to existing persona toolsets. It was appropriately scoped as a full workflow (context → vision → design → implement → build → test → validate → pr → release) with all phases exercised. A `bugfix` or `task` classification (lite mode) would have skipped the vision/design/release phases, which were all load-bearing for this architectural change — particularly the decision-gate report and doc updates.

One classification refinement worth noting: the feature involved a significant evaluation/research component (LLM harness, adopt/revert decision gate) that has no natural home in the standard feature workflow. Future tickets of this type (exploratory delivery with a formal adopt/revert decision) would benefit from a dedicated `evaluation` domain or an explicit `research-phase` step before `implement`, so the harness scaffolding is designed during the design phase rather than folded into FR-005 as an implementation detail.

3. Were any steps redundant, or were any missing entirely?

**Missing — test-infra**: The workflow skipped `test-infra` entirely. This was the right call for a Python/FastMCP server with no database migrations, but the skip was implicit (no project-level test-infra configuration). For future features that involve environment setup (fixtures, seed data, mock DCT endpoints), test-infra has no stub in this project and would need to be bootstrapped from scratch.

**Redundant check — E2E in validate**: The validate phase attempted curl-based E2E testing, which is structurally inapplicable to an MCP stdio server. The phase ran through docker-compose, bootRun, FastAPI, and Gin detection before concluding SKIPPED. This adds noise for every validate run in this project. A project-level `.claude/settings.local.json` override that sets `e2e_mode: mcp_stdio` would allow the validate phase to immediately document the correct test mechanism without running inapplicable checks.

**Actionable improvement — uv.lock drift**: `uv.lock` appeared as a modified untracked file in git status throughout the workflow, indicating a dependency sync was needed that didn't fit cleanly into any existing phase. A post-build or post-pr step that runs `uv lock --check` (or commits the updated lockfile) would prevent this from surfacing as noise in the PR diff.
