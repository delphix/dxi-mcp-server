"""
Connector fixture layer — loads connector topology + credentials from:

  1. tests/fixtures/connectors/.secrets.yaml  (local dev, gitignored)
  2. DCT_CONNECTOR_<TYPE>_<FIELD> env vars     (CI — GitHub Secrets)

The connector schema (field docs + defaults) lives in:
  tests/fixtures/connectors/schema.yaml       (committed, no secrets)

Usage:
    CONNECTOR_TYPE=mysql pytest tests/llm_local/ -m llm_driven
    CONNECTOR_TYPE=db2   pytest tests/llm_local/ -m llm_driven

    # Or point at a custom secrets file:
    CONNECTOR_SECRETS=/path/to/my-env.yaml CONNECTOR_TYPE=mysql pytest ...
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "connectors"
_SCHEMA_FILE = _FIXTURES_DIR / "schema.yaml"
_DEFAULT_SECRETS = _FIXTURES_DIR / ".secrets.yaml"


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ConnectorSpec:
    """All fields needed to drive the full dSource + VDB flow for one connector."""

    connector_type: str
    display_name: str
    source_host: str
    target_host: str
    env_user: str
    env_password: str
    link_user: str
    link_password: str
    dsource_link_action: str
    provision_action: str
    link_fields: dict = field(default_factory=dict)
    provision_fields: dict = field(default_factory=dict)
    connector_search_keyword: str = "plugin"

    @property
    def source_short(self) -> str:
        return self.source_host.split(".")[0]

    @property
    def target_short(self) -> str:
        return self.target_host.split(".")[0]

    def link_prompt_detail(self) -> str:
        if not self.link_fields:
            return ""
        lines = ["Use these connector-specific fields for the dSource link:"]
        for k, v in self.link_fields.items():
            lines.append(f"  {k}: {v!r}")
        return "\n".join(lines)

    def provision_prompt_detail(self) -> str:
        if not self.provision_fields:
            return ""
        lines = ["Use these connector-specific fields for VDB provisioning:"]
        for k, v in self.provision_fields.items():
            lines.append(f"  {k}: {v!r}")
        return "\n".join(lines)

    def schema_hint(self, schema_fields: list[dict]) -> str:
        """Format schema field docs as a hint for Claude."""
        if not schema_fields:
            return ""
        lines = ["Required fields (use DCT get-defaults or these hints if unsure):"]
        for f in schema_fields:
            default = f.get("default") or f.get("example", "")
            src = f.get("source", "")
            hint = f"  {f['name']}: {f['description']}"
            if default:
                hint += f" (default: {default!r})"
            if src:
                hint += f" (from: {src})"
            lines.append(hint)
        return "\n".join(lines)


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_schema() -> dict:
    if not _SCHEMA_FILE.exists():
        return {}
    return yaml.safe_load(_SCHEMA_FILE.read_text()) or {}


def _load_secrets(connector_type: str, secrets_file: Path | None = None) -> dict:
    """
    Load secrets for `connector_type` from:
    1. The secrets YAML file (local dev)
    2. DCT_CONNECTOR_<TYPE>_<FIELD> env vars (CI)
    Returns a flat dict of field→value.
    """
    secrets: dict[str, Any] = {}

    # 1. Secrets file
    path = secrets_file or Path(os.environ.get("CONNECTOR_SECRETS", str(_DEFAULT_SECRETS)))
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {}
        secrets.update(data.get(connector_type, {}))

    # 2. CI env vars override (DCT_CONNECTOR_MYSQL_ENV_PASSWORD, etc.)
    prefix = f"DCT_CONNECTOR_{connector_type.upper()}_"
    for key, val in os.environ.items():
        if key.startswith(prefix):
            field_name = key[len(prefix):].lower()
            secrets[field_name] = val

    return secrets


def _resolve_field(value: Any, source: str, secrets: dict) -> Any:
    """If value is None, resolve via the 'source' field (e.g. 'link_user' → secrets['link_user'])."""
    if value is not None:
        return value
    if source:
        return secrets.get(source)
    return None


def load_connector_spec(
    connector_type: str | None = None,
    secrets_file: Path | None = None,
) -> ConnectorSpec:
    """
    Build a ConnectorSpec for the given connector type.

    Priority:
      topology + credentials → .secrets.yaml  or  DCT_CONNECTOR_* env vars
      field defaults/docs    → tests/fixtures/connectors/schema.yaml
    """
    ctype = (connector_type or os.environ.get("CONNECTOR_TYPE", "mysql")).lower()

    schema = _load_schema()
    connector_schema = schema.get("connectors", {}).get(ctype)
    if connector_schema is None:
        supported = list(schema.get("connectors", {}).keys())
        raise ValueError(
            f"Unknown connector type {ctype!r}. "
            f"Supported in schema: {supported}. "
            f"Add it to tests/fixtures/connectors/schema.yaml to support it."
        )

    secrets = _load_secrets(ctype, secrets_file)

    # Topology + credentials from secrets
    source_host  = secrets.get("source_host", "")
    target_host  = secrets.get("target_host", "")
    env_user     = secrets.get("env_user", "delphix")
    env_password = secrets.get("env_password", "")
    link_user    = secrets.get("link_user", "delphix")
    link_password = secrets.get("link_password", "")

    # Build link_fields from schema required_link_fields + secrets + defaults
    link_fields: dict[str, Any] = {}
    for f in connector_schema.get("required_link_fields", []):
        name = f["name"]
        src  = f.get("source", "")
        default = f.get("default")
        example = f.get("example")

        # Try: explicit secret override → source resolution → default → example
        val = (
            secrets.get(name)
            or secrets.get(name.lower().replace("-", "_"))
            or _resolve_field(None, src, {
                "source_host": source_host, "target_host": target_host,
                "link_user": link_user, "link_password": link_password,
            })
            or default
            or example
        )
        if val is not None:
            link_fields[name] = val

    # Build provision_fields similarly
    provision_fields: dict[str, Any] = {}
    for f in connector_schema.get("provision_fields", []):
        name = f["name"]
        src  = f.get("source", "")
        default = f.get("default")
        example = f.get("example")

        val = (
            secrets.get(name)
            or secrets.get(name.lower().replace("-", "_"))
            or _resolve_field(None, src, {
                "link_user": link_user, "link_password": link_password,
            })
            or default
            or example
        )
        if val is not None:
            provision_fields[name] = val

    return ConnectorSpec(
        connector_type=ctype,
        display_name=connector_schema.get("display_name", ctype),
        source_host=source_host,
        target_host=target_host,
        env_user=env_user,
        env_password=env_password,
        link_user=link_user,
        link_password=link_password,
        dsource_link_action=connector_schema["dsource_link_action"],
        provision_action=connector_schema.get("provision_action", "provision_by_snapshot"),
        link_fields=link_fields,
        provision_fields=provision_fields,
        connector_search_keyword=connector_schema.get("connector_search_keyword", ctype),
    )


def schema_link_hints(connector_type: str) -> str:
    """Return the schema's required_link_fields as a human-readable hint for Claude."""
    schema = _load_schema()
    fields = schema.get("connectors", {}).get(connector_type, {}).get("required_link_fields", [])
    if not fields:
        return ""
    lines = ["Required fields for dSource link (use DCT get-defaults or these hints if unsure):"]
    for f in fields:
        hint = f"  {f['name']}: {f['description']}"
        if f.get("default"):
            hint += f" [default: {f['default']!r}]"
        elif f.get("example"):
            hint += f" [example: {f['example']!r}]"
        if f.get("source"):
            hint += f" [from: {f['source']}]"
        lines.append(hint)
    return "\n".join(lines)


# ── pytest fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def connector_spec() -> ConnectorSpec:
    """Session-scoped ConnectorSpec. Selected by CONNECTOR_TYPE env var (default: mysql)."""
    spec = load_connector_spec()
    print(
        f"\nConnectorSpec: {spec.display_name} | "
        f"source={spec.source_host} | target={spec.target_host} | "
        f"link_action={spec.dsource_link_action}"
    )
    return spec
