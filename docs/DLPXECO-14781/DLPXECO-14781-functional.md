# Functional Specification: DLPXECO-14781

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14781
**Generated from**: Acceptance criteria in Jira ticket (via `docs/DLPXECO-14781/DLPXECO-14781-facts.json`) and the ticket's Proposed Change section

**Terminology used throughout**

- **AppData operation**: a mutating (POST/PUT/PATCH) DCT operation whose request body carries toolkit-defined connector parameters. Examples: link/create an AppData dSource, update AppData dSource parameters, provision an AppData VDB, update AppData VDB parameters, create/update an AppData source config.
- **Parameters sub-object**: the key in the request body that holds connector parameters for that operation (e.g. `parameters`, `sync_parameters`, `appdata_source_params`, `appdata_config_params`). Each one is paired with one toolkit definition (`linked_source_definition`, `snapshot_parameters_definition`, `virtual_source_definition`, `source_config_definition`, `repository_definition`).
- **Connector secret**: a property, at any depth of a toolkit definition schema, that declares `"format": "password"`.
- **Location**: a dotted path from the request body root to a field, with concrete array indices, e.g. `appdata_source_params.dbPassword` or `parameters.nodes[1].instancePassword`. The schema-side equivalent uses `[*]` for "any array index" (e.g. `parameters.nodes[*].instancePassword`).
- **Capture-capable host**: the existing host-scoping condition from DLPXECO-14642 (embedded auth mode and the spawn-time sensitive nonce both set). Unchanged by this feature.

---

## FR-001: Resolve the toolkit for an AppData operation

### Description
For a mutating AppData operation, determine which toolkit (id and version) defines the connector parameters in the request, so the connector's secret fields can be derived.

### Input
- method (string, required): HTTP method of the call. Only POST, PUT and PATCH are considered.
- resolved path (string, required): the DCT API path after path-parameter substitution.
- path_params (object, optional): path parameters, e.g. a dSource id or VDB id.
- body (object, optional): the request body.
- capture-capable host flag (boolean, required): result of the existing host-scoping check.

### Processing
1. If the host is not capture-capable, or the method is not POST/PUT/PATCH, stop. No toolkit resolution and no DCT lookup are performed.
2. Determine whether the operation is an AppData operation using a static mapping from operation (method + path template) to its parameters sub-object(s) and the toolkit definition each one is validated against. Operations not in the mapping are not AppData operations; stop.
3. If none of the operation's parameters sub-objects are present in the body, stop. There is nothing to inspect.
4. Collect candidate toolkit identities:
   a. from a toolkit identifier in the body (e.g. `toolkit_id`), if present;
   b. from the DCT object the request references (source config, environment/repository, dSource, VDB, snapshot or bookmark), looked up through the existing authenticated DCT client, where the operation's mapping names such a reference.
5. For each distinct candidate toolkit id, obtain its version from the toolkit details (FR-008 governs caching of the details and derived set).
6. Return the set of resolved (toolkit id, version) pairs, which may be empty.

### Output
- Success: a set of zero or more (toolkit id, toolkit version) pairs, with the mapped parameters sub-object name(s) and definition name(s) for the operation.
- Resolution failure (lookup error, timeout, not found, no identifier available): an empty set plus a warning-level log entry naming the operation and the failure class (FR-007). Never an error returned to the caller.
- Side effect: at most one DCT lookup per referenced object per call. No lookup at all on non-capture-capable hosts or non-AppData operations.

### Acceptance Criteria
- [ ] AC-1: Given a capture-capable host and a POST AppData dSource link body containing a toolkit identifier, when the call is evaluated, then that toolkit's id and version are resolved.
      Source: facts.json acceptance_criteria[0] — "For an AppData operation (e.g. DB2 or MySQL dSource link / VDB provision) on a capture-capable host …"
- [ ] AC-2: Given a capture-capable host and an AppData VDB provision that references a source dSource/snapshot but carries no toolkit identifier, when the call is evaluated, then the toolkit is resolved from the referenced object.
      Source: derived — ticket Proposed Change item 1 ("or from the source/environment/dSource referenced by the request")
- [ ] AC-3: Given a non-capture-capable host, when any AppData operation is evaluated, then no toolkit lookup request is made to DCT.
      Source: facts.json acceptance_criteria[5] — "Non-capture-capable clients … behave as today. The gate stays host-scoped (DLPXECO-14642)."
- [ ] AC-4: Given a native (non-AppData) operation such as an Oracle dSource link, when evaluated on a capture-capable host, then no toolkit lookup is made.
      Source: facts.json acceptance_criteria[4] — "Native (non-AppData) operations behave exactly as today"
- [ ] AC-5: Given the body's toolkit identifier disagrees with the toolkit of the object the request references, when evaluated, then both toolkits are resolved and both credential sets are applied, so detection is never narrowed by a caller-supplied identifier.
      Source: derived — vision Risks ("A model forges a toolkit identifier to suppress detection")

---

## FR-002: Derive connector secret paths from a toolkit definition schema

### Description
Walk a toolkit definition's JSON schema recursively and produce the set of schema-relative paths of every property declared `"format": "password"`.

### Input
- definition schema (object, required): one toolkit definition (e.g. `virtual_source_definition`), as returned by DCT. The schema may sit directly under the definition or under its `parameters` key.
- definition root (object, required): the enclosing document used to resolve local `$ref` pointers (`#/definitions/...`, `#/$defs/...`, `#/properties/...`).

### Processing
1. Start at the schema root with an empty path.
2. For each node:
   a. If the node has `$ref`, resolve it against the definition root. If the reference was already visited on the current branch, stop descending (cycle guard). If it cannot be resolved, skip it and record a walker warning.
   b. For each entry in `properties`: if the property schema (after `$ref` resolution) has `"format": "password"` (exact, case-sensitive string), record `<path>.<property>` together with whether the property is listed in its parent's `required`. Then recurse into the property with that path.
   c. If the node has `items` (an object, or a list for tuple validation), recurse with `<path>[*]`.
   d. If the node has `additionalProperties` or `patternProperties` whose schema contains password-format properties, recurse with `<path>.*` (any key).
   e. For `oneOf`, `anyOf` and `allOf`, recurse into each branch with the same path. Paths from `oneOf`/`anyOf` branches are tagged as conditional (FR-003 uses this for absent-field handling).
3. Enforce a maximum depth of 32 and a maximum of 10,000 visited nodes. On reaching either bound, stop descending that branch and record a walker warning. Paths found so far are kept.
4. Ignore non-object nodes, booleans-as-schemas and unknown keywords without error.
5. Return the de-duplicated set of secret path records.

### Output
- Success: a set of secret path records `{path, required, conditional}`, e.g. `{dbPassword, required=true}`, `{nodes[*].instancePassword, required=false}`. The set may be empty.
- Walker warnings (unresolvable `$ref`, depth/node bound reached): logged at warning level with the toolkit id/version and definition name only. Partial results are still returned.
- Failure (definition is not an object / unparseable): an empty set and a warning. This feeds FR-007's fallback.

### Acceptance Criteria
- [ ] AC-1: Given a definition with a top-level `dbPassword` declared `"format": "password"` and a `dbUser` with no format, when walked, then exactly `dbPassword` is returned.
      Source: facts.json acceptance_criteria[0] and [3] — "every connector parameter declared \"format\": \"password\" … triggers"; "Non-password connector fields … are never flagged"
- [ ] AC-2: Given password-format properties nested in an object, in array `items`, inside `oneOf`/`anyOf`/`allOf` branches, and reached only through `$ref`, when walked, then each is returned with its correct path (`a.b.secret`, `list[*].secret`, etc.).
      Source: facts.json acceptance_criteria[7] — "Unit tests cover the schema walker (nested, arrays, combinators, $ref)"
- [ ] AC-3: Given a self-referencing or mutually referencing `$ref` cycle, when walked, then the walk terminates and returns every password path reachable without repeating the cycle.
      Source: derived — vision Risks ("Infinite recursion … on cyclic or deeply nested $ref schemas")
- [ ] AC-4: Given a property with `"format": "Password"`, `"format": "secret"` or a name like `password` but no format, when walked, then it is not returned.
      Source: derived — vision NG2 (no name heuristics; only the exact SDK convention)
- [ ] AC-5: Given a definition that is a string, null or otherwise not a JSON object, when walked, then an empty set is returned and no exception propagates.
      Source: facts.json acceptance_criteria[6] — "If the toolkit schema can't be … parsed, the server logs a warning and falls back"

---

## FR-003: Gate AppData connector secrets scoped to the parameters sub-object

### Description
On a capture-capable host, flag every connector secret that is supplied inline or required-but-absent, matching only inside the operation's parameters sub-object, and raise `sensitive_input_required` for it exactly as for spec-annotated fields.

### Input
- body (object, required): the request body.
- secret path records per parameters sub-object (from FR-002 via FR-008), keyed by sub-object name.
- host-applied fields (from FR-005): names and locations the host attests it injected.
- spec-annotated credential fields (existing behaviour, unchanged).

### Processing
1. Evaluate the existing spec-annotation detection exactly as today and keep its result (names, first-seen order).
2. For each parameters sub-object present in the body, and each secret path record for it:
   a. Expand the path against the actual body value: `[*]` expands to each existing array index, `.*` to each existing key. This yields concrete locations prefixed with the sub-object name.
   b. **Present**: if the value at a concrete location exists (any value, including empty string or null), flag it as inline-supplied.
   c. **Absent**: if the value does not exist, flag it only when all of these hold:
      - the record is `required`;
      - it is not `conditional` (not only under a `oneOf`/`anyOf` branch);
      - its immediate parent object exists in the body (the sub-object root counts as existing when the sub-object key is present).
      Absent fields under arrays are never flagged, because no index exists to point at.
3. Drop any flagged location that the host attests it applied (FR-005).
4. Never flag a field outside the parameters sub-object because of a connector schema, even if its name matches a connector secret name.
5. Merge the results: final names = spec-annotated names followed by connector secret leaf names not already listed (first-seen order, de-duplicated). Final locations = connector locations (FR-006).
6. If the merged result is non-empty, return `sensitive_input_required` before the confirmation gate and do not dispatch. Otherwise continue to the confirmation gate unchanged.

### Output
- Success (nothing to capture): the call proceeds to the confirmation gate and dispatch as today.
- Gate raised: `{"status": "sensitive_input_required", "required_sensitive_fields": [...names...], <location data per FR-006>, "message": ..., "operation": {...}, "instructions": ...}`. The response never contains any field value.

### Acceptance Criteria
- [ ] AC-1: Given a capture-capable host and a DB2 AppData dSource link whose `parameters` omits a required `"format": "password"` field, when executed, then `sensitive_input_required` is returned naming that field and DCT is not called.
      Source: facts.json acceptance_criteria[0] — "triggers sensitive_input_required when missing"
- [ ] AC-2: Given a capture-capable host and a MySQL AppData VDB provision whose `appdata_source_params` contains a password-format field with a value typed inline by the model, when executed, then `sensitive_input_required` is returned for it and DCT is not called.
      Source: facts.json acceptance_criteria[0] — "… or supplied inline"
- [ ] AC-3: Given a nested password-format field at `parameters.nodes[1].instancePassword` supplied inline, when executed, then it is flagged at that concrete location.
      Source: facts.json acceptance_criteria[0] — "This includes nested properties."
- [ ] AC-4: Given connector fields `dbUser`, `port`, `mountPath`, `instanceId` (no password format) present in the sub-object, when executed, then none of them are flagged.
      Source: facts.json acceptance_criteria[3] — "Non-password connector fields (usernames, ports, paths, ids) are never flagged."
- [ ] AC-5: Given the connector schema declares `password` as a secret and the body also has a top-level or native field named `password` that the spec does not annotate, when executed, then the non-sub-object field is not flagged because of the connector schema.
      Source: facts.json constraints[6] — "Path-scoped matching … relative to the AppData parameters sub-object, not globally by name."
- [ ] AC-6: Given an optional (non-required) or `oneOf`-branch password field that is absent, when executed, then it is not flagged. If it is present, it is flagged.
      Source: derived — avoid over-prompting for secrets the chosen connector configuration does not need (see Assumptions)

---

## FR-004: Keep connector secrets out of the LLM context

### Description
Make sure the gate's response, logs and audit trail give the host what it needs to show its secure credential UI without any connector secret value being exposed to the model.

### Input
- the gate decision from FR-003, including flagged names and locations.
- body (object): may contain an inline secret value.

### Processing
1. Build the `sensitive_input_required` response from field names and locations only. Never copy a body value into it.
2. Keep the existing instructions telling the model not to ask for the value in chat and not to put it in the body.
3. Any log line or audit event emitted for the gate decision records names/locations, toolkit id/version and operation only, never body values.
4. When the host re-calls with the captured value injected at the reported location and an authenticated `sensitive_applied`, the body is dispatched to DCT unchanged (the server does not strip, move or rewrite the injected value).
5. The success response returned to the model after dispatch follows today's shape. The server adds no echo of request body secrets.

### Output
- `sensitive_input_required` response containing no secret value.
- A dispatched DCT request carrying the host-injected secret.

### Acceptance Criteria
- [ ] AC-1: Given a body with an inline connector secret value `S3cr3t!`, when the gate fires, then the string `S3cr3t!` does not appear in the response, in captured log output or in any emitted audit event.
      Source: facts.json acceptance_criteria[1] — "the value reaches DCT without entering the LLM context"
- [ ] AC-2: Given the host re-calls with the secret injected at `appdata_source_params.dbPassword` and a valid `sensitive_applied`, when executed, then the DCT client receives a body containing that value at that location.
      Source: facts.json acceptance_criteria[1] — "The DCT AI Assistant shows the secure credential UI for those fields, and the value reaches DCT"

---

## FR-005: Honour host-applied connector fields by name and by location

### Description
Treat connector secrets that the embedding host injected out-of-band (authenticated `sensitive_applied`) as satisfied, matching each entry by location or by bare name, so a re-call never re-prompts.

### Input
- sensitive_applied (object, optional): `{"nonce": <host secret>, "fields": [<name or location>, ...]}`.
- flagged connector locations from FR-003.

### Processing
1. If the nonce does not authenticate (existing check), host-applied fields are empty. Every flagged field stays flagged (unchanged behaviour).
2. Split `fields` entries into locations (containing `.` or `[`) and bare names.
3. A flagged connector location is satisfied when:
   a. it equals an applied location exactly; or
   b. an applied location equals the flagged location with its sub-object prefix omitted (host reports relative to the sub-object); or
   c. its leaf name equals an applied bare name.
4. Spec-annotated (native) matching keeps working by bare name exactly as today.
5. Remove satisfied fields before deciding whether to raise the gate.

### Output
- The reduced set of flagged fields. When it is empty, the call proceeds to the confirmation gate and dispatch.

### Acceptance Criteria
- [ ] AC-1: Given a re-call with the connector secret present at `appdata_source_params.dbPassword` and `sensitive_applied` (valid nonce) listing `"appdata_source_params.dbPassword"`, when executed, then no `sensitive_input_required` is returned and the call proceeds.
      Source: facts.json acceptance_criteria[9] — "sensitive_applied.fields … is matched by location as well as by name, so injected connector fields are not flagged again."
- [ ] AC-2: Given the same re-call but `sensitive_applied.fields` lists the bare name `"dbPassword"`, when executed, then the call proceeds without re-prompting.
      Source: facts.json acceptance_criteria[2] — "Re-calls with the field supplied via sensitive_applied (valid nonce) succeed and do not re-prompt (no regression of DLPXECO-14603)."
- [ ] AC-3: Given `sensitive_applied` with a wrong or missing nonce listing the connector field, when executed, then the field is still flagged.
      Source: derived — existing nonce trust rule (a model cannot smuggle a secret past the gate)
- [ ] AC-4: Given two connector secrets flagged and the host applied only one, when executed, then `sensitive_input_required` names only the remaining one.
      Source: derived — partial re-call handling

---

## FR-006: Report flagged field locations in `sensitive_input_required`

### Description
Add each flagged field's location in the request to the `sensitive_input_required` response, keeping today's `required_sensitive_fields` name list unchanged, so the host knows where to inject the captured value.

### Input
- flagged spec-annotated names (existing) and flagged connector locations (FR-003, after FR-005).

### Processing
1. Keep `required_sensitive_fields` as a list of bare field names, with the same meaning and ordering rules as today. Connector leaf names are appended de-duplicated.
2. Add a new, additive response key (proposed: `sensitive_field_locations`) listing one entry per flagged connector field: `{"name": <leaf name>, "location": <concrete dotted location>}`.
3. Spec-annotated (native) fields may also be listed with their location where it is known. Their presence in `required_sensitive_fields` is unchanged either way.
4. The exact key name and entry shape must be agreed with DLPXECO-14782 before merge. Whatever is agreed, it is additive only.

### Output
- `sensitive_input_required` response containing `required_sensitive_fields` (unchanged semantics) plus the new location list.

### Acceptance Criteria
- [ ] AC-1: Given an AppData provision missing `appdata_source_params.dbPassword`, when the gate fires, then the response contains `required_sensitive_fields: ["dbPassword"]` and a location entry `{"name": "dbPassword", "location": "appdata_source_params.dbPassword"}`.
      Source: facts.json acceptance_criteria[8] — "sensitive_input_required returns each flagged field's location in the request (e.g. appdata_source_params.dbPassword), alongside today's required_sensitive_fields names"
- [ ] AC-2: Given a native operation that triggers the gate today, when the gate fires, then `required_sensitive_fields` is identical to the current output and every pre-existing response key is unchanged.
      Source: facts.json constraints[0] — "required_sensitive_fields names must remain … new location-keyed fields are additions, not replacements."

---

## FR-007: Fall back to annotation-only detection when the toolkit schema is unavailable

### Description
If the toolkit cannot be resolved, fetched or parsed, log a warning and continue with today's spec-annotation-only detection. Never block or fail the operation because of the toolkit lookup.

### Input
- the outcome of FR-001 (resolution), the toolkit details fetch, and FR-002 (walk).

### Processing
1. Catch every failure from resolution, fetch and parse: connection error, timeout, HTTP 4xx/5xx, missing definition, non-JSON or non-object schema, and unexpected exceptions in the walker.
2. Log one warning per failure, containing the operation (method + path template), toolkit id/version where known, and the failure class or HTTP status. Never include request body values or full response bodies.
3. Use an empty connector secret set for the affected toolkit/definition. Other definitions or toolkits that succeeded still apply.
4. Proceed with spec-annotation detection, the confirmation gate and dispatch exactly as today.
5. Do not cache the failure as a permanent result. A short negative-cache window (60 seconds per toolkit id) prevents hammering DCT during an outage.

### Output
- The operation continues with annotation-only detection. A warning is in the server log.

### Acceptance Criteria
- [ ] AC-1: Given the toolkit details request fails with a timeout or a 500, when an AppData link is executed on a capture-capable host, then a warning is logged and the call is evaluated with annotation-only detection, so it is not blocked.
      Source: facts.json acceptance_criteria[6] — "If the toolkit schema can't be fetched … the server logs a warning and falls back to spec-annotation-only behaviour. The operation is not blocked."
- [ ] AC-2: Given the toolkit details return a definition that is not a JSON object, when executed, then a warning is logged and the operation proceeds.
      Source: facts.json acceptance_criteria[6] — "… or parsed …"
- [ ] AC-3: Given a fetch failure for toolkit T, when a second call for T arrives within 60 seconds, then no new fetch is attempted. After 60 seconds, a new fetch is attempted.
      Source: derived — bounded retry under DCT outage (vision Risks)

---

## FR-008: Cache derived connector secret sets per toolkit id and version

### Description
Cache the derived secret path records per (toolkit id, toolkit version, definition) in memory, so the toolkit schema is not re-fetched or re-walked on every call.

### Input
- toolkit id (string), toolkit version (string, may be absent), definition name.

### Processing
1. Look up the cache by (id, version). On a hit, return the stored secret path records per definition with no DCT request.
2. On a miss, fetch the toolkit details once, walk each relevant definition (FR-002), and store the result. Only store successful parses (failures follow FR-007).
3. Concurrent misses for the same key coalesce into a single fetch. Waiters receive the same result.
4. When the version is absent from toolkit details, key the entry on (id, no-version) with a 15-minute expiry, so an in-place toolkit upgrade is eventually picked up.
5. Bound the cache to 256 entries, evicting least recently used.
6. Where the object-to-toolkit resolution (FR-001 step 4b) needs a lookup, it uses the same client and timeout. Its result may be cached per object id for 15 minutes.

### Output
- Secret path records per definition for the toolkit, from cache or freshly derived.

### Acceptance Criteria
- [ ] AC-1: Given two consecutive AppData calls for the same toolkit id and version, when executed, then the toolkit details are fetched exactly once.
      Source: facts.json constraints[5] — "Cache derived credential set per toolkit (id + version) to avoid re-fetching schema on every call."
- [ ] AC-2: Given a call for toolkit T version 1.0.0 and then one for T version 1.1.0, when executed, then a second fetch occurs and the 1.1.0 secret set is used.
      Source: facts.json acceptance_criteria[7] — "Unit tests cover … caching"
- [ ] AC-3: Given 5 concurrent first-time calls for the same toolkit, when executed, then exactly one toolkit details fetch is made.
      Source: derived — single-flight requirement (vision SC9)

---

## FR-009: Preserve native-operation and host-scoping behaviour

### Description
Native (non-AppData) operations and non-capture-capable clients behave exactly as before the change.

### Input
- any execute call.

### Processing
1. For non-AppData operations, connector detection contributes nothing. Detection is the existing spec-annotation logic (including its identity-pairing rule), unchanged.
2. On non-capture-capable hosts, the sensitive-input gate does not run, no toolkit lookup is made, and no discovery secret marking is added (FR-010).
3. The identity-pairing (username → password) rule is not applied to connector fields. Connector detection is driven only by the schema format.

### Output
- Responses identical to the pre-change behaviour for those calls.

### Acceptance Criteria
- [ ] AC-1: Given the existing sensitive-input-gate unit tests and gate-scoping integration tests, when run against the change, then all pass without modification.
      Source: facts.json acceptance_criteria[4] — "Native (non-AppData) operations behave exactly as today, still driven by x-dct-toolkit-credential-field."
- [ ] AC-2: Given Claude Desktop-style configuration (no sensitive nonce or non-embedded auth mode) and an AppData link with an inline connector password, when executed, then the call dispatches with the inline value as today and no toolkit lookup occurs.
      Source: facts.json acceptance_criteria[5] — "Non-capture-capable clients (Claude Desktop/Code, VS Code Copilot) behave as today. The gate stays host-scoped (DLPXECO-14642)."

---

## FR-010: Mark connector secrets in discovery for AppData operations

### Description
On a capture-capable host, when discovery describes an AppData operation's parameters, tell the model which connector fields are secrets that the host captures, so it does not ask for them in chat.

### Input
- discovery request for an operation schema (operation identified by method + path).
- optional toolkit identifier, if the discovery call supplies one.

### Processing
1. If the host is not capture-capable, or the operation is not an AppData operation, return the operation schema exactly as today.
2. Otherwise add a note to the operation's description. The note says that connector parameters declared `"format": "password"` in the toolkit schema are secrets captured by the host, and must not be requested in chat or placed in the body.
3. If a toolkit can be resolved for the discovery call, list the specific secret locations (from the FR-008 cache, or derived with FR-007 fallback). Otherwise give the generic note only.
4. A discovery-side lookup failure never causes discovery to fail.

### Output
- Operation schema with an added secret note (capture-capable host + AppData operation only). Otherwise unchanged.

### Acceptance Criteria
- [ ] AC-1: Given a capture-capable host, when discovery describes the AppData VDB provision operation, then the response contains a note identifying connector password-format fields as host-captured secrets.
      Source: derived — ticket Proposed Change item 7 ("Expose it in discovery … mark connector password-format fields as secrets so the model knows not to ask for them in chat")
- [ ] AC-2: Given a non-capture-capable host, when discovery describes the same operation, then the response is byte-identical to the pre-change output.
      Source: facts.json acceptance_criteria[5] — "Non-capture-capable clients … behave as today"

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1: API backward compatibility | Every pre-existing key and value in `sensitive_input_required`, and every other execute/discovery response, is unchanged. New data is additive only. | Contract test asserting the full pre-change response for native gate cases; existing suites pass unmodified | | |
| QR-2: No regression of native/host-scoped behaviour | Existing sensitive-input-gate and gate-scoping suites pass with zero edits to their assertions | CI run of the existing unit and integration suites; diff review shows no assertion changes | | |
| QR-3: No secrets in output | No connector secret value appears in any tool response, log line, audit event or telemetry record | Unit test injects a sentinel secret and asserts it is absent from the response and captured logs/audit events | | |
| QR-4: Zero false positives on non-password fields | No field lacking `"format": "password"` is ever flagged by connector detection | Unit tests over DB2 and MySQL fixture schemas assert the exact flagged set | | |
| QR-5: Fail-open on schema unavailability | Toolkit resolution/fetch/parse failures never block or error an operation | Unit tests for timeout, 4xx, 5xx, malformed schema and walker exception, each asserting dispatch proceeds and one warning is logged | | |
| QR-6: Bounded lookup cost | At most one toolkit details fetch per (id, version) per process. No fetch on non-capture-capable hosts or non-AppData operations. | Unit tests count DCT client calls (sequential and concurrent) | | |
| QR-7: Coverage | New and changed code reaches at least 80% line coverage | pytest-cov report in the test phase | | |
| QR-8: Migration path | No configuration, environment variable or host change is required for existing deployments. Hosts that ignore the new location key keep working by name. | Integration test with a host that matches by name only | | |
| QR-9: Project conventions | New code uses the project logger helper, raises project exception types (no bare `Exception`), sends HTTP through the existing DCT client, and adds no third-party dependency | Code review checklist; grep for `logging.getLogger` and new imports in the diff | | |

---

## Edge Cases

- EC-1: AppData operation body has no parameters sub-object at all → connector detection contributes nothing. DCT validates the payload as today.
- EC-2: Parameters sub-object is present but empty (`{}`) → only required, non-conditional, top-level password fields are flagged as absent.
- EC-3: Parameters sub-object is not an object (string, list, null) → connector detection contributes nothing for it. No exception is raised.
- EC-4: Connector secret is present with an empty string or null value → treated as present-inline and flagged, consistent with "never supplied inline by the model".
- EC-5: Array parameter with 3 items, each with a password field, and 2 of them supplied inline → exactly those 2 concrete locations (`list[0]…`, `list[2]…`) are flagged. The absent one is not.
- EC-6: Connector schema declares the same leaf name (`password`) at two different paths → each present instance is reported at its own location. `required_sensitive_fields` lists the name once.
- EC-7: Spec annotation and connector schema both flag a field with the same leaf name → the name appears once in `required_sensitive_fields`. The connector location is still listed.
- EC-8: Toolkit has no password-format fields at all (e.g. a connector that uses environment users) → connector detection contributes nothing. The result is cached, so no re-fetch occurs.
- EC-9: Schema uses `$ref` to a definition missing from the document → that branch is skipped with a warning. Other branches are still walked.
- EC-10: Very large or deeply nested schema exceeding the depth/node bounds → the walk stops at the bound with a warning. Paths found so far are used.
- EC-11: Body supplies a toolkit identifier that doesn't exist in DCT (404) → warning plus fallback for that toolkit. A toolkit resolved from a referenced object is still applied.
- EC-12: Two concurrent calls for a toolkit not yet cached → one fetch. Both calls see the same derived set.
- EC-13: Toolkit upgraded in DCT while the server is running (new version) → the next call resolves the new version and derives a new set. The old entry ages out of the LRU.
- EC-14: `sensitive_applied.fields` contains a location with a different array index than the flagged one → not treated as satisfied. That field is still flagged.
- EC-15: PATCH update of AppData VDB/dSource parameters that sends only a subset of connector parameters → only present secrets are flagged inline. Absent required ones are flagged only when their parent object is present in the patch body.
- EC-16: Property schema declares `"format": "password"` together with `"type": "array"` or `"type": "object"` → flagged as a whole at its location (the host captures the entire value). The walker does not descend for further flags under it.

## Error Scenarios

- ERR-1: DCT unreachable or timing out during toolkit fetch → warning logged, 60-second negative cache entry, annotation-only detection, and the operation proceeds. Recovery: the next call after the window retries the fetch.
- ERR-2: Toolkit details return HTTP 401/403 (API key lacks permission to read toolkits) → warning logged once per negative-cache window. Fallback as ERR-1. The operation itself still goes to DCT, which applies its own authorisation.
- ERR-3: Referenced object lookup (dSource/VDB/source config) fails during resolution → that toolkit candidate is dropped with a warning. Other candidates (e.g. body toolkit identifier) are still used.
- ERR-4: Walker raises an unexpected exception on a malformed schema → caught, warning logged, empty set for that definition, not cached. The operation proceeds.
- ERR-5: Gate fires but the host never re-calls (user abandons the secure prompt) → no state is held server-side beyond the cache. Nothing to roll back.
- ERR-6: Host re-calls with the value injected at a location that does not match the schema path (e.g. wrong nesting) → the flagged location is still unsatisfied, so the gate fires again with the expected location. No partial dispatch happens, so there is nothing to roll back.
- ERR-7: Partial failure across multiple definitions or toolkits (one fetch succeeds, one fails) → apply what succeeded and fall back for what failed. Never discard successful results because of an unrelated failure.
- Rollback strategy: the feature is purely additive in the request path and holds only in-memory state. Reverting the change restores annotation-only behaviour with no data migration. No configuration flag is required for rollback.

## Performance Considerations

- Cache hit path: in-memory lookup plus a body walk proportional to the size of the parameters sub-object. Target under 5 ms p99 added to an execute call.
- Cache miss path: one toolkit details request (plus at most one referenced-object lookup) bounded by the existing DCT client timeout and retry settings (`DCT_TIMEOUT`, default 30 s). This occurs at most once per (toolkit id, version) per process.
- No added DCT requests on non-capture-capable hosts, for non-mutating methods, or for non-AppData operations.
- Cache bounded to 256 toolkit entries (LRU). Negative cache is 60 seconds per toolkit id. Object-to-toolkit resolution cache is 15 minutes.
- Walker bounded to depth 32 and 10,000 visited nodes per definition, so a pathological schema cannot exhaust CPU or memory.
- Concurrent misses for the same toolkit coalesce into one fetch.

## Assumptions

- FR-003: "Missing" in facts.json acceptance_criteria[0] is interpreted as "absent and required by the connector schema at a level whose parent object is present, outside `oneOf`/`anyOf`-only branches". Prompting for optional or alternative-branch secrets the user's chosen configuration doesn't need would cause spurious prompts. Present password fields are always flagged, regardless of required-ness.
- FR-001: The exact operation-to-sub-object-to-definition mapping, and which referenced object yields the toolkit for each operation, is finalised in the design phase from the bundled DCT OpenAPI spec. The baseline is the mapping already used for toolkit schema hints (`parameters`/`sync_parameters` for dSource link/update, and `appdata_source_params`/`appdata_config_params` for VDB provision).
- FR-002: The DCT toolkit details response exposes each definition either as a JSON schema or as an object with a `parameters` JSON schema. Both shapes are handled.
- FR-006: The new response key name (`sensitive_field_locations`) and entry shape are proposals pending agreement with DLPXECO-14782.
- FR-008: Toolkit `version` (or the equivalent build/version field in toolkit details) uniquely identifies a schema revision.
- FR-010: Discovery marking applies only on capture-capable hosts. On other clients the model must still collect the credential inline (the deliberate DLPXECO-14642 trade-off), so telling it not to ask would deadlock the operation.

---
<!-- Cross-reference: FR descriptions map to vision Goals (G1→FR-001/002/003, G2→FR-004, G3→FR-005, G4→FR-006, G5→FR-007/009, G6→FR-010; caching→FR-008).
     FR Acceptance Criteria satisfy vision Success Criteria SC1–SC10.
     FR-IDs defined here are referenced in tasks-template (Spec References) and validation-template (FR Coverage). -->
