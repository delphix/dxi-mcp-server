"""
P1 — Connector fixture layer.

Provides a `ConnectorSpec` dataclass that holds all connector-type-specific
fields needed at each step of the CDA prerequisite chain:
    engine → connector install → hosts → source config → dSource link → VDB provision

Selected via CONNECTOR_TYPE env var (default: "appdata" / MySQL plugin).
Each preset reads from named env vars so credentials stay out of code.

Supported connector types:
    appdata   — MySQL via Delphix MySQL Plugin (PLUGIN on the engine)
    oracle    — Oracle dSource (dsource_link_oracle)
    mssql     — MS SQL Server (dsource_link_mssql)
    ase       — SAP ASE / Sybase (dsource_link_ase)

Usage:
    @pytest.fixture
    def spec(connector_spec):
        return connector_spec  # ConnectorSpec for the current CONNECTOR_TYPE

    def test_something(spec):
        print(spec.dsource_link_action)
        print(spec.link_fields)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import pytest


@dataclass
class ConnectorSpec:
    """All connector-specific fields for one connector type."""

    # Identity
    connector_type: str                # "appdata" | "oracle" | "mssql" | "ase"
    display_name: str                  # human label for messages

    # Hosts (env vars: MYSQL_SOURCE_HOST / MYSQL_TARGET_HOST or generic)
    source_host: str                   # source data host (r95-mys-s11.dlpxdc.co)
    target_host: str                   # target/staging host (r95-mys-t11.dlpxdc.co)

    # Environment credentials (OS SSH)
    env_user: str                      # OS user for adding environments
    env_password: str                  # OS password

    # Link credentials (OS + DB level)
    link_os_user: str                  # OS user for dSource link (delphix_os)
    link_os_password: str              # OS password for link

    # dSource link action + connector-specific parameters
    dsource_link_action: str           # "dsource_link_appdata" | "dsource_link_oracle" ...
    link_fields: dict = field(default_factory=dict)
    # ^ connector-specific extra fields embedded in the prompt for Claude to use

    # VDB provision action + connector-specific parameters
    provision_action: str = "provision_by_snapshot"
    provision_fields: dict = field(default_factory=dict)
    # ^ connector-specific extra fields for VDB provision

    # Toolkit/connector name to verify in toolkit_tool.search
    connector_search_keyword: str = "appdata"

    @property
    def source_short(self) -> str:
        return self.source_host.split(".")[0]

    @property
    def target_short(self) -> str:
        return self.target_host.split(".")[0]

    def link_prompt_detail(self) -> str:
        """Format the connector-specific link fields for embedding in a Claude prompt."""
        if not self.link_fields:
            return ""
        lines = [f"Use these connector-specific fields for the link:"]
        for k, v in self.link_fields.items():
            lines.append(f"  {k}: {v!r}")
        return "\n".join(lines)

    def provision_prompt_detail(self) -> str:
        """Format provision-specific fields for embedding in a Claude prompt."""
        if not self.provision_fields:
            return ""
        lines = [f"Use these connector-specific fields for VDB provisioning:"]
        for k, v in self.provision_fields.items():
            lines.append(f"  {k}: {v!r}")
        return "\n".join(lines)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _load_appdata_spec() -> ConnectorSpec:
    """MySQL via Delphix MySQL Plugin (AppData/PLUGIN)."""
    return ConnectorSpec(
        connector_type="appdata",
        display_name="MySQL (AppData/Plugin)",
        source_host=_env("MYSQL_SOURCE_HOST", "r95-mys-s11.dlpxdc.co"),
        target_host=_env("MYSQL_TARGET_HOST", "r95-mys-t11.dlpxdc.co"),
        env_user=_env("MYSQL_ENV_USER", "mysql"),
        env_password=_env("MYSQL_ENV_PASSWORD"),
        link_os_user=_env("MYSQL_LINK_USER", "delphix_os"),
        link_os_password=_env("MYSQL_LINK_PASSWORD"),
        dsource_link_action="dsource_link_appdata",
        link_fields={
            # MySQL plugin dSource link parameters (from PLUGIN-1 linked_source_definition)
            "mountPath": _env("MYSQL_MOUNT_PATH", "/mnt/provision"),
            "stagingBasedir": _env("MYSQL_STAGING_BASEDIR", "/usr"),
            "stagingPort": int(_env("MYSQL_STAGING_PORT", "3308")),
            "sourceUser": _env("MYSQL_DB_USER", "delphix_os"),
            "sourcePass": _env("MYSQL_DB_PASS", _env("MYSQL_LINK_PASSWORD")),
            "sourceip": _env("MYSQL_SOURCE_HOST", "r95-mys-s11.dlpxdc.co"),
            "serverId": int(_env("MYSQL_SERVER_ID", "200")),
            "dSourceType": _env("MYSQL_DSOURCE_TYPE", ""),
        },
        provision_action="provision_by_snapshot",
        provision_fields={
            # MySQL plugin VDB provision parameters (from PLUGIN-1 virtual_source_definition)
            "vdbUser": _env("MYSQL_VDB_USER", "delphix_os"),
            "vdbPass": _env("MYSQL_VDB_PASS", _env("MYSQL_LINK_PASSWORD")),
            "baseDir": _env("MYSQL_VDB_BASEDIR", "/usr"),
            "port": int(_env("MYSQL_VDB_PORT", "3309")),
            "serverId": int(_env("MYSQL_VDB_SERVER_ID", "300")),
            "mPath": _env("MYSQL_VDB_MOUNT_PATH", "/mnt/provision"),
        },
        connector_search_keyword="plugin",
    )


def _load_oracle_spec() -> ConnectorSpec:
    """Oracle dSource."""
    return ConnectorSpec(
        connector_type="oracle",
        display_name="Oracle",
        source_host=_env("ORACLE_SOURCE_HOST"),
        target_host=_env("ORACLE_TARGET_HOST"),
        env_user=_env("ORACLE_ENV_USER", "delphix"),
        env_password=_env("ORACLE_ENV_PASSWORD"),
        link_os_user=_env("ORACLE_LINK_USER", "delphix"),
        link_os_password=_env("ORACLE_LINK_PASSWORD"),
        dsource_link_action="dsource_link_oracle",
        link_fields={
            "db_credentials_username": _env("ORACLE_DB_USER"),
            "db_credentials_password": _env("ORACLE_DB_PASSWORD"),
            "oracle_jdbc_connection_string": _env("ORACLE_JDBC"),
        },
        provision_action="provision_by_snapshot",
        provision_fields={
            "mount_path": _env("ORACLE_VDB_MOUNT_PATH", "/mnt/provision"),
        },
        connector_search_keyword="oracle",
    )


def _load_mssql_spec() -> ConnectorSpec:
    """MS SQL Server dSource."""
    return ConnectorSpec(
        connector_type="mssql",
        display_name="MS SQL Server",
        source_host=_env("MSSQL_SOURCE_HOST"),
        target_host=_env("MSSQL_TARGET_HOST"),
        env_user=_env("MSSQL_ENV_USER", "delphix"),
        env_password=_env("MSSQL_ENV_PASSWORD"),
        link_os_user=_env("MSSQL_LINK_USER", "delphix"),
        link_os_password=_env("MSSQL_LINK_PASSWORD"),
        dsource_link_action="dsource_link_mssql",
        link_fields={},
        provision_action="provision_by_snapshot",
        provision_fields={},
        connector_search_keyword="mssql",
    )


def _load_ase_spec() -> ConnectorSpec:
    """SAP ASE / Sybase dSource."""
    return ConnectorSpec(
        connector_type="ase",
        display_name="SAP ASE",
        source_host=_env("ASE_SOURCE_HOST"),
        target_host=_env("ASE_TARGET_HOST"),
        env_user=_env("ASE_ENV_USER", "delphix"),
        env_password=_env("ASE_ENV_PASSWORD"),
        link_os_user=_env("ASE_LINK_USER", "delphix"),
        link_os_password=_env("ASE_LINK_PASSWORD"),
        dsource_link_action="dsource_link_ase",
        link_fields={},
        provision_action="provision_by_snapshot",
        provision_fields={},
        connector_search_keyword="ase",
    )


_LOADERS = {
    "appdata": _load_appdata_spec,
    "oracle": _load_oracle_spec,
    "mssql": _load_mssql_spec,
    "ase": _load_ase_spec,
}


def load_connector_spec(connector_type: Optional[str] = None) -> ConnectorSpec:
    """Load the ConnectorSpec for the given type (defaults to CONNECTOR_TYPE env var)."""
    ctype = (connector_type or os.environ.get("CONNECTOR_TYPE", "appdata")).lower()
    loader = _LOADERS.get(ctype)
    if loader is None:
        raise ValueError(
            f"Unknown connector type {ctype!r}. "
            f"Supported: {sorted(_LOADERS)}"
        )
    return loader()


# ── pytest fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def connector_spec() -> ConnectorSpec:
    """
    Session-scoped ConnectorSpec loaded from env vars.
    Selected by CONNECTOR_TYPE (default: appdata/MySQL).
    """
    spec = load_connector_spec()
    print(
        f"\nConnectorSpec loaded: {spec.display_name} | "
        f"source={spec.source_host} | target={spec.target_host} | "
        f"link_action={spec.dsource_link_action}"
    )
    return spec
