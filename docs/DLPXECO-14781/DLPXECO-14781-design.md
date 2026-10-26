# Feature Design: DLPXECO-14781

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14781
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

---

## Summary
<!-- Guidance: One paragraph (3–5 sentences). What this feature does, who it is for, why it is being built now. Avoid implementation detail — that belongs in Architecture Changes below. -->

This feature extends the dynamic-mode `execute` sensitive-input gate. On a host that can capture secrets out-of-band (the DCT AI Assistant), it now also recognises AppData connector secrets: every connector parameter that the toolkit's own schema declares `"format": "password"`. Those secrets are routed through the host's secure UI instead of the LLM context. Today the gate only knows fields that the DCT OpenAPI spec annotates with `x-dct-toolkit-credential-field`. AppData connector parameters (DB2, MySQL, HANA, MongoDB, Couchbase, …) travel inside free-form objects (`parameters`, `sync_parameters`, `appdata_source_params`, `appdata_config_params`, `appdata_parameters`, `appdata_v2p_params`), so their passwords pass through chat in plain text. The change does four things:
- resolves the toolkit behind each AppData operation;
- derives and caches that toolkit's password-format paths;
- gates them by location, scoped to the parameters sub-object;
- reports each flagged field's location alongside the unchanged `required_sensitive_fields` name list.

Native operations, non-capture-capable clients and toolkit-lookup failures behave exactly as they do today.

## Affected Components
<!-- Guidance: Render the component checklist from .claude/architecture.md. Tick `[x]` for components this feature changes; leave `[ ]` for the rest. Do not invent components — only those listed in architecture.md may appear here. -->

- [ ] `main.py` — entry point, lifespan (unchanged)
- [ ] `toolsgenerator/driver.py` — OpenAPI tool generation (unchanged; its `ACTIONS_REQUIRING_TOOLKIT_SCHEMA` hint table was the starting point for the new mapping file)
- [ ] `tools/__init__.py` — dynamic tool registration (unchanged)
- [ ] `tools/core/meta_tools.py` — retained spec helpers (unchanged)
- [ ] `tools/core/tool_factory.py` — runtime tool generation (unchanged)
- [x] `tools/core/dynamic.py` — dynamic mode `discovery` + `execute`, Step 3.5 sensitive-input gate (gate extended, discovery note, response key added)
- [x] `tools/core/` (new modules) — `tools/core/connector_secrets.py` (AppData connector-secret detection) and `tools/core/host_trust.py` (shared nonce check moved from `dynamic.py`)
- [ ] `tools/core/confirmation_token.py` — single-use tokens (unchanged; the gate runs before confirmation)
- [ ] `tools/core/confirmation_store.py` — ConsumedTokenStore + GrantStore (unchanged)
- [ ] `tools/core/confirmation_levels.py` — level validation (unchanged)
- [ ] `tools/core/confirmation_resolver.py` — fallback/velocity routing (unchanged)
- [ ] `tools/core/audit.py` — gate-event emitter (unchanged; the sensitive gate emits no audit events today and still doesn't, per NG7)
- [ ] `tools/core/floor_operations.py` — floor operations (unchanged)
- [ ] `tools/core/velocity_counter.py` — velocity counter (unchanged)
- [ ] `tools/*_endpoints_tool.py` — pre-built grouped tools (unchanged; they have no sensitive gate)
- [ ] `config/config.py` — env var loading (unchanged; no new env vars)
- [x] `config/loader.py` — mapping-file parsing (new `load_appdata_operations()` / `match_appdata_operation()`, plus `clear_cache()` wiring)
- [x] `config/mappings/*` — new `appdata_operations.txt` mapping (operation → parameters sub-object → toolkit definition → toolkit resolver chain)
- [ ] `config/toolsets/*.txt` — persona toolsets (unchanged)
- [ ] `dct_client/client.py` — async HTTP client (reused unchanged for toolkit and referenced-object lookups)
- [ ] `testing/cli.py` — dct-mcp-test CLI (unchanged)
- [x] `core/` infrastructure — `core/client_registry.py` gains a public, stable `identity_key(auth_ctx)` for cache keying. `logging.py`, `session.py`, `decorators.py` and `exceptions.py` are reused unchanged.

## Architecture Changes

### Schema / Config Changes
<!-- Guidance: Every change to schema files, config formats, or persisted state shapes. Include the field path, type, sensitivity flag (if a credential), and which object it lives under. If your project has no schema layer, write "None." -->

| Field / Artifact | Type | Object | Notes |
|------------------|------|--------|-------|
| `sensitive_field_locations` | array of `{"name": str, "location": str}` | `execute` → `sensitive_input_required` response | **New, additive** (FR-006). Present only when at least one connector secret is flagged, so native-only gate responses stay byte-identical (FR-006 AC-2). `name` = leaf property name. `location` = concrete dotted path from the body root with integer array indices, e.g. `appdata_source_params.dbPassword` or `parameters.nodes[1].instancePassword`. A key that is not a plain identifier (`^[A-Za-z_][A-Za-z0-9_\-]*$`) is rendered as a JSON-quoted bracket segment, e.g. `parameters["db.pass"]`. Never carries a value. The key name is a proposal pending agreement with DLPXECO-14782. |
| `required_sensitive_fields` | array of str | `execute` → `sensitive_input_required` response | **Semantics unchanged.** Spec-annotated names first (today's first-seen order), then connector leaf names not already listed, de-duplicated (FR-003 step 5, EC-6, EC-7). |
| `sensitive_applied.fields[]` | str | `execute` input (host only) | **Accepted values widened, shape unchanged.** An entry containing `.` or `[` is treated as a location, otherwise as a bare name (FR-005). Nonce authentication is unchanged. |
| `host_captured_connector_secrets` | array of `{"sub_object": str, "toolkit_definition": str}` | `discovery(action="get_operation_schema")` response | **New, additive** (FR-010). Emitted only on a capture-capable host for a mapped AppData operation. A matching note is appended to that response's `description`. |
| `config/mappings/appdata_operations.txt` | text mapping file | package data | **New.** Grammar and full content below. Loaded once with `@lru_cache` by `load_appdata_operations()`. |
| In-memory connector-secret caches | process state | `connector_secrets` module | **New, not persisted** (NG6). See "Caching and concurrency" for keys and TTLs. |

**Mapping file grammar (`appdata_operations.txt`)**

```
# Blank lines and lines starting with # are ignored. Malformed lines are skipped with a warning.
#
# Directive (exactly one):
#   @toolkit|<GET path with {id}>                  -> toolkit details endpoint
#
# Operation line:
#   METHOD|path_template|sub_object:definition[,sub_object:definition...]|chain[;chain...]
#
#   definition ∈ linked_source_definition | snapshot_parameters_definition |
#                virtual_source_definition | virtual_to_physical_definition |
#                source_config_definition
#
#   chain  := source ( ">" hop )*
#   source := "body:" field | "path:" param           -> the starting id (string); chain skipped if absent/non-string
#   hop    := get_path ( "^" get_path )* [ "." select ]
#     get_path : a GET path; "{id}" is replaced by the current id; "{body.<field>}" by a body string field
#                (chain skipped if that field is absent). Alternatives separated by "^" are tried in order;
#                a 404 moves to the next alternative, any other error ends the chain.
#     select   : field            -> next id = response[field]
#              | field "[" n "]"  -> next id = response[field][n]
#              | field "[id=" "$" "]" -> next = the element of list response[field] whose "id" equals
#                                       the id that entered this hop; its "toolkit_id" ends the chain
#   A hop with no select ends the chain: toolkit id = response["toolkit_id"].
#   A chain consisting only of "body:toolkit_id" uses that value as the toolkit id directly.
```

**Full mapping content.** There is one file line per table row. `SRC` is shorthand used only in this table; the file spells it out in full as `appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition`. "Same as the line above" means the identical sub-object list, `appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition`.

| METHOD | path_template | sub-objects | chains (in file syntax) |
|--------|---------------|-------------|-------------------------|
| POST | `/dsources/appdata` | `parameters:linked_source_definition,sync_parameters:snapshot_parameters_definition` | `body:toolkit_id;body:source_id>/sources/{id}` |
| PATCH | `/dsources/appdata/{dsourceId}` | `parameters:linked_source_definition` | `body:toolkit_id;path:dsourceId>/dsources/{id}` |
| POST | `/dsources/{dsourceId}/snapshots` | `appdata_parameters:snapshot_parameters_definition` | `path:dsourceId>/dsources/{id}` |
| POST | `/vdbs/provision_by_snapshot` | SRC | `body:toolkit_id;body:source_data_id>/dsources/{id}^/vdbs/{id};body:snapshot_id>/snapshots/{id}.dataset_id>/dsources/{id}^/vdbs/{id}` |
| POST | `/vdbs/provision_by_timestamp` | SRC | `body:toolkit_id;body:source_data_id>/dsources/{id}^/vdbs/{id};body:timeflow_id>/timeflows/{id}.dataset_id>/dsources/{id}^/vdbs/{id}` |
| POST | `/vdbs/provision_by_location` | SRC | `body:toolkit_id;body:source_data_id>/dsources/{id}^/vdbs/{id};body:timeflow_id>/timeflows/{id}.dataset_id>/dsources/{id}^/vdbs/{id}` |
| POST | `/vdbs/provision_from_bookmark` | SRC | `body:toolkit_id;body:bookmark_id>/bookmarks/{id}.dsource_ids[0]>/dsources/{id};body:bookmark_id>/bookmarks/{id}.vdb_ids[0]>/vdbs/{id}` |
| POST | `/vdbs/empty_vdb` | SRC | `body:toolkit_id;body:repository_id>/environments/{body.environment_id}.repositories[id=$]` |
| PATCH | `/vdbs/{vdbId}` | SRC | `body:toolkit_id;path:vdbId>/vdbs/{id}` |
| POST | `/sources/appdata` | `parameters:source_config_definition` | `body:toolkit_id;body:repository_id>/environments/{body.environment_id}.repositories[id=$]` |
| PATCH | `/sources/appdata/{sourceId}` | `parameters:source_config_definition` | `body:toolkit_id;path:sourceId>/sources/{id}` |
| POST | `/dsources/{dsourceId}/export-by-snapshot` | `appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition` | `path:dsourceId>/dsources/{id}` |
| POST | `/dsources/{dsourceId}/export-by-timestamp` | same as the line above | `path:dsourceId>/dsources/{id}` |
| POST | `/dsources/{dsourceId}/export-by-location` | same as the line above | `path:dsourceId>/dsources/{id}` |
| POST | `/dsources/{dsourceId}/export-from-bookmark` | same as the line above | `path:dsourceId>/dsources/{id}` |
| POST | `/vdbs/{vdbId}/export-by-snapshot` | same as the line above | `path:vdbId>/vdbs/{id}` |
| POST | `/vdbs/{vdbId}/export-by-timestamp` | same as the line above | `path:vdbId>/vdbs/{id}` |
| POST | `/vdbs/{vdbId}/export-by-location` | same as the line above | `path:vdbId>/vdbs/{id}` |
| POST | `/vdbs/{vdbId}/export-from-bookmark` | same as the line above | `path:vdbId>/vdbs/{id}` |

The directive line is `@toolkit|/toolkits/{id}`. The mapping was verified against DCT spec 3.31.0:
- `DSource`, `VDB`, `Source` and `Repository` expose `toolkit_id`.
- `Snapshot` and `Timeflow` expose `dataset_id`.
- `Bookmark` exposes `dsource_ids`/`vdb_ids`.
- `Environment.repositories[]` items are `Repository` objects.
- There is no `GET /environments/{environmentId}/repository/{repositoryId}`, so repository resolution goes through `GET /environments/{id}`.

`body:toolkit_id` is listed first on operations where a model might add it. No mapped request body defines `toolkit_id`, so it is an optional extra id and never the only chain. All chains are unioned (FR-001 AC-5).

ASM `export-*` operations (Oracle-only) are excluded. `POST /vdb-groups/provision_from_bookmark` nests `appdata_source_params` under `provision_parameters.<vdb_id>`, which the top-level sub-object model does not cover. It is a known gap (see Open Questions / Risks).

**Toolkit-definition lookup** (`definition` name → schema document inside the `GET /toolkits/{id}` response). Each key is tried in snake_case, then camelCase. The first entry that is a JSON object wins.

| Logical definition | Toolkit response key(s), in order | Schema inside the definition |
|--------------------|-----------------------------------|------------------------------|
| `linked_source_definition` | `linked_source_definition` | `.parameters` if it is a dict schema, else the definition itself |
| `virtual_source_definition` | `virtual_source_definition` | `.parameters` if it is a dict schema, else the definition itself |
| `virtual_to_physical_definition` | `virtual_to_physical_definition` | `.parameters` if it is a dict schema, else the definition itself |
| `snapshot_parameters_definition` | `snapshot_parameters_definition`, then `snapshot_schema` | `.schema`, then `.parameters`, else the definition itself |
| `source_config_definition` | `discovery_definition.source_config_schema`, then `source_config_definition` | the value itself |

The DCT 3.31 spec's `Toolkit` model has no `source_config_definition` property. The source-config schema is exposed through `discovery_definition`, which corrects the vision's assumption. The selected schema document is also the `$ref` resolution root (`#/definitions/…`, `#/$defs/…`, `#/properties/…`).

### Source Files to Modify
<!-- Guidance: One row per file. The path must exist in the repo (check-structure.sh cross-references these rows against git status during the implement phase). Group by component. The "Purpose" column says what changes in that file. -->

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/tools/core/dynamic.py` | Step 3.5 gate wiring (see "Gate flow" below). Changes:<br>- Call `connector_secrets.find_flagged_connector_secrets(...)` on capture-capable hosts for POST/PUT/PATCH.<br>- Run the native walker on a body view that excludes the connector sub-objects connector detection covered.<br>- Add applied-location leaf names to the native applied-name set.<br>- Merge leaf names into `required_sensitive_fields`, and add `sensitive_field_locations` only when non-empty.<br>- Extract the Step 7 `ClientRegistry`/`resolve_auth()` client selection into `_resolve_client(dct_client) -> tuple[DCTAPIClient, str]`, which returns `(client, identity)`. In embedded mode that is `(registry.get_client(auth), registry.identity_key(auth))`; in standalone mode it is `(dct_client, "standalone")`. Both the gate and dispatch use it, and dispatch ignores the identity.<br>- Move `_host_nonce_ok` and `_SENSITIVE_NONCE_ENV` into `host_trust.py`, re-importing them under the same names so existing imports and tests keep working.<br>- In `discovery`, after a successful `_action_get_operation_schema(...)` on a capture-capable host for a mapped AppData operation, append the host-captured-secret note to `description` and add `host_captured_connector_secrets`. This does no I/O. | FR-001, FR-003, FR-004, FR-005, FR-006, FR-007, FR-009, FR-010 |
| `src/dct_mcp_server/config/loader.py` | Add `@lru_cache(maxsize=1) load_appdata_operations()`, which parses `config/mappings/appdata_operations.txt` into immutable `AppDataOperation(method, path_template, sub_objects, chains)` records and the `@toolkit` path. Add `match_appdata_operation(method, path)`, which reuses `_path_matches`, strips a leading `/dct/v3`, and prefers literal templates over parameterised ones. Malformed lines produce a warning and are skipped, never raised. Add `load_appdata_operations.cache_clear()` to `clear_cache()`. | FR-001, FR-009, FR-010 |
| `src/dct_mcp_server/core/client_registry.py` | Add a public method `ClientRegistry.identity_key(self, auth_ctx) -> str` that returns `self._identity_hash(auth_ctx)`, a stable hash that is never logged raw. The connector caches use it to key per-caller entries. | FR-001, FR-007, FR-008 |
| `src/dct_mcp_server/tools/core/connector_secrets.py` | New file. AppData connector-secret detection: walker, definition lookup, caches, resolver chains, path expansion and present/absent rules, applied-field matching, and the fail-open, time-budgeted `find_flagged_connector_secrets` entry point (see "New Files" and "Detailed design notes"). | FR-001, FR-002, FR-003, FR-004, FR-005, FR-007, FR-008 |
| `src/dct_mcp_server/tools/core/host_trust.py` | New file. `_SENSITIVE_NONCE_ENV` and `host_nonce_ok(marker)`, moved verbatim from `dynamic.py`, so that both `dynamic.py` and `connector_secrets.py` can use them without a circular import. | FR-005, FR-009 |
| `src/dct_mcp_server/config/mappings/appdata_operations.txt` | New file. The AppData operation → sub-object → toolkit definition → resolver-chain mapping and the `@toolkit` directive (full content above). | FR-001, FR-010 |
| `CLAUDE.md` | Document AppData connector-secret detection under the confirmation/sensitive-gate section. Add the new mapping file, `connector_secrets.py` and `host_trust.py` to Key Source Layout, and describe the additive `sensitive_field_locations` response key. | FR-003, FR-006 |
| `.claude/architecture.md` | Add `tools/core/connector_secrets.py`, `tools/core/host_trust.py` and `config/mappings/appdata_operations.txt` to the Layer Map. Add a "Key Platform Behaviors" bullet: AppData secret detection is capture-host-only, fail-open, time-budgeted, with in-memory caches only. | FR-002, FR-007, FR-008 |

### New Files (if any)
<!-- Guidance: Path + one-line purpose. check-structure.sh does not cross-reference this list mechanically — it is purely for review readability. If no new files, write "None." -->

- `src/dct_mcp_server/tools/core/connector_secrets.py` — AppData connector-secret detection. Its public API is listed under "Module API" in Detailed design notes. It uses `get_logger(__name__)`, only stdlib plus project modules, and catches `DCTClientError` and any other exception at its public entry point.
- `src/dct_mcp_server/tools/core/host_trust.py` — shared nonce trust check (`host_nonce_ok`, `_SENSITIVE_NONCE_ENV`), moved from `dynamic.py`.
- `src/dct_mcp_server/config/mappings/appdata_operations.txt` — static AppData operation mapping (content above).
- `tests/unit/test_connector_secrets.py` — walker, path expansion/present-absent rules, location rendering, applied-field matching, caches, definition-key lookup variants, resolver chains, time budget.
- `tests/unit/test_appdata_operations_loader.py` — mapping parser, malformed-line tolerance, `match_appdata_operation()`.
- `tests/integration/test_appdata_secret_gate.py` — end-to-end through the real `execute`/`discovery` closures with a routing stub for `make_request`, using the DB2 and MySQL fixtures.
- `tests/fixtures/toolkits/db2_toolkit.json` — DB2 toolkit details fixture. It contains password-format fields at top level, nested, in arrays, and under `virtual_to_physical_definition` and `discovery_definition.source_config_schema`, alongside non-secret `instanceUser`, `port`, `mountPath` and `instanceId` fields.
- `tests/fixtures/toolkits/mysql_toolkit.json` — MySQL toolkit details fixture covering the same shapes, plus a `$ref`-reached password, a `oneOf` alternative-branch password and an `if`/`then` conditional password.

### Alternatives Considered
<!-- Guidance: One row per rejected approach: the option, its trade-off, and why it was rejected in favor of the chosen design above. If nothing substantive was considered and rejected, write "None." -->

| Option | Trade-off | Why rejected |
|--------|-----------|---------------|
| Name heuristics inside the parameters sub-object (`*password*`, `*secret*`, `*token*`) | No toolkit lookup, no network cost, no cache | Explicitly excluded by NG2. It also over-flags (e.g. `passwordPolicy`) and misses secrets with non-obvious names. DLPXECO-14641 showed that name-derived secrets cause phantom prompts that block operations. |
| Match connector secret leaf names globally across the whole body (extend `_annotated_credential_fields` with the toolkit's names) | Minimal code: one set union with the existing name-based walker | Violates the path-scoping constraint (facts.json constraints[6]). A connector `password` would flag a top-level/native `password` the spec doesn't annotate (FR-003 AC-5). The name-only walker also can't produce locations (FR-006) or apply the required/conditional absent-field rule. |
| Fetch `GET /toolkits/{id}` on every AppData call with no cache | Always fresh; no cache invalidation logic | Violates facts.json constraints[5] and SC9, and adds DCT latency to every AppData call. |
| Key the cache on `toolkit_id` alone (no version) | One fewer lookup to learn the version | A toolkit upgrade that adds a password field is missed until restart (EC-13, vision risk "stale cache"). |
| Validate the full connector payload against the toolkit schema with a JSON-schema library | Would reuse a mature `$ref`/combinator implementation | NG5 (DCT stays the validator). It would add a third-party dependency (QR-9), and a validator reports violations, not "which properties are password-format", so a custom walker is still needed. |
| Put detection in the pre-built `*_endpoints_tool.py` grouped tools as well | Covers fixed-toolset mode | The sensitive gate exists only in dynamic `execute` today, and the DCT AI Assistant (the only capture-capable host) uses dynamic mode. Adding a gate to fixed toolsets is a separate change, out of scope here. |
| Resolve `toolkit_id` only from the body and trust it | No referenced-object lookup | No mapped AppData request body defines `toolkit_id`. Trusting a body id alone would also let a forged id narrow detection (FR-001 AC-5). |
| Static AppData operation table as a Python dict in `connector_secrets.py` | Simpler loading; type-checked | The project rule "do not inline DCT API paths as raw strings in tool functions — paths come from config files resolved through `config/loader.py`" applies. The mapping file follows the existing `floor_operations.txt`/`read_exclusions.txt` pattern and can be extended without code changes. |
| Add an optional `toolkit_id` argument to `discovery` so it can list concrete secret locations | More precise discovery output (FR-010 step 3) | It changes the `discovery` tool signature for every client, including non-capture-capable ones (FR-010 AC-2), and `discovery` is a sync function that can't await a DCT lookup. Discovery gives the generic per-sub-object note. Concrete locations are returned by the gate in `sensitive_field_locations`. |
| Keep the native walker scanning connector sub-objects unchanged | Zero change to the native code path | When the host reports a connector secret only by location, the native walker re-flags an annotated leaf name such as `password` forever (DLPXECO-14603 regression). Identity pairing could also invent a location-less `password` for a connector `username`, which contradicts FR-009 step 3. Excluding the sub-objects that connector detection covered fixes both. |

#### Detailed design notes (normative for implement)

**Module API (`connector_secrets.py`)**
- `SecretPath(path: str, required: bool, conditional: bool)` (frozen dataclass);
- `FlaggedLocation(name: str, location: str)`;
- `ConnectorResult(flagged: list[FlaggedLocation], covered_sub_objects: frozenset[str])`;
- `walk_secret_paths(schema: Any, root: dict | None = None, *, context: str = "") -> frozenset[SecretPath]`;
- `ToolkitSecretCache.get(client, identity: str, toolkit_id: str, context: str) -> dict[str, frozenset[SecretPath]] | None` (async; `None` = failure/fallback);
- `async resolve_toolkit_ids(client, identity: str, op: AppDataOperation, path_params: dict, body: dict) -> set[str]`;
- `expand_and_flag(sub_object: str, value: Any, records: frozenset[SecretPath]) -> list[FlaggedLocation]`;
- `parse_applied(sensitive_applied: Any) -> tuple[frozenset[str], frozenset[str]]` (names, locations);
- `drop_applied(flagged: list[FlaggedLocation], names: frozenset[str], locations: frozenset[str]) -> list[FlaggedLocation]`;
- `async find_flagged_connector_secrets(...)` (signature in Gate flow step 1);
- `clear_caches() -> None`, for tests.

**Gate flow (Step 3.5; capture-capable host; POST/PUT/PATCH only — otherwise Step 3.5 is byte-identical to today)**
1. `result = await connector_secrets.find_flagged_connector_secrets(client_resolver: Callable[[], tuple[DCTAPIClient, str]], method: str, resolved_path: str, path_params: dict, body: dict | None, sensitive_applied: Any) -> ConnectorResult`. `client_resolver` is `lambda: _resolve_client(dct_client)`. It returns `ConnectorResult(flagged: list[FlaggedLocation(name, location)], covered_sub_objects: frozenset[str])` and never raises.
   1. `op = match_appdata_operation(method, resolved_path)`. If there is none, return an empty result without any lookup (FR-001 AC-4, FR-009).
   2. Keep only the mapped sub-objects present in the body as dicts. If none remain, return empty without a lookup (EC-1, EC-3).
   3. `client, identity = client_resolver()`. The client is the same one dispatch uses, and `identity` keys every per-caller cache entry. It is called lazily, only after steps 1–2 found work to do, and a failure inside it is a `stage=resolve` fallback.
   4. Run all resolver chains **concurrently** (`asyncio.gather`), then union and de-duplicate the toolkit ids (FR-001 AC-5). Each chain fails independently: it is dropped with one warning (ERR-3) and the others still apply. A 404 on a `^` alternative moves on silently. Each referenced object is fetched at most once per call. A 404 probe on a `^` alternative (e.g. `/dsources/{id}` before `/vdbs/{id}` for a dataset id) is an identification step, not a second lookup of the same object, so it is the one intentional relaxation of FR-001's "one lookup per referenced object".
   5. For each toolkit id, `await cache.get(client, identity, toolkit_id)` returns `dict[definition, frozenset[SecretPath]]`. Toolkits are fetched concurrently. A failure for one toolkit doesn't discard another (ERR-7).
   6. Steps 3–5 together run under one overall budget, `asyncio.wait_for(..., timeout=_resolution_budget_s())`. `_resolution_budget_s()` reads `DCT_TIMEOUT` (default 30 s) from `get_dct_config(require_key=False)` at call time, falling back to 30 on error. It is a module-level function, so tests can monkeypatch it to shorten the budget. If the budget is exceeded, the result is a warning plus fallback (FR-007).
   7. A sub-object is **covered** if at least one resolved toolkit produced a derived record set for its definition. An empty set from a successful parse still counts as covered (EC-8). For each covered sub-object, take the union of the records across toolkits, run `expand_and_flag(...)`, then `drop_applied(...)`.
2. Native detection: `native = _missing_sensitive_fields(body_view, _annotated_credential_fields(spec) - (_host_applied_fields(sensitive_applied) ∪ applied_location_leaf_names))`.
   - `body_view` is a shallow copy of `body` with the `covered_sub_objects` keys removed. When nothing is covered (non-AppData operation, fallback, or a sub-object whose toolkit didn't resolve), `body_view` is `body` itself, so native behaviour and annotation-only fallback are exactly as today (FR-007, FR-009).
   - In fallback, a sub-object that is not covered is still walked by the native walker, including identity pairing. That is exactly the pre-change behaviour, which FR-007 ("falls back to spec-annotation-only behaviour") requires. FR-009 step 3 ("no identity pairing for connector fields") is therefore enforced wherever connector detection is active, i.e. for covered sub-objects.
   - `applied_location_leaf_names` are the leaf names of nonce-authenticated location entries. A host that reports `parameters.password` therefore also satisfies the native `password` name (DLPXECO-14603).
3. `names = native + [f.name for f in result.flagged if f.name not in native]` (de-duplicated, first-seen order).
4. If `names` is non-empty, return today's response dict, and add `"sensitive_field_locations": [{"name", "location"} …]` only if `result.flagged` is non-empty. `message` still joins `names`, and `instructions` is unchanged.

**Walker rules (`walk_secret_paths`)**
- Tracks visited `$ref` strings per branch (cycle guard), depth ≤ 32 (`_MAX_DEPTH`) and ≤ 10,000 visited nodes per definition (`_MAX_NODES`). When a bound is hit it stops that branch, records a warning and keeps the partial result (EC-10).
- `properties`: if `prop["format"] == "password"` (exact, case-sensitive, after `$ref` resolution), record `SecretPath(path + key, required = key in node["required"], conditional = inherited_conditional)` and **do not descend** into it (EC-16: the whole value is the secret). *Deviation from FR-002 step 2b* ("then recurse into the property"): EC-16 takes precedence. A password-format property's descendants are already inside the flagged value, so recursing would only produce redundant nested locations. Otherwise descend into the property.
- `items` (dict, or list for tuple validation) → `path[*]`. `additionalProperties`/`patternProperties` (dict values) → `path.*`.
- `allOf` branches → same path, conditional unchanged.
- `oneOf`, `anyOf`, `if`/`then`/`else`, `dependencies` (schema form), `dependentSchemas` → same path, `conditional=True`. Draft-07 plugin schemas can declare secrets under these keywords. Walking them as conditional means a *present* secret is still flagged.
- `$ref` → JSON-pointer resolution against the definition root. If it can't be resolved, skip with a warning (EC-9).
- Non-dict nodes, boolean schemas and unknown keywords are ignored. A non-dict root returns `frozenset()` with a warning, and the result is not cached (FR-002 AC-5, ERR-4).

**Present/absent rules (`expand_and_flag`)**
- Expand `[*]` over existing list indices and `.*` over existing dict keys of the actual body value.
- If the key exists, the field is flagged, whatever its value (including `""` and `null`) (EC-4).
- If the key is missing, the field is flagged only if all of these hold:
  - `required` is true;
  - `conditional` is false;
  - the path contains no `[*]`/`.*`;
  - the immediate parent dict exists in the body.

  The sub-object root counts as existing when its key is present and the value is a dict (EC-2, EC-15).
- **Type mismatch:** if the body value at a `[*]` segment is not a list, or at a `.`-segment is not a dict where the schema expects descent, the walker does not give up. It scans that subtree for keys equal to the record's leaf name and flags each one it finds at its concrete location. The scan is scoped to the mismatched subtree, never global, so a model can't evade detection by sending the wrong container type.

**Applied-field matching (`parse_applied` / `drop_applied`)**
- `parse_applied` authenticates with `host_trust.host_nonce_ok`. A wrong or missing nonce yields nothing (FR-005 AC-3).
- A flagged location is satisfied in any of these cases:
  - it is an exact location match;
  - an applied location equals the flagged location minus its `<sub_object>.` prefix, **and** exactly one flagged location has that relative form (an ambiguous relative match doesn't satisfy, so the host must send the full location);
  - an applied bare name equals the leaf name, which keeps the name-only host contract of DLPXECO-14603.
- Locations with a different array index never match (EC-14).

**Caching and concurrency (`ToolkitSecretCache`)**
- One module-level instance, used on the single FastMCP event loop. In-flight fetches are coalesced with a per-key `asyncio.Future` map, so N concurrent misses produce one `GET /toolkits/{id}` (FR-008 AC-3, EC-12).
- Derived records are keyed `(base_url, toolkit_id, version)` in an LRU capped at 256 entries (`_MAX_CACHE_ENTRIES`). Only successful parses are stored.
- The id→version binding, keyed `(base_url, toolkit_id)`, lasts 15 minutes (`_VERSION_BINDING_TTL_S = 900`). Within that window repeated calls make no request (FR-008 AC-1). After it expires, one `GET /toolkits/{id}` refreshes the version. If the version is unchanged, the derived records are reused without re-walking. If it changed, they are re-derived and the old entry ages out of the LRU (FR-008 AC-2, EC-13 — see the explicit deviation note in Acceptance Criteria). A toolkit with no `version` uses key `(base_url, id, None)` under the same 15-minute rule (FR-008 step 4).
- Toolkit negative cache, 60 s (`_NEGATIVE_TTL_S`):
  - 5xx, timeouts, connection errors and unparseable responses are keyed `(base_url, toolkit_id)` (global);
  - 401/403/404 are keyed `(identity, base_url, toolkit_id)`, so one caller lacking toolkit permission never disables detection for other callers.

  Within the window there is no fetch. One warning is logged per window (FR-007 AC-3, ERR-1, ERR-2).
- Object→next-id cache, keyed `(identity, get_path_template, object_id)`:
  - successes are kept 15 minutes (`_OBJECT_TTL_S = 900`);
  - failures (non-404, or 404 on the last alternative) are negative-cached for 60 s (`_OBJECT_NEGATIVE_TTL_S`).

  This bounds the cost of repeated referenced-object lookups during an outage. Only the selected id is cached, never the object payload.
- All constants are named module-level values, not env vars, so no new configuration is required (QR-8).

**Logging and secrecy (FR-004, QR-3)**
- Warnings use the format `"AppData secret detection fallback: op=%s %s toolkit=%s version=%s stage=%s reason=%s"`.
  - `op` is the method and path template.
  - `stage` is one of `resolve`, `fetch`, `parse`, `walk` or `budget`.
  - `reason` is the exception class name or the HTTP status parsed via `_extract_http_status`.
- `str(exc)` of a `DCTClientError` is never logged, because it can contain response text. Body values, referenced-object payloads and toolkit responses are never logged.

**Discovery (FR-010)**. On a capture-capable host, for `get_operation_schema` of a mapped operation, the note and the `host_captured_connector_secrets` list come only from the static mapping. The note says connector parameters declared `"format": "password"` in the toolkit schema for those sub-objects are captured by the host and must not be requested in chat or placed in the body. FR-010 step 3 (listing concrete locations) is intentionally not implemented in discovery: a discovery call carries no toolkit identity (see Alternatives). Concrete locations are delivered by the gate in `sensitive_field_locations`.

## Version Compatibility
<!-- Guidance: Pull the version table from .claude/architecture.md and mark whether this feature requires branching per version. "Branch?" = Yes if code path differs by version, No if behavior is identical. -->

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11+ (`requires-python = ">=3.11"`) | Yes | No | Uses `asyncio`, `dataclasses(frozen=True)`, `collections.OrderedDict` and PEP 604 unions. No new dependency. |
| FastMCP `>=2.13.2,<4` | Yes | No | No new FastMCP API used. `discovery`/`execute` signatures are unchanged. |
| DCT API v3 with `GET /toolkits/{toolkitId}` returning definitions (DCT spec 3.31.0 verified) | Yes | No | Definition shape differences (snake/camel case, `parameters`/`schema` wrapper, source-config under `discovery_definition`) are handled by the lookup table, not version branches. |
| DCT API where toolkit details omit definitions, or the API key lacks toolkit/object read permission | Yes (degraded) | No | Fail-open per FR-007: one warning per 60-second window, annotation-only detection, the operation proceeds. |
| `DCT_TOOLSET=dynamic` (default) | Yes | No | The only mode with the sensitive gate. All FRs apply. |
| `DCT_TOOLSET=<fixed toolset>` (`self_service`, `continuous_data_admin`, …) | Yes | No | Unchanged. Pre-built grouped tools have no sensitive gate today, and none is added (see Alternatives). |
| Embedded mode (`DCT_AUTH_MODE=embedded` + `DCT_MCP_SENSITIVE_NONCE`, capture-capable host) | Yes | No | Connector detection, `sensitive_field_locations` and the discovery note are active. Lookups go through the per-caller `ClientRegistry` client, with per-identity cache keys. |
| Standalone / non-capture-capable clients (Claude Desktop/Code, VS Code Copilot) | Yes | No | Byte-identical behaviour: no toolkit lookup, no new response keys, no discovery note (FR-009, FR-010 AC-2). |

## Platform Behavior Notes
<!-- Guidance: Flag each "Non-Obvious Platform Behavior" from CLAUDE.md / architecture.md that this feature interacts with. Mark each as "Affects" (this feature must respect the behavior) or "N/A" (unrelated). -->

- **API key prefix (`apk `)**: N/A. Lookups use the existing `DCTAPIClient`, which adds the prefix.
- **SSL default `verify=false`**: N/A. The client is unchanged.
- **Retries / exponential backoff (`DCT_MAX_RETRIES`, 4xx not retried)**: Affects.
  - A single lookup inherits the client's retry loop.
  - The connector step as a whole is capped by `_resolution_budget_s()` (= `DCT_TIMEOUT`), so an outage adds at most about one `DCT_TIMEOUT` to an AppData call before failing open. Positive and negative caches then make subsequent calls cheap.
  - 4xx (404 on a `^` alternative, 401/403) is not retried, so alternative probing is cheap.
  - The client itself logs an `error` line for 4xx/5xx. The "exactly one warning per failure" assertion (SC6) applies to the `connector_secrets` logger.
- **Toolset config cache (`loader.py` `@lru_cache`)**: Affects. `load_appdata_operations()` is lru-cached like the other mapping loaders and is added to `clear_cache()`.
- **Telemetry opt-in (`IS_LOCAL_TELEMETRY_ENABLED`) and `@log_tool_execution`**: Affects. The decorator records tool calls. The connector gate must not add any body value to anything it logs or returns, and the gate response carries only names and locations.
- **Embedded mode `ClientRegistry` (per-caller client keyed by `X-CLIENT-ID`)**: Affects.
  - Lookups use the same per-caller client as dispatch (`_resolve_client`).
  - Object caches and 401/403/404 negative entries are keyed by `identity_key`, so one caller's visibility or permissions never affect another caller.
  - Toolkit schemas are DCT-global and keyed by `base_url`.
- **Spec cache (`spec_cache.py`, no bundled-spec fallback)**: N/A for detection. The AppData mapping is a static config file, not derived from the live spec at runtime. `execute` already returns `SPEC_NOT_LOADED` before the gate.
- **Sensitive gate host scoping (`_secure_capture_host`, DLPXECO-14642)**: Affects. Every new code path (lookup, gate, discovery note) sits behind this check. The check itself is unchanged.
- **`sensitive_applied` nonce trust (DLPXECO-14603)**: Affects. The trust check moves to `host_trust.py` verbatim. Location matching only applies after it passes.
- **Async-first: `execute` is async, `discovery` is sync**: Affects. Lookups are awaited only in `execute`. `discovery` reads the static mapping synchronously and never performs I/O.
- **Pre-built tool docstring hints (`driver.py` `ACTIONS_REQUIRING_TOOLKIT_SCHEMA`)**: N/A. They are unchanged and remain advisory text for fixed toolsets.

## Open Questions / Risks
<!-- Guidance: One bullet per item. Format: "Q: <question> — Owner: <name or TBD>" or "R: <risk> — Mitigation: <action>". Keep blocking items at the top. -->

No blocking items. Every question below has a defined default, so implementation can proceed.

- Q (non-blocking): Final key name and entry shape for the location list (`sensitive_field_locations: [{name, location}]`), and whether the host sends full or sub-object-relative locations in `sensitive_applied.fields`. — Owner: Shreyas Kulkarni with the DLPXECO-14782 (DCT AI Assistant) team. Default implemented: the key above, with full, relative (when unambiguous) and bare-name matching all accepted. This must be agreed before merge/release. The change is additive, so renaming the key is a one-line edit.
- Q (non-blocking): The exact JSON shape of `GET /toolkits/{id}` definitions on a live DCT: snake versus camel case, the `parameters`/`schema` wrapper, and `discovery_definition.source_config_schema` versus `sourceConfigSchema`. — Owner: Shreyas Kulkarni. Default: the lookup table accepts all listed variants. The test phase should confirm against a live DCT with DB2/MySQL toolkits if one is available. A missing variant is a one-line addition to the lookup constants.
- Q (non-blocking): Functional spec FR-008 AC-2 and EC-13 say a toolkit version change is picked up "on the next call". Request bodies and referenced objects never carry the toolkit version, so this design picks it up when the 15-minute id→version binding next refreshes (see the AC deviation note). — Owner: Shreyas Kulkarni. This also relaxes FR-008 step 4 (the TTL applied to every toolkit, not only versionless ones), QR-6 and the Performance Considerations "at most one fetch per (id, version)" bullet to "at most one fetch per toolkit per 15 minutes". Default: the 15-minute binding. If the functional wording must hold literally, the trade-off is one `GET /toolkits/{id}` on every AppData call, which violates FR-008 AC-1 and SC9.
- R: Resolution gaps:
  - `POST /vdbs/empty_vdb` and `POST /sources/appdata` resolve only when the body has both `repository_id` and `environment_id`.
  - `POST /vdb-groups/provision_from_bookmark` (nested `provision_parameters.<vdb_id>.appdata_*`) is not mapped.
  - Bookmarks spanning several datasets resolve only the first dSource and the first VDB.

  — Mitigation: unresolved cases fall back to annotation-only with a warning. Integration tests assert the fallback. The gaps are documented in `CLAUDE.md`. The vdb-group nested form is a candidate follow-up ticket.
- R: Fail-open means that during a DCT outage, or for an API key without toolkit or object read permission, an inline connector password typed by the model is dispatched without the secure prompt. — Mitigation: this is required by facts.json acceptance_criteria[6]. A warning is logged on every negative-cache window so operators see the gap, and native annotation-based detection still applies to every sub-object that wasn't covered.
- R: The overall `_resolution_budget_s()` budget can fail open on a DCT that is slow but working. — Mitigation: the budget equals `DCT_TIMEOUT`. A cache hit costs no I/O, so this only affects the first call per toolkit or object per window.
- R: A connector schema that marks an entire object/array as `"format": "password"` produces a location whose value is non-scalar, and the host may only inject scalars. — Mitigation: it is flagged at the container location (EC-16) and documented for DLPXECO-14782.
- R: Bare-name entries in `sensitive_applied.fields` satisfy every flagged connector location with that leaf name. — Mitigation: this preserves the name-only host contract (DLPXECO-14603). The nonce check prevents abuse by the model. Hosts that adopt locations get exact matching.
- R: Excluding covered sub-objects from the native walker changes which walker reports a connector field named like an annotated native field. — Mitigation: this only applies when connector detection succeeded for that sub-object, so detection is never narrowed. Native operations and fallback paths are unchanged. Existing suites run unmodified (QR-2).
- `testing.md` may be stale — review before the test phase. `.claude/test/testing.md` describes only live-DCT scenario execution and `tests/<ticket>-test.py` subprocess tests. This feature's tests follow the repository's actual unit/integration layout (`tests/unit/`, `tests/integration/`, `tests/fixtures/`, run via `pytest` / `dct-mcp-test --layer ci`) with a stubbed DCT client. Proposed `testing.md` addition, not applied because this is a pipeline run: a "Track 3 — CI unit/integration tests (stubbed DCT)" section naming those directories, `dct-mcp-test --layer ci` and `pytest --cov=src/dct_mcp_server --cov-report=term-missing`.

## Acceptance Criteria
<!-- Guidance: Pull directly from the Jira ticket "Acceptance Criteria" section if present, else derive from vision-doc Goals. Each AC must be testable and map to at least one FR-* in functional.md. -->

- [ ] AC-1: For an AppData operation (e.g. DB2 or MySQL dSource link / VDB provision) on a capture-capable host, every connector parameter declared `"format": "password"` in the toolkit schema, including nested properties, triggers `sensitive_input_required` when missing or supplied inline. — FR-001, FR-002, FR-003
- [ ] AC-2: The DCT AI Assistant shows the secure credential UI for those fields, and the value reaches DCT without entering the LLM context: no value appears in any response, log line or audit event, and the host-injected body is dispatched unchanged. — FR-004
- [ ] AC-3: Re-calls with the field supplied via `sensitive_applied` (valid nonce) succeed and do not re-prompt, whether the host reports it by name or by location (no regression of DLPXECO-14603). — FR-005
- [ ] AC-4: Non-password connector fields (usernames, ports, paths, ids) are never flagged, including through identity pairing inside covered sub-objects. — FR-002, FR-003, FR-009
- [ ] AC-5: Native (non-AppData) operations behave exactly as today, still driven by `x-dct-toolkit-credential-field`. The existing gate suites pass unmodified. — FR-009
- [ ] AC-6: Non-capture-capable clients (Claude Desktop/Code, VS Code Copilot) behave as today: no toolkit lookup, no new response keys, no discovery note. The gate stays host-scoped (DLPXECO-14642). — FR-009, FR-010
- [ ] AC-7: If the toolkit schema can't be resolved, fetched or parsed, or resolution exceeds the time budget, the server logs a warning and falls back to spec-annotation-only behaviour. The operation is not blocked, and failures are retried no more often than every 60 s per toolkit or object. — FR-007
- [ ] AC-8: Unit tests cover the schema walker (nested, arrays, combinators including `if`/`then`/`else`, `$ref`, cycles, bounds), path-scoped matching, caching (hit, miss, version change, single-flight, LRU, negative) and fallback. Integration tests cover at least the DB2 and MySQL toolkits. New code has ≥ 80% line coverage. — FR-002, FR-003, FR-007, FR-008
- [ ] AC-9: `sensitive_input_required` returns each flagged connector field's location (e.g. `appdata_source_params.dbPassword`) in `sensitive_field_locations`, alongside today's `required_sensitive_fields` names, which are unchanged. — FR-006
- [ ] AC-10: `sensitive_applied.fields` (from the host) is matched by location as well as by name, so injected connector fields are not flagged again. — FR-005
- [ ] AC-11: Repeated AppData calls for the same toolkit fetch the toolkit details once per 15-minute version-binding window, concurrent first calls coalesce into one fetch, and a changed version is re-derived when the binding refreshes. — FR-008. *Deviation from functional FR-008 AC-2 / EC-13, FR-008 step 4, QR-6 and the Performance Considerations bullet ("at most one toolkit details fetch per (id, version) per process"):*
  - The id→version binding refreshes every 15 minutes for every toolkit, not only versionless ones. That is one extra `GET /toolkits/{id}` per toolkit per 15 minutes even when the version is unchanged, and the walk is still skipped.
  - A changed version is picked up at the next call after the refresh, not the very next call.
  - The reason is that no request or referenced object carries the toolkit version, so the version can't be known without a fetch. See Open Questions.
- [ ] AC-12: On a capture-capable host, `discovery(action="get_operation_schema")` for an AppData operation marks connector password-format fields as host-captured secrets that must not be requested in chat. Concrete locations are delivered by the gate, not by discovery. — FR-010

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/$NAME/$NAME-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/$NAME/$NAME-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh $NAME --step design -->
