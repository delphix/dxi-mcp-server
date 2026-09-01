# Spec-Code Coverage: DLPXECO-14458

<!-- Every FR from docs/DLPXECO-14458/DLPXECO-14458-functional.md must have at least one row.
     PASS requires a file:line citation from grep output — not reasoning alone. -->

| FR-ID | Description | Status | Evidence (file:line or "none") |
|-------|-------------|--------|-------------------------------|
| FR-001 | Single-Use Body-Bound Confirmation Token — canonical_json, issue_token, verify_and_consume_token | PASS | src/dct_mcp_server/tools/core/confirmation_token.py:32 (canonical_json), confirmation_token.py:80 (verify_and_consume_token), tests/unit/test_dynamic.py:377 (issue_token exercised in test) |
| FR-002 | Differentiated Confirmation Levels — required_fields, validate_elevated, validate_manual | PASS | src/dct_mcp_server/tools/core/confirmation_resolver.py:16 (build_required_fields imported), confirmation_levels.py:107 (validate_elevated), tests/unit/test_confirmation_resolver.py:87 (manual level test), test_confirmation_resolver.py:105 (elevated level test), test_dynamic.py:389 (required_fields assertion) |
| FR-003 | Close Confirmation Coverage Gap — keyword fallback, read_exclusions, dynamic_confirmation | PASS | tests/unit/test_dynamic_confirmation.py:64 (get_confirmation_for_operation_dynamic tests), test_dynamic_confirmation.py:84 (DELETE always manual), src/dct_mcp_server/config/config.py:38 (DCT_CONFIRMATION_FALLBACK default=keyword) |
| FR-004 | Scoped Batch Grants — batch_intent, grant_token, confirmation_store | PASS | src/dct_mcp_server/tools/core/dynamic.py:298 (batch_intent parameter), dynamic.py:499 (grant_store.create_grant), confirmation_store.py:1 (ConsumedTokenStore for grant tracking) |
| FR-005 | Elicitation-Based Enforcement — DCT_CONFIRMATION_ENFORCEMENT, _build_elicitation_schema, ToolAnnotations | PASS | src/dct_mcp_server/tools/core/dynamic.py:96 (_build_elicitation_schema), dynamic.py:109 (_check_elicitation_capability), config/config.py:35 (DCT_CONFIRMATION_ENFORCEMENT), dynamic.py:670 (strict enforcement message) |
| FR-006 | Per-Identity Velocity Detection — get_process_identity, batch_check:N:T, velocity_counter | PASS | src/dct_mcp_server/core/session.py:235 (get_process_identity), tools/core/velocity_counter.py:35 (counter file path), tools/core/confirmation_resolver.py:17 (increment_and_check imported), tests/unit/test_session.py:254 (process identity test) |
| FR-007 | Non-Relaxable Floor Operations — is_floor_operation, floor_operations.txt | PASS | src/dct_mcp_server/tools/core/floor_operations.py:20 (floor_operations.txt loaded), floor_operations.py:107 (DELETE fast-path), dynamic.py:59 (is_floor_operation imported), dynamic.py:479 (floor check before grant) |
| FR-008 | Audit Events for Every Gate Decision — emit_gate_event, gate_decision log | PASS | src/dct_mcp_server/tools/core/audit.py:45 (emit_gate_event function), dynamic.py:43 (emit_gate_event imported), dynamic.py:508 (batch grant required event), dynamic.py:543 (grant_covered event) |
