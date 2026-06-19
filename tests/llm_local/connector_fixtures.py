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
import random
import string
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
class EngineSpec:
    """Fields needed to register a Delphix Engine with DCT."""

    hostname: str
    name: str
    username: str
    password: str
    insecure_ssl: bool = True

    def registration_prompt_detail(self) -> str:
        return (
            f"hostname='{self.hostname}', name='{self.name}', "
            f"username='{self.username}', password='{self.password}', "
            f"insecure_ssl={str(self.insecure_ssl).lower()}"
        )


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
    toolkit_path: str = "/tmp"
    source_config_name: str = "mysql_test"
    source_config_host: str = "target"   # "source" or "target"
    data_dir: str = "/var/lib/mysql"
    source_port: int = 3306
    base_dir: str = "/usr"
    vdb_name: str = "TEST1"
    vdb_port: int = 2151
    vdb_server_id: int = 151
    vdb_mount_path: str = "/mnt/provision/2151"
    vdb_basedir: str = "/usr"
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


# ── Runtime config allocator ─────────────────────────────────────────────────

class MySQLConfigAllocator:
    """
    Generates unique (serverId, port, mountPath, name) tuples for MySQL
    dSources and VDBs on the fly.  Rules come from schema.yaml
    connectors.mysql.config_generation — nothing is hardcoded here.

    Usage (session-scoped fixture recommended):
        alloc = MySQLConfigAllocator()
        ds = alloc.next_dsource()   # {"name": "mysql_test", "serverId": 201, ...}
        vdb = alloc.next_vdb()      # {"name": "TEST1", "serverId": 251, ...}
    """

    def __init__(self, connector_type: str = "mysql") -> None:
        schema = _load_schema_raw()
        rules: dict = (
            schema.get("connectors", {})
                  .get(connector_type, {})
                  .get("config_generation", {})
        )
        self._sid_range: tuple[int, int] = tuple(rules.get("server_id_range", [200, 800]))
        self._ds_step: int   = rules.get("dsource_server_id_step", 100)
        self._vdb_offset: int = rules.get("vdb_server_id_offset", 50)
        self._port_prefix: int = rules.get("port_prefix", 2000)
        self._ds_mount: str  = rules.get("dsource_mount_template", "/mnt/link/staging{port}")
        self._vdb_mount: str = rules.get("vdb_mount_template", "/mnt/link/vdb{port}")
        self._ds_name: str   = rules.get("dsource_name_template", "mysql_test{suffix}")
        self._vdb_templates: list[str] = rules.get(
            "vdb_name_templates", ["TEST{n}", "{rand6}"]
        )

        self._used_sids: set[int] = set()
        self._ds_count: int = 0
        self._vdb_count: int = 0

    # ── internal helpers ──────────────────────────────────────────────────────

    def _next_ds_sid(self) -> int:
        start = self._sid_range[0] + 1          # e.g. 201
        sid = start + self._ds_count * self._ds_step
        while sid in self._used_sids or sid > self._sid_range[1]:
            sid += self._ds_step
        if sid > self._sid_range[1]:
            raise RuntimeError("MySQLConfigAllocator: serverId range exhausted for dSources")
        self._used_sids.add(sid)
        return sid

    def _next_vdb_sid(self, ds_sid: int) -> int:
        sid = ds_sid + self._vdb_offset
        while sid in self._used_sids or sid > self._sid_range[1]:
            sid += 1
        if sid > self._sid_range[1]:
            raise RuntimeError("MySQLConfigAllocator: serverId range exhausted for VDBs")
        self._used_sids.add(sid)
        return sid

    @staticmethod
    def _rand6() -> str:
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=6))

    def _vdb_name(self, n: int) -> str:
        tpl = self._vdb_templates[0] if n <= 999 else self._vdb_templates[-1]
        return tpl.format(n=n, rand6=self._rand6())

    # ── public API ────────────────────────────────────────────────────────────

    def next_dsource(self, name: str | None = None) -> dict[str, Any]:
        """Return a fresh dSource config dict derived from schema rules."""
        self._ds_count += 1
        sid = self._next_ds_sid()
        port = self._port_prefix + sid
        suffix = "" if self._ds_count == 1 else str(self._ds_count - 1)
        return {
            "name":        name or self._ds_name.format(suffix=suffix),
            "serverId":    sid,
            "stagingPort": port,
            "mountPath":   self._ds_mount.format(port=port),
        }

    def next_vdb(self, ds_config: dict | None = None, name: str | None = None) -> dict[str, Any]:
        """Return a fresh VDB config dict.  Pass ds_config to keep serverId close."""
        self._vdb_count += 1
        ds_sid = ds_config["serverId"] if ds_config else (self._sid_range[0] + 1)
        sid = self._next_vdb_sid(ds_sid)
        port = self._port_prefix + sid
        return {
            "name":     name or self._vdb_name(self._vdb_count),
            "serverId": sid,
            "vdbPort":  port,
            "mountPath": self._vdb_mount.format(port=port),
        }


def _load_schema_raw() -> dict:
    if not _SCHEMA_FILE.exists():
        return {}
    return yaml.safe_load(_SCHEMA_FILE.read_text()) or {}


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_schema() -> dict:
    return _load_schema_raw()


def load_engine_spec(secrets_file: Path | None = None) -> EngineSpec:
    """
    Load engine registration details from:
    1. .secrets.yaml under the 'engine' key (local dev)
    2. DCT_ENGINE_<FIELD> env vars (CI)
    """
    secrets: dict[str, Any] = {}

    path = secrets_file or Path(os.environ.get("CONNECTOR_SECRETS", str(_DEFAULT_SECRETS)))
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {}
        secrets.update(data.get("engine", {}))

    for key, val in os.environ.items():
        if key.startswith("DCT_ENGINE_"):
            field_name = key[len("DCT_ENGINE_"):].lower()
            secrets[field_name] = val

    hostname = secrets.get("hostname", "")
    name = secrets.get("name", "")
    username = secrets.get("username", "admin")
    password = secrets.get("password", "")
    insecure_ssl_raw = secrets.get("insecure_ssl", True)
    insecure_ssl = insecure_ssl_raw if isinstance(insecure_ssl_raw, bool) else str(insecure_ssl_raw).lower() == "true"

    return EngineSpec(
        hostname=hostname,
        name=name,
        username=username,
        password=password,
        insecure_ssl=insecure_ssl,
    )


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

    # Environment fields — toolkit_path with schema default fallback
    env_field_defaults = {
        f["name"]: f.get("default", f.get("example", ""))
        for f in connector_schema.get("environment_fields", [])
    }
    toolkit_path = secrets.get("toolkit_path", env_field_defaults.get("toolkit_path", "/tmp"))

    # Source config fields with schema default fallback
    sc_field_defaults = {
        f["name"]: f.get("default", f.get("example", ""))
        for f in connector_schema.get("source_config_fields", [])
    }
    source_config_name = secrets.get("source_config_name", sc_field_defaults.get("name", "mysql_test"))
    source_config_host = secrets.get("source_config_host", sc_field_defaults.get("source_config_host", "target"))
    data_dir = secrets.get("data_dir", sc_field_defaults.get("data_dir", "/var/lib/mysql"))
    source_port = int(secrets.get("port", sc_field_defaults.get("port", 3306)))
    base_dir = secrets.get("base_dir", sc_field_defaults.get("base_dir", "/usr"))

    # VDB provision fields with schema default fallback
    prov_field_defaults = {
        f["name"]: f.get("default", f.get("example", ""))
        for f in connector_schema.get("provision_fields", [])
    }
    vdb_name = secrets.get("vdb_name", "TEST1")
    vdb_port = int(secrets.get("vdb_port", prov_field_defaults.get("port", 2151)))
    vdb_server_id = int(secrets.get("vdb_server_id", prov_field_defaults.get("serverId", 151)))
    vdb_mount_path = secrets.get("vdb_mount_path", prov_field_defaults.get("mPath", "/mnt/provision/2151"))
    vdb_basedir = secrets.get("vdb_basedir", prov_field_defaults.get("baseDir", "/usr"))

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
        toolkit_path=toolkit_path,
        source_config_name=source_config_name,
        source_config_host=source_config_host,
        data_dir=data_dir,
        source_port=source_port,
        base_dir=base_dir,
        vdb_name=vdb_name,
        vdb_port=vdb_port,
        vdb_server_id=vdb_server_id,
        vdb_mount_path=vdb_mount_path,
        vdb_basedir=vdb_basedir,
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


def write_connector_preprompt(spec: ConnectorSpec, output_path: Path | None = None) -> Path:
    """
    Write a connector-specific system pre-prompt to a temp file.
    When appended to Claude's system prompt via --append-system-prompt-file,
    Claude can handle prompts like "Link an AppData dSource using those defaults"
    without needing the fields pre-embedded in the task prompt.

    Includes:
      - Which dSource link action and provision action to use
      - Required fields with descriptions, defaults, and resolved values
      - Resolved credentials (session-scoped, not committed anywhere)
    """
    schema = _load_schema()
    connector_schema = schema.get("connectors", {}).get(spec.connector_type, {})

    lines = [
        f"## Active Connector Context: {spec.display_name}",
        "",
        f"When linking a dSource, use: data_tool action={spec.dsource_link_action}",
        f"When provisioning a VDB, use: data_tool action={spec.provision_action}",
        "",
        f"Source host (read/backup): {spec.source_host}",
        f"Target host (staging/link here): {spec.target_host}",
        f"Environment OS user: {spec.env_user}",
        f"Link OS user: {spec.link_user}",
        "",
    ]

    # Link fields
    link_fields = connector_schema.get("required_link_fields", [])
    if link_fields:
        lines.append("### Required fields for dSource link:")
        for f in link_fields:
            resolved = spec.link_fields.get(f["name"])
            val_hint = f"value={resolved!r}" if resolved is not None else (
                f"default={f['default']!r}" if f.get("default") else
                f"example={f['example']!r}" if f.get("example") else "no default"
            )
            lines.append(f"  {f['name']}: {f['description']} [{val_hint}]")
        lines.append("")

    # Provision fields
    prov_fields = connector_schema.get("provision_fields", [])
    if prov_fields:
        lines.append("### Required fields for VDB provision:")
        for f in prov_fields:
            resolved = spec.provision_fields.get(f["name"])
            val_hint = f"value={resolved!r}" if resolved is not None else (
                f"default={f['default']!r}" if f.get("default") else
                f"example={f['example']!r}" if f.get("example") else "no default"
            )
            lines.append(f"  {f['name']}: {f['description']} [{val_hint}]")
        lines.append("")

    lines += [
        "### Instructions:",
        "- Search DCT automatically for the environment_id and repository_id on the target host.",
        "- Use the field values listed above; fall back to DCT get-defaults for anything not listed.",
        "- For any dSource or VDB name, use a unique run-tagged name if not specified.",
    ]

    content = "\n".join(lines)

    if output_path is None:
        import tempfile
        fd, path_str = tempfile.mkstemp(
            prefix=f"connector-preprompt-{spec.connector_type}-", suffix=".md"
        )
        import os as _os
        with _os.fdopen(fd, "w") as fh:
            fh.write(content)
        return Path(path_str)
    else:
        output_path.write_text(content)
        return output_path


# ── pytest fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine_spec() -> EngineSpec:
    """Session-scoped EngineSpec loaded from .secrets.yaml or DCT_ENGINE_* env vars."""
    spec = load_engine_spec()
    print(f"\nEngineSpec: name={spec.name!r} | hostname={spec.hostname} | insecure_ssl={spec.insecure_ssl}")
    return spec


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
