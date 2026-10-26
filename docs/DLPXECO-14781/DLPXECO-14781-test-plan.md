# Test Plan: DLPXECO-14781

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14781
**Derived from**: `docs/DLPXECO-14781/DLPXECO-14781-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach
<!-- Guidance: 1–2 sentences naming the framework, runner, and where tests will execute. Pull from .claude/test/testing.md if it exists. -->

The automated tests are `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) unit and integration tests. They run locally and in CI via `pytest tests/unit tests/integration` (or `dct-mcp-test --layer ci`), with coverage from `pytest --cov=src/dct_mcp_server --cov-report=term-missing`.
- **Integration tests** follow the existing `tests/integration/_gate_helpers.py` pattern. They drive the real `execute`/`discovery` closures, and only `dct_client.make_request` and the cached spec are stubbed. The `make_request` stub is a routing stub: it serves `/toolkits/{id}`, `/sources/{id}`, `/dsources/{id}`, `/vdbs/{id}`, `/snapshots/{id}`, `/timeflows/{id}`, `/bookmarks/{id}` and `/environments/{id}` from fixtures, and records the final dispatch call and all GET counts.
- **Optional live check**: Track 1 scenario execution per `.claude/test/testing.md`, against a live DCT with DB2/MySQL toolkits (`real_dct` marker). It is not required.

## Environment / Landscape
<!-- Guidance: Name the test landscape and any preconditions. -->

- **Landscape:** local developer machine or CI runner with Python 3.11+, with the project installed (`uv sync` or `pip install -e .` per `.claude/test/test-infra.md` Option C).
- **Service under test:** the in-process dynamic-mode `execute`/`discovery` closures (`tools/core/dynamic.py`). No live DCT is needed for the required scenarios.
- **Capture-capable host simulation:** `monkeypatch.setenv("DCT_MCP_SENSITIVE_NONCE", <nonce>)`, with `get_dct_config(require_key=False)` returning `auth_mode="embedded"`. A non-capture host is simulated by unsetting the nonce, or by setting auth mode to a non-embedded value.
- **Optional live landscape:** `<dct-host>` with an engine that has the DB2 and MySQL AppData toolkits installed, plus a linkable source on `<staging-host>`. Credentials go in `.claude/settings.local.json` per `.claude/test/test-infra.md`. No VMs need to be provisioned for the required scenarios.

## Versions to Cover
<!-- Guidance: List every version branch this feature must be exercised on. Pull from the design doc `## Version Compatibility` table — only versions marked "Supported = Yes" appear here. -->

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11+ / FastMCP 2.13.2+ | Only supported runtime | Yes |
| `DCT_TOOLSET=dynamic` + embedded capture-capable host (`DCT_AUTH_MODE=embedded` + `DCT_MCP_SENSITIVE_NONCE`) | All new behaviour is active here | Yes |
| `DCT_TOOLSET=dynamic` + non-capture-capable client (no nonce / non-embedded) | Must be byte-identical to pre-change behaviour | Yes |
| DCT API v3 toolkit details, both definition shapes (snake_case and camelCase, with and without the `parameters`/`schema` wrapper) | Lookup-table robustness without version branching | Yes |
| DCT API degraded (toolkit details without definitions, 401/403) | Fail-open path | Yes |
| `DCT_TOOLSET=<fixed toolset>` | Unchanged. The existing suites act as a smoke check | No (smoke-only, via existing suites) |
| Live DCT 3.31.0 with DB2/MySQL toolkits | Confirms the real toolkit JSON shape (design Open Question) | No (optional, `real_dct`) |

## Scenarios
<!-- Guidance: One row per testable scenario. Map each scenario to at least one FR-* from docs/$NAME/$NAME-functional.md. -->

"Cap" = a capture-capable host (embedded mode plus nonce). "Non-cap" = a non-capture-capable client. "Dyn" = `DCT_TOOLSET=dynamic`.

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | DB2 AppData dSource link whose `parameters` omits a required top-level password field returns `sensitive_input_required` | FR-001, FR-003 | Dyn + Cap | `status == "sensitive_input_required"`. The DB2 password leaf is in `required_sensitive_fields`. `sensitive_field_locations` contains `{"name": <leaf>, "location": "parameters.<leaf>"}`. The dispatch stub is never called with `POST /dsources/appdata`. The toolkit is resolved via `GET /sources/{source_id}` and then `GET /toolkits/{id}`. |
| S2 | MySQL AppData VDB provision by snapshot with an inline `appdata_source_params` password is gated and resolved through the snapshot→dataset chain | FR-001, FR-003 | Dyn + Cap | `sensitive_input_required` with location `appdata_source_params.<leaf>`. GETs recorded: `/snapshots/{id}` → `/dsources/{dataset_id}` → `/toolkits/{id}`. No dispatch. |
| S3 | Nested array passwords supplied inline at `parameters.nodes[0]` and `parameters.nodes[2]` but absent at `nodes[1]` are flagged only at indices 0 and 2 | FR-003 | Dyn + Cap | `sensitive_field_locations` contains exactly `parameters.nodes[0].instancePassword` and `parameters.nodes[2].instancePassword` (EC-5). `parameters.nodes[1].instancePassword` is not listed. |
| S4 | Non-password connector fields `instanceUser`, `port`, `mountPath`, `instanceId` are never flagged | FR-002, FR-003 | Dyn + Cap | With all four present and the password applied via a valid `sensitive_applied`, the call dispatches. None of the four names appears in any gate response produced over the DB2 and MySQL fixtures. |
| S5 | A top-level `password` outside the sub-object is not flagged because of the connector schema | FR-003 | Dyn + Cap | In a spec without a `password` annotation, a body with top-level `password` plus a fully applied connector sub-object dispatches. `sensitive_field_locations` never lists a location outside the mapped sub-object. |
| S6 | An optional absent password and a `oneOf`-branch absent password are not flagged, but a present one is | FR-002, FR-003 | Dyn + Cap | Absent: no gate (dispatch occurs). Present: gate with that location. |
| S7 | Walker returns exact paths for nested object, array items, `oneOf`/`anyOf`/`allOf`, `if`/`then`/`else`, `dependencies` and `$ref`-reached passwords | FR-002 | Python 3.11+ | `walk_secret_paths(...)` returns exactly the expected `SecretPath` set, including the `required` and `conditional` flags. |
| S8 | Walker terminates on self- and mutually-referencing `$ref` cycles and on depth/node bounds | FR-002 | Python 3.11+ | It returns within the test timeout with every reachable password path. Exactly one warning is recorded for the bound hit. No `RecursionError` occurs. |
| S9 | Walker ignores `"format": "Password"`, `"format": "secret"`, name-only `password` and non-dict roots | FR-002 | Python 3.11+ | Empty set for the miscased/other-format/name-only cases. Non-dict root (`"x"`, `None`, `[]`): empty set plus a warning, no exception. |
| S10 | Re-call with `sensitive_applied` (valid nonce) listing the full location dispatches without re-prompting | FR-005 | Dyn + Cap | `status == "success"`. The dispatch body contains the injected value at `appdata_source_params.<leaf>` unchanged. |
| S11 | Re-call with `sensitive_applied` (valid nonce) listing only the bare leaf name dispatches without re-prompting | FR-005 | Dyn + Cap | `status == "success"`. No `sensitive_input_required`. |
| S12 | Re-call with a connector field named `password` (spec-annotated name) applied by location only does not re-prompt through the native walker | FR-005, FR-009 | Dyn + Cap | `status == "success"`. This guards against the native-walker re-prompt loop (DLPXECO-14603). |
| S13 | `sensitive_applied` with a wrong or missing nonce leaves the connector field flagged | FR-005 | Dyn + Cap | `sensitive_input_required` still lists the location. No dispatch. |
| S14 | Two connector secrets flagged, host applies one: the gate names only the remaining one | FR-005 | Dyn + Cap | `required_sensitive_fields` and `sensitive_field_locations` contain only the unapplied field. |
| S15 | An applied location with a different array index does not satisfy the flagged location | FR-005 | Dyn + Cap | The flagged location remains in `sensitive_field_locations` (EC-14). |
| S16 | Inline secret sentinel `S3cr3t!-14781` never appears in the gate response, captured logs or audit events | FR-004 | Dyn + Cap | Asserted over `json.dumps(response)`, all `caplog` records at every level, and the audit emitter spy: the sentinel string is absent from each. |
| S17 | Host-injected secret is dispatched unchanged at its location | FR-004 | Dyn + Cap | The dispatch stub's `json` argument equals the input body exactly, including the secret at `appdata_source_params.dbPassword`. |
| S18 | Native gate response is unchanged when no connector field is flagged | FR-006, FR-009 | Dyn + Cap | For the existing `/environments` annotated-password case, the response dict equals the pre-change shape exactly. There is no `sensitive_field_locations` key. |
| S19 | Connector-flagged response keeps `required_sensitive_fields` names and adds location entries; a shared leaf name is listed once | FR-006 | Dyn + Cap | Names are de-duplicated in first-seen order (spec names first). The location list has one entry per concrete location (EC-6, EC-7). |
| S20 | Toolkit details timeout / HTTP 500 → warning plus annotation-only fallback, call not blocked | FR-007 | Dyn + Cap, degraded | Exactly one `connector_secrets` warning with `stage=fetch`. The call proceeds to the confirmation gate and dispatch. The native annotated fields inside the uncovered sub-object are still evaluated by the native walker. |
| S21 | Toolkit definition is not a JSON object → warning, call proceeds | FR-007 | Dyn + Cap, degraded | One warning with `stage=parse`. Dispatch occurs. Nothing is cached as a positive entry. |
| S22 | Negative cache: a second call within 60 s makes no new toolkit fetch; after 60 s it refetches | FR-007 | Dyn + Cap, degraded | Toolkit GET count is 1 after two calls inside the window (clock patched) and 2 after advancing the clock by 61 s. |
| S23 | 401/403 negative entry is per identity: caller A's 403 does not suppress detection for caller B | FR-007 | Dyn + Cap (embedded registry) | With two `identity_key` values, B's call still fetches the toolkit and gets gated. |
| S24 | Resolution exceeding the time budget fails open with one `stage=budget` warning | FR-007 | Dyn + Cap, degraded | With `connector_secrets._resolution_budget_s` monkeypatched to 0.2 s and a slow stub (`asyncio.sleep(1)`), the call proceeds within budget plus a small tolerance, and one warning is logged. |
| S25 | Referenced-object lookup fails, but a second chain (e.g. `snapshot_id`) still resolves the toolkit | FR-001, FR-007 | Dyn + Cap | The gate fires using the resolved toolkit. One warning for the failed chain (ERR-3). |
| S26 | Two consecutive calls for the same toolkit fetch the details once | FR-008 | Dyn + Cap | Toolkit GET count is 1. Object GETs are also served from the object cache on the second call. |
| S27 | A toolkit version change is re-derived when the 15-minute binding refreshes | FR-008 | Dyn + Cap | After the clock advances 901 s and the stub returns version `1.1.0` with an extra password field, the next call fetches once more and flags the new field. |
| S28 | Five concurrent first-time calls for the same toolkit produce exactly one toolkit fetch | FR-008 | Dyn + Cap | Under `asyncio.gather` of 5 `execute` calls, toolkit GET count is 1 and all 5 responses are identical gate responses. |
| S29 | LRU caps derived entries at 256 | FR-008 | Python 3.11+ | After 257 distinct toolkit inserts, the first is evicted (a fresh fetch occurs for it). |
| S30 | Native operation on a capture host makes no toolkit lookup | FR-001, FR-009 | Dyn + Cap | For `POST /environments` (annotated password), zero GETs are recorded and the response is unchanged from the pre-change one. |
| S31 | Non-capture client with an inline connector password dispatches as today with no lookup | FR-009 | Dyn + Non-cap | `status == "success"` with zero GETs recorded, and the dispatch body unchanged. |
| S32 | The existing `tests/test_sensitive_input_gate.py` and `tests/integration/test_sensitive_gate_scoping.py` pass unmodified | FR-009 | Dyn + Cap, Dyn + Non-cap | Both suites pass, and `git diff` shows no changes to those files. |
| S33 | Body `toolkit_id` that disagrees with the referenced object's toolkit cannot narrow detection | FR-001 | Dyn + Cap | With a body `toolkit_id` pointing at a toolkit with no password fields and a `source_id` whose toolkit is DB2, the DB2 password is still flagged. Both toolkits are fetched. |
| S34 | `POST /vdbs/empty_vdb` resolves through `GET /environments/{environment_id}` `repositories[id=$]`, and without `environment_id` falls back with a warning | FR-001, FR-007 | Dyn + Cap | With `environment_id`: gate fires using the repository's `toolkit_id`. Without it: one `stage=resolve` warning and annotation-only behaviour. |
| S35 | Discovery `get_operation_schema` for `POST /vdbs/provision_by_snapshot` on a capture host includes the host-captured-secret note | FR-010 | Dyn + Cap | `host_captured_connector_secrets == [{"sub_object": "appdata_source_params", "toolkit_definition": "virtual_source_definition"}, {"sub_object": "appdata_config_params", "toolkit_definition": "source_config_definition"}]`. `description` ends with the note text. Zero DCT requests. |
| S36 | Discovery `get_operation_schema` for the same operation on a non-capture client is byte-identical to pre-change output | FR-010 | Dyn + Non-cap | `json.dumps(result, sort_keys=True)` equals the baseline captured with connector detection disabled. |
| S37 | Mapping loader parses every line, skips malformed lines with a warning, and matches literal before parameterised templates | FR-001 | Python 3.11+ | `match_appdata_operation("POST", "/vdbs/provision_by_snapshot")` returns the provision entry. `("PATCH", "/vdbs/vdb-1")` returns the PATCH VDB entry. `("POST", "/dct/v3/dsources/appdata")` matches. A malformed line logs one warning and is not loaded. |
| S38 | Toolkit-definition lookup accepts snake/camel case, the `parameters`/`schema` wrappers and `discovery_definition.source_config_schema` | FR-002 | DCT toolkit-shape variants | For each variant fixture, the same `SecretPath` set is derived. |
| S39 | Type mismatch (array expected, dict sent) still flags the leaf by a scoped scan | FR-003 | Dyn + Cap | `parameters.nodes` sent as `{"0": {"instancePassword": "x"}}` is flagged at `parameters.nodes["0"].instancePassword`. |
| S40 | Empty sub-object `{}` flags only required, non-conditional top-level passwords, and a non-dict sub-object contributes nothing | FR-003 | Dyn + Cap | `parameters: {}` flags the required top-level password only (EC-2). `parameters: "x"` produces no connector flag and no exception (EC-3). |
| S41 | New and changed code reaches ≥ 80% line coverage | FR-002, FR-003, FR-007, FR-008 | Python 3.11+ | `pytest --cov` reports ≥ 80% for `connector_secrets.py`, `host_trust.py` and the changed lines of `dynamic.py` and `loader.py`. |

## Out of Scope
<!-- Guidance: Scenarios the test plan deliberately skips, with a one-line reason. Pull from vision-doc Non-Goals. -->

- Host-side secure UI rendering and value injection in the DCT AI Assistant (NG1: owned by DLPXECO-14782). Only the server's response contract and its re-call handling are tested.
- Name-heuristic detection for AppData fields (NG2). S9 asserts its absence, but no positive tests are written.
- Any change in behaviour for non-capture-capable clients beyond the "unchanged" assertions (NG3).
- Changes to the native `x-dct-toolkit-credential-field` mechanism (NG4). It is covered only by the unmodified existing suites (S32).
- Validation of connector parameter values against the toolkit schema (NG5).
- Cache persistence across restarts (NG6).
- Confirmation gate, batch grants, floor operations and host-attested approval (NG7). Existing suites cover them unchanged.
- `POST /vdb-groups/provision_from_bookmark` nested AppData params: a documented resolution gap, not tested beyond "no crash, unchanged behaviour".
- Fixed-toolset (`*_endpoints_tool.py`) tools: they have no sensitive gate, so this feature doesn't touch them.

## Test Data Requirements
<!-- Guidance: What data or fixture state must exist before tests run? -->

- `tests/fixtures/toolkits/db2_toolkit.json` contains toolkit details (`id`, `version: "1.0.0"`, `linked_source_definition.parameters`, `virtual_source_definition.parameters`, `virtual_to_physical_definition`, `snapshot_parameters_definition`, `discovery_definition.source_config_schema`). It includes:
  - a required top-level password;
  - an optional password;
  - a nested object password;
  - an array `nodes[*].instancePassword`;
  - non-secret `instanceUser`, `port`, `mountPath`, `instanceId`.
- `tests/fixtures/toolkits/mysql_toolkit.json` covers the same shapes plus a `$ref`-reached password, a `oneOf` alternative-branch password, an `if`/`then` conditional password and a `"format": "Password"` decoy. A camelCase-key variant (`linkedSourceDefinition`, `sourceConfigSchema`) is generated in the test from the same fixture.
- Fixture content is modelled on the published Delphix DB2 and MySQL connector `schema.json` files. Where the real files are available they should be copied into the fixture definitions, keeping the field names; otherwise the documented shapes are hand-crafted.
- Referenced-object fixtures are inline dicts in the test module. Each carries only `id` and `toolkit_id`, `dataset_id`, `dsource_ids`/`vdb_ids` or `repositories[]`:
  - `/sources/{id}`, `/dsources/{id}`, `/vdbs/{id}`;
  - `/snapshots/{id}`, `/timeflows/{id}`;
  - `/bookmarks/{id}`;
  - `/environments/{id}`.
- Test spec: a minimal OpenAPI dict (as in `tests/integration/_gate_helpers.py`) containing the mapped AppData paths, plus `/environments` with an annotated `password` for the native regression cases.
- Each test calls `connector_secrets.clear_caches()` and `loader.clear_cache()` in an autouse fixture, and patches the monotonic clock used by the caches to test TTLs.

## Exit Criteria
<!-- Guidance: How the test phase decides "done". Be specific about pass thresholds. -->

- All Required scenarios PASS on all Required versions
- Smoke suite PASSes (or "first feature in repo — smoke skipped" note)
- No scenario marked SKIPPED without a documented reason
- The existing `tests/` suite (`pytest tests/unit tests/integration tests/test_*.py`) passes with zero modifications to existing assertion files (S32).
- Coverage of new and changed code is ≥ 80% (S41, facts.json `limits.coverage_threshold`).
- No captured log record during the run contains a fixture secret value (S16 also scans the full-run `caplog`).

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/$NAME.spec.* (test-generation phase)
     - Each FR in docs/$NAME/$NAME-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/$NAME/$NAME-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
