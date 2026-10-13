# Proposal: Merge "Agent Ready OpenAPI Spec" into PPM-1129

| | |
|---|---|
| **Status** | Draft for review |
| **Date** | 2026-09-28 |
| **Audience** | Geeta Zanvar, Elima Sugunan, Nick Mathison; ARB and CTC reviewers |
| **Concerns** | PPM-1129 (Vocabulary & Domain Model Guidance); row 6 of the [DCT AI Assistant – Delphix MCP Server – GA](https://perforce.atlassian.net/wiki/spaces/DLXEN/pages/3570598020) page ("Agent Ready Open API Spec"); DLPXECO-14529 |

---

## Recommendation

Track the agent-ready OpenAPI spec work **inside PPM-1129** rather than as a second idea.
Retitle PPM-1129 to reflect the widened scope, point both row 5 and row 6 of the GA page at it,
and split delivery into two epics so the DCT-side build blockers do not gate the MCP-side work.

No second PPM is needed. Row 6 has no ticket today, so this is a decision not to create a
duplicate rather than a consolidation of two live items.

---

## Why these are one piece of work, not two

### 1. They are the same edit to the same fields

Agent-readiness asks whether an operation says anything useful at all. Vocabulary asks which
words it uses when it does. Both are answered by writing the `summary` and `description` of the
same operations in the same five source specs (`core-api`, `virtualization-api`, `masking-api`,
`syngen-api`, `ai-control-api`).

Writing the 1,025 currently-missing descriptions *is* the moment the vocabulary gets chosen.
Sequencing them as separate tickets means authoring the same YAML twice, with the second pass
conflicting with the first.

### 2. Both compete for one scarce field

The MCP server matches user intent on `operationId` + `summary` + `path` + `tags`, and **never on
`description`** (measured in DLPXECO-14529; confirmed in `tools/core/dynamic.py:1197`, where
`_action_list_operations` returns exactly those four fields to the model).

This has a consequence that reshapes both efforts: any synonym intended to be *searchable* must
live in `summary`, not `description`. Vocabulary work and agent-readiness work therefore contend
for the same handful of characters in the same field. That is a single editorial decision per
operation, not two independent ones.

### 3. The implementing story already spans both

DLPXECO-14529 ("Enrich DCT OpenAPI descriptions so the MCP server can infer user intent") opens
with *"Implements the spec-level lever of PPM-1129"* and is linked to PPM-1129 as *is implemented
by*. It already carries the measurements, a working prototype branch, and both blockers. A second
PPM for row 6 would give one prototype branch two parents.

### 4. They share every gate

Rows 5 and 6 of the GA page are identical on every axis that matters: Teams = DCT + MCP, Status =
Exploration, ARB Required, CTC for MCP Required, and the same release pair (DCT GA 2026.6.0 /
MCP GA 2026.1.0). One PPM means one ARB submission, one CTC page, one set of Design reviewers.

---

## What "agent-ready" means concretely

The phrase needs pinning down in the ticket, because the work behind it is specific. Baseline
measured against DCT 3.30.0, 1,044 external operations in `api-external.yaml`; "prototype" column
is the state reached on the unpushed branch described in DLPXECO-14529.

| Dimension | Today | Agent-ready target |
|-----------------------------------|--------------------------|-----------------------------|
| Operations carrying a `description` | 19 (1.8%) | 1,044 (100%) |
| Operations stating an explicit use case | 198 (18.6%) | 406 (38.2%) |
| Purely mechanical descriptions | 533 (50.1%) | 326 (30.6%) |
| Terse generic-verb summaries | 540 (51.7%) | materially reduced |
| Request-body properties undescribed | 144 | 0 |
| Searchable vocabulary / synonyms | none | present in `summary`, where routing reads |
| `filter_expression` documentation | one cryptic example, shared by all 138 `/search` endpoints | operator grammar plus per-endpoint filterable-field lists |
| Operation mechanics | implicit | pagination, async job polling and required fields stated |

Descriptions in the prototype are generated from facts already in the spec, not invented: for
long-tail endpoints the lead sentence is the existing summary verbatim with derived mechanics
appended, and domain prose is drawn from the 505 component schemas that already carry
descriptions.

**Demonstrated effect.** An A/B harness run against the MCP server's own `endpoint_discovery`
module showed routing changes such as:

- *"list my golden copies"* — `GET /compliance-job-collections` → `GET /vdbs`
- *"generate a secure lookup list for a masking algorithm"* — a masking-file-download endpoint → `POST /ai/generate`

**Annotation precedent.** The spec already carries `x-dct-toolkit-credential-field`, which the MCP
server treats as the authoritative list of secret fields. Agent-affordance annotations
(idempotency, destructiveness, long-running) would extend that established pattern rather than
introduce a new one, and would feed PPM-1127 (Tool Annotations) directly.

---

## What the vocabulary work covers concretely

The other half of the merged scope. Where agent-readiness asks whether an operation says anything
useful, this decides the words it uses. Source is PPM-1129's problem statement, to be reconciled
against Glossary v1.2 (28 canonical terms, 172 synonym rows).

| Concern | Canonical | Accept as input | Avoid in output | Why it matters |
|------------|----------|--------------------|-------------|----------------------------------------|
| Core data object | VDB | database, virtual database, clone, copy | — | Customers use all five interchangeably; the model cannot know they are one thing unless told |
| Source object | dSource | Delphix source, source DB, linked source | — | "Data source" is *not* an alias: v1.2 defines it as the upstream system a dSource ingests from (#3). Retained as canonical in v1.2; Design System Glossary recommends deprecating it — resolved, Product has decided to keep dSource as-is for this PPM |
| Infrastructure | environment | host, infrastructure, machine, VM | — | Four common aliases, none currently mapped |
| Timeline | timeline | timeflow | timeflow | Legacy Continuous Data engine term; the model echoes it back wherever tool definitions use it |
| Grouping | VDB Group | container | container | "Container" reads as Kubernetes in today's context; legacy Self-Service / Jetstream users mean VDB Group |
| Connector split | connector | AppData, plugin, native connector | AppData, plugin | Oracle/SQL Server/ASE/V-files are native; PostgreSQL/MongoDB/SAP HANA/Db2 are AppData plugins. An implementation split customers should never see |
| Product boundary | DCT, or *Continuous Data engine* / *Continuous Compliance engine* (whichever the context shows) | engine (unqualified), Delphix engine | bare "engine", "Delphix engine" | Unqualified "engine" is repeatedly conflated with DCT itself, and is ambiguous between the two engine products (v1.2 #8) |

**Where each lands.** These are not all the same kind of edit, which is part of why the two-epic
split works:

- *Spec-side (DCT epic)* — synonyms into `summary` so they are searchable; canonical terms in
  `description` prose; hiding the AppData/native split in customer-facing wording.
- *MCP-side epic* — `server_instructions` carries the cross-cutting rules (accept these aliases,
  emit these canonical terms, never surface these); the 79 `manual_confirmation.txt` templates get
  a direct pass, since they are hand-authored in this repo and reach every user regardless of
  toolset.

**Current exposure in this repo**, as a sizing input for the MCP-side epic:

| Surface | timeflow | dSource | VDB | AppData | environment |
|---|---|---|---|---|---|
| `config/toolsets/*.txt` (5 files, legacy) | 73 | 183 | 377 | 14 | — |
| `tools/*.py` (pre-built fallback) | 281 | 959 | 1,759 | 159 | — |
| `manual_confirmation.txt` (79 rules, reaches everyone) | 6 | 31 | 87 | — | 12 |

The first two rows are opt-in legacy surfaces under dynamic mode; the third is not, which is why
Lever 4 stays in scope at full weight even as Levers 1–2 shrink.

---

## Why the original PPM-1129 lever split needs rescoping

PPM-1129 was written on 2026-04-17, before PPM-1174 (2-tool revision) landed. Its four levers
assume the curated per-domain toolsets are the primary surface. They no longer are.

`DCT_TOOLSET` now defaults to `dynamic` (`config/config.py:28`). In dynamic mode the server
registers exactly two tools — `discovery` and `execute` — and downloads the spec live from the
customer's own DCT instance at `{DCT_BASE_URL}/dct/static/api-external.yaml`, with **no bundled
fallback** (`tools/core/spec_cache.py`). Everything the model sees about the API therefore comes
from that spec.

| Lever | As written | Assessment against current architecture |
|--------------------|------------------------|-------------------------------------------------------------|
| 1. Tool/action renames across 5 toolsets (~1.5 wk) | Rename actions containing `database`, `plugin`, `appdata`, `timeflow` | **Largely inert.** Dynamic mode has no action names to rename. The five `.txt` toolsets do carry the terminology (183 `dsource`, 377 `vdb`, 73 `timeflow`, 14 `appdata` hits) but are opt-in legacy. |
| 2. Docstrings and descriptions (~1 wk) | Rewrite every tool- and action-level description | **Shrinks to two docstrings** (`discovery`, `execute`) plus the spec — which this repo does not own. This is the lever that becomes the spec work. |
| 3. Server instructions (~3 d) | Author `server_instructions.txt` loaded at FastMCP init | **Highest leverage, cheapest.** *(At time of writing 0% done; now done — see status below.)* `main.py:69` is `FastMCP(name=..., lifespan=...)` with no `instructions=`. `fastmcp>=2.13.2` is already pinned and supports it — **the "FastMCP version bump may be a prerequisite" open question is resolved: no bump needed.** |
| 4. Errors and confirmation prompts (~2 d) | Audit `manual_confirmation.txt` | **Real and correctly sized.** 79 hand-authored rules in this repo reaching every user regardless of toolset; message templates contain 87 `VDB`, 31 `dSource`, 12 `environment`, 9 `database`, 6 `timeflow` occurrences. |

**Status (current).** Lever 3 is done: `config/server_instructions.md` is loaded by
`load_server_instructions()` and passed as `instructions=` to `FastMCP(...)` in `main.py`.
Levers 1, 2 and 4 have also been applied in this repo for the toolsets and pre-built tools:
tool/action renames (`timeline_tool`, `connector_schema_tool`, `vdb_template_tool`, ...),
canonical pre-built docstrings with per-tool customer-alias lines, canonical confirmation
templates with `{name}` placeholders rendered in every toolset, and `to_canonical()` applied to
raw error bodies and to OpenAPI summaries shown by `discovery`. The spec-side work (DCT epic)
is unchanged by this.

The net effect: the original "~3 weeks, mostly editorial, in the MCP repo" estimate is inverted.
Most of the user-visible benefit sits in Levers 3–4 (~1 week, no cross-team dependency), and the
dominant vocabulary surface is the spec — owned by another team and carrying real build risk.

---

## Known blockers, inherited from DLPXECO-14529

These belong to the DCT-side epic and must be visible at ARB.

**A hard 3 MB build ceiling.** `app/build/api-codeGen.yaml` must stay under SnakeYAML's
3,145,728 code-point limit or `validateSwaggerApi_` and `openApiGenerate_` fail. It was already at
~81% before any enrichment; the prototype lands at ~0.5% headroom. Verified by bytecode inspection
that the limit is SnakeYAML's own `LoaderOptions` default, identical in 1.33 and 2.5, and that
neither `jackson-dataformat-yaml` nor `swagger-core` ever calls `setCodePointLimit`. It is only
configurable from swagger-parser-v3 ≥ 2.1.43, absent from the 2.1.2 pinned by openapi-generator
6.3.0. **Bumping openapi-generator alone does nothing** — it needs the bump plus a
`maxYamlCodePoints` system property, or descriptions stripped from the codegen input only.

**A breaking-change trap for description work.** `UpdateComplianceJobRequest` declares `pre_script`
and `post_script` as two byte-identical inline schemas sharing `title: UpdateComplianceJobScript`,
which openapi-generator deduplicates into one model class. Giving them different descriptions
splits it into `UpdateComplianceJobScript` + `UpdateComplianceJobScript1` and changes the type of
`postScript` — breaking for every published client library. Caught by generating Java before and
after and diffing all 1,534 files; fixed by giving both identical text. It is the only such case
across the five source specs today, but the pattern will recur.

---

## Proposed shape

**One PPM.** Retitle PPM-1129 to *"AI Assistant (GA) — Agent-Ready API Surface: Vocabulary &
Domain Model"*. Fold row 6's intent into it and update the GA page so rows 5 and 6 both reference
it. One ARB, one CTC, one set of Design reviewers.

**Two delivery epics**, because the risk profiles differ sharply:

| Epic | Scope | Risk | Rough size |
|--------------------|----------------------------------------|--------------------------|------------|
| MCP-side (`dxi-mcp-server`) | `server_instructions` wired into `FastMCP(...)`; vocabulary pass over the 79 `manual_confirmation.txt` templates; error-message translation layer; BYO AI provider startup notice (PPM-1077) | None known. No cross-team dependency, no version bump. | ~1 week |
| DCT-side (`apigw-services`) | DLPXECO-14529 un-deferred: description coverage to 100%, synonyms into `summary`, `filter_expression` grammar, per-endpoint filterable fields, agent-affordance annotations | SnakeYAML ceiling; codegen model-split trap; needs DCT team capacity | Prototyped; needs re-estimation after the ceiling decision |

Splitting this way means a build-toolchain problem gates only its own epic, not the November date
for both.

---

## Sequencing

1. **Now, unblocked:** MCP-side epic. Nothing outside this repo is required.
2. **Decision needed early:** how to clear the 3 MB ceiling — lift it deliberately (generator bump
   plus system property) or strip descriptions from the codegen input. This determines whether the
   DCT-side epic fits the November release at all.
3. **Design input needed before the spec pass is finalised:** connector vs. connection/subconnection
   timing, glossary hosting. (dSource deprecation direction is resolved — see below.) Reviewers
   named in PPM-1129 are Jake Smith and Brian Deverter.
4. **Downstream:** PPM-1174 Phase 2 (semantic search tool) depends on this landing. The fuzzy
   ranker that would back it already exists at `tools/core/endpoint_discovery.py` but is dormant —
   imported only by `meta_tools.py`, which is not registered as MCP tools. It ranks on the same
   thin `summary`/`path` tokens, which is precisely why it returns noise without this work. The
   prerequisite claim in PPM-1129 checks out.

---

## Open questions carried forward

- **Glossary hosting and Design review.** Glossary v1.2 (28 canonical terms, 172 synonym rows,
  three sheets) exists only as `DCT_MCP_Server_Vocabulary_Glossary_v1.2.xlsx` and is not in any
  repo. PPM-1129 recommends hosting the MCP-specific layer as a PDUX Confluence page linked to
  canonical Delphix terminology, the Perforce Lexicon and the Design System Glossary. Blocks the
  spec pass; does **not** block the MCP-side epic.
- **dSource deprecation direction — resolved.** The Design System Glossary recommends deprecating
  customer-facing *dSource*; Glossary v1.2 retains it because no clean replacement exists. Product
  has confirmed (PPM-1129, 2026-10-12): deprecation is deferred to a future initiative, and dSource
  stays canonical for this PPM. No code change was required — the vocabulary layer already treats
  dSource as canonical throughout.
- **Connector vs. connection/subconnection.** *Connector* has dual meanings and Delphix is moving
  toward connection/subconnection. Need Design confirmation of timing before renaming anything.
- **Raw API error translation layer — resolved.** `tools/core/vocabulary.py:to_canonical()`,
  driven by `config/mappings/vocabulary.txt`, translates raw DCT/engine error bodies in both the
  dynamic `execute` tool and the pre-built tools (`core/decorators.py`), additively as
  `message_for_user`. It never rewrites paths, URLs or IDs, and skips words with an unrelated
  meaning (Oracle "container database", "VDB inventory report").
- **Terminology not yet applied by the prototype — since applied.** `timeflow` → `timeline`;
  VDB Group ↔ "container"; environment/host/machine synonyms; hiding the AppData vs. native
  connector split; unqualified "engine" vs. DCT. These were PPM-1129's headline items; they have
  since been reconciled against the real Glossary v1.2 and applied in `server_instructions.md`,
  `vocabulary.txt`, `manual_confirmation.txt`, and the toolset/tool names and docstrings.

---

## Explicitly out of scope

- Renaming API endpoints or OpenAPI tags. A tag rename also renames the generated client class
  (`Connectors` → `ConnectorsApi`), which is breaking.
- An API version bump. The structural diff is descriptions and summaries only, consistent with the
  PPM-1124 precedent.
- Full Continuous Compliance terminology reconciliation.
- Customer-facing glossary publication.
- The post-GA "Guidance for AI Agents" documentation page — revisit once 3–6 months of real agent
  interaction data exist.

---

## Sources

- PPM-1129 description (Ready to Review, 18 pts, target 2026-11-24)
- DLPXECO-14529 description — measurements, prototype results, blockers
- GA planning page, rows 5 and 6, last edited 2026-09-23
- `dxi-mcp-server` @ `7f2f4da`: `config/config.py:28`, `main.py:69`, `tools/core/spec_cache.py`,
  `tools/core/dynamic.py:1197`, `config/mappings/manual_confirmation.txt`,
  `config/toolsets/*.txt`, `tools/core/endpoint_discovery.py`, `pyproject.toml`
