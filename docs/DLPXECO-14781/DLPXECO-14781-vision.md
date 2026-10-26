# Vision: DLPXECO-14781

**Jira**: DLPXECO-14781 — dxi-mcp-server: Detect AppData connector credential fields from toolkit schema.json for out-of-band secure capture

## Problem Statement

The MCP server's sensitive-input gate stops a mutating call and asks the embedding host (the DCT AI Assistant) to capture a secret through its masked, out-of-band UI, so the secret never enters the LLM context. The gate only knows a field is a secret when the DCT OpenAPI spec annotates it as a credential field. That covers native Delphix data sources. It does not cover AppData (toolkit/connector-based) sources such as DB2, MySQL, SAP HANA, MongoDB and Couchbase. For those, the DCT API takes the connector parameters as a free-form object, and only the connector's own toolkit schema (`schema.json`, where secrets are declared `"format": "password"`) says which attributes are secrets. As a result, AppData credentials such as a DB2 instance password or a MySQL database-user password are never routed through secure capture. The model asks for them in chat and passes them inline through the LLM context. That is a credential exposure on exactly the host built to prevent it.

## Goals

- G1: Treat every AppData connector parameter declared `"format": "password"` in the toolkit schema (including nested, array-item, combinator and `$ref`-reached properties) as a secret. On a capture-capable host, raise `sensitive_input_required` for it when it is missing or supplied inline.
  Source: facts.json acceptance_criteria[0] — "every connector parameter declared \"format\": \"password\" in the toolkit schema.json triggers sensitive_input_required when missing or supplied inline. This includes nested properties."
- G2: Get AppData connector secrets to DCT through the DCT AI Assistant's secure credential UI without the value entering the LLM context.
  Source: facts.json acceptance_criteria[1] — "The DCT AI Assistant shows the secure credential UI for those fields, and the value reaches DCT without entering the LLM context."
- G3: Let a re-call carrying host-injected connector secrets (authenticated `sensitive_applied`) proceed without re-prompting. Match host-applied fields by location as well as by name.
  Source: facts.json acceptance_criteria[2] and [9] — "Re-calls … via sensitive_applied (valid nonce) succeed and do not re-prompt"; "sensitive_applied.fields … is matched by location as well as by name"
- G4: Report each flagged connector secret's location inside the request (e.g. `appdata_source_params.dbPassword`) in the `sensitive_input_required` response, in addition to the existing field-name list.
  Source: facts.json acceptance_criteria[8] — "sensitive_input_required returns each flagged field's location in the request … alongside today's required_sensitive_fields names"
- G5: Keep the false-positive rate at zero for non-secret connector fields. Leave native operations, non-capture-capable clients and operations whose toolkit schema can't be obtained exactly as they behave today.
  Source: facts.json acceptance_criteria[3], [4], [5], [6] — non-password fields never flagged; native ops unchanged; non-capture clients unchanged; schema failure falls back without blocking
- G6: Let the model know, at discovery time, which AppData connector fields are secrets, so it does not ask the user for them in chat.
  Source: derived — ticket "Proposed Change" item 7 ("Expose it in discovery … mark connector password-format fields as secrets so the model knows not to ask for them in chat"); not captured as a separate facts.json AC

## Non-Goals

- NG1: No change to how secrets are captured, stored or injected by the DCT AI Assistant. The host-side secure UI and its re-call behaviour are owned by the host (the response shape is coordinated with DLPXECO-14782; implementing the host side is out of scope here).
- NG2: No secret detection by name heuristics for AppData fields. A connector field is a secret only when its schema declares `"format": "password"`. A field merely named `password`, `token`, `secret` or similar, with no such declaration, is not flagged.
- NG3: No change to secret handling for non-capture-capable clients (Claude Desktop, Claude Code, VS Code Copilot, other MCP clients). They keep passing credentials inline as today; the gate stays host-scoped.
- NG4: No change to the native credential mechanism (the spec's credential-field annotation and its identity-pairing rule) beyond merging in the new connector-derived set.
- NG5: No validation of connector parameter values against the toolkit schema (types, required properties, enums). DCT remains the validator of the payload; this feature only identifies secrets.
- NG6: No persistence of derived credential sets across server restarts. The cache is in-memory only.
- NG7: No change to the confirmation gate, batch grants, floor operations or host-attested approval flows.

## Success Criteria

- SC1: On a capture-capable host, a DB2 and a MySQL AppData dSource link and AppData VDB provision each return `sensitive_input_required` naming every `"format": "password"` connector field (including nested ones) that is missing or supplied inline. No DCT dispatch happens until the secret is applied.
  Source: facts.json acceptance_criteria[0] — "every connector parameter declared \"format\": \"password\" … triggers sensitive_input_required when missing or supplied inline. This includes nested properties."
- SC2: After the host captures the value and re-calls with an authenticated `sensitive_applied`, the request reaches DCT with the secret applied. The secret appears in no tool result and no model-visible message.
  Source: facts.json acceptance_criteria[1] — "the value reaches DCT without entering the LLM context"
- SC3: A re-call whose `sensitive_applied.fields` (valid nonce) lists the connector field, by name or by location, dispatches on the first re-call, with zero additional `sensitive_input_required` responses for those fields.
  Source: facts.json acceptance_criteria[2] and [9] — "do not re-prompt (no regression of DLPXECO-14603)"; "matched by location as well as by name"
- SC4: For every connector schema in the test fixtures, no field without `"format": "password"` (usernames, ports, paths, ids, mount points) appears in `required_sensitive_fields` or in the location list.
  Source: facts.json acceptance_criteria[3] — "Non-password connector fields (usernames, ports, paths, ids) are never flagged."
- SC5: The existing sensitive-input-gate and gate-scoping test suites (native operations, non-capture-capable clients) pass unmodified.
  Source: facts.json acceptance_criteria[4] and [5] — "Native (non-AppData) operations behave exactly as today"; "Non-capture-capable clients … behave as today"
- SC6: When the toolkit lookup fails (network error, 404, timeout) or returns an unparseable schema, the operation proceeds with spec-annotation-only detection and exactly one warning is logged per failure. The operation is never blocked or errored by the lookup.
  Source: facts.json acceptance_criteria[6] — "the server logs a warning and falls back to spec-annotation-only behaviour. The operation is not blocked."
- SC7: The `sensitive_input_required` response still contains `required_sensitive_fields` (names) unchanged, plus a new location-keyed entry per flagged field (e.g. `appdata_source_params.dbPassword`).
  Source: facts.json acceptance_criteria[8] — "returns each flagged field's location … alongside today's required_sensitive_fields names, which stay for backward compatibility"
- SC8: Unit tests cover the schema walker (nested objects, arrays, `oneOf`/`anyOf`/`allOf`, `$ref`, cycles), path-scoped matching, cache hit/miss/version change and fallback. Integration tests cover at least DB2 and MySQL toolkit schemas. Line coverage of new code is at least 80%.
  Source: facts.json acceptance_criteria[7] — "Unit tests cover the schema walker … Integration tests cover at least DB2 and MySQL toolkits."; coverage threshold from facts.json limits.coverage_threshold
- SC9: Repeated AppData calls for the same toolkit (same id and version) within one server process fetch the toolkit schema at most once.
  Source: derived — facts.json constraints[5] "Cache derived credential set per toolkit (id + version)"
- SC10: Discovery's description of an AppData operation marks each connector `"format": "password"` field as a secret that must not be requested in chat.
  Source: derived — ticket "Proposed Change" item 7 (discovery exposure)

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Shreyas Kulkarni (reporter / assignee) | AppData credentials get the same out-of-band protection as native ones, with no regression of the gate work in DLPXECO-14603/14641/14642/14650 |
| DCT AI Assistant users (DBAs linking/provisioning DB2, MySQL, HANA, MongoDB, Couchbase) | Never typing a database password into a chat that the LLM can see |
| DCT AI Assistant (embedding host) team — DLPXECO-14782 | A stable, backward-compatible `sensitive_input_required` shape that tells them where in the request to inject each captured secret |
| Users of generic MCP clients (Claude Desktop/Code, VS Code Copilot) | No new prompts, deadlocks or blocked operations |
| Security / compliance | Measurable reduction in credentials reaching LLM context and logs |
| Connector (toolkit) authors | Declaring `"format": "password"` in `schema.json` is enough. No extra annotation is required. |

## Constraints

- `required_sensitive_fields` (names) must remain in the `sensitive_input_required` response. Location-keyed data is an addition, not a replacement. (facts.json constraints[0])
- Must not regress DLPXECO-14603: re-calls with authenticated `sensitive_applied` must not re-prompt. (facts.json constraints[1])
- Native credential detection via the spec's `x-dct-toolkit-credential-field` annotation must remain unchanged. (facts.json constraints[2])
- Host scoping from DLPXECO-14642 must remain: the gate fires only for capture-capable hosts. (facts.json constraints[3])
- A toolkit schema fetch/parse failure must fall back to spec-annotation-only detection and must not block the operation. (facts.json constraints[4])
- The derived credential set must be cached per toolkit (id + version). (facts.json constraints[5])
- Connector password fields are matched relative to the AppData parameters sub-object, never globally by name. (facts.json constraints[6])
- Secret values must never be written to logs, audit events, telemetry or any tool result, including warnings emitted on fallback.
- The toolkit lookup must use the server's existing authenticated DCT client and its configured timeout/retry settings. It adds no new credentials, endpoints outside the DCT API, or third-party dependencies.
- Python 3.11+; must follow the project's logging, exception and async conventions.
- The `sensitive_input_required` response shape for location data must be agreed with DLPXECO-14782 before release.
- Added latency on a cache hit must be negligible (in-memory lookup only). On a cache miss it is bounded by at most one toolkit request per toolkit per process lifetime.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| The toolkit cannot be resolved for some AppData operations (e.g. update/refresh calls that reference a dSource/VDB/source config by id with no `toolkit_id` in the body), so their secrets are missed | Medium | High | Resolve from the body first, then by a bounded lookup of the referenced object. Where resolution is impossible, log a warning and fall back (never block). Integration tests enumerate which AppData operations resolve, and gaps are listed in the design. |
| Over-flagging: a connector schema with a generic name (`password`) causes unrelated top-level or native fields to be flagged | Medium | High | Path-scoped matching relative to the AppData parameters sub-object only. Unit tests put same-named fields outside the sub-object and assert they are not flagged. |
| Infinite recursion or blow-up on cyclic or deeply nested `$ref` schemas | Low | Medium | Track visited references and enforce a depth bound in the walker. Unit tests use self-referencing and mutually-referencing schemas. |
| Toolkit fetch adds latency or fails under DCT outage, degrading every AppData call | Medium | Medium | Per-(id, version) cache, the existing client timeout, and failure fallback to annotation-only so the operation still proceeds. Cache only successful parses. |
| Stale cache after a toolkit upgrade adds a new password field | Low | Medium | Key the cache on toolkit id and version, so a version bump produces a new entry. |
| Response-shape mismatch with the host (DLPXECO-14782) means injected values land in the wrong place or are re-flagged | Medium | High | Keep the name list unchanged, add location data additively, match `sensitive_applied.fields` by location and by name, and agree the shape with DLPXECO-14782 before merge. |
| Re-prompt loop regression (DLPXECO-14603) for connector fields the host just injected | Low | High | Remove host-applied fields from the connector set by location and by name before evaluation. Regression test for re-call with a valid nonce. |
| A secret value leaks through a fallback warning, error message or audit event | Low | High | Warnings carry only toolkit id/version and the error class, never request bodies. Tests assert that no secret value appears in captured log output. |
| A model forges a toolkit identifier to suppress detection (e.g. points `toolkit_id` at a toolkit with no password fields) | Low | Medium | Toolkit identity is taken from DCT-side data where the request references an existing object. A forged id that doesn't match the referenced object's toolkit is not trusted to reduce detection, and annotation-based detection still applies. Covered as an edge case in the design. |
| Absent optional or alternative-branch (`oneOf`/`anyOf`) password fields cause spurious secure prompts for credentials the chosen configuration doesn't use, or a too-strict rule misses a needed one | Medium | Medium | Always flag present secrets. Flag absent ones only when required, outside alternative branches, and with their parent present (functional spec Assumptions). Fixture tests over the DB2 and MySQL schemas confirm the expected prompt set. |
| The DCT API key lacks permission to read toolkit details (401/403), silently disabling connector detection for that deployment | Low | Medium | Log a warning on every negative-cache window (not once per process) so the gap is visible to operators. Fall back without blocking. |
| A connector schema declares an entire object or array as `"format": "password"`, and the host can only inject scalars | Low | Low | Flag the whole value at its location. Document the case for DLPXECO-14782. |
| Connector schemas that declare secrets with a non-standard marker (no `"format": "password"`) are still missed | Medium | Low | Out of scope by design (NG2). Documented as a known limitation for connector authors. |

## Assumptions

- The DCT toolkit details response exposes the plugin's definitions (`linked_source_definition`, `virtual_source_definition`, `repository_definition`, `source_config_definition`, `snapshot_parameters_definition`, or their camelCase equivalents) as JSON-schema objects, as the ticket states.
- The AppData parameters sub-objects in request bodies are: `parameters` / `sync_parameters` for AppData dSource link/update, `appdata_source_params` / `appdata_config_params` for AppData VDB provision/update, and `parameters` for AppData source-config create/update. The exact operation-to-sub-object mapping is finalised in the design phase.
- The embedding host can inject a captured secret at a nested location in the body when given that location, which is the purpose of the location data coordinated with DLPXECO-14782.
- A toolkit's version identifies its schema. Two toolkits with the same id and version have the same schema.

---
<!-- Cross-reference: Goals (G1–G6) map to FR descriptions in the functional spec.
     Success Criteria (SC1–SC10) map to Acceptance Criteria in FR-* entries.
     Constraints and Risks inform the Quality Rules and Edge Cases sections. -->
