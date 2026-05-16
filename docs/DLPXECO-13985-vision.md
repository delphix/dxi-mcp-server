# Vision: DLPXECO-13985 — 3-Tool Dynamic API Architecture for DCT MCP Server

## Problem Statement

The current DCT MCP Server exposes DCT API capabilities through statically pre-mapped, persona-based toolsets (e.g., `self_service`, `continuous_data_admin`). This approach requires manual mapping of every API endpoint into grouped tool files and toolset `.txt` configs, meaning that when DCT adds new endpoints the MCP server lags behind and engineers must update Python code and config files in lock-step. Additionally, the existing "auto mode" exposes meta-tools that dynamically enable toolsets but still relies on pre-built tool modules, limiting the AI's ability to discover and use the full DCT API surface without prior mapping work. A 3-tool architecture — **List**, **Get**, **Execute** — backed by a live-fetched and cached OpenAPI spec would allow the AI to autonomously browse, understand, and call any DCT API operation without requiring pre-mapped tool definitions, while preserving all existing security controls (confirmation gates, RBAC, error handling).

## Goals

- G1: Design a 3-tool MCP architecture (List, Get, Execute) that allows an LLM to discover, inspect, and call any DCT API operation using the live OpenAPI spec, without requiring pre-mapped Python tool modules per endpoint
- G2: Define an OpenAPI spec download-and-cache strategy that ensures the spec is available at startup, refreshable on demand, and fault-tolerant when the DCT host is unreachable
- G3: Produce a formal architecture design document (`.docx` format) covering tool responsibilities, request/response schemas, confirmation gate flow, RBAC model, and LLM evaluation methodology — ready for PM and Ecosystem team sign-off before any implementation begins
- G4: Include a comparison table of the 3-tool Dynamic mode versus the existing Auto mode covering token economics, tool count, latency, maintenance burden, and recommended approach

## Non-Goals

- NG1: This story does not implement the 3-tool architecture in code — it produces a design document only; implementation is tracked in a separate epic
- NG2: Does not modify or remove existing persona-based toolsets (`self_service`, `continuous_data_admin`, etc.) — the design must co-exist with the current architecture
- NG3: Does not redesign the MCP transport layer, FastMCP version, or Python runtime requirements
- NG4: Does not define UI changes to any MCP client (Claude Desktop, Cursor, VS Code Copilot)
- NG5: Does not address DCT API authentication redesign — the existing `DCT_API_KEY` / `apk` prefix mechanism is retained as-is

## Success Criteria

- SC1: The published design document explicitly covers all six areas from AC-1 (tool responsibilities, OpenAPI spec download-and-cache strategy, request/response schemas, confirmation gate flow, RBAC model, and LLM evaluation methodology) with no section left as a placeholder
- SC2: The comparison table between Dynamic mode (3-tool) and Auto mode includes token economics analysis with concrete token-count estimates or ranges for typical LLM interactions
- SC3: The design document receives recorded sign-off from PM (Nick/Geeta) and the Ecosystem team as a Jira comment on the epic (DLPXECO-13984) before any implementation ticket is opened
- SC4: The architecture design document is produced in `.docx` format and linked from the Jira epic
- SC5: The design demonstrates that the 3-tool approach retains all existing security controls: confirmation gates for destructive operations, error handling equivalent to current grouped tool pattern, and no new unauthenticated attack surface

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Vinay Byrappa (Assignee) | Delivery of a complete, reviewable design document that unblocks the Ecosystem team |
| Nick / Geeta (PM) | Sign-off that the architecture meets product requirements before implementation spend begins |
| Ecosystem Engineering Team | Confidence that the 3-tool design is safe, maintainable, and technically sound |
| AI/LLM Consumers (Claude, Cursor) | Ability to discover and call any DCT API endpoint without toolset pre-configuration |
| DCT Platform Team | Assurance that the MCP server does not expose security vulnerabilities or bypass RBAC |
| On-call / Operations | Fewer incidents from spec drift between DCT API updates and MCP server tool mappings |

## Constraints

- The design document must be in `.docx` format as required by stakeholder review workflow
- No implementation code may be written until PM and Ecosystem team sign-off is recorded on the Jira epic (DLPXECO-13984)
- The design must be compatible with Python 3.11+ and FastMCP 2.13.2+ (existing runtime constraints)
- The 3-tool architecture must not introduce any new unauthenticated API surface — all DCT calls go through `DCTAPIClient` with the existing auth mechanism
- The design must account for DCT OpenAPI spec availability: the spec endpoint (`{DCT_BASE_URL}/dct/static/api-external.yaml`) may be unreachable; the design must specify a fallback to the bundled spec
- Design review must complete before the Q3 implementation freeze

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenAPI spec download fails at MCP server startup (DCT host unreachable, network partition) | Medium | High | Design mandates a bundled fallback spec shipped with the package; cache persists across restarts in `$TEMP/dct_mcp_tools/`; spec version is logged at startup for observability |
| LLM constructs malformed API calls using Execute tool (schema misinterpretation) | Medium | High | Execute tool validates request shape against the cached OpenAPI schema before dispatching; returns structured validation errors the LLM can self-correct from |
| Confirmation gate bypassed when LLM uses Execute tool for destructive operations | Low | Critical | Execute tool routes all requests through the existing `manual_confirmation.txt` rule engine identically to the current grouped tool pattern; no bypass path exists by design |
| Token cost per interaction exceeds existing Auto mode due to full spec context sent to LLM | Medium | Medium | Get tool returns only the single operation schema (not the full spec); List tool returns operation names and summaries only; full spec is never injected into LLM context in one shot |
| Design document scope creep delays PM review | Low | Medium | Scope is explicitly bounded by AC-1 and AC-2; design does not include implementation code, migration scripts, or client config changes |
| Existing `self_service` and other toolset users experience regression if 3-tool mode is introduced improperly | Low | High | Design specifies 3-tool mode as an opt-in via a new `DCT_TOOLSET=dynamic` value; existing toolsets remain fully operational with no changes |
| DCT OpenAPI spec format changes between DCT versions break the List/Get/Execute routing | Medium | Medium | Cache stores spec with a DCT version tag; Get tool returns a schema-parse-error if the spec format is unrecognised, allowing graceful degradation |

---
<!-- Cross-reference: Goals (G1–G4) map to FR descriptions in the functional spec.
     Success Criteria (SC1–SC5) map to Acceptance Criteria in FR-* entries.
     Constraints and Risks inform the Quality Rules and Edge Cases sections. -->
