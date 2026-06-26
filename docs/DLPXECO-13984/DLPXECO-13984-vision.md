# Vision: DLPXECO-13984

## Problem Statement

The Delphix MCP Server currently exposes ~22 persona-based grouped tools (e.g. `vdb_tool`, `engine_tool`, `iam_tool`) that each map to a curated subset of DCT API endpoints, requiring ongoing manual CRUD maintenance for every new Delphix product area (Compliance, Synthetic, PaaS DBs, etc.). When a new DCT endpoint ships, MCP code, toolset `.txt` files, and confirmation rules all require explicit updates — blocking AI assistants from using new capabilities until a developer does that work. The business impact is twofold: product teams wait for MCP updates before new DCT features are accessible to AI workflows, and new PPM tickets (PPM-1013, PPM-1014, PPM-1073) must be filed and staffed for every major CRUD domain.

## Goals

- G1: Deliver a **2-tool architecture** (Discovery + Execute) that provides full DCT CRUD coverage from the live OpenAPI spec with zero MCP code changes per new endpoint
- G2: Implement an **OpenAPI spec download-and-cache subsystem** that fetches the spec from the configured DCT instance at startup, validates it, and serves both tools from the cache
- G3: Implement a **Discovery tool** (merged List + Get) that lets the AI browse the DCT API surface, retrieve operation schemas, and understand available endpoints from the cached spec
- G4: Implement an **Execute tool** that validates parameters, applies confirmation gates, annotates read-only vs. destructive operations at runtime, and dispatches a single DCT API call per invocation
- G5: Provide an **LLM evaluation harness** covering the top-10 common DCT workflows across at least two frontier models (Claude + GPT or Gemini) to produce an evidence-based adopt/revert decision
- G6: Define **Phase 2 entry criteria** — the Search tool and sandbox execution mode remain gated on Phase 1 validation and PPM-1129 completion

## Non-Goals

- NG1: Phase 2 features are out of scope — the **Search tool** (semantic NL → endpoint matching) and **Execute sandbox mode** (code-generation + isolated runtime) are not delivered in this epic
- NG2: No changes to the existing persona-based toolsets (`self_service`, `continuous_data_admin`, etc.) — they remain available and fully functional as an opt-in alternative
- NG3: Public Docker Hub image promotion (PPM-1172) is not part of this epic
- NG4: OpenTelemetry integration (PPM-1173) is not included
- NG5: Streamable HTTP transport (PPM-1015) is out of scope
- NG6: Per-tool RBAC — authorization boundary is the DCT API key; no additional per-tool permission layers
- NG7: Vocabulary translation (PPM-1129 canonical domain model) is out of scope for Phase 1; Discovery and Execute ship with pass-through vocabulary only

## Success Criteria

- SC1: A new DCT endpoint added to the OpenAPI spec is callable via Execute with zero MCP code changes after spec cache refresh
- SC2: Discovery returns accurate operation schemas (path, method, parameters, request/response shape) for every endpoint in the cached spec
- SC3: Execute applies confirmation gates with the correct level (standard/elevated/manual) for all operations currently covered by `manual_confirmation.txt` with ≥99% accuracy
- SC4: LLM evaluation harness achieves ≥80% success rate on the top-10 DCT workflows across at least two frontier models
- SC5: Spec cache refresh (startup download + fallback to bundled spec) completes in ≤5 seconds under normal network conditions
- SC6: Decision-gate report is produced with an adopt/revert recommendation, migration plan, and Phase 2 entry criteria

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Shreyas Kulkarni (Assignee) | Technical delivery of Phase 1 — spec cache, Discovery, Execute, eval harness |
| Product/OCTO team | Adopt/revert decision: 2-tool model supersedes PPM-1013, PPM-1014, PPM-1073 if viable |
| AI assistant users (Claude Desktop, Cursor, VS Code Copilot) | Zero-friction access to all DCT API capabilities without domain-specific tool updates |
| DCT platform team | New endpoints callable immediately after spec update with no MCP PR required |
| Delphix on-call / ops | Confirmation-gate fidelity preserved for destructive operations under new architecture |

## Constraints

- Must be backward-compatible with all existing MCP clients (Claude Desktop, Cursor, VS Code Copilot, Continue.dev) — no client-side configuration changes required
- Phase 2 (Search tool + Execute sandbox) cannot begin until Phase 1 validation is complete **and** PPM-1129 (vocabulary & domain model) is finished
- Python 3.11+ required; no new third-party dependencies that are not already present in the project without explicit approval
- Persona-based toolsets must remain fully functional as an opt-in mode — the 2-tool architecture is an additive new `DCT_TOOLSET` value, not a replacement
- The DCT API key is the sole authorization boundary; no per-tool RBAC is introduced
- Bundled fallback spec (`docs/api-external.yaml`) must remain valid as the cache miss path — live-spec-only-mode is not acceptable in disconnected or CI environments

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| DCT OpenAPI spec quality is insufficient for automated tool generation (missing descriptions, incorrect parameter types, sparse examples) | Medium | High | Add OCTO spec-quality audit step; define minimum quality threshold for Phase 1 go/no-go; raise spec fix requests to DCT platform team |
| LLM success rate on top-10 workflows falls below 80% threshold, blocking adopt decision | Medium | High | Include both Claude and a second frontier model; analyze failure modes; use results to refine Discovery schema output before re-evaluating |
| Confirmation-gate resolver misses destructive operations not currently in `manual_confirmation.txt` | Low | High | Implement runtime read-only/destructive annotation from HTTP method (GET=safe, DELETE/POST/PATCH=potentially destructive); add regression tests against full `manual_confirmation.txt` |
| Spec download at startup adds latency or fails in air-gapped / CI environments | Low | Medium | Mandatory fallback to bundled `docs/api-external.yaml` with warning log; startup must not block on spec download failure |
| Tool count explosion — Discovery + Execute surface hundreds of operations, exceeding LLM context window or degrading tool selection accuracy | Medium | Medium | Discovery uses lazy pagination (fetch schema on demand, not all at once); evaluate context window usage in LLM harness; set operation count budget |
| Phase 2 slippage: PPM-1129 delayed, blocking Search tool delivery | Low | Low | Phase 1 is independently deliverable; Phase 2 gating is explicitly documented in decision-gate report |
| Existing auto-mode meta-tools (`list_available_toolsets`, `enable_toolset`, etc.) overlap with Discovery in intent | Low | Low | Clearly document the distinction in tool descriptions; Discovery operates on raw OpenAPI spec surface, not persona-based toolsets |
