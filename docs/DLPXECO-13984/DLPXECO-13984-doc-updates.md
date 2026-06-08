# Documentation Updates: Dynamic 2-Tool Architecture (Phase 1)

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13984
**Affects**: README / Getting Started guide, Configuration reference, Toolset overview, MCP client setup guide

---

## Summary of Change

The DCT MCP Server now supports a new mode — `DCT_TOOLSET=dynamic` — that gives AI assistants full access to every DCT API operation through just two tools: `discovery` and `execute`. Previously, each DCT product area required dedicated MCP code and toolset configuration to be usable by AI clients; with the dynamic mode, any endpoint available in the DCT OpenAPI spec is immediately callable without MCP changes. This is an additive option — all existing persona-based toolsets (`self_service`, `continuous_data_admin`, `platform_admin`, `reporting_insights`, `self_service_provision`) continue to work exactly as before.

---

## Pages to Update

### Getting Started / README — root-level README.md or docs site landing page

| Section | What to change |
|---------|---------------|
| Toolset overview | Add `dynamic` to the list of valid `DCT_TOOLSET` values alongside existing personas. Note that `dynamic` mode exposes two universal tools instead of grouped persona tools. |
| Quick start example | Add a one-paragraph callout explaining that `DCT_TOOLSET=dynamic` is the recommended starting point when the full DCT API surface is needed and no persona filtering is required. |

**Suggested new content:**

> **Dynamic mode** (`DCT_TOOLSET=dynamic`)
>
> Dynamic mode gives AI assistants access to every DCT API endpoint through two tools: `discovery` (browse the API surface and retrieve operation schemas) and `execute` (call any endpoint with automatic confirmation gating for destructive operations). The server downloads and caches the OpenAPI spec from your DCT instance at startup — no MCP updates are required when new DCT endpoints ship.
>
> To use dynamic mode, set `DCT_TOOLSET=dynamic` in your environment. All other configuration (API key, base URL, SSL settings, timeout) remains unchanged.

---

### Configuration Reference

| Section | What to change |
|---------|---------------|
| `DCT_TOOLSET` env var entry | Add `dynamic` as a valid value. Update the description to note it registers two universal tools instead of a persona toolset. |
| New env vars table | Add two new optional variables: `DCT_SPEC_CACHE_PATH` and `DCT_SPEC_MAX_AGE_HOURS`. |

## New Configuration Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `DCT_TOOLSET=dynamic` | Activates the 2-tool dynamic mode (`discovery` + `execute`) driven by the live DCT OpenAPI spec. All existing toolset values remain valid. | No | `self_service` |
| `DCT_SPEC_CACHE_PATH` | Path where the downloaded DCT OpenAPI spec is cached between server restarts. Used only when `DCT_TOOLSET=dynamic`. | No | System temp directory |
| `DCT_SPEC_MAX_AGE_HOURS` | Number of hours before the cached spec is considered stale and re-downloaded at the next server start. | No | `24` |

---

### Toolset Overview / Persona Guide

| Section | What to change |
|---------|---------------|
| Toolset comparison table | Add a `dynamic` row. Mark tool count as 2. Describe the audience as: "Users who need full DCT API coverage without persona filtering." |
| When to choose each toolset | Add guidance: use `dynamic` when you need access to DCT endpoints not yet covered by a persona toolset, or when building automations that span multiple DCT product areas in a single session. |

**Suggested comparison table row:**

| Toolset | Tools | Best for |
|---------|-------|---------|
| `dynamic` | 2 (`discovery`, `execute`) | Full DCT API access; zero MCP updates needed for new endpoints |

---

### MCP Client Setup Guide (Claude Desktop / Cursor / VS Code Copilot)

| Section | What to change |
|---------|---------------|
| Client compatibility note | Add a note that `dynamic` mode works with all supported clients. The two-tool surface is small enough that no special client configuration is needed. |
| VS Code Copilot note | Confirm that `dynamic` mode is fully compatible with VS Code Copilot (fixed tool set at startup; no dynamic switching required). |

---

### Operator / Admin Notes

| Section | What to change |
|---------|---------------|
| Startup behavior | Document that when `DCT_TOOLSET=dynamic` is set, the server downloads the DCT OpenAPI spec from the configured DCT instance at startup (reusing a fresh on-disk cache when available). If the spec cannot be downloaded and no fresh cache exists, startup aborts with `SPEC_LOAD_FAILED` — there is no bundled-spec fallback, since a failed download means the DCT instance is unreachable and the server could not serve any API call anyway. |
| Confirmation gating | Note that all destructive operations (deletes, failovers, upgrades) continue to require explicit confirmation when called via the `execute` tool, consistent with behavior in persona-based toolsets. |
| Spec freshness | Operators can force a spec refresh by deleting the cached file at `DCT_SPEC_CACHE_PATH` or by setting `DCT_SPEC_MAX_AGE_HOURS=0` before restarting the server. |

---

## Release Notes Entry

**Release: 2026.0.2.0-preview**

The DCT MCP Server now includes a **dynamic mode** (`DCT_TOOLSET=dynamic`) that provides AI assistants with access to every DCT API endpoint through two universal tools — `discovery` and `execute` — without requiring MCP updates when new DCT endpoints ship. The `discovery` tool lets AI clients browse the full DCT API surface and retrieve operation schemas on demand; the `execute` tool dispatches any API call with the same confirmation gating that protects destructive operations in persona-based toolsets. All existing toolsets (`self_service`, `continuous_data_admin`, `platform_admin`, `reporting_insights`, `self_service_provision`) are unaffected. Two new optional environment variables — `DCT_SPEC_CACHE_PATH` and `DCT_SPEC_MAX_AGE_HOURS` — control where and how long the downloaded spec is cached between server restarts.
