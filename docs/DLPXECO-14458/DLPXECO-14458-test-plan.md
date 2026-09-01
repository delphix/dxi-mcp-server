# Test Plan: DLPXECO-14458

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14458
**Derived from**: `docs/DLPXECO-14458/DLPXECO-14458-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in ## Scenarios becomes one test() / def test_* block in .claude/test/generated-test/.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

Automated regression tests using `pytest` + `pytest-asyncio` + `fastmcp` client; the server is spawned as a subprocess via `start_mcp_server_uv.sh` (or `start_mcp_server_python.sh` fallback). The primary runner is `dct-mcp-test --layer ci`. Confirmation-flow scenarios require no live DCT instance — they are exercised by inspecting response shapes from the MCP server directly. Elicitation scenarios (FR-005) require an MCP Inspector or Claude Desktop client that declares elicitation capability.

---

## Environment / Landscape

- Landscape: Local development (unit/integration CI) and, for elicitation scenarios, an MCP Inspector instance
- Service under test: Local DCT MCP server process (port assigned at startup, read from startup log)
- Credentials: `DCT_API_KEY` and `DCT_BASE_URL` from `.claude/settings.local.json` under `mcpServers.dct.env` — **not required** for most confirmation gate tests (which return before the DCT call)
- For FR-003 spec-coverage test: bundled `docs/api-external.yaml` is sufficient; no live DCT needed

---

## Versions to Cover

<!-- Guidance: From design doc Version Compatibility table — only Supported=Yes versions. -->

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11+ / FastMCP 2.13.2+ | Only supported runtime; `Context.elicit()` and `ToolAnnotations` require this version | Yes |
| `DCT_TOOLSET=dynamic` | Primary path for all FRs | Yes |
| `DCT_TOOLSET=continuous_data_admin` | Fixed-toolset regression: FR-001/FR-002/FR-003 must not break existing grouped tool confirmation flows | Yes |
| `DCT_CONFIRMATION_FALLBACK=keyword` (default) | New default; keyword resolver must not gate read-shaped POSTs | Yes |
| `DCT_CONFIRMATION_FALLBACK=off` | Must reproduce pre-change resolution exactly | Yes |
| `DCT_CONFIRMATION_ENFORCEMENT=advisory` (default) | Must preserve today's advisory behaviour for non-elicitation clients | Yes |
| `DCT_CONFIRMATION_ENFORCEMENT=strict` | Must refuse non-elicitation clients naming the missing capability | Yes |

---

## Scenarios

<!-- Guidance: One row per testable scenario. Map each to at least one FR-*. -->

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | token issued for body A, submitted with body B at same path → confirmation_required, no execution | FR-001 | dynamic, advisory | `status="confirmation_required"`, fresh token in response, DCT not called |
| S2 | confirm-and-execute (path P, body A), then replay identical (path, body, token) → confirmation_required, no second execution | FR-001 | dynamic, advisory | `status="confirmation_required"` on second call; first call produces DCT result |
| S3 | body keys submitted in different order on confirm vs execute calls → token still verifies | FR-001 | dynamic, advisory | Operation executes on second call; no confirmation_required returned |
| S4 | token issued for `{"a":1,"b":2}`, submitted with `{"a":1,"b":3}` → confirmation_required | FR-001 | dynamic, advisory | `status="confirmation_required"` with fresh token |
| S5 | 100 distinct-body provision calls with no batch_intent → 100 confirmation_required responses | FR-001 | dynamic, advisory | Each of 100 calls returns `status="confirmation_required"`; no call auto-executes |
| S6 | token issued before server restart, submitted after → confirmation_required | FR-001 | dynamic, advisory | `status="confirmation_required"` after restart; old token not accepted |
| S7 | existing item-scoped confirmation flow (e.g. POST /vdbs/{vdbId}/delete) confirm then execute → works, token is now single-use | FR-001 | dynamic, continuous_data_admin | First call: `confirmation_required`; second call with correct token: DCT result; third replay of same token: `confirmation_required` |
| S8 | standard operation — confirmation_token alone satisfies the gate | FR-002 | dynamic | `required_fields: ["confirmation_token"]`; operation executes after token echo |
| S9 | elevated operation — only confirmation_token submitted (no confirmed_resource_name) → confirmation_required with required_fields | FR-002 | dynamic | `status="confirmation_required"`, `required_fields: ["confirmation_token","confirmed_resource_name"]` |
| S10 | elevated operation — confirmed_resource_name does not match resource name/ID → confirmation_required | FR-002 | dynamic | `status="confirmation_required"` with message stating expected value format |
| S11 | manual operation — confirmation_token and correct name but acknowledged_impact absent → confirmation_required | FR-002 | dynamic | `status="confirmation_required"`, `required_fields: ["confirmation_token","confirmed_resource_name","acknowledged_impact"]` |
| S12 | manual operation — all three fields correctly supplied → operation executes | FR-002 | dynamic | DCT API called; `status="success"` in response |
| S13 | every confirmation_required response (at any level) includes non-empty required_fields | FR-002 | dynamic | Assertion over all 7 confirmation response shapes in S1–S12: `required_fields` is non-empty list |
| S14 | regression: submitting only confirmation_token to a manual-gated operation is rejected | FR-002 | dynamic | `status="confirmation_required"`; test name asserts `manual` != `standard` |
| S15 | all 20 PPM-1128 scope table operations resolve to non-none confirmation level | FR-003 | dynamic, fallback=keyword | For each of 20 operations: `check_confirmation` returns level != "none" |
| S16 | read-shaped POSTs (/vdbs/provision_by_snapshot/defaults, /snapshots/search, /paas-snapshots/search, /environments/compatible_repositories_by_snapshot, /file-mapping/validate-file-mapping-by-snapshot) resolve to none | FR-003 | dynamic, fallback=keyword | `check_confirmation` returns `level="none"` for all 5 paths |
| S17 | enumerate every mutating operation in bundled spec: each resolves to non-none or appears on triaged exception list | FR-003 | dynamic, fallback=keyword | All mutating operations accounted for; zero unexamined gaps |
| S18 | explicit static rule takes precedence over keyword fallback message | FR-003 | dynamic, fallback=keyword | When operation covered by both: response uses static rule's message text, not fallback generic |
| S19 | DCT_CONFIRMATION_FALLBACK=off reproduces pre-change resolution exactly | FR-003 | dynamic, fallback=off | Resolution for all 20 PPM-1128 operations matches baseline snapshot (7 gated, 13 ungated) |
| S20 | no unreachable confirmation resolver in tree | FR-003, QR-4 | any | Import/call-graph check: `dynamic_confirmation.get_confirmation_for_operation_dynamic` has at least one non-test caller in the import graph |
| S21 | 100-target batch_intent → single confirmation_required with count:100 and all 100 targets | FR-004 | dynamic | `status="confirmation_required"`, `count=100`, `targets` field contains all 100 bodies |
| S22 | after batch grant approval, 100 calls execute with no further prompt; each response reports remaining grant count | FR-004 | dynamic | Calls 1–100: each returns DCT result with `grant_status.remaining` decrementing from 99 to 0 |
| S23 | call 101 against exhausted grant → confirmation_required | FR-004 | dynamic | `status="confirmation_required"` on 101st call |
| S24 | call with body not in enumerated grant targets → confirmation_required | FR-004 | dynamic | `status="confirmation_required"` for out-of-set body |
| S25 | grant TTL expires → confirmation_required on next call | FR-004 | dynamic | After clock-advance past DCT_GRANT_TTL: `status="confirmation_required"` |
| S26 | batch containing floor operation → refused before grant is issued | FR-004, FR-007 | dynamic | `status="error"` naming the floor operation; no grant token issued |
| S27 | without batch_intent, behavior is exactly FR-001 per-call confirmation | FR-004 | dynamic | Standard single-call confirmation flow; no `batch_confirmation_token` in response |
| S28 | elicitation-capable client: destructive operation triggers elicit(); user decline → operation does not execute | FR-005 | dynamic, elicitation client | `elicit()` called; on decline: operation not dispatched to DCT |
| S29 | elicitation schema for elevated requests confirmed_resource_name; for manual, also requests acknowledged_impact | FR-005 | dynamic, elicitation client | Elicitation schema fields match `required_fields` from FR-002 |
| S30 | DCT_CONFIRMATION_ENFORCEMENT=strict + non-elicitation client → operation refused naming missing capability | FR-005 | dynamic, strict, non-elicitation | `status="error"` with message naming `elicitation` capability missing |
| S31 | DCT_CONFIRMATION_ENFORCEMENT=advisory (default) + non-elicitation client → existing advisory confirmation_required response | FR-005 | dynamic, advisory | `status="confirmation_required"` with `instructions` field; no error |
| S32 | tools/list reports readOnlyHint=true for discovery; readOnlyHint=false + destructiveHint=true + idempotentHint=false for execute | FR-005 | dynamic | `tools/list` response annotations match specification |
| S33 | elicitation approval satisfies the gate without the token being returned to the model | FR-005 | dynamic, elicitation client | Elicitation response → operation executes; model does not echo `confirmation_token` |
| S34 | two identities each making 3 calls to same operation (N=5 threshold) → no trigger; one identity making 6 → trigger | FR-006 | dynamic | Identities A,B: 3 calls each → no `batch_confirmation_required`; identity A: 6 calls → `status="batch_confirmation_required"` |
| S35 | counter state isolated per identity | FR-006 | dynamic | Identity A's count does not affect identity B's threshold window |
| S36 | session/identity UUID exists with IS_LOCAL_TELEMETRY_ENABLED=false | FR-006 | dynamic | `get_process_identity()` returns non-empty UUID string when telemetry is disabled |
| S37 | batch_check:5:60 parses correctly alongside manual, elevated, standard, retention_check:N, policy_impact_check:N | FR-006 | dynamic | `load_manual_confirmation_rules()` returns correct parsed structure for all level types; no parsing error |
| S38 | velocity trigger emits audit event whether or not user confirms | FR-006, FR-008 | dynamic | After velocity trigger: audit log contains `batch_triggered` event regardless of confirmation outcome |
| S39 | server restart resets velocity counters with persistence=off (default) | FR-006 | dynamic | After server restart: counter at 0 for all identities; documented in config help output |
| S40 | floor operation in batch grant → refused with error naming operations | FR-007 | dynamic | `status="error"` before any grant token is issued |
| S41 | no config combination causes floor operation to skip individual confirmation | FR-007 | dynamic | Exhaustive test over all config-knob combinations: floor operation always returns `confirmation_required` |
| S42 | test asserts no config knob disables confirmation globally | FR-007 | dynamic | Enumerate DCT_CONFIRMATION_ENFORCEMENT, DCT_CONFIRMATION_FALLBACK, DCT_GRANT_TTL variations: none results in floor op being silently executed |
| S43 | standing approvals expire by count and TTL, whichever comes first — count expiry | FR-007 | dynamic | Grant with count=3 exhausted after 3 calls; 4th call returns `confirmation_required` |
| S44 | standing approvals expire by count and TTL, whichever comes first — TTL expiry | FR-007 | dynamic | Grant with TTL=1s; after 1s: next call returns `confirmation_required` even if count not exhausted |
| S45 | responses executed under a grant carry authorization metadata | FR-007 | dynamic | Each successful grant-covered call: response contains `authorization: {"type":"grant","id":...,"remaining":...}` |
| S46 | each of 7 outcomes produces exactly one audit event with specified fields | FR-008 | dynamic | Audit log inspected after triggering each outcome: one event per trigger, all fields present |
| S47 | no audit event contains credential, request body, or confirmed_resource_name | FR-008 | dynamic | Grep audit log for known credential patterns, body content, and resource names: zero matches |
| S48 | audit records produced with IS_LOCAL_TELEMETRY_ENABLED=false | FR-008 | dynamic | Local audit log file contains events with telemetry disabled |
| S49 | with IS_LOCAL_TELEMETRY_ENABLED=true, same event forwarded to telemetry backend (stub) | FR-008 | dynamic, telemetry=on | Telemetry stub receives event matching local audit event fields |
| S50 | STDIO + DCT_API_KEY default-config full regression: no new prompts, existing flows unchanged | constraint | dynamic, advisory, fallback=keyword | Baseline scenario set passes; no new `confirmation_required` responses compared to pre-change baseline |

---

## Out of Scope

<!-- Guidance: Scenarios deliberately skipped, with one-line reason. -->

- Host-side interception testing in DCT AI Assistant (NG1 — separate `apigw-services` story)
- DCT-side RBAC policy for standing approvals (NG2 — DCT authorization policy, out of scope)
- Vocabulary and message wording consistency (NG3 — PPM-1129 Lever 4, separate story)
- Tool annotation work beyond `discovery` and `execute` tools (NG4 — scope limited to two dynamic tools)
- Persona-toolset action renaming (NG5 — separate story)
- Load/stress testing of the token store under >1000 req/s sustained (performance characteristic is documented; load testing is tracked separately)
- Elicitation testing against production DCT AI Assistant embedded deployment (FR-005 elicitation is local MCP client test only; DCT assistant host-side interception is NG1)

---

## Test Data Requirements

<!-- Guidance: What data or fixture state must exist before tests run? -->

- Most confirmation gate tests do NOT require a live DCT connection — they exercise the gate layer before the DCT HTTP call; the server can be started with a dummy `DCT_API_KEY` and `DCT_BASE_URL` pointing to a non-existent host.
- For S28–S33 (elicitation): an MCP Inspector or Claude Desktop client that declares `ElicitationCapability`; no live DCT needed.
- For S50 (regression): a live DCT instance with at least one existing VDB for item-scoped confirmation flows.
- Bundled `docs/api-external.yaml` provides the spec for FR-003 coverage test (S17) without live DCT.
- Velocity counter tests (S34–S35) use per-test process-scoped identity values to avoid cross-test contamination.

---

## Exit Criteria

<!-- Guidance: How the test phase decides "done". -->

- All Required scenarios (S1–S50 marked Required) PASS on all Required versions
- Smoke suite (existing `tests/` excluding DLPXECO-14458 test file) PASSES with no new failures
- No scenario marked SKIPPED without a documented reason in the test output
- FR-003 coverage test (S17): zero mutating operations in bundled spec are uncovered (either gated or on the exception list)
- FR-007 floor test (S41–S42): exhaustive config combination assertion passes with zero bypasses found
- Audit event test (S46–S47): audit log contains zero credential-containing entries

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-14458.spec.* (test-generation phase)
     - Each FR in docs/DLPXECO-14458/DLPXECO-14458-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/DLPXECO-14458/DLPXECO-14458-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
