# Running Connector Workflow Tests

These tests verify that an **LLM can drive the DCT MCP server through a full
dSource/VDB lifecycle** for a given connector — i.e. that the right MCP tool is
called for each operation and the operation actually completes against a real DCT.

You do **not** need to know the codebase. Three commands.

> ⚠️ Run only against a **disposable / cloned DCT** — these tests create and
> delete dSources and VDBs.

---

## 1. See what a connector needs

```bash
dct-mcp-test --connector mysql --show-requirements
```

This reads the connector schema and prints exactly which hosts/credentials are
required and which are still missing — for example:

```
MySQL (AppData / Plugin)  (connector=mysql)
Workflows that will run: link_dsource, snapshot_dsource, provision_vdb, refresh_vdb, delete_vdb, delete_dsource

Required inputs:
  ✗ MISSING  source_host    — Source DB hostname/FQDN
  ✗ MISSING  target_host    — Target/staging DB hostname/FQDN
  ...
  ✗ MISSING  engine         — Delphix engine hostname + password
```

## 2. Supply the credentials (once)

Either copy the template and fill in your connector:

```bash
cp tests/fixtures/connectors/.secrets.yaml.example tests/fixtures/connectors/.secrets.yaml
# edit .secrets.yaml — fill the `engine:` block and the `mysql:` block
```

…**or** set environment variables (good for CI / autonomous runs):

```bash
export DCT_ENGINE_HOSTNAME=...      DCT_ENGINE_PASSWORD=...
export DCT_CONNECTOR_MYSQL_SOURCE_HOST=...   DCT_CONNECTOR_MYSQL_TARGET_HOST=...
export DCT_CONNECTOR_MYSQL_ENV_USER=...      DCT_CONNECTOR_MYSQL_ENV_PASSWORD=...
export DCT_CONNECTOR_MYSQL_LINK_USER=...     DCT_CONNECTOR_MYSQL_LINK_PASSWORD=...
```

Re-run step 1 until every line shows `✓`.

## 3. Run

```bash
dct-mcp-test --connector mysql --base-url https://your-dct --api-key <key>
```

It runs a **preflight** (credentials present? engine set?) and fails fast with a
clear message if anything is missing — then runs the workflow matrix
autonomously (no prompts) and writes two CSVs:

```
test-results/mysql-MCP-test-results(Results).csv   # one row per workflow step
test-results/mysql-MCP-test-results(Summary).csv   # pass/fail + accuracy per connector
```

---

## Self-bootstrapping

The run **creates its own prerequisites** before exercising operations. A `Setup`
section runs first, idempotently (creates only if missing):

```
engine → toolkit → environment → source config → dSource → VDB
```

So you can point it at a bare DCT and it will add the engine, upload the connector
(`toolkit_file` in schema.yaml / `.secrets.yaml`), register the environment, create
the source config, link the dSource, and provision the VDB — then run all the
list/enable/disable/refresh/snapshot/rollback/delete tests against them. If an object
already exists, that setup step confirms it and moves on (nothing is recreated).

## What gets checked per step

| Check | Meaning |
|-------|---------|
| **Tool correct** | the LLM called the expected MCP tool (e.g. `data_tool`) |
| **Action correct** | it called the expected action (e.g. `provision_by_snapshot`) |
| **Operation completed** | an independent read confirms the object was actually created/removed |

Per-row verdicts: **PASS**, **FAIL**, **EXPECTED-ERROR** (op correctly rejected, e.g.
deleting an in-use toolkit), **N/A** (not applicable to this connector, e.g. V2P),
**SKIPPED** (destructive-to-shared ops like engine deregister — opt in with
`CONNECTOR_DESTRUCTIVE=1`).

## Other connectors

Same three commands with `--connector db2` or `--connector postgresql`. Fill the
matching block in `.secrets.yaml` (or `DCT_CONNECTOR_DB2_*` env vars) first.

## Editing the test matrix (no code)

The workflow steps live in `tests/fixtures/connectors/schema.yaml` under each
connector's `workflows:` block. Add, remove, reorder, or re-word a step there —
no Python changes needed. Placeholders like `{dsource_name}`, `{target_host}`,
`{provision_action}` are filled at runtime from your secrets + schema.
