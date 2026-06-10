# CDA LLM Test Suite — Prerequisite Chain Plan

> **Goal:** before running any CDA scenario, verify the full prerequisite chain is satisfied and
> print a specific, actionable message if any step is missing. Each step is a hard prerequisite
> for all subsequent steps. After the chain is validated, run all `continuous_data_admin.md`
> prompts as the priority LLM scenario suite.
>
> **Start date:** building begins 2026-06-10. Read STATUS first.

---

## STATUS

**State:** plan written 2026-06-10. Not started.

| Phase | What | State |
|---|---|---|
| P0 | Prerequisite checker: read-only DCT health check (engine → connector → hosts → source config → dsource → vdb) | ☑ DONE 2026-06-10 — live validated (PASSED, chain reads correctly) |
| P1 | Connector fixture layer: ConnectorSpec with all link+provision fields per type | ☑ DONE 2026-06-10 |
| P2 | 6-step setup flow: idempotent Claude-driven steps, live run in progress | ◑ live run b9i4wr3s3 |
| P3 | Full CDA scenario suite: all 431 prompts gated on prerequisite checker | ☐ |
| P4 | Teardown: cleanup in reverse order | ☐ |

---

## THE PREREQUISITE CHAIN

```
DCT instance accessible
    └─ Engine registered (engine_tool.search → at least one engine)
           └─ Connector installed on engine (toolkit_tool.search → connector for this type)
                  └─ Hosts added to engine (environment_source_tool.search → hosts present)
                         └─ Source config / repository exists (data_connection_tool or
                            environment_source_tool → repository for this connector)
                                └─ dSource linked (dsource_tool.search → dsource present)
                                       └─ VDB provisioned (vdb_tool.search → vdb present)
```

**Rule:** each step checks DCT state via a real tool call. If a step is missing:
- Print exactly what is missing and what to do next.
- Skip all downstream tests (pytest.skip with the specific reason).
- Never fail — only skip with an informative message.

---

## CURRENT LLM TEST COUNT

**Total LLM test functions today: 9** across 6 files:
| File | Tests | Coverage |
|---|---|---|
| `test_scenarios.py` | 1 (parametrized → 904 cases) | All persona read-tier prompts |
| `test_discoverability.py` | 1 (parametrized → 7) | self_service tool discovery |
| `test_discoverability_cda.py` | 1 (parametrized → 7) | CDA tool discovery |
| `test_act_verify.py` | 2 | self_service vdb-tag + bookmark act→verify |
| `test_act_verify_cda.py` | 2 | admin engine-tag + engine register→verify |
| `test_act_verify_mysql.py` | 2 | add MySQL envs + AppData dSource link→verify |

**After this plan: +~15–20 new test functions** (prereq checker + setup + per-connector scenarios
+ teardown), covering all 431 CDA prompts with a gated, stateful workflow.

---

## CONNECTOR TYPES AND THEIR SPECIFIC FIELDS

Each connector type has different required parameters at each step. The test framework
must be parameterizable by connector type.

### Field matrix per connector

| Step | AppData (MySQL) | Oracle | MSSQL | ASE |
|---|---|---|---|---|
| **Connector install** | AppData plugin name | Oracle connector | MSSQL connector | ASE connector |
| **Add host** | environment user + SSH creds | same | same | same |
| **Source config params** | plugin-specific (mount path, backup path) | SID/service, home, oracle_user | db_name, backup_path | server_name, db_name |
| **dSource link action** | `dsource_link_appdata` | `dsource_link_oracle` | `dsource_link_mssql` | `dsource_link_ase` |
| **dSource link key fields** | environment_user, parameters (plugin JSON), sync_parameters | source_id, oracle_jdbc_string, mount_path | source_id | source_id, database_name |
| **VDB provision actions** | `provision_by_snapshot`, `provision_by_timestamp` | same | same | same |

**For today's MySQL/AppData setup:**
- MYSQL_SOURCE_HOST + MYSQL_TARGET_HOST registered as environments
- Connector: AppData plugin (already installed when toolkit is present)
- Source config: plugin-specific mount path, backup location
- dSource link: on target host, environment_user=delphix_os
- VDB provision: from the dSource just linked

---

## PHASE P0 — Prerequisite checker  (the keystone)

File: `tests/llm_local/prereq_checker.py`

A pytest fixture `cda_prereqs(connector_type)` that runs a series of read-only Claude
calls against the real DCT and returns a `PrereqState` dataclass:

```python
@dataclass
class PrereqState:
    engine_id: str | None        # None = not found
    engine_name: str | None
    connector_ok: bool           # connector for this type is installed
    hosts: list[str]             # hostnames added to the engine
    source_config_ok: bool       # repository / source config present
    dsource_id: str | None       # None = no dSource for this connector type
    dsource_name: str | None
    vdb_id: str | None           # None = no VDB from this dSource
    vdb_name: str | None

    def first_missing(self) -> str | None:
        """Returns the name of the first unmet prerequisite, or None if all met."""
        if not self.engine_id:   return "engine"
        if not self.connector_ok: return "connector"
        if not self.hosts:       return "hosts"
        if not self.source_config_ok: return "source_config"
        if not self.dsource_id:  return "dsource"
        if not self.vdb_id:      return "vdb"
        return None
```

Each check is a Claude read call (not a direct API call) so it exercises the real tool
surface. Skip message template:

```
PREREQ MISSING [{step}]: {specific message}
  engine:        No Delphix engine registered in DCT — run test_setup_engine first.
  connector:     No {type} connector installed on engine {name} — run test_setup_connector.
  hosts:         No hosts added to engine {name} — run test_setup_hosts first.
  source_config: No {type} repository/source config found — run test_setup_source_config.
  dsource:       No {type} dSource linked — run test_setup_dsource first.
  vdb:           No VDB provisioned from {dsource_name} — run test_setup_vdb first.
```

---

## PHASE P1 — Connector fixture layer

File: `tests/llm_local/connector_fixtures.py`

A `ConnectorSpec` dataclass loaded from env vars. Each connector type has a named
preset, selected by `CONNECTOR_TYPE` env var (default: `appdata`):

```python
@dataclass
class ConnectorSpec:
    type: str                    # "appdata" | "oracle" | "mssql" | "ase"
    source_host: str             # source host (e.g. r95-mys-s11.dlpxdc.co)
    target_host: str             # target host (where dSource links and VDBs provision)
    env_user: str                # OS user for environment
    env_password: str
    link_user: str               # OS user for dSource link
    link_password: str
    db_user: str | None          # DB-level user (if needed)
    db_password: str | None
    dsource_link_action: str     # "dsource_link_appdata" | "dsource_link_oracle" | ...
    link_extra_fields: dict      # connector-specific extra fields for the link call
    provision_extra_fields: dict # connector-specific extras for provision call
```

Env vars (current MySQL/AppData defaults already defined in .env.local):
```
CONNECTOR_TYPE=appdata          # or oracle, mssql, ase
MYSQL_SOURCE_HOST / MYSQL_TARGET_HOST
MYSQL_ENV_USER / MYSQL_ENV_PASSWORD
MYSQL_LINK_USER / MYSQL_LINK_PASSWORD
# Oracle adds: ORACLE_SID, ORACLE_HOME, ORACLE_USER
# MSSQL adds:  MSSQL_DB_NAME, MSSQL_BACKUP_PATH
# ASE adds:    ASE_SERVER_NAME, ASE_DB_NAME
```

---

## PHASE P2 — Setup flow (6 steps, each gated on previous)

File: `tests/llm_local/test_cda_setup.py`

Six sequential test functions, each using `llm_driver_for("continuous_data_admin")`.
Each **checks the prerequisite first** (skip if already done, act if not):

```
test_setup_01_engine           — register engine, wait for job, verify
test_setup_02_connector        — install connector on engine (toolkit_tool), verify
test_setup_03_hosts            — add source + target hosts as environments, verify each
test_setup_04_source_config    — create source config / verify repository is discoverable
test_setup_05_dsource          — link dSource on target host, wait for job, verify
test_setup_06_vdb              — provision VDB from dSource, wait for job, verify
```

Each step:
- Runs the prereq checker first; if the step is already done, skips with "already present"
- On act: explicit prompt with all required fields embedded (no asking for missing params)
- On verify: independent read with the identifier NOT in the prompt
- On failure: marks the step as failed so all downstream tests skip with the prereq message

---

## PHASE P3 — Full CDA scenario suite gated on prereq checker

File: `tests/llm_local/test_cda_scenarios.py`

The 431 `continuous_data_admin.md` prompts run as parametrized scenarios (same mechanism
as `test_scenarios.py`) BUT gated on `PrereqState.first_missing()`:

```python
@pytest.fixture(autouse=True)
def require_cda_prereqs(cda_prereqs, scenario):
    missing = cda_prereqs.first_missing()
    if missing:
        pytest.skip(f"PREREQ MISSING [{missing}]: ...")
```

The pre-run check is cached per session (one Claude call per chain-link, not per scenario).

**Smart skip logic per scenario group:**
- `engine_tool` prompts → only need `engine` prereq
- `toolkit_tool` prompts → need `engine` + `connector`
- `environment_source_tool` prompts → need `engine` + `hosts`
- `data_tool` / `dsource_tool` / `vdb_tool` → need full chain
- `iam_tool`, `reporting_tool`, `tag_tool` etc → no infra prereqs (skip check for those)

---

## PHASE P4 — Teardown

File: `tests/llm_local/test_cda_teardown.py`

Reverse-order cleanup (VDB → dSource → environments → engine unregister). Each step
checks the prereq state and only acts if the object exists. Tagged with `E2E_RUN_TAG`.

---

## HOW TO RUN

```bash
# Full setup + all 431 CDA prompts + teardown:
set -a; source .env.local; set +a
export CONNECTOR_TYPE=appdata
export MYSQL_SOURCE_HOST=r95-mys-s11.dlpxdc.co
export MYSQL_TARGET_HOST=r95-mys-t11.dlpxdc.co
export MYSQL_ENV_USER=mysql       MYSQL_ENV_PASSWORD=connect_123
export MYSQL_LINK_USER=delphix_os  MYSQL_LINK_PASSWORD='Delphix@123'
export E2E_RUN_TAG="cda-$(date +%s)"
LLM_ALLOW_MUTATION=1 \
  .venv-live/bin/python -m pytest tests/llm_local/test_cda_setup.py \
                                  tests/llm_local/test_cda_scenarios.py \
                                  tests/llm_local/test_cda_teardown.py \
  -m llm_driven -v

# Or via the CLI runner (once wired in S5):
.venv-live/bin/dct-mcp-test --layer scenarios --persona continuous_data_admin \
  --mutations --report cda-report.xml
```

---

## WHAT CHANGES IN EXISTING TESTS

- `test_act_verify_mysql.py` → **absorbed into** `test_cda_setup.py` P3+P4 steps
  (add-environments and link-dsource become `test_setup_03_hosts` / `test_setup_05_dsource`).
- `test_act_verify_cda.py` (engine-tag / engine-register) → stays but engine-register
  is now also `test_setup_01_engine`.
- `test_scenarios.py` (the generic harness) → CDA scenarios move to `test_cda_scenarios.py`
  which adds the prereq gate. Other personas stay in `test_scenarios.py`.
- `test_discoverability_cda.py` → stays as a fast standalone discoverability check.

---

## EFFORT ESTIMATE

| Phase | Effort | Output |
|---|---|---|
| P0 prereq checker | 0.5d | `prereq_checker.py` |
| P1 connector fixtures | 0.5d | `connector_fixtures.py` |
| P2 setup 6 steps | 1d | `test_cda_setup.py` + live tuning |
| P3 full 431 scenarios gated | 0.5d code + 2h live run | `test_cda_scenarios.py` |
| P4 teardown | 0.5d | `test_cda_teardown.py` |
| **Total** | **~3 days** | prereq-gated, stateful 431-prompt CDA suite |
