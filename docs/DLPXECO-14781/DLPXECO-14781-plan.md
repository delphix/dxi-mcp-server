# DLPXECO-14781 AppData Connector Secret Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the dynamic-mode `execute` sensitive-input gate to detect AppData connector credential fields declared `"format": "password"` in toolkit schema.json, routing them through the DCT AI Assistant's out-of-band secure capture instead of the LLM context.

**Architecture:** A new `connector_secrets.py` module resolves the toolkit behind each AppData operation, walks the toolkit schema for password-format fields (recursive, with $ref/combinator support, depth/node guards), and caches results per (base_url, toolkit_id, version). The existing Step 3.5 gate in `dynamic.py` is extended to call this module and merge connector-derived secret locations with native annotation-based detection. All lookups are host-scoped (capture-capable only), fail-open, and time-budgeted.

**Tech Stack:** Python 3.11+, asyncio, stdlib only (no new dependencies), pytest, existing `DCTAPIClient`, `ClientRegistry`, `loader.py` pattern, FastMCP dynamic mode.

## Global Constraints

- Python 3.11+; no new third-party dependencies
- Every new logger uses `get_logger(__name__)` from `dct_mcp_server.core.logging`
- Never log body values, secret values, toolkit response payloads, or `str(exc)` of `DCTClientError`
- Warnings carry only: op method+path, toolkit id, version, error class name, stage name
- All new tool functions use `@log_tool_execution`; async execute helpers do NOT
- `connector_secrets.py` must never raise from its public entry point `find_flagged_connector_secrets`
- `sensitive_field_locations` entries carry `name` and `location` only — never a value
- Gate fires only when `_secure_capture_host()` returns True (host-scoped)
- All AppData path strings come from `config/mappings/appdata_operations.txt` via `loader.py`
- Test coverage of new code ≥ 80% line coverage
- `sensitive_applied` nonce must be authenticated before any host-applied fields are trusted

## Progress Tracker

| Task | Status | Notes |
|------|--------|-------|
| Task 1: Test fixtures | [ ] | db2_toolkit.json + mysql_toolkit.json |
| Task 2: host_trust.py | [ ] | Move nonce check from dynamic.py |
| Task 3: appdata_operations.txt | [ ] | 19 operations + @toolkit directive |
| Task 4: loader.py additions | [ ] | load_appdata_operations + match |
| Task 5: client_registry.py | [ ] | Add identity_key() |
| Task 6: connector_secrets.py | [ ] | Core module — walker, caches, gate entry |
| Task 7: dynamic.py wiring | [ ] | Extend Step 3.5, discovery note |
| Task 8: Integration tests | [ ] | test_appdata_secret_gate.py |
| Task 9: Docs | [ ] | CLAUDE.md + architecture.md |

---

### Task 1: Test Fixtures [sequential] [model:haiku]

**Spec References:** AC-1, AC-4, AC-8

**Files:**
- Create: `tests/fixtures/toolkits/db2_toolkit.json`
- Create: `tests/fixtures/toolkits/mysql_toolkit.json`
- Create: `tests/fixtures/toolkits/__init__.py` (empty, if missing)

**Interfaces:**
- Produces: JSON toolkit fixture objects loaded by unit and integration tests via `json.load(open(...))`
- Both fixtures have shape: `{"id": "<id>", "version": "1.0", "linked_source_definition": {...}, "virtual_source_definition": {...}, "snapshot_parameters_definition": {...}, "discovery_definition": {"source_config_schema": {...}}}`

- [ ] **Step 1: Create DB2 toolkit fixture**

```json
{
  "id": "db2-toolkit-001",
  "version": "2.3.1",
  "name": "DB2 Toolkit",
  "linked_source_definition": {
    "type": "object",
    "properties": {
      "instanceUser": {"type": "string"},
      "instancePassword": {"type": "string", "format": "password"},
      "port": {"type": "integer"},
      "mountPath": {"type": "string"},
      "backupPath": {"type": "string"},
      "nodes": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "instanceId": {"type": "string"},
            "instancePassword": {"type": "string", "format": "password"}
          },
          "required": ["instanceId", "instancePassword"]
        }
      }
    },
    "required": ["instanceUser", "instancePassword", "port", "mountPath"]
  },
  "virtual_source_definition": {
    "type": "object",
    "properties": {
      "mountPath": {"type": "string"},
      "appDataPort": {"type": "integer"}
    }
  },
  "virtual_to_physical_definition": {
    "type": "object",
    "properties": {
      "targetHost": {"type": "string"},
      "targetUser": {"type": "string"},
      "targetPassword": {"type": "string", "format": "password"},
      "targetMountPath": {"type": "string"}
    },
    "required": ["targetHost", "targetUser", "targetPassword", "targetMountPath"]
  },
  "snapshot_parameters_definition": {
    "schema": {
      "type": "object",
      "properties": {
        "resync": {"type": "boolean"},
        "snapshotLabel": {"type": "string"}
      }
    }
  },
  "discovery_definition": {
    "source_config_schema": {
      "type": "object",
      "properties": {
        "databaseName": {"type": "string"},
        "instanceId": {"type": "string"}
      },
      "required": ["databaseName", "instanceId"]
    }
  }
}
```

Save to: `tests/fixtures/toolkits/db2_toolkit.json`

- [ ] **Step 2: Create MySQL toolkit fixture**

```json
{
  "id": "mysql-toolkit-001",
  "version": "3.1.0",
  "name": "MySQL Toolkit",
  "linked_source_definition": {
    "type": "object",
    "definitions": {
      "Credentials": {
        "type": "object",
        "properties": {
          "dbUser": {"type": "string"},
          "dbPassword": {"type": "string", "format": "password"}
        },
        "required": ["dbUser", "dbPassword"]
      }
    },
    "properties": {
      "host": {"type": "string"},
      "port": {"type": "integer"},
      "credentials": {"$ref": "#/definitions/Credentials"},
      "replicationUser": {"type": "string"},
      "replicationPassword": {"type": "string", "format": "password"},
      "authConfig": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "method": {"type": "string", "enum": ["password"]},
              "password": {"type": "string", "format": "password"}
            }
          },
          {
            "type": "object",
            "properties": {
              "method": {"type": "string", "enum": ["key"]},
              "privateKeyPath": {"type": "string"}
            }
          }
        ]
      }
    },
    "required": ["host", "port", "credentials"]
  },
  "virtual_source_definition": {
    "type": "object",
    "properties": {
      "mountPath": {"type": "string"},
      "port": {"type": "integer"}
    }
  },
  "virtual_to_physical_definition": {
    "type": "object",
    "properties": {
      "targetHost": {"type": "string"},
      "targetUser": {"type": "string"},
      "targetPassword": {"type": "string", "format": "password"}
    }
  },
  "snapshot_parameters_definition": {
    "schema": {
      "type": "object",
      "properties": {
        "resync": {"type": "boolean"}
      }
    }
  },
  "discovery_definition": {
    "source_config_schema": {
      "type": "object",
      "properties": {
        "databaseName": {"type": "string"},
        "port": {"type": "integer"}
      }
    }
  }
}
```

Save to: `tests/fixtures/toolkits/mysql_toolkit.json`

- [ ] **Step 3: Create empty __init__.py if it does not exist**

```bash
touch tests/fixtures/toolkits/__init__.py
```

- [ ] **Step 4: Verify fixtures are valid JSON**

```bash
python3 -c "import json; json.load(open('tests/fixtures/toolkits/db2_toolkit.json')); json.load(open('tests/fixtures/toolkits/mysql_toolkit.json')); print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/toolkits/
git commit -m "test: add DB2 and MySQL toolkit JSON fixtures for DLPXECO-14781"
```

---

### Task 2: host_trust.py — Shared Nonce Trust Module [sequential] [model:haiku]

**Spec References:** FR-005, FR-009

**Files:**
- Create: `src/dct_mcp_server/tools/core/host_trust.py`
- Modify: `src/dct_mcp_server/tools/core/dynamic.py` (re-import only, remove the originals)
- Test: `tests/unit/test_dynamic.py` (imports from dynamic must still work)

**Interfaces:**
- Produces: `_SENSITIVE_NONCE_ENV: str`, `host_nonce_ok(marker: Any) -> bool`
- `dynamic.py` re-exports both under the same names so all existing tests pass without change

- [ ] **Step 1: Write failing test — import from host_trust directly**

In `tests/unit/test_connector_secrets.py` (file to be created in Task 6; for now, inline this check in a temporary test or just verify the import works):

```python
# tests/unit/test_host_trust.py  (temporary, to verify move)
import os
from dct_mcp_server.tools.core.host_trust import _SENSITIVE_NONCE_ENV, host_nonce_ok

def test_host_nonce_ok_env_match(monkeypatch):
    monkeypatch.setenv(_SENSITIVE_NONCE_ENV, "test-nonce")
    assert host_nonce_ok("test-nonce") is True

def test_host_nonce_ok_mismatch(monkeypatch):
    monkeypatch.setenv(_SENSITIVE_NONCE_ENV, "test-nonce")
    assert host_nonce_ok("wrong") is False

def test_host_nonce_ok_no_env(monkeypatch):
    monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
    assert host_nonce_ok("anything") is False
```

Run: `pytest tests/unit/test_host_trust.py -v`
Expected: FAIL (module not found)

- [ ] **Step 2: Read the current _host_nonce_ok and _SENSITIVE_NONCE_ENV from dynamic.py**

Open `src/dct_mcp_server/tools/core/dynamic.py` and find the definitions. They look like:

```python
_SENSITIVE_NONCE_ENV = "DCT_MCP_SENSITIVE_NONCE"

def _host_nonce_ok(marker: Any) -> bool:
    """Return True if *marker* matches the nonce the host injected."""
    nonce = os.environ.get(_SENSITIVE_NONCE_ENV)
    if not nonce:
        return False
    return hmac.compare_digest(str(marker), nonce)
```

- [ ] **Step 3: Create host_trust.py**

```python
"""
host_trust.py — shared nonce trust check for the sensitive-input gate.

Moved from tools/core/dynamic.py so that connector_secrets.py can import it
without creating a circular dependency.
"""
from __future__ import annotations

import hmac
import os
from typing import Any

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# Name of the env var the embedding host injects at startup.
_SENSITIVE_NONCE_ENV = "DCT_MCP_SENSITIVE_NONCE"


def host_nonce_ok(marker: Any) -> bool:
    """Return True if *marker* matches the process-startup nonce.

    The host (DCT AI Assistant) injects the nonce via ``_SENSITIVE_NONCE_ENV``
    at process startup and passes it back in ``sensitive_applied.marker``.
    A wrong or missing nonce means the ``sensitive_applied`` payload was not
    injected by the trusted host, so applied fields are not trusted.
    """
    nonce = os.environ.get(_SENSITIVE_NONCE_ENV)
    if not nonce:
        return False
    return hmac.compare_digest(str(marker), nonce)
```

Save to: `src/dct_mcp_server/tools/core/host_trust.py`

- [ ] **Step 4: Update dynamic.py to import from host_trust and re-export**

In `dynamic.py`, find the existing definitions:
- Remove the `_SENSITIVE_NONCE_ENV = "DCT_MCP_SENSITIVE_NONCE"` constant
- Remove the `_host_nonce_ok` function definition
- Add at the top imports section:

```python
from dct_mcp_server.tools.core.host_trust import (
    _SENSITIVE_NONCE_ENV,
    host_nonce_ok as _host_nonce_ok,
)
```

Also add `host_nonce_ok` to the import so it is re-exported for any callers that use `_host_nonce_ok` from dynamic:

```python
# Re-export for backward compatibility with existing tests and callers
_host_nonce_ok = _host_nonce_ok  # already bound above
```

The key is: existing code that does `from dct_mcp_server.tools.core.dynamic import _SENSITIVE_NONCE_ENV` or `_host_nonce_ok` must continue working.

Also update any internal calls in `_secure_capture_host()` and `_host_applied_fields()` to use `_host_nonce_ok` (unchanged since we bound it above).

- [ ] **Step 5: Run tests to verify pass**

```bash
pytest tests/unit/test_host_trust.py tests/unit/test_dynamic.py tests/integration/test_sensitive_gate_scoping.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/dct_mcp_server/tools/core/host_trust.py src/dct_mcp_server/tools/core/dynamic.py tests/unit/test_host_trust.py
git commit -m "refactor: move host nonce check into host_trust.py (DLPXECO-14781)"
```

---

### Task 3: appdata_operations.txt Mapping File [sequential] [model:haiku]

**Spec References:** FR-001, FR-009, FR-010

**Files:**
- Create: `src/dct_mcp_server/config/mappings/appdata_operations.txt`

**Interfaces:**
- Produces: static text file parsed by `load_appdata_operations()` in Task 4
- Format: `@toolkit|/toolkits/{id}` directive + 19 operation lines
- Grammar: `METHOD|path_template|sub_object:definition[,...]|chain[;chain...]`

- [ ] **Step 1: Create appdata_operations.txt**

```
# AppData operation → sub-object → toolkit-definition → resolver-chain mapping
# DLPXECO-14781
#
# Grammar:
#   @toolkit|<GET path>                          directive: toolkit details endpoint
#   METHOD|path_template|sub_obj:def[,...]|chain[;chain...]
#
#   definition ∈ linked_source_definition | snapshot_parameters_definition |
#                virtual_source_definition | virtual_to_physical_definition |
#                source_config_definition
#
#   chain  := source ( ">" hop )*
#   source := "body:" field | "path:" param
#   hop    := get_path ( "^" get_path )* [ "." select ]
#   select : field | field "[" n "]" | field "[id=$]"
#   A hop with no select ends the chain: toolkit id = response["toolkit_id"].

@toolkit|/toolkits/{id}

POST|/dsources/appdata|parameters:linked_source_definition,sync_parameters:snapshot_parameters_definition|body:toolkit_id;body:source_id>/sources/{id}
PATCH|/dsources/appdata/{dsourceId}|parameters:linked_source_definition|body:toolkit_id;path:dsourceId>/dsources/{id}
POST|/dsources/{dsourceId}/snapshots|appdata_parameters:snapshot_parameters_definition|path:dsourceId>/dsources/{id}
POST|/vdbs/provision_by_snapshot|appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition|body:toolkit_id;body:source_data_id>/dsources/{id}^/vdbs/{id};body:snapshot_id>/snapshots/{id}.dataset_id>/dsources/{id}^/vdbs/{id}
POST|/vdbs/provision_by_timestamp|appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition|body:toolkit_id;body:source_data_id>/dsources/{id}^/vdbs/{id};body:timeflow_id>/timeflows/{id}.dataset_id>/dsources/{id}^/vdbs/{id}
POST|/vdbs/provision_by_location|appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition|body:toolkit_id;body:source_data_id>/dsources/{id}^/vdbs/{id};body:timeflow_id>/timeflows/{id}.dataset_id>/dsources/{id}^/vdbs/{id}
POST|/vdbs/provision_from_bookmark|appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition|body:toolkit_id;body:bookmark_id>/bookmarks/{id}.dsource_ids[0]>/dsources/{id};body:bookmark_id>/bookmarks/{id}.vdb_ids[0]>/vdbs/{id}
POST|/vdbs/empty_vdb|appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition|body:toolkit_id;body:repository_id>/environments/{body.environment_id}.repositories[id=$]
PATCH|/vdbs/{vdbId}|appdata_source_params:virtual_source_definition,appdata_config_params:source_config_definition|body:toolkit_id;path:vdbId>/vdbs/{id}
POST|/sources/appdata|parameters:source_config_definition|body:toolkit_id;body:repository_id>/environments/{body.environment_id}.repositories[id=$]
PATCH|/sources/appdata/{sourceId}|parameters:source_config_definition|body:toolkit_id;path:sourceId>/sources/{id}
POST|/dsources/{dsourceId}/export-by-snapshot|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:dsourceId>/dsources/{id}
POST|/dsources/{dsourceId}/export-by-timestamp|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:dsourceId>/dsources/{id}
POST|/dsources/{dsourceId}/export-by-location|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:dsourceId>/dsources/{id}
POST|/dsources/{dsourceId}/export-from-bookmark|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:dsourceId>/dsources/{id}
POST|/vdbs/{vdbId}/export-by-snapshot|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:vdbId>/vdbs/{id}
POST|/vdbs/{vdbId}/export-by-timestamp|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:vdbId>/vdbs/{id}
POST|/vdbs/{vdbId}/export-by-location|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:vdbId>/vdbs/{id}
POST|/vdbs/{vdbId}/export-from-bookmark|appdata_config_params:source_config_definition,appdata_v2p_params:virtual_to_physical_definition|path:vdbId>/vdbs/{id}
```

Save to: `src/dct_mcp_server/config/mappings/appdata_operations.txt`

- [ ] **Step 2: Verify line count**

```bash
grep -c '^[A-Z@]' src/dct_mcp_server/config/mappings/appdata_operations.txt
```

Expected: `20` (1 @toolkit directive + 19 operation lines)

- [ ] **Step 3: Commit**

```bash
git add src/dct_mcp_server/config/mappings/appdata_operations.txt
git commit -m "feat: add appdata_operations.txt mapping file (DLPXECO-14781)"
```

---

### Task 4: loader.py — AppData Operation Loader [sequential] [model:sonnet]

**Spec References:** FR-001, FR-009, FR-010

**Files:**
- Modify: `src/dct_mcp_server/config/loader.py`
- Create: `tests/unit/test_appdata_operations_loader.py`

**Interfaces:**
- Consumes: `appdata_operations.txt` (Task 3), existing `_path_matches(path, pattern) -> bool` in loader.py
- Produces:
  - `AppDataOperation(method: str, path_template: str, sub_objects: dict[str, str], chains: list[list[dict]])` frozen dataclass
  - `load_appdata_operations() -> tuple[list[AppDataOperation], str]` — cached, returns `(ops, toolkit_path)`
  - `match_appdata_operation(method: str, path: str) -> AppDataOperation | None`
  - `clear_cache()` extended to call `load_appdata_operations.cache_clear()`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_appdata_operations_loader.py`:

```python
"""Unit tests for AppData operation loader (DLPXECO-14781)."""
import pytest
from dct_mcp_server.config.loader import (
    load_appdata_operations,
    match_appdata_operation,
    clear_cache,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_load_returns_ops_and_toolkit_path():
    ops, toolkit_path = load_appdata_operations()
    assert toolkit_path == "/toolkits/{id}"
    assert len(ops) == 19


def test_all_ops_have_sub_objects():
    ops, _ = load_appdata_operations()
    for op in ops:
        assert op.sub_objects, f"{op.method} {op.path_template} has no sub_objects"


def test_dsources_appdata_post():
    op = match_appdata_operation("POST", "/dsources/appdata")
    assert op is not None
    assert "parameters" in op.sub_objects
    assert op.sub_objects["parameters"] == "linked_source_definition"
    assert "sync_parameters" in op.sub_objects
    assert op.sub_objects["sync_parameters"] == "snapshot_parameters_definition"


def test_dsources_appdata_patch():
    op = match_appdata_operation("PATCH", "/dsources/appdata/ds-123")
    assert op is not None
    assert op.path_template == "/dsources/appdata/{dsourceId}"
    assert "parameters" in op.sub_objects
    assert op.sub_objects["parameters"] == "linked_source_definition"


def test_vdbs_provision_by_snapshot():
    op = match_appdata_operation("POST", "/vdbs/provision_by_snapshot")
    assert op is not None
    assert "appdata_source_params" in op.sub_objects
    assert "appdata_config_params" in op.sub_objects


def test_no_match_for_native_operation():
    op = match_appdata_operation("POST", "/environments")
    assert op is None


def test_no_match_for_get():
    op = match_appdata_operation("GET", "/dsources/appdata")
    assert op is None


def test_path_with_dct_prefix_stripped():
    # Paths may come in with /dct/v3 prefix from the resolved path
    op = match_appdata_operation("POST", "/dct/v3/dsources/appdata")
    assert op is not None


def test_match_export_by_snapshot_dsource():
    op = match_appdata_operation("POST", "/dsources/ds-abc/export-by-snapshot")
    assert op is not None
    assert "appdata_config_params" in op.sub_objects
    assert "appdata_v2p_params" in op.sub_objects


def test_match_export_by_snapshot_vdb():
    op = match_appdata_operation("POST", "/vdbs/vdb-abc/export-by-snapshot")
    assert op is not None
    assert "appdata_config_params" in op.sub_objects


def test_chains_nonempty():
    op = match_appdata_operation("POST", "/dsources/appdata")
    assert op is not None
    assert len(op.chains) > 0


def test_load_is_cached(monkeypatch):
    calls = []
    original = load_appdata_operations.__wrapped__
    ops1, _ = load_appdata_operations()
    ops2, _ = load_appdata_operations()
    assert ops1 is ops2  # same object (cached)
```

Run: `pytest tests/unit/test_appdata_operations_loader.py -v`
Expected: FAIL (ImportError — `load_appdata_operations` not defined)

- [ ] **Step 2: Implement in loader.py**

Open `src/dct_mcp_server/config/loader.py` and add the following after the existing imports and before `clear_cache()`:

```python
import importlib.resources
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class AppDataOperation:
    """Parsed record from appdata_operations.txt."""
    method: str          # upper-case HTTP method
    path_template: str   # e.g. "/dsources/appdata"
    sub_objects: dict    # {sub_object_name: definition_name}
    chains: list         # list of chain dicts; each chain is a list of hop dicts


@lru_cache(maxsize=1)
def load_appdata_operations() -> tuple[list[AppDataOperation], str]:
    """Parse appdata_operations.txt and return (ops, toolkit_path).

    Malformed lines are skipped with a warning; never raises.
    """
    from dct_mcp_server.core.logging import get_logger
    _log = get_logger(__name__)

    mapping_path = (
        Path(__file__).parent / "mappings" / "appdata_operations.txt"
    )
    try:
        text = mapping_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("AppData mapping file not found: %s", exc)
        return [], ""

    ops: list[AppDataOperation] = []
    toolkit_path = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@toolkit|"):
            toolkit_path = line.split("|", 1)[1].strip()
            continue
        parts = line.split("|")
        if len(parts) != 4:
            _log.warning("AppData mapping: malformed line (expected 4 fields): %r", line)
            continue
        method, path_tmpl, sub_obj_str, chain_str = parts
        method = method.strip().upper()
        path_tmpl = path_tmpl.strip()
        # Parse sub_objects: "key:def,key2:def2"
        sub_objects = {}
        for pair in sub_obj_str.split(","):
            pair = pair.strip()
            if ":" not in pair:
                _log.warning("AppData mapping: malformed sub_object pair %r in line %r", pair, line)
                continue
            k, v = pair.split(":", 1)
            sub_objects[k.strip()] = v.strip()
        if not sub_objects:
            _log.warning("AppData mapping: no sub_objects in line %r", line)
            continue
        # Parse chains: semicolon-separated chain strings
        chains = []
        for chain_raw in chain_str.split(";"):
            chain_raw = chain_raw.strip()
            if not chain_raw:
                continue
            chains.append(chain_raw)
        ops.append(AppDataOperation(
            method=method,
            path_template=path_tmpl,
            sub_objects=sub_objects,
            chains=chains,
        ))

    return ops, toolkit_path


def match_appdata_operation(method: str, path: str) -> "AppDataOperation | None":
    """Return the first AppDataOperation matching *method* and *path*.

    Strips a leading /dct/v3 or /dct prefix before matching.
    Prefers literal (non-parameterised) templates over parameterised ones.
    Returns None if no match.
    """
    # Normalise path — strip /dct/v3 or /dct prefix
    norm = re.sub(r"^/dct/v\d+", "", path)
    norm = re.sub(r"^/dct", "", norm)
    if not norm.startswith("/"):
        norm = "/" + norm

    method_upper = method.upper()
    ops, _ = load_appdata_operations()

    literal_match: "AppDataOperation | None" = None
    param_match: "AppDataOperation | None" = None

    for op in ops:
        if op.method != method_upper:
            continue
        if not _path_matches(norm, op.path_template):
            continue
        if "{" in op.path_template:
            if param_match is None:
                param_match = op
        else:
            if literal_match is None:
                literal_match = op

    return literal_match if literal_match is not None else param_match
```

Also update `clear_cache()` to include:
```python
    load_appdata_operations.cache_clear()
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/unit/test_appdata_operations_loader.py -v
```

Expected: all PASS

- [ ] **Step 4: Run existing loader tests to check no regression**

```bash
pytest tests/unit/test_loader.py tests/unit/test_loader_extended.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/dct_mcp_server/config/loader.py tests/unit/test_appdata_operations_loader.py
git commit -m "feat: add load_appdata_operations and match_appdata_operation to loader.py (DLPXECO-14781)"
```

---

### Task 5: client_registry.py — identity_key() [sequential] [model:haiku]

**Spec References:** FR-001, FR-007, FR-008

**Files:**
- Modify: `src/dct_mcp_server/core/client_registry.py`
- Test: inline in existing `tests/unit/` or new small test

**Interfaces:**
- Consumes: existing `ClientRegistry._identity_hash(auth_ctx) -> str` private method
- Produces: `ClientRegistry.identity_key(self, auth_ctx) -> str` — stable, non-logged public hash

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_client_registry_identity.py
from dct_mcp_server.core.client_registry import ClientRegistry

def test_identity_key_returns_string():
    reg = ClientRegistry(capacity=4)
    auth = {"account_id": "user-1", "auth_mode": "embedded"}
    key = reg.identity_key(auth)
    assert isinstance(key, str)
    assert len(key) > 0

def test_identity_key_consistent():
    reg = ClientRegistry(capacity=4)
    auth = {"account_id": "user-1", "auth_mode": "embedded"}
    assert reg.identity_key(auth) == reg.identity_key(auth)

def test_identity_key_differs_by_account():
    reg = ClientRegistry(capacity=4)
    a1 = reg.identity_key({"account_id": "u1", "auth_mode": "embedded"})
    a2 = reg.identity_key({"account_id": "u2", "auth_mode": "embedded"})
    assert a1 != a2
```

Run: `pytest tests/unit/test_client_registry_identity.py -v`
Expected: FAIL (`identity_key` not defined)

- [ ] **Step 2: Add identity_key() to ClientRegistry**

Open `src/dct_mcp_server/core/client_registry.py` and find the class. After the `_identity_hash` private method, add:

```python
    def identity_key(self, auth_ctx: dict) -> str:
        """Return a stable, non-logged hash for *auth_ctx* for use as a cache key.

        Delegates to the private ``_identity_hash`` so callers outside this
        module have a stable, public surface without depending on the private
        name.  The return value is safe to use as a dict key but must not be
        logged raw (it is a hash of account_id and auth_mode).
        """
        return self._identity_hash(auth_ctx)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/unit/test_client_registry_identity.py -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/dct_mcp_server/core/client_registry.py tests/unit/test_client_registry_identity.py
git commit -m "feat: add identity_key() public method to ClientRegistry (DLPXECO-14781)"
```

---

### Task 6: connector_secrets.py — Core Detection Module [sequential] [model:sonnet]

**Spec References:** FR-001, FR-002, FR-003, FR-004, FR-005, FR-007, FR-008

**Files:**
- Create: `src/dct_mcp_server/tools/core/connector_secrets.py`
- Create: `tests/unit/test_connector_secrets.py`

**Interfaces:**
- Consumes: `host_trust.host_nonce_ok` (Task 2), `loader.match_appdata_operation` / `load_appdata_operations` (Task 4), `client_registry.ClientRegistry.identity_key` (Task 5), `DCTAPIClient.make_request`, `get_dct_config`
- Produces public API:
  - `SecretPath(path: str, required: bool, conditional: bool)` frozen dataclass
  - `FlaggedLocation(name: str, location: str)` frozen dataclass
  - `ConnectorResult(flagged: list[FlaggedLocation], covered_sub_objects: frozenset[str])` dataclass
  - `walk_secret_paths(schema, root=None, *, context="") -> frozenset[SecretPath]`
  - `expand_and_flag(sub_object, value, records) -> list[FlaggedLocation]`
  - `parse_applied(sensitive_applied) -> tuple[frozenset[str], frozenset[str]]` (names, locations)
  - `drop_applied(flagged, names, locations) -> list[FlaggedLocation]`
  - `async find_flagged_connector_secrets(client_resolver, method, resolved_path, path_params, body, sensitive_applied) -> ConnectorResult`
  - `clear_caches() -> None`

- [ ] **Step 1: Write unit tests for walk_secret_paths (RED)**

Create `tests/unit/test_connector_secrets.py`:

```python
"""Unit tests for connector_secrets.py (DLPXECO-14781)."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from dct_mcp_server.tools.core.connector_secrets import (
    walk_secret_paths,
    expand_and_flag,
    parse_applied,
    drop_applied,
    clear_caches,
    SecretPath,
    FlaggedLocation,
    ConnectorResult,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "toolkits"


@pytest.fixture(autouse=True)
def reset():
    clear_caches()
    yield
    clear_caches()


# ── walk_secret_paths ─────────────────────────────────────────────────────────

def test_flat_password_field():
    schema = {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "password": {"type": "string", "format": "password"},
        },
        "required": ["username", "password"],
    }
    paths = walk_secret_paths(schema)
    names = {p.path for p in paths}
    assert "password" in names
    assert "username" not in names


def test_required_flag_propagated():
    schema = {
        "type": "object",
        "properties": {
            "secret": {"type": "string", "format": "password"},
        },
        "required": ["secret"],
    }
    paths = walk_secret_paths(schema)
    p = next(x for x in paths if x.path == "secret")
    assert p.required is True


def test_optional_password_not_required():
    schema = {
        "type": "object",
        "properties": {
            "optSecret": {"type": "string", "format": "password"},
        },
    }
    paths = walk_secret_paths(schema)
    p = next(x for x in paths if x.path == "optSecret")
    assert p.required is False


def test_nested_object():
    schema = {
        "type": "object",
        "properties": {
            "credentials": {
                "type": "object",
                "properties": {
                    "user": {"type": "string"},
                    "pass": {"type": "string", "format": "password"},
                },
                "required": ["user", "pass"],
            }
        }
    }
    paths = walk_secret_paths(schema)
    names = {p.path for p in paths}
    assert "credentials.pass" in names
    assert "credentials.user" not in names


def test_array_items():
    schema = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "nodePassword": {"type": "string", "format": "password"},
                    },
                    "required": ["nodeId", "nodePassword"],
                }
            }
        }
    }
    paths = walk_secret_paths(schema)
    names = {p.path for p in paths}
    assert "nodes[*].nodePassword" in names
    assert "nodes[*].nodeId" not in names


def test_ref_resolution():
    schema = {
        "type": "object",
        "properties": {
            "creds": {"$ref": "#/definitions/Creds"}
        },
        "definitions": {
            "Creds": {
                "type": "object",
                "properties": {
                    "pw": {"type": "string", "format": "password"},
                },
                "required": ["pw"],
            }
        }
    }
    paths = walk_secret_paths(schema, root=schema)
    names = {p.path for p in paths}
    assert "creds.pw" in names


def test_oneof_marks_conditional():
    schema = {
        "type": "object",
        "properties": {
            "authConfig": {
                "oneOf": [
                    {
                        "properties": {
                            "method": {"type": "string"},
                            "password": {"type": "string", "format": "password"},
                        }
                    },
                    {
                        "properties": {
                            "method": {"type": "string"},
                            "keyPath": {"type": "string"},
                        }
                    }
                ]
            }
        }
    }
    paths = walk_secret_paths(schema)
    pw = next((p for p in paths if "password" in p.path), None)
    assert pw is not None
    assert pw.conditional is True


def test_allof_not_conditional():
    schema = {
        "type": "object",
        "allOf": [
            {
                "properties": {
                    "sharedPass": {"type": "string", "format": "password"},
                }
            }
        ]
    }
    paths = walk_secret_paths(schema)
    pw = next((p for p in paths if "sharedPass" in p.path), None)
    assert pw is not None
    assert pw.conditional is False


def test_cycle_guard():
    """Self-referencing schema must not infinite-loop."""
    schema = {
        "type": "object",
        "properties": {
            "child": {"$ref": "#"},
            "pw": {"type": "string", "format": "password"},
        },
        "required": ["pw"],
    }
    paths = walk_secret_paths(schema, root=schema)
    # Should not hang; pw at root level must be found
    names = {p.path for p in paths}
    assert "pw" in names


def test_depth_bound_terminates():
    """Deeply nested schema terminates before depth 33."""
    schema: dict = {"type": "object", "properties": {"pw": {"type": "string", "format": "password"}}}
    current = schema
    for i in range(40):
        wrapper = {"type": "object", "properties": {"child": current}}
        current = wrapper
    paths = walk_secret_paths(current)
    assert isinstance(paths, frozenset)  # terminated without error


def test_non_dict_root_returns_empty():
    paths = walk_secret_paths("not a dict")
    assert paths == frozenset()


def test_db2_fixture_passwords():
    tk = json.loads((FIXTURES / "db2_toolkit.json").read_text())
    schema = tk["linked_source_definition"]
    paths = walk_secret_paths(schema, root=schema)
    names = {p.path for p in paths}
    assert "instancePassword" in names
    assert "nodes[*].instancePassword" in names
    assert "instanceUser" not in names
    assert "port" not in names


def test_mysql_fixture_ref_password():
    tk = json.loads((FIXTURES / "mysql_toolkit.json").read_text())
    schema = tk["linked_source_definition"]
    paths = walk_secret_paths(schema, root=schema)
    names = {p.path for p in paths}
    assert "credentials.dbPassword" in names
    assert "replicationPassword" in names


# ── expand_and_flag ───────────────────────────────────────────────────────────

def test_expand_present_flat():
    records = frozenset([SecretPath("password", required=True, conditional=False)])
    body_val = {"username": "alice", "password": "s3cr3t"}
    result = expand_and_flag("parameters", body_val, records)
    locs = {f.location for f in result}
    assert "parameters.password" in locs


def test_expand_array_present():
    records = frozenset([SecretPath("nodes[*].nodePassword", required=True, conditional=False)])
    body_val = {
        "nodes": [
            {"nodeId": "n1", "nodePassword": "pw1"},
            {"nodeId": "n2", "nodePassword": "pw2"},
        ]
    }
    result = expand_and_flag("parameters", body_val, records)
    locs = {f.location for f in result}
    assert "parameters.nodes[0].nodePassword" in locs
    assert "parameters.nodes[1].nodePassword" in locs


def test_expand_missing_required_flagged():
    records = frozenset([SecretPath("password", required=True, conditional=False)])
    body_val = {"username": "alice"}  # password absent
    result = expand_and_flag("parameters", body_val, records)
    locs = {f.location for f in result}
    assert "parameters.password" in locs


def test_expand_missing_optional_not_flagged():
    records = frozenset([SecretPath("optPass", required=False, conditional=False)])
    body_val = {"username": "alice"}
    result = expand_and_flag("parameters", body_val, records)
    assert result == []


def test_expand_missing_conditional_not_flagged():
    records = frozenset([SecretPath("authPass", required=True, conditional=True)])
    body_val = {"method": "key"}
    result = expand_and_flag("parameters", body_val, records)
    assert result == []


def test_expand_present_overrides_conditional():
    """A conditional field that IS present must still be flagged."""
    records = frozenset([SecretPath("authPass", required=True, conditional=True)])
    body_val = {"authPass": "typed-in-chat"}
    result = expand_and_flag("parameters", body_val, records)
    assert len(result) == 1
    assert result[0].location == "parameters.authPass"


# ── parse_applied / drop_applied ──────────────────────────────────────────────

def test_parse_applied_no_nonce(monkeypatch):
    from dct_mcp_server.tools.core import host_trust
    monkeypatch.delenv(host_trust._SENSITIVE_NONCE_ENV, raising=False)
    names, locs = parse_applied({"marker": "any", "fields": ["password"]})
    assert names == frozenset()
    assert locs == frozenset()


def test_parse_applied_good_nonce(monkeypatch):
    from dct_mcp_server.tools.core import host_trust
    monkeypatch.setenv(host_trust._SENSITIVE_NONCE_ENV, "testnonce")
    names, locs = parse_applied({"marker": "testnonce", "fields": ["password", "parameters.dbPass"]})
    assert "password" in names
    assert "parameters.dbPass" in locs


def test_drop_applied_exact_location():
    flagged = [FlaggedLocation(name="dbPass", location="parameters.dbPass")]
    _, locs = frozenset(), frozenset(["parameters.dbPass"])
    result = drop_applied(flagged, frozenset(), frozenset(["parameters.dbPass"]))
    assert result == []


def test_drop_applied_bare_name():
    flagged = [FlaggedLocation(name="password", location="parameters.password")]
    result = drop_applied(flagged, frozenset(["password"]), frozenset())
    assert result == []


def test_drop_applied_relative_location():
    """Sub-object-relative location match."""
    flagged = [FlaggedLocation(name="dbPass", location="parameters.dbPass")]
    result = drop_applied(flagged, frozenset(), frozenset(["dbPass"]))
    # bare name "dbPass" matches leaf name
    assert result == []


def test_drop_applied_different_index_no_match():
    flagged = [
        FlaggedLocation(name="nodePassword", location="parameters.nodes[0].nodePassword"),
        FlaggedLocation(name="nodePassword", location="parameters.nodes[1].nodePassword"),
    ]
    result = drop_applied(flagged, frozenset(), frozenset(["parameters.nodes[0].nodePassword"]))
    assert len(result) == 1
    assert result[0].location == "parameters.nodes[1].nodePassword"
```

Run: `pytest tests/unit/test_connector_secrets.py -v`
Expected: FAIL (ImportError — connector_secrets not found)

- [ ] **Step 2: Implement connector_secrets.py**

Create `src/dct_mcp_server/tools/core/connector_secrets.py`:

```python
"""
connector_secrets.py — AppData connector-secret detection (DLPXECO-14781).

Detects connector parameters declared ``"format": "password"`` in a toolkit's
schema.json and routes them through the sensitive-input gate.

Public API:
    SecretPath, FlaggedLocation, ConnectorResult
    walk_secret_paths(schema, root, *, context) -> frozenset[SecretPath]
    expand_and_flag(sub_object, value, records) -> list[FlaggedLocation]
    parse_applied(sensitive_applied) -> tuple[frozenset[str], frozenset[str]]
    drop_applied(flagged, names, locations) -> list[FlaggedLocation]
    find_flagged_connector_secrets(...) -> ConnectorResult  (async, never raises)
    clear_caches() -> None
"""
from __future__ import annotations

import asyncio
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

from dct_mcp_server.config.loader import load_appdata_operations, match_appdata_operation
from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.tools.core.host_trust import _SENSITIVE_NONCE_ENV, host_nonce_ok

logger = get_logger(__name__)

# Walker limits
_MAX_DEPTH = 32
_MAX_NODES = 10_000

# Cache limits and TTLs (seconds)
_MAX_CACHE_ENTRIES = 256
_VERSION_BINDING_TTL_S = 900   # 15 min — id→version binding
_OBJECT_TTL_S = 900            # 15 min — referenced object id→next_id
_NEGATIVE_TTL_S = 60           # 60 s  — failures
_OBJECT_NEGATIVE_TTL_S = 60


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SecretPath:
    """A password-format field path within a toolkit schema."""
    path: str           # dotted path with [*] for arrays, e.g. "nodes[*].password"
    required: bool      # field is in parent "required" list
    conditional: bool   # inside oneOf/anyOf/if/then/else/dependencies


@dataclass(frozen=True)
class FlaggedLocation:
    """A concrete secret location within the request body."""
    name: str           # leaf property name
    location: str       # full dotted path from body root, e.g. "parameters.nodes[0].password"


@dataclass
class ConnectorResult:
    """Result of AppData connector-secret detection for one execute call."""
    flagged: list[FlaggedLocation] = field(default_factory=list)
    covered_sub_objects: frozenset[str] = field(default_factory=frozenset)


# ─────────────────────────────────────────────────────────────────────────────
# Schema walker
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_ref(ref: str, root: dict) -> dict | None:
    """Resolve a JSON pointer $ref against *root*. Returns None on failure."""
    if not ref.startswith("#"):
        return None
    parts = ref[1:].lstrip("/").split("/") if ref != "#" else []
    node = root
    try:
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[part]
        return node if isinstance(node, dict) else None
    except (KeyError, TypeError):
        return None


def walk_secret_paths(
    schema: Any,
    root: dict | None = None,
    *,
    context: str = "",
) -> frozenset[SecretPath]:
    """Recursively walk *schema* and return all password-format field paths.

    Args:
        schema: The JSON-schema object to walk (the definition body).
        root: The $ref resolution root. Defaults to *schema* if None.
        context: Caller label for warning messages (e.g. toolkit id).

    Returns:
        frozenset of SecretPath. Empty on a non-dict root (with a warning).
    """
    if not isinstance(schema, dict):
        if schema is not None:
            logger.warning(
                "AppData secret detection: non-dict schema root; context=%s", context
            )
        return frozenset()

    if root is None:
        root = schema

    results: set[SecretPath] = set()
    visited_refs: set[str] = set()
    node_count = [0]

    def _walk(node: Any, path: str, required: bool, conditional: bool, depth: int) -> None:
        if depth > _MAX_DEPTH:
            logger.warning(
                "AppData secret detection: max depth %d reached; context=%s path=%s",
                _MAX_DEPTH, context, path,
            )
            return
        if node_count[0] >= _MAX_NODES:
            return
        node_count[0] += 1

        if not isinstance(node, dict):
            return

        # $ref resolution
        if "$ref" in node:
            ref = node["$ref"]
            if ref in visited_refs:
                return  # cycle guard
            visited_refs.add(ref)
            resolved = _resolve_ref(ref, root)
            if resolved is None:
                logger.warning(
                    "AppData secret detection: unresolvable $ref %r; context=%s", ref, context
                )
                visited_refs.discard(ref)
                return
            _walk(resolved, path, required, conditional, depth + 1)
            visited_refs.discard(ref)
            return

        # password-format leaf — record and do NOT descend (EC-16)
        if node.get("format") == "password":
            leaf = path.rsplit(".", 1)[-1] if "." in path else path
            # strip array suffix for the name
            leaf = re.sub(r"\[\*\]$", "", leaf).split(".")[-1]
            results.add(SecretPath(path=path, required=required, conditional=conditional))
            return

        # properties
        req_set: set[str] = set(node.get("required", []) if isinstance(node.get("required"), list) else [])
        for prop_name, prop_schema in (node.get("properties") or {}).items():
            child_path = f"{path}.{prop_name}" if path else prop_name
            child_req = prop_name in req_set
            _walk(prop_schema, child_path, child_req, conditional, depth + 1)

        # array items
        items = node.get("items")
        if isinstance(items, dict):
            _walk(items, f"{path}[*]", False, conditional, depth + 1)
        elif isinstance(items, list):
            for i, item in enumerate(items):
                _walk(item, f"{path}[{i}]", False, conditional, depth + 1)

        # additionalProperties / patternProperties
        for kw in ("additionalProperties", "patternProperties"):
            val = node.get(kw)
            if isinstance(val, dict):
                # Walk as a single ".*" sub-schema (schema value for additionalProperties)
                # or walk each pattern value
                if kw == "additionalProperties":
                    _walk(val, f"{path}.*", False, conditional, depth + 1)
                else:
                    for _pat, pschema in val.items():
                        _walk(pschema, f"{path}.*", False, conditional, depth + 1)

        # allOf — same path, conditional unchanged
        for sub in (node.get("allOf") or []):
            _walk(sub, path, False, conditional, depth + 1)

        # oneOf, anyOf, if/then/else, dependencies, dependentSchemas → conditional=True
        for kw in ("oneOf", "anyOf"):
            for sub in (node.get(kw) or []):
                _walk(sub, path, False, True, depth + 1)
        for kw in ("if", "then", "else"):
            sub = node.get(kw)
            if isinstance(sub, dict):
                _walk(sub, path, False, True, depth + 1)
        for kw in ("dependencies", "dependentSchemas"):
            val = node.get(kw)
            if isinstance(val, dict):
                for _dep_name, dep_schema in val.items():
                    if isinstance(dep_schema, dict):
                        _walk(dep_schema, path, False, True, depth + 1)

    _walk(schema, "", False, False, 0)
    # Remove the empty-string root entry if any
    return frozenset(p for p in results if p.path)


# ─────────────────────────────────────────────────────────────────────────────
# Definition-key lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

# Maps logical definition name → (toolkit_response_keys_in_order, schema_extractor)
_DEFINITION_LOOKUP: dict[str, tuple[list[str], Callable[[dict], dict | None]]] = {
    "linked_source_definition": (
        ["linked_source_definition", "linkedSourceDefinition"],
        lambda d: d.get("parameters") if isinstance(d.get("parameters"), dict) else d,
    ),
    "virtual_source_definition": (
        ["virtual_source_definition", "virtualSourceDefinition"],
        lambda d: d.get("parameters") if isinstance(d.get("parameters"), dict) else d,
    ),
    "virtual_to_physical_definition": (
        ["virtual_to_physical_definition", "virtualToPhysicalDefinition"],
        lambda d: d.get("parameters") if isinstance(d.get("parameters"), dict) else d,
    ),
    "snapshot_parameters_definition": (
        ["snapshot_parameters_definition", "snapshotParametersDefinition", "snapshot_schema", "snapshotSchema"],
        lambda d: (
            d.get("schema") if isinstance(d.get("schema"), dict)
            else d.get("parameters") if isinstance(d.get("parameters"), dict)
            else d
        ),
    ),
    "source_config_definition": (
        ["discovery_definition.source_config_schema", "discoveryDefinition.sourceConfigSchema",
         "source_config_definition", "sourceConfigDefinition"],
        lambda d: d,
    ),
}


def _extract_definition_schema(toolkit_resp: dict, definition_name: str) -> dict | None:
    """Return the schema dict for *definition_name* from a toolkit API response."""
    keys_and_extractor = _DEFINITION_LOOKUP.get(definition_name)
    if not keys_and_extractor:
        return None
    keys, extractor = keys_and_extractor
    for key in keys:
        # Support dotted paths like "discovery_definition.source_config_schema"
        parts = key.split(".")
        node: Any = toolkit_resp
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                node = None
                break
        if isinstance(node, dict):
            return extractor(node)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Simple TTL LRU cache (pure stdlib, no third-party)
# ─────────────────────────────────────────────────────────────────────────────


class _TTLCache:
    """OrderedDict-based LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self._cache: OrderedDict[Any, tuple[Any, float]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: Any) -> tuple[bool, Any]:
        """Return (found, value). Expired entries are evicted."""
        entry = self._cache.get(key)
        if entry is None:
            return False, None
        value, exp = entry
        if time.monotonic() > exp:
            del self._cache[key]
            return False, None
        self._cache.move_to_end(key)
        return True, value

    def set(self, key: Any, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.monotonic() + self._ttl)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ToolkitSecretCache
# ─────────────────────────────────────────────────────────────────────────────


class _ToolkitSecretCache:
    """In-memory, single-event-loop cache for toolkit-derived SecretPath sets.

    Keying:
      version bindings: (base_url, toolkit_id) → version string, 15 min TTL
      derived records:  (base_url, toolkit_id, version) → dict[def_name, frozenset[SecretPath]], LRU 256
      global negative:  (base_url, toolkit_id) → True, 60 s TTL (5xx, timeout, parse errors)
      identity negative:(identity, base_url, toolkit_id) → True, 60 s TTL (401/403/404)
    """

    def __init__(self) -> None:
        self._version_bindings: _TTLCache = _TTLCache(512, _VERSION_BINDING_TTL_S)
        self._derived: _TTLCache = _TTLCache(_MAX_CACHE_ENTRIES, _VERSION_BINDING_TTL_S * 10)
        self._global_neg: _TTLCache = _TTLCache(512, _NEGATIVE_TTL_S)
        self._identity_neg: _TTLCache = _TTLCache(512, _NEGATIVE_TTL_S)
        # Single-flight: pending asyncio.Future per (base_url, toolkit_id)
        self._inflight: dict[tuple, asyncio.Future] = {}

    def clear(self) -> None:
        self._version_bindings.clear()
        self._derived.clear()
        self._global_neg.clear()
        self._identity_neg.clear()
        self._inflight.clear()

    async def get(
        self,
        client: Any,
        identity: str,
        toolkit_id: str,
        toolkit_path: str,
        context: str = "",
    ) -> dict[str, frozenset[SecretPath]] | None:
        """Return derived records or None on failure/fallback.

        Never raises.
        """
        from dct_mcp_server.config.config import get_dct_config
        try:
            cfg = get_dct_config(require_key=False)
            base_url = cfg.get("base_url", "")
        except Exception:
            base_url = ""

        g_key = (base_url, toolkit_id)
        i_key = (identity, base_url, toolkit_id)

        # Check negative caches
        found, _ = self._global_neg.get(g_key)
        if found:
            return None
        found, _ = self._identity_neg.get(i_key)
        if found:
            return None

        # Check version binding
        found_ver, version = self._version_bindings.get(g_key)
        if found_ver and version is not None:
            d_key = (base_url, toolkit_id, version)
            found_d, records = self._derived.get(d_key)
            if found_d:
                return records
            # version known but derived evicted — re-derive
            return await self._fetch_and_derive(
                client, identity, toolkit_id, toolkit_path, base_url,
                version, context,
            )

        # Cache miss — single-flight coalescing
        if g_key in self._inflight:
            try:
                return await asyncio.shield(self._inflight[g_key])
            except Exception:
                return None

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._inflight[g_key] = fut
        try:
            result = await self._fetch_and_derive(
                client, identity, toolkit_id, toolkit_path, base_url,
                None, context,
            )
            fut.set_result(result)
            return result
        except Exception as exc:
            fut.set_exception(exc)
            return None
        finally:
            self._inflight.pop(g_key, None)

    async def _fetch_and_derive(
        self,
        client: Any,
        identity: str,
        toolkit_id: str,
        toolkit_path: str,
        base_url: str,
        known_version: str | None,
        context: str,
    ) -> dict[str, frozenset[SecretPath]] | None:
        """Fetch toolkit from DCT, derive records, update caches. None = fallback."""
        endpoint = toolkit_path.replace("{id}", toolkit_id)
        g_key = (base_url, toolkit_id)
        i_key = (identity, base_url, toolkit_id)

        try:
            resp = await client.make_request("GET", endpoint)
        except DCTClientError as exc:
            status = _extract_http_status(exc)
            if status in (401, 403, 404):
                logger.warning(
                    "AppData secret detection fallback: op=GET %s toolkit=%s stage=fetch reason=%s",
                    endpoint, toolkit_id, status,
                )
                self._identity_neg.set(i_key, True)
            else:
                logger.warning(
                    "AppData secret detection fallback: op=GET %s toolkit=%s stage=fetch reason=%s",
                    endpoint, toolkit_id, type(exc).__name__,
                )
                self._global_neg.set(g_key, True)
            return None
        except Exception as exc:
            logger.warning(
                "AppData secret detection fallback: op=GET %s toolkit=%s stage=fetch reason=%s",
                endpoint, toolkit_id, type(exc).__name__,
            )
            self._global_neg.set(g_key, True)
            return None

        if not isinstance(resp, dict):
            logger.warning(
                "AppData secret detection fallback: op=GET %s toolkit=%s stage=parse reason=non-dict-response",
                endpoint, toolkit_id,
            )
            self._global_neg.set(g_key, True)
            return None

        version = resp.get("version") or resp.get("pluginVersion")
        version_str: str | None = str(version) if version is not None else None
        self._version_bindings.set(g_key, version_str)

        d_key = (base_url, toolkit_id, version_str)
        found_d, cached = self._derived.get(d_key)
        if found_d:
            return cached

        # Walk all definitions
        records: dict[str, frozenset[SecretPath]] = {}
        for def_name in _DEFINITION_LOOKUP:
            schema = _extract_definition_schema(resp, def_name)
            if schema is None:
                continue
            try:
                paths = walk_secret_paths(schema, root=schema, context=f"{toolkit_id}/{def_name}")
                records[def_name] = paths
            except Exception as exc:
                logger.warning(
                    "AppData secret detection fallback: toolkit=%s stage=walk reason=%s",
                    toolkit_id, type(exc).__name__,
                )

        self._derived.set(d_key, records)
        return records


def _extract_http_status(exc: DCTClientError) -> int | None:
    """Extract HTTP status from a DCTClientError without logging its message."""
    try:
        return int(exc.args[0]) if exc.args else None
    except (ValueError, TypeError):
        # Try looking for a status attribute
        return getattr(exc, "status_code", getattr(exc, "status", None))


# Module-level cache instances
_toolkit_cache = _ToolkitSecretCache()
_object_cache: _TTLCache = _TTLCache(1024, _OBJECT_TTL_S)
_object_neg_cache: _TTLCache = _TTLCache(1024, _OBJECT_NEGATIVE_TTL_S)


def clear_caches() -> None:
    """Clear all in-memory caches. Used in tests."""
    _toolkit_cache.clear()
    _object_cache.clear()
    _object_neg_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# expand_and_flag
# ─────────────────────────────────────────────────────────────────────────────


def _key_to_segment(key: str) -> str:
    """Render a dict key as a path segment: plain identifier or ["key"]."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", key):
        return key
    return f'["{key}"]'


def _expand_path(
    path_template: str,
    body_value: Any,
) -> list[tuple[str, Any]]:
    """Expand [*] and .* wildcards to concrete indices/keys.

    Returns list of (concrete_path, value_at_that_path).
    """
    segments = re.split(r"(\[\*\]|\.\*)", path_template)
    results: list[tuple[str, Any]] = [("", body_value)]

    i = 0
    accumulated = ""
    for seg in segments:
        if seg == "[*]":
            new_results = []
            for partial_path, val in results:
                if isinstance(val, list):
                    for idx, item in enumerate(val):
                        new_results.append((f"{partial_path}[{idx}]", item))
                else:
                    # Type mismatch: scan for leaf name
                    new_results.append((partial_path, val))
            results = new_results
        elif seg == ".*":
            new_results = []
            for partial_path, val in results:
                if isinstance(val, dict):
                    for k, v in val.items():
                        new_results.append((f"{partial_path}.{_key_to_segment(k)}", v))
                else:
                    new_results.append((partial_path, val))
            results = new_results
        else:
            # Regular path segment(s)
            for part in re.split(r"\.", seg):
                if not part:
                    continue
                new_results = []
                for partial_path, val in results:
                    new_path = f"{partial_path}.{part}" if partial_path else part
                    child = val.get(part) if isinstance(val, dict) else None
                    new_results.append((new_path, child))
                results = new_results

    return results


def expand_and_flag(
    sub_object: str,
    value: Any,
    records: frozenset[SecretPath],
) -> list[FlaggedLocation]:
    """Expand wildcard paths against *value* and produce FlaggedLocation list.

    *sub_object* is the body key (e.g. "parameters") and *value* is its dict value.
    """
    flagged: list[FlaggedLocation] = []

    for sp in records:
        path = sp.path  # e.g. "nodes[*].nodePassword"

        # Determine if the field has wildcards
        has_wildcard = "[*]" in path or ".*" in path

        if has_wildcard:
            expansions = _expand_path(path, value)
            for concrete_path, leaf_val in expansions:
                if leaf_val is not None or (
                    isinstance(value, dict)
                    and _path_exists(value, concrete_path)
                ):
                    leaf_name = re.split(r"[.\[]", path)[-1].rstrip("]")
                    full_loc = f"{sub_object}.{concrete_path}" if concrete_path else sub_object
                    flagged.append(FlaggedLocation(name=leaf_name, location=full_loc))
        else:
            # No wildcard — navigate the path
            parts = path.split(".")
            node: Any = value
            parent_exists = True
            for part in parts[:-1]:
                if isinstance(node, dict):
                    node = node.get(part)
                    if node is None:
                        parent_exists = False
                        break
                else:
                    parent_exists = False
                    break

            leaf_name = parts[-1] if parts else path
            if parent_exists and isinstance(node, dict) and leaf_name in node:
                # Present — always flag
                full_loc = f"{sub_object}.{path}" if path else sub_object
                flagged.append(FlaggedLocation(name=leaf_name, location=full_loc))
            elif (
                sp.required
                and not sp.conditional
                and not has_wildcard
                and parent_exists
                and isinstance(node, dict)
            ):
                # Absent but required and non-conditional — flag
                full_loc = f"{sub_object}.{path}" if path else sub_object
                flagged.append(FlaggedLocation(name=leaf_name, location=full_loc))

    return flagged


def _path_exists(root: dict, dotted_path: str) -> bool:
    """Return True if the dotted/bracketed path exists in *root*."""
    node: Any = root
    for part in re.split(r"\.|(?=\[)", dotted_path):
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            idx_str = part[1:-1]
            if isinstance(node, list):
                try:
                    node = node[int(idx_str)]
                except (IndexError, ValueError):
                    return False
            else:
                return False
        elif isinstance(node, dict):
            if part not in node:
                return False
            node = node[part]
        else:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# parse_applied / drop_applied
# ─────────────────────────────────────────────────────────────────────────────


def parse_applied(
    sensitive_applied: Any,
) -> tuple[frozenset[str], frozenset[str]]:
    """Authenticate and parse sensitive_applied.

    Returns (bare_names, location_strings). Both empty if nonce is wrong/missing.
    """
    if not isinstance(sensitive_applied, dict):
        return frozenset(), frozenset()
    marker = sensitive_applied.get("marker")
    if not host_nonce_ok(marker):
        return frozenset(), frozenset()

    fields = sensitive_applied.get("fields", [])
    if not isinstance(fields, list):
        return frozenset(), frozenset()

    names: set[str] = set()
    locs: set[str] = set()
    for f in fields:
        if not isinstance(f, str):
            continue
        if "." in f or "[" in f:
            locs.add(f)
        else:
            names.add(f)

    return frozenset(names), frozenset(locs)


def drop_applied(
    flagged: list[FlaggedLocation],
    names: frozenset[str],
    locations: frozenset[str],
) -> list[FlaggedLocation]:
    """Remove from *flagged* any entry satisfied by an applied name or location.

    Matching rules (any one satisfies):
    1. Exact location match
    2. Applied location equals flagged location minus its <sub_object>. prefix
       (only when exactly one flagged entry has that relative form)
    3. Applied bare name equals the leaf name

    Array index differences are NOT considered equal (EC-14).
    """
    if not names and not locations:
        return flagged

    # Build relative location → count map for rule 2
    rel_counts: dict[str, int] = {}
    rel_to_flagged: dict[str, list[FlaggedLocation]] = {}
    for fl in flagged:
        # Relative = strip first path component
        parts = fl.location.split(".", 1)
        rel = parts[1] if len(parts) == 2 else ""
        rel_counts[rel] = rel_counts.get(rel, 0) + 1
        rel_to_flagged.setdefault(rel, []).append(fl)

    result = []
    for fl in flagged:
        parts = fl.location.split(".", 1)
        rel = parts[1] if len(parts) == 2 else ""

        # Rule 1: exact location
        if fl.location in locations:
            continue
        # Rule 2: relative location (unambiguous only)
        if rel in locations and rel_counts.get(rel, 0) == 1:
            continue
        # Rule 3: bare name
        if fl.name in names:
            continue
        result.append(fl)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Resolver chains (simple parsing and execution)
# ─────────────────────────────────────────────────────────────────────────────


def _resolution_budget_s() -> float:
    """Return the configured DCT_TIMEOUT as the overall resolution budget."""
    try:
        from dct_mcp_server.config.config import get_dct_config
        cfg = get_dct_config(require_key=False)
        return float(cfg.get("timeout", 30))
    except Exception:
        return 30.0


async def _execute_chain(
    client: Any,
    identity: str,
    chain_str: str,
    path_params: dict,
    body: dict,
    method_path: str,
) -> str | None:
    """Execute a single chain string and return a toolkit_id or None."""

    async def _get_object(get_path: str, current_id: str) -> dict | None:
        endpoint = get_path.replace("{id}", current_id)
        # Replace {body.<field>} references
        endpoint = re.sub(
            r"\{body\.([^}]+)\}",
            lambda m: str(body.get(m.group(1), "")),
            endpoint,
        )
        cache_key = (identity, get_path, current_id)
        found, cached = _object_cache.get(cache_key)
        if found:
            return cached
        found_neg, _ = _object_neg_cache.get(cache_key)
        if found_neg:
            return None
        try:
            resp = await client.make_request("GET", endpoint)
            if isinstance(resp, dict):
                _object_cache.set(cache_key, resp)
                return resp
        except DCTClientError as exc:
            status = _extract_http_status(exc)
            if status != 404:
                logger.warning(
                    "AppData secret detection fallback: op=GET %s stage=resolve reason=%s",
                    endpoint, status or type(exc).__name__,
                )
            _object_neg_cache.set(cache_key, True)
        except Exception as exc:
            logger.warning(
                "AppData secret detection fallback: op=GET %s stage=resolve reason=%s",
                endpoint, type(exc).__name__,
            )
            _object_neg_cache.set(cache_key, True)
        return None

    # Parse chain_str: "source > hop1 > hop2"
    # source: "body:field" or "path:param"
    steps = [s.strip() for s in chain_str.split(">")]
    if not steps:
        return None

    source_str = steps[0]
    if source_str.startswith("body:"):
        field = source_str[5:]
        current_id = body.get(field)
        if not isinstance(current_id, str) or not current_id:
            return None
        # If no hops, current_id IS the toolkit_id (e.g. body:toolkit_id)
        if len(steps) == 1:
            return current_id
    elif source_str.startswith("path:"):
        param = source_str[5:]
        current_id = path_params.get(param)
        if not isinstance(current_id, str) or not current_id:
            return None
    else:
        return None

    # Walk hops
    for hop_str in steps[1:]:
        # Split alternatives on ^
        alternatives = [a.strip() for a in hop_str.split("^")]
        # Last part after final "." is the select
        # But a hop can look like: /path/{id}.field or /path/{id}.field[0]
        #                          or just /path/{id} (no select — toolkit_id is response field)

        result_id: str | None = None
        for alt in alternatives:
            # Extract select
            # Pattern: get_path "." select (select may contain brackets)
            # A select is present if there's a "." AFTER the last "/" in the path
            match = re.match(r"^([^.]+(?:\.[^.]+)*?)(?:\.([a-zA-Z_][a-zA-Z0-9_\[\]=$.]*))$", alt)
            if match:
                get_path_part = match.group(1).strip()
                select = match.group(2).strip()
            else:
                get_path_part = alt.strip()
                select = None

            obj = await _get_object(get_path_part, current_id)
            if obj is None:
                continue  # try next alternative

            if select is None:
                # No select: toolkit_id is from response
                tk = obj.get("toolkit_id") or obj.get("toolkitId")
                if isinstance(tk, str):
                    result_id = tk
                    break
                continue

            # Parse select
            # Could be: "field", "field[N]", "field[id=$]"
            arr_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+|id=\$)\])?$", select)
            if not arr_match:
                continue
            field_name = arr_match.group(1)
            arr_idx = arr_match.group(2)

            field_val = obj.get(field_name)
            if arr_idx is None:
                # Plain field select — value is the next id
                if isinstance(field_val, str):
                    result_id = field_val
                    break
                # Could also be a list; take first
                if isinstance(field_val, list) and field_val:
                    result_id = field_val[0] if isinstance(field_val[0], str) else None
                    break
            elif arr_idx.isdigit():
                idx = int(arr_idx)
                if isinstance(field_val, list) and idx < len(field_val):
                    item = field_val[idx]
                    if isinstance(item, str):
                        result_id = item
                        break
            elif arr_idx == "id=$":
                # Find item in list whose "id" matches current_id
                if isinstance(field_val, list):
                    for item in field_val:
                        if isinstance(item, dict) and item.get("id") == current_id:
                            tk = item.get("toolkit_id") or item.get("toolkitId")
                            if isinstance(tk, str):
                                result_id = tk
                                break
                    if result_id:
                        break

        if result_id is None:
            return None
        current_id = result_id

    return current_id


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


async def find_flagged_connector_secrets(
    client_resolver: Callable[[], tuple[Any, str]],
    method: str,
    resolved_path: str,
    path_params: dict,
    body: dict | None,
    sensitive_applied: Any,
) -> ConnectorResult:
    """Detect AppData connector secret fields in *body* that need secure capture.

    Never raises. Returns ConnectorResult(flagged=[], covered_sub_objects=frozenset())
    on any failure (fail-open).

    Args:
        client_resolver: Callable returning (DCTAPIClient, identity_str).
        method: HTTP method string (e.g. "POST").
        resolved_path: Concrete path with {params} already substituted.
        path_params: Dict of path parameter values (e.g. {"dsourceId": "ds-1"}).
        body: The parsed request body dict, or None.
        sensitive_applied: The sensitive_applied payload from the caller.
    """
    try:
        return await _find_flagged_inner(
            client_resolver, method, resolved_path, path_params, body, sensitive_applied
        )
    except Exception as exc:
        logger.warning(
            "AppData secret detection fallback: stage=budget reason=%s", type(exc).__name__
        )
        return ConnectorResult()


async def _find_flagged_inner(
    client_resolver: Callable[[], tuple[Any, str]],
    method: str,
    resolved_path: str,
    path_params: dict,
    body: dict | None,
    sensitive_applied: Any,
) -> ConnectorResult:
    # Step 1: Match operation
    op = match_appdata_operation(method, resolved_path)
    if op is None:
        return ConnectorResult()

    # Step 2: Keep only present sub-objects
    if body is None:
        return ConnectorResult()
    present_sub_objects = {
        k: v for k, v in op.sub_objects.items()
        if isinstance(body.get(k), dict)
    }
    if not present_sub_objects:
        return ConnectorResult()

    # Step 3: Resolve client and identity (lazy — only now that we have work)
    try:
        client, identity = client_resolver()
    except Exception as exc:
        logger.warning(
            "AppData secret detection fallback: op=%s %s stage=resolve reason=%s",
            method, resolved_path, type(exc).__name__,
        )
        return ConnectorResult()

    _, toolkit_path = load_appdata_operations()
    if not toolkit_path:
        logger.warning(
            "AppData secret detection fallback: op=%s %s stage=resolve reason=no-toolkit-path",
            method, resolved_path,
        )
        return ConnectorResult()

    method_path = f"{method} {resolved_path}"

    async def _run_with_budget() -> ConnectorResult:
        # Step 4: Resolve toolkit ids from all chains concurrently
        chain_tasks = [
            _execute_chain(client, identity, chain, path_params, body or {}, method_path)
            for chain in op.chains
        ]
        chain_results = await asyncio.gather(*chain_tasks, return_exceptions=True)
        toolkit_ids: set[str] = set()
        for r in chain_results:
            if isinstance(r, str) and r:
                toolkit_ids.add(r)
            elif isinstance(r, Exception):
                logger.warning(
                    "AppData secret detection fallback: op=%s stage=resolve reason=%s",
                    method_path, type(r).__name__,
                )

        if not toolkit_ids:
            return ConnectorResult()

        # Step 5: Fetch toolkit schema for each toolkit id concurrently
        fetch_tasks = [
            _toolkit_cache.get(client, identity, tid, toolkit_path, method_path)
            for tid in toolkit_ids
        ]
        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        # Step 6 + 7: For each covered sub-object, union records across toolkits
        sub_obj_records: dict[str, frozenset[SecretPath]] = {}
        covered: set[str] = set()

        for tid, result in zip(toolkit_ids, fetch_results):
            if isinstance(result, dict):
                for sub_obj_name, def_name in present_sub_objects.items():
                    if def_name in result:
                        covered.add(sub_obj_name)
                        existing = sub_obj_records.get(sub_obj_name, frozenset())
                        sub_obj_records[sub_obj_name] = existing | result[def_name]
            elif isinstance(result, Exception):
                logger.warning(
                    "AppData secret detection fallback: op=%s toolkit=unknown stage=fetch reason=%s",
                    method_path, type(result).__name__,
                )

        # Parse applied fields
        applied_names, applied_locs = parse_applied(sensitive_applied)

        # For each covered sub-object: expand, flag, drop applied
        all_flagged: list[FlaggedLocation] = []
        for sub_obj_name in covered:
            records = sub_obj_records.get(sub_obj_name, frozenset())
            sub_val = body.get(sub_obj_name, {})
            flagged = expand_and_flag(sub_obj_name, sub_val, records)
            flagged = drop_applied(flagged, applied_names, applied_locs)
            all_flagged.extend(flagged)

        return ConnectorResult(
            flagged=all_flagged,
            covered_sub_objects=frozenset(covered),
        )

    budget = _resolution_budget_s()
    try:
        return await asyncio.wait_for(_run_with_budget(), timeout=budget)
    except asyncio.TimeoutError:
        logger.warning(
            "AppData secret detection fallback: op=%s stage=budget reason=timeout",
            method_path,
        )
        return ConnectorResult()
```

- [ ] **Step 3: Run unit tests**

```bash
pytest tests/unit/test_connector_secrets.py -v
```

Expected: all PASS (or minimal failures for edge cases — fix inline)

- [ ] **Step 4: Run full test suite to verify no regressions**

```bash
pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```

Expected: all previously passing tests still PASS

- [ ] **Step 5: Commit**

```bash
git add src/dct_mcp_server/tools/core/connector_secrets.py tests/unit/test_connector_secrets.py
git commit -m "feat: implement connector_secrets.py for AppData secret detection (DLPXECO-14781)"
```

---

### Task 7: dynamic.py — Extend Step 3.5 Gate and Discovery [sequential] [model:sonnet]

**Spec References:** FR-001, FR-003, FR-004, FR-005, FR-006, FR-007, FR-009, FR-010

**Files:**
- Modify: `src/dct_mcp_server/tools/core/dynamic.py`

**Interfaces:**
- Consumes: `connector_secrets.find_flagged_connector_secrets`, `connector_secrets.parse_applied`, `loader.match_appdata_operation`, `host_trust._SENSITIVE_NONCE_ENV` (already imported via Task 2)
- Produces: extended gate response with `sensitive_field_locations`, extended discovery note for AppData ops

The gate currently (Step 3.5, around line 461-487):
```python
if method_upper in ("POST", "PUT", "PATCH") and _secure_capture_host():
    missing_secrets = _missing_sensitive_fields(
        body,
        _annotated_credential_fields(spec) - _host_applied_fields(sensitive_applied),
    )
    if missing_secrets:
        return {"status": "sensitive_input_required", ...}
```

After this task it will:
1. Call `find_flagged_connector_secrets` (async) to detect connector secrets
2. Run native detection on a body_view with covered_sub_objects excluded
3. Merge names + add `sensitive_field_locations` if non-empty

- [ ] **Step 1: Add import to dynamic.py**

At the top of `dynamic.py`, after the existing imports, add:

```python
from dct_mcp_server.tools.core import connector_secrets as _connector_secrets
from dct_mcp_server.config.loader import match_appdata_operation as _match_appdata_operation
```

- [ ] **Step 2: Add _resolve_client helper**

Anywhere before the `execute` function body, add this helper. It encapsulates the Step 7 client selection so the gate can use the same client without duplicating logic:

```python
def _resolve_client(dct_client: Any) -> tuple[Any, str]:
    """Return (client, identity) for the current request.

    In embedded mode with a ClientRegistry: uses the per-caller client.
    In standalone mode: returns (dct_client, "standalone").
    """
    if isinstance(dct_client, ClientRegistry):
        auth = resolve_auth()
        client = dct_client.get_client(auth)
        identity = dct_client.identity_key(auth)
        return client, identity
    return dct_client, "standalone"
```

- [ ] **Step 3: Replace Step 3.5 in the execute closure**

Find the existing Step 3.5 block (the `if method_upper in ("POST", "PUT", "PATCH") and _secure_capture_host():` block) and replace it with:

```python
        # ---------------------------------------------------------------- #
        # Step 3.5 — Sensitive-input gate (DLPXECO-14641/14642/14603/14781)
        # ---------------------------------------------------------------- #
        # On a capture-capable host, detect both spec-annotated native
        # secrets AND AppData connector secrets (DLPXECO-14781). Runs
        # before the confirmation gate: capture the secret first.
        if method_upper in ("POST", "PUT", "PATCH") and _secure_capture_host():
            # -- Connector detection (DLPXECO-14781) ----------------------
            connector_result = await _connector_secrets.find_flagged_connector_secrets(
                client_resolver=lambda: _resolve_client(dct_client),
                method=method_upper,
                resolved_path=resolved_path,
                path_params=_extract_path_params(resolved_path, spec),
                body=body if isinstance(body, dict) else None,
                sensitive_applied=sensitive_applied,
            )

            # -- Native detection -----------------------------------------
            # Parse applied fields so we can use applied_location_leaf_names
            applied_names, applied_locs = _connector_secrets.parse_applied(sensitive_applied)
            # Leaf names of location-based applied entries satisfy native name check too
            applied_loc_leaf_names = frozenset(
                loc.rsplit(".", 1)[-1].rstrip("]").rsplit("[", 1)[0]
                for loc in applied_locs
            )
            # Exclude covered sub-objects from native body view so the native
            # walker doesn't double-report connector fields (FR-009 step 3).
            if connector_result.covered_sub_objects:
                body_view = {
                    k: v for k, v in (body or {}).items()
                    if k not in connector_result.covered_sub_objects
                }
            else:
                body_view = body

            missing_secrets = _missing_sensitive_fields(
                body_view,
                _annotated_credential_fields(spec)
                - (_host_applied_fields(sensitive_applied) | applied_loc_leaf_names),
            )

            # -- Merge names ----------------------------------------------
            connector_names = [f.name for f in connector_result.flagged]
            all_names = list(missing_secrets)
            for name in connector_names:
                if name not in all_names:
                    all_names.append(name)

            if all_names:
                response = {
                    "status": "sensitive_input_required",
                    "required_sensitive_fields": all_names,
                    "message": (
                        "This operation needs sensitive input: "
                        + ", ".join(all_names)
                    ),
                    "operation": {"path": resolved_path, "method": method_upper},
                    "instructions": (
                        "STOP. Do NOT ask for these secret value(s) in chat and do "
                        "NOT put them in body. The host securely captures them from "
                        "the user (masked input or a stored-credential alias) and "
                        "re-calls execute with them applied automatically. Simply "
                        "wait for the next turn."
                    ),
                }
                if connector_result.flagged:
                    response["sensitive_field_locations"] = [
                        {"name": f.name, "location": f.location}
                        for f in connector_result.flagged
                    ]
                return response
```

Note: `_extract_path_params` does not yet exist — see next step.

- [ ] **Step 4: Add _extract_path_params helper**

This extracts path parameter values by matching the resolved path against the spec's path templates. Add before the execute closure:

```python
def _extract_path_params(resolved_path: str, spec: Any) -> dict:
    """Extract path parameter values from a resolved path by matching templates."""
    import re
    if not isinstance(spec, dict):
        return {}
    paths = spec.get("paths") or {}
    for template, _ in paths.items():
        # Build regex from template
        pattern = re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", re.escape(template))
        m = re.fullmatch(pattern, resolved_path.lstrip("/"))
        if m is None:
            # Try with leading slash stripped from resolved_path differently
            m = re.fullmatch(pattern, resolved_path)
        if m:
            return m.groupdict()
    # Fallback: parse from matched appdata operation template
    op = _match_appdata_operation("ANY", resolved_path)
    if op:
        pattern = re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", re.escape(op.path_template))
        m = re.fullmatch(pattern, resolved_path.lstrip("/"))
        if m:
            return m.groupdict()
    return {}
```

- [ ] **Step 5: Extend discovery for AppData operations (FR-010)**

In the `discovery` function, find the `_action_get_operation_schema` call and the code that builds the response dict. After calling `_action_get_operation_schema`, add:

```python
            # FR-010: On a capture-capable host, annotate AppData operations
            # with a note that connector password fields are host-captured.
            if _secure_capture_host() and isinstance(result, dict):
                op = _match_appdata_operation(
                    result.get("method", "").upper(),
                    result.get("path", ""),
                )
                if op is not None:
                    sub_obj_list = [
                        {"sub_object": k, "toolkit_definition": v}
                        for k, v in op.sub_objects.items()
                    ]
                    existing_desc = result.get("description", "")
                    connector_note = (
                        "\n\n**Connector credential note:** Parameters declared "
                        "`\"format\": \"password\"` in the toolkit schema for sub-objects "
                        + ", ".join(f"`{k}`" for k in op.sub_objects)
                        + " are captured by the host securely. Do NOT request them in "
                        "chat or include them in the body — the host captures them "
                        "out-of-band and applies them automatically."
                    )
                    result["description"] = existing_desc + connector_note
                    result["host_captured_connector_secrets"] = sub_obj_list
```

This must be added in the sync `discovery` function's `get_operation_schema` branch. Discovery is sync, so no await.

- [ ] **Step 6: Run the full unit test suite**

```bash
pytest tests/unit/ tests/integration/ -v --tb=short 2>&1 | tail -40
```

Expected: all previously passing tests PASS; new connector tests pass too.

- [ ] **Step 7: Commit**

```bash
git add src/dct_mcp_server/tools/core/dynamic.py
git commit -m "feat: extend Step 3.5 gate and discovery for AppData connector secrets (DLPXECO-14781)"
```

---

### Task 8: Integration Tests [sequential] [model:sonnet]

**Spec References:** AC-1, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9, AC-10, AC-12

**Files:**
- Create: `tests/integration/test_appdata_secret_gate.py`

**Interfaces:**
- Consumes: `make_execute` from `_gate_helpers.py`, `connector_secrets.clear_caches`, toolkit fixtures, `_SENSITIVE_NONCE_ENV` from host_trust
- Tests the full execute path end-to-end with stubbed `make_request`

- [ ] **Step 1: Create integration test file**

```python
"""Integration tests for AppData connector-secret gate (DLPXECO-14781).

Exercises the full execute wiring in dynamic.py with a stubbed DCT client.
The toolkit details endpoint is stubbed via the client mock. Only make_request
is stubbed — everything between execute() and the wire is production code.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import dct_mcp_server.tools.core.dynamic as dynamic
import dct_mcp_server.tools.core.connector_secrets as connector_secrets_mod
from dct_mcp_server.tools.core.host_trust import _SENSITIVE_NONCE_ENV
from tests.integration._gate_helpers import make_execute

FIXTURES = Path(__file__).parent.parent / "fixtures" / "toolkits"
NONCE = "integration-nonce-14781"
DB2_TK = json.loads((FIXTURES / "db2_toolkit.json").read_text())
MYSQL_TK = json.loads((FIXTURES / "mysql_toolkit.json").read_text())

# Minimal spec for AppData dsource link
APPDATA_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "appdata-gate-test", "version": "1.0.0"},
    "paths": {
        "/dsources/appdata": {
            "post": {
                "operationId": "linkAppDataDSource",
                "summary": "Link AppData dSource",
                "tags": ["DSources"],
            },
        },
        "/vdbs/provision_by_snapshot": {
            "post": {
                "operationId": "provisionVdbBySnapshot",
                "summary": "Provision VDB by snapshot",
                "tags": ["VDBs"],
            },
        },
        "/environments": {
            "post": {
                "operationId": "createEnvironment",
                "tags": ["Environments"],
            },
        },
    },
}


@pytest.fixture(autouse=True)
def reset_caches():
    connector_secrets_mod.clear_caches()
    yield
    connector_secrets_mod.clear_caches()


@pytest.fixture
def spec_loaded(monkeypatch):
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: APPDATA_SPEC)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")


def _as_host(monkeypatch, *, nonce=True, auth_mode="embedded"):
    if nonce:
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, NONCE)
    else:
        monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
    monkeypatch.setattr(dynamic, "get_dct_config", lambda **_: {"auth_mode": auth_mode})


def _make_client_with_toolkit(toolkit_json: dict):
    """Return (execute_fn, client_mock) where GET /toolkits/{id} returns toolkit_json."""
    execute, client = make_execute(return_value={"id": "ds-1", "toolkit_id": "db2-toolkit-001"})

    async def _smart_request(method, endpoint, **kwargs):
        if method.upper() == "GET" and "/toolkits/" in endpoint:
            return toolkit_json
        if method.upper() == "GET" and "/dsources/" in endpoint:
            return {"id": "ds-1", "toolkit_id": toolkit_json["id"]}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_smart_request)
    return execute, client


# ── AC-1: connector secrets trigger sensitive_input_required ─────────────────

@pytest.mark.asyncio
async def test_db2_dsource_link_triggers_gate(spec_loaded, monkeypatch):
    """DB2 dSource link with inline instancePassword triggers sensitive_input_required."""
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "leaked-in-chat",
                "port": 50000,
                "mountPath": "/mnt/db2",
            },
        },
    )

    assert result["status"] == "sensitive_input_required"
    assert "instancePassword" in result["required_sensitive_fields"]


@pytest.mark.asyncio
async def test_mysql_dsource_link_triggers_gate_for_ref_password(spec_loaded, monkeypatch):
    """MySQL dSource link: $ref-reached password triggers the gate."""
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(MYSQL_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "mysql-toolkit-001",
            "parameters": {
                "host": "mysql.example.com",
                "port": 3306,
                "credentials": {
                    "dbUser": "repl",
                    "dbPassword": "typed-in-chat",
                },
            },
        },
    )

    assert result["status"] == "sensitive_input_required"
    assert "dbPassword" in result["required_sensitive_fields"]


# ── AC-9: sensitive_field_locations is present ────────────────────────────────

@pytest.mark.asyncio
async def test_sensitive_field_locations_present(spec_loaded, monkeypatch):
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "leaked",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    assert "sensitive_field_locations" in result
    locs = {e["location"] for e in result["sensitive_field_locations"]}
    assert any("instancePassword" in loc for loc in locs)


# ── AC-3 / AC-10: re-call with sensitive_applied does not re-prompt ───────────

@pytest.mark.asyncio
async def test_recall_with_applied_location_dispatches(spec_loaded, monkeypatch):
    """Re-call with connector secret in sensitive_applied (by location) dispatches."""
    _as_host(monkeypatch)
    execute, client = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "injected-by-host",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
        sensitive_applied={
            "marker": NONCE,
            "fields": ["parameters.instancePassword"],
        },
    )

    # Should NOT be sensitive_input_required — should proceed to confirmation or dispatch
    assert result.get("status") != "sensitive_input_required"


@pytest.mark.asyncio
async def test_recall_with_applied_bare_name_dispatches(spec_loaded, monkeypatch):
    """Re-call with connector secret applied by bare name dispatches."""
    _as_host(monkeypatch)
    execute, client = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "injected-by-host",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
        sensitive_applied={
            "marker": NONCE,
            "fields": ["instancePassword"],
        },
    )

    assert result.get("status") != "sensitive_input_required"


# ── AC-4: non-secret fields are never flagged ─────────────────────────────────

@pytest.mark.asyncio
async def test_non_secret_fields_not_flagged(spec_loaded, monkeypatch):
    """instanceUser, port, mountPath are never in required_sensitive_fields."""
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "port": 50000,
                "mountPath": "/mnt",
                # No instancePassword — gate should fire for it, but NOT for the others
            },
        },
    )

    if result.get("status") == "sensitive_input_required":
        for field in ("instanceUser", "port", "mountPath", "backupPath"):
            assert field not in result["required_sensitive_fields"]


# ── AC-5: native ops unchanged ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_native_op_unchanged(spec_loaded, monkeypatch):
    """POST /environments (native op) is unaffected by connector detection."""
    _as_host(monkeypatch)
    execute, client = make_execute(return_value={"ok": True})
    # No toolkit lookup should occur for a native op
    toolkit_calls = []
    original = client.make_request

    async def tracking_request(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            toolkit_calls.append(endpoint)
        return await original(method, endpoint, **kwargs)
    client.make_request = tracking_request

    result = await execute(
        path="/environments",
        method="POST",
        body={"name": "test-env", "hostname": "h.example.com"},
    )

    assert not toolkit_calls, "Toolkit lookup must not fire for native ops"


# ── AC-6: non-capture-capable clients unaffected ─────────────────────────────

@pytest.mark.asyncio
async def test_non_capture_client_no_gate(spec_loaded, monkeypatch):
    """Without embedded auth mode, no gate is raised."""
    _as_host(monkeypatch, auth_mode="standalone")  # not capture-capable
    execute, client = _make_client_with_toolkit(DB2_TK)
    toolkit_calls = []
    orig = client.make_request

    async def track(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            toolkit_calls.append(endpoint)
        return await orig(method, endpoint, **kwargs)
    client.make_request = track

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "u",
                "instancePassword": "p",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    assert result.get("status") != "sensitive_input_required"
    assert not toolkit_calls


# ── AC-7: toolkit lookup failure falls back ───────────────────────────────────

@pytest.mark.asyncio
async def test_toolkit_fetch_failure_fallback(spec_loaded, monkeypatch):
    """Toolkit fetch failure causes fail-open, no block."""
    from dct_mcp_server.core.exceptions import DCTClientError
    _as_host(monkeypatch)
    execute, client = make_execute(return_value={"ok": True})
    client.make_request = AsyncMock(side_effect=DCTClientError("500"))

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "u",
                "instancePassword": "p",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    # Should not be sensitive_input_required (fallback); should not crash
    # It may return an error from the stub, but not a gate stop
    assert result.get("status") != "sensitive_input_required"


# ── AC-12: discovery annotates AppData operations ────────────────────────────

def test_discovery_appdata_note(spec_loaded, monkeypatch):
    """discovery get_operation_schema for an AppData op adds connector note."""
    _as_host(monkeypatch)
    from dct_mcp_server.tools.core.dynamic import _make_discovery_fn
    app = MagicMock()
    client = MagicMock()
    discovery = _make_discovery_fn(app, client)

    result = discovery(
        action="get_operation_schema",
        tag=None,
        operation_id="linkAppDataDSource",
        path="/dsources/appdata",
        method="POST",
    )

    if isinstance(result, dict) and "description" in result:
        assert "connector credential" in result.get("description", "").lower() or \
               "host_captured_connector_secrets" in result
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/integration/test_appdata_secret_gate.py -v --tb=short
```

Expected: most tests PASS. Fix any failures inline (stub shapes, helper adjustments).

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -50
```

Expected: no previously passing tests regress.

- [ ] **Step 4: Check coverage of new code**

```bash
pytest tests/ --cov=src/dct_mcp_server/tools/core/connector_secrets --cov-report=term-missing 2>&1 | tail -20
```

Expected: ≥ 80% line coverage of `connector_secrets.py`

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_appdata_secret_gate.py
git commit -m "test: AppData secret gate integration tests (DLPXECO-14781)"
```

---

### Task 9: Docs Update [sequential] [model:haiku]

**Spec References:** FR-003, FR-006, FR-010

**Files:**
- Modify: `CLAUDE.md` (at repo root — `src/CLAUDE.md` or worktree root)
- Modify: `.claude/architecture.md` (if it exists in the worktree)

- [ ] **Step 1: Update CLAUDE.md Key Source Layout**

Open the CLAUDE.md file (it's in `/aidlc-app/dxi-aidlc/repos/users/shreyas.kulkarni/dxi-mcp-server/.worktrees/dlpxeco-14781/CLAUDE.md`) and find the `### Key Source Layout` section (or equivalent). Add entries for the new files:

```markdown
│   ├── tools/core/
│   │   ├── host_trust.py          # Shared nonce check (_SENSITIVE_NONCE_ENV, host_nonce_ok)
│   │   ├── connector_secrets.py   # AppData connector-secret detection: toolkit walker, caches, gate entry
│   │   │                          # (DLPXECO-14781) Detects "format":"password" fields from toolkit schema.json
```

And update the Confirmation System section to add:

```markdown
**AppData connector secrets (DLPXECO-14781):** On a capture-capable host, the gate also resolves the toolkit behind each AppData operation (DB2, MySQL, HANA, MongoDB, Couchbase) and detects connector parameters declared `"format": "password"` in the toolkit's schema. Those fields are routed through secure capture like spec-annotated credentials. The gate response gains an additive `sensitive_field_locations` key (list of `{name, location}`) when connector secrets are flagged. Detection is host-scoped (embedded mode only), fail-open, and time-budgeted. Caches are in-memory only (not persisted). The `config/mappings/appdata_operations.txt` file maps 19 AppData operations to their sub-objects and toolkit resolver chains.

**Known gaps:** `POST /vdb-groups/provision_from_bookmark` (nested provision parameters) is not mapped. Resolution falls back to annotation-only for operations where the toolkit id cannot be determined.
```

- [ ] **Step 2: Update .claude/architecture.md if it exists**

```bash
ls .claude/architecture.md 2>/dev/null && echo "exists" || echo "missing"
```

If it exists, add to the Layer Map:
- `tools/core/host_trust.py` — Shared nonce trust check; imported by dynamic.py and connector_secrets.py
- `tools/core/connector_secrets.py` — AppData connector-secret detection; fail-open, host-scoped, time-budgeted
- `config/mappings/appdata_operations.txt` — Static AppData operation → sub-object → toolkit definition mapping

And add to Key Platform Behaviors:
- AppData secret detection is capture-host-only, fail-open, time-budgeted (= DCT_TIMEOUT), with in-memory caches only (not persisted across restart).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git add .claude/architecture.md 2>/dev/null || true
git commit -m "docs: document AppData connector-secret detection components (DLPXECO-14781)"
```

---

## Self-Review Checklist

- [ ] AC-1: DB2 + MySQL connector password fields trigger `sensitive_input_required` — covered by Task 8 tests
- [ ] AC-3/10: Re-calls with `sensitive_applied` (by name and by location) dispatch without re-prompt — covered by Task 8
- [ ] AC-4: Non-secret fields (usernames, ports) never flagged — covered by Tasks 6 + 8
- [ ] AC-5: Native ops unchanged (existing test suites pass) — covered by Task 8 + full suite runs
- [ ] AC-6: Non-capture-capable clients unaffected — covered by Task 8
- [ ] AC-7: Toolkit fetch failure causes fail-open — covered by Tasks 6 + 8
- [ ] AC-8: ≥ 80% line coverage of new code — checked in Task 8 Step 4
- [ ] AC-9: `sensitive_field_locations` in response — covered by Task 8
- [ ] AC-11: Per-(id,version) caching, single-flight coalescing — covered by Task 6 unit tests
- [ ] AC-12: Discovery annotates AppData ops — covered by Task 8
- [ ] Secret values never logged — enforced in connector_secrets.py (never log body/response/str(exc) of DCTClientError)
- [ ] No new third-party dependencies — verified: all stdlib + existing project modules
