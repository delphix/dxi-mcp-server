![Support](https://img.shields.io/badge/Support-Community-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

# Delphix DCT API MCP Server

The Delphix DCT API MCP Server provides a robust Model Context Protocol (MCP) interface for interacting with the Delphix Data Control Tower (DCT) API. This service enables AI assistants and client applications to securely access test data management capabilities through a structured toolset.

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [Videos](#videos)
- [Environment Variables](#environment-variables)
- [MCP Client Configuration](#mcp-client-configuration)
- [Advanced Installation](#advanced-installation)
- [Toolsets](#toolsets)
- [Available Tools](#available-tools)
- [Privacy & Telemetry](#privacy--telemetry)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [License](#license)
- [Support & Contributing](#support--contributing)

## Features

- **Persona-Based Toolsets**: Choose from 5 pre-configured toolsets tailored for different roles (Self-Service, Self-Service Provisioning, Continuous Data Admin, Platform Admin, Reporting & Insights).
- **Auto Mode**: Dynamic toolset discovery with runtime switching - no server restart required.
- **Grouped Tools**: Each tool handles multiple related actions via an `action` parameter, reducing tool count while maintaining full functionality.
- **Confirmation System**: Built-in confirmation checks for destructive operations to prevent accidental data loss.
- **Comprehensive DCT integration**: Access datasets, environments, engines, compliance, jobs, and reporting through specialized tools.
- **Security and reliability**: API client includes retry logic, exponential backoff, and SSL configuration.  
- **Flexible configuration**: Environment-based setup with validation.
- **Cross-platform support**: Startup scripts for Windows, macOS, and Linux.
- **Structured logging**: Application and session logging with telemetry tracking.
- **Telemetry (Optional)**: Usage analytics are disabled by default and require user consent.


## Quick Start

Configure the MCP server within your AI client application (such as Claude Desktop, Cursor, or VS Code). This is the recommended method and does not require separate installation.

**What you need:**
- **Delphix DCT Instance**: Running Delphix Data Control Tower instance
- **API Key**: Valid DCT API key with the following READ permissions:
  - VDBs
  - VDB Groups
  - dSources
  - Environments
  - Bookmarks
  - Snapshots
  - Data Connections
  - Engines
  - Virtualization and Compliance Job Executions
  - All Virtualization Storage Insights
- **uv** (recommended): Install using [uv](https://pypi.org/project/uv/). This method provides access to the uvx command. 
- **OR Python 3.11+**: If not using uv/uvx

**Next step:** Proceed to [MCP Client Configuration](#mcp-client-configuration) to complete setup.

**Alternative:** To run the server as a standalone command-line tool or contribute to development, see [Advanced Installation](#advanced-installation).

## Videos

Watch these videos to see the MCP Server in action:

 - [General overview of the MCP Server](https://help.delphix.com/eh/current/content/resources/media/general-overview-mcp-server.mp4)
 - [Claude App configuration and sample usage](https://help.delphix.com/eh/current/content/resources/media/claude-configuration-mcp-server.mp4)
 - [Visual Studio Code configuration and sample usage](https://help.delphix.com/eh/current/content/resources/media/mcp-server-visual-studio-code-config.mp4)

## Environment Variables

All configuration methods use these environment variables:

- `DCT_API_KEY` - Your Delphix DCT API key (required).

   _Do not prefix with `apk`. Use the key exactly as provided by DCT. Example: `2.123abc...`_
- `DCT_BASE_URL` - Your DCT instance URL (required).

   _Do not append with `/dct`. Example: `https://dct-hostname.com`_
- `DCT_VERIFY_SSL` - Enable SSL verification (`true`/`false`, default: `false`)
- `DCT_LOG_LEVEL` - Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `DCT_TIMEOUT` - Request timeout in seconds (default: `30`)
- `DCT_MAX_RETRIES` - Maximum retry attempts (default: `3`)
- `DCT_TOOLSET` - Toolset to load (see [Toolsets](#toolsets) section below)
  - `self_service` (default) - Basic VDB operations (6 tools)
  - `auto` - Dynamic discovery with 5 meta-tools for runtime switching
  - `self_service_provision` - Self-service + provisioning (12 tools)
  - `continuous_data_admin` - Full DBA operations (14 tools)
  - `platform_admin` - System administration (10 tools)
  - `reporting_insights` - Read-only reporting (13 tools)
- `IS_LOCAL_TELEMETRY_ENABLED` - Enable telemetry (`true`/`false`, default: `false`)

## MCP Client Configuration

> **Note:** Use absolute paths for the `command` field in all configurations. Ensure environment variables are set for each client application.

Configuration examples for popular MCP clients are provided below. The structure may vary (some use mcpServers, others use servers).

### Configuration Methods

All clients support three installation methods:

 - **Using uvx (Recommended):**

    Requires [uv](https://pypi.org/project/uv/). Handles dependencies automatically.

 - **Using Python directly:**

    Point to the main.py file in your local repository clone.

 - **Using shell/batch scripts**

    Use provided startup scripts (`_python.sh` for Linux/macOS, `_python.bat` for Windows). The `_uv.sh` and `_uv.bat` scripts require `uv`.

See below for the full JSON configuration examples for each client.

---

<details>
<summary><strong>Claude Desktop</strong></summary>

**Option 1: Using uvx (Recommended)**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_LOG_LEVEL": "INFO",
        "DCT_TOOLSET": "self_service"
      }
    }
  }
}
```

> **Tip**: Use `"DCT_TOOLSET": "self_service"` (default) for basic VDB operations, or `"auto"` for dynamic toolset discovery, or `"continuous_data_admin"` for full DBA operations.

**Option 2: Using Python directly**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "python",
      "args": ["/absolute/path/to/dxi-mcp-server/src/dct_mcp_server/main.py"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TOOLSET": "self_service"
      }
    }
  }
}
```

**Option 3: Using shell/batch scripts**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TOOLSET": "self_service"
      }
    }
  }
}
```
</details>

<details>
<summary><strong>Cursor IDE & Windsurf</strong></summary>

**Option 1: Using uvx (Recommended)**
```json
{
  "mcpServers": [
    {
      "name": "delphix-dct", 
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_LOG_LEVEL": "INFO",
        "DCT_TOOLSET": "self_service"
      }
    }
  ]
}
```

**Option 2: Using Python directly**
```json
{
  "mcpServers": [
    {
      "name": "delphix-dct",
      "command": "python",
      "args": ["/absolute/path/to/dxi-mcp-server/src/dct_mcp_server/main.py"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TOOLSET": "self_service"
      }
    }
  ]
}
```

**Option 3: Using shell scripts**
```json
{
  "mcpServers": [
    {
      "name": "delphix-dct",
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TOOLSET": "self_service"
      }
    }
  ]
}
```

> **Note**: Windsurf uses the same configuration format as Cursor (mcpServers object).
</details>

<details>
<summary><strong>VS Code, Eclipse, & IntelliJ IDEA</strong></summary>

> **VS Code Copilot Note**: For best experience, use a fixed toolset instead of `auto` mode, as VS Code Copilot doesn't refresh tools mid-session.

**Option 1: Using uvx (Recommended)**
```json
{
  "servers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_LOG_LEVEL": "INFO",
        "DCT_TOOLSET": "self_service"
      }
    }
  }
}
```

**Option 2: Using Python directly**
```json
{
  "servers": {
    "delphix-dct": {
      "command": "python",
      "args": ["/absolute/path/to/dxi-mcp-server/src/dct_mcp_server/main.py"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TOOLSET": "self_service"
      }
    }
  }
}
```

**Option 3: Using shell scripts**
```json
{
  "servers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TOOLSET": "self_service"
      }
    }
  }
}
```

> **Note**: VS Code, Eclipse, and IntelliJ all use the same configuration format (servers object).
</details>

## Advanced Installation

For running as a standalone command-line tool or contributing to development.

Most users should use the [MCP Client Configuration](#mcp-client-configuration) above instead.

### Setting Environment Variables

For standalone installation, set the [environment variables](#environment-variables) in your shell before running the server.

<details>
<summary><strong>Linux/macOS</strong></summary>

Use the `export` command to set variables for your current shell session. For improved security, avoid adding secrets like the API key to your shell's profile file.

**Production Example:**
```bash
export DCT_API_KEY="your-production-key"
export DCT_BASE_URL="https://dct-prod.company.com"
export DCT_VERIFY_SSL="true"
export DCT_LOG_LEVEL="INFO"
```

**Development Example:**
```bash
export DCT_API_KEY="your-development-key"
export DCT_BASE_URL="https://dct-dev.company.com"
export DCT_VERIFY_SSL="false"
export DCT_LOG_LEVEL="DEBUG"
```
</details>

<details>
<summary><strong>Windows</strong></summary>

Use the `set` command in Command Prompt or `$env:` in PowerShell for the current session. For improved security, avoid setting secrets like the API key permanently.

**Command Prompt:**
```powershell
set DCT_API_KEY="your-production-key"
set DCT_BASE_URL="https://dct-prod.company.com"
set DCT_VERIFY_SSL="true"
```

**PowerShell:**
```powershell
$env:DCT_API_KEY="your-production-key"
$env:DCT_BASE_URL="https://dct-prod.company.com"
$env:DCT_VERIFY_SSL="true"
```
</details>

### Quick Start (Command-Line Tool)

Recommended method for users who want to use the server without modifying its code.

**Prerequisites**:
- Python 3.11+
- `pip` and `git` installed on your system
- [Environment variables](#environment-variables) configured in your shell. See above examples.

Install the server directly from GitHub using `pip`:
```bash
pip install git+https://github.com/delphix/dxi-mcp-server.git

# Verify the installation
dct-mcp-server --help
```

This makes the `dct-mcp-server` command available globally in your environment.

### Developer Setup

Method for developers who want to modify the code or run it from a local clone.

**Prerequisites**:
- Python 3.11+
- `git` installed on your system
- [Environment variables](#environment-variables) configured in your shell. See above examples.

**Steps**:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/delphix/dxi-mcp-server.git
   cd dxi-mcp-server
   ```

2. **Set up the environment and install dependencies:**
   
   The included scripts handle environment setup automatically. We recommend using `uv` (which provides `uvx`) for the best performance:
   
   **Linux/macOS:**
   ```bash
   chmod +x start_mcp_server_uv.sh
   ./start_mcp_server_uv.sh
   ```
   
   **Windows:**
   ```bash
   start_mcp_server_windows_uv.bat
   ```
   
   > **Note**: If you prefer not to use `uv`, scripts for standard Python with `venv` are also provided (`start_mcp_server_python.sh` and `start_mcp_server_windows_python.bat`).

### Connecting a Client to a Running Server

Once the server is running (either via the command-line tool or from the source), it will print the port it is listening on to the console (e.g., `INFO:     Uvicorn running on http://127.0.0.1:6790 (Press CTRL+C to quit)`). 

To connect your client, you only need to specify this port number. You do not need to provide environment variables in the client configuration, as the server already has them from your terminal session.

**Example for Claude Desktop:**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "port": 6790
    }
  }
}
```

> **Note**: You can configure other MCP clients similarly by providing the port number. This method is ideal for development, as it allows you to restart the server without reconfiguring or restarting your client application. For troubleshooting, all log files can be found in the `logs` directory created in the project root.

## Toolsets

The server organizes tools into **persona-based toolsets** designed for specific roles and use cases. Each toolset provides a curated set of grouped tools.

### Available Toolsets

| Toolset | Tools | Target Users | Description |
|---------|-------|--------------|-------------|
| `self_service` | 6 tools | Developers, QA | Basic VDB operations: search, refresh, rollback, start/stop (default) |
| `auto` | 5 meta-tools | All users | Dynamic discovery mode - start minimal, enable toolsets at runtime |
| `self_service_provision` | 12 tools | Dev leads | Self-service + VDB provisioning capabilities |
| `continuous_data_admin` | 14 tools | DBAs | Full data management: VDBs, dSources, snapshots, policies |
| `platform_admin` | 10 tools | Admins | System administration: engines, environments, IAM, reporting |
| `reporting_insights` | 13 tools | Managers | Read-only reporting and analytics |

### Auto Mode

When `DCT_TOOLSET=auto`, the server starts with **5 meta-tools** for dynamic toolset discovery:

| Meta-Tool | Description |
|-----------|-------------|
| `list_available_toolsets` | List all toolsets with descriptions and tool counts |
| `get_toolset_tools` | Get detailed list of tools and actions in a toolset |
| `enable_toolset` | Enable a toolset at runtime (no restart required) |
| `disable_toolset` | Return to meta-tools only mode |
| `check_operation_confirmation` | Check if an operation requires confirmation |

**Example workflow:**
```
User: "What toolsets are available?"
AI: [calls list_available_toolsets] → Shows 5 toolsets

User: "I need to work with VDBs"
AI: [calls enable_toolset("self_service")] → 6 tools now available

User: "Show me all VDBs"
AI: [calls vdb_tool(action="search_vdbs")] → Returns VDB list
```

### Fixed Toolset Mode

For environments where you always need the same toolset, set it directly:

```json
{
  "env": {
    "DCT_TOOLSET": "self_service"
  }
}
```

This pre-registers all tools at startup (no runtime switching).

### Agent Compatibility for Auto Mode

Not all MCP clients support dynamic tool registration mid-session:

| Agent | Dynamic Tools | Notes |
|-------|---------------|-------| 
| Claude Desktop | ✅ Yes | Fully supports `tools/list_changed` notifications |
| Cursor | ✅ Yes | Refreshes tool list dynamically |
| Continue.dev | ✅ Yes | Supports runtime tool changes |
| VS Code Copilot | ⚠️ Limited | Requires chat restart after `enable_toolset` |

**Recommendation**: For VS Code Copilot, use a fixed toolset (`DCT_TOOLSET=self_service`) for the best experience.

### Grouped Tools

Each tool in a toolset handles multiple related **actions** via an `action` parameter:

```python
# Instead of calling separate tools:
search_vdbs(filter_expression="...")
get_vdb(vdbId="...")
refresh_vdb_by_timestamp(vdbId="...", timestamp="...")

# Call one grouped tool with different actions:
vdb_tool(action="search_vdbs", filter_expression="...")
vdb_tool(action="get_vdb", vdbId="...")
vdb_tool(action="refresh_vdb_by_timestamp", vdbId="...", timestamp="...")
```

This reduces tool count while maintaining full functionality.

### Confirmation for Destructive Operations

Destructive operations (delete, disable, etc.) require explicit confirmation:

```python
# First call returns confirmation requirement
vdb_tool(action="delete_vdb", vdbId="vdb-123")
# Response: {"status": "confirmation_required", "confirmation_level": "manual", ...}

# Confirm by setting confirmed=True
vdb_tool(action="delete_vdb", vdbId="vdb-123", confirmed=True)
# Response: {"status": "success", ...}
```

## Available Tools

The tools available depend on the configured toolset. Below are the grouped tools for each toolset.

### continuous_data_admin Toolset (14 Tools)

<details>
<summary><strong><code>data_tool</code></strong> - VDB, VDB Group, and dSource operations (41 actions)</summary>

- **Actions**: `search_vdbs`, `get_vdb`, `provision_by_timestamp`, `provision_by_snapshot`, `provision_from_bookmark`, `refresh_vdb_by_timestamp`, `refresh_vdb_by_snapshot`, `rollback_vdb_by_timestamp`, `start_vdb`, `stop_vdb`, `enable_vdb`, `disable_vdb`, `delete_vdb`, `search_vdb_groups`, `get_vdb_group`, `create_vdb_group`, `refresh_vdb_group`, `rollback_vdb_group`, `search_dsources`, `get_dsource`, `list_dsource_snapshots`, and more
- **Use cases**: VDB lifecycle management, data provisioning, refresh/rollback operations
</details>

<details>
<summary><strong><code>snapshot_bookmark_tool</code></strong> - Snapshot and Bookmark operations (18 actions)</summary>

- **Actions**: `search_snapshots`, `get_snapshot`, `delete_snapshot`, `update_snapshot`, `search_bookmarks`, `get_bookmark`, `create_bookmark`, `delete_bookmark`, `find_snapshot_by_timestamp`, `find_snapshot_by_location`
- **Use cases**: Point-in-time recovery, bookmark management, snapshot retention
</details>

<details>
<summary><strong><code>environment_source_tool</code></strong> - Environment and Source operations (17 actions)</summary>

- **Actions**: `search_environments`, `get_environment`, `create_environment`, `enable_environment`, `disable_environment`, `refresh_environment`, `search_sources`, `get_source`, `update_source`
- **Use cases**: Environment management, source discovery, host configuration
</details>

<details>
<summary><strong><code>instance_tool</code></strong> - CDB and vCDB operations (14 actions)</summary>

- **Actions**: `search_cdbs`, `get_cdb`, `search_vcdbs`, `get_vcdb`, `start_vcdb`, `stop_vcdb`, `enable_vcdb`, `disable_vcdb`, `delete_vcdb`
- **Use cases**: Oracle container database management
</details>

<details>
<summary><strong><code>iam_tool</code></strong> - Identity and Access Management (21 actions)</summary>

- **Actions**: `search_accounts`, `get_account`, `create_account`, `enable_account`, `disable_account`, `reset_password`, `search_roles`, `create_role`, `search_access_groups`, `create_access_group`
- **Use cases**: User management, role-based access control, API client management
</details>

<details>
<summary><strong><code>reporting_tool</code></strong> - Reporting and Analytics (16 actions)</summary>

- **Actions**: `get_storage_capacity_report`, `get_vdb_inventory_report`, `get_dsource_consumption_report`, `get_engine_performance_report`, `search_storage_savings_report`, `get_license`, `create_scheduled_report`
- **Use cases**: Capacity planning, usage reporting, compliance auditing
</details>

<details>
<summary><strong><code>virtualization_policy_tool</code></strong> - Policy management (10 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `apply`, `unapply`, `search_targets`
- **Use cases**: Retention policies, refresh schedules, sync policies
</details>

<details>
<summary><strong><code>job_tool</code></strong> - Job monitoring (6 actions)</summary>

- **Actions**: `search`, `get`, `abandon`, `get_result`
- **Use cases**: Job tracking, error analysis, operation monitoring
</details>

<details>
<summary><strong><code>engine_tool</code></strong> - Engine management (5 actions)</summary>

- **Actions**: `search`, `get`, `update`, `add_tags`, `delete_tags`
- **Use cases**: Engine monitoring, configuration management
</details>

<details>
<summary><strong><code>replication_tool</code></strong> - Replication profiles (8 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `execute`
- **Use cases**: Data replication, disaster recovery
</details>

<details>
<summary><strong><code>database_template_tool</code></strong> - VDB templates (7 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`
- **Use cases**: Standardized VDB provisioning
</details>

<details>
<summary><strong><code>hook_template_tool</code></strong> - Hook templates (7 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`
- **Use cases**: Pre/post operation scripts
</details>

<details>
<summary><strong><code>tag_tool</code></strong> - Tag management (6 actions)</summary>

- **Actions**: `search`, `get`, `create`, `delete`, `search_usages`
- **Use cases**: Resource tagging, organization
</details>

<details>
<summary><strong><code>data_connection_tool</code></strong> - Data connections (5 actions)</summary>

- **Actions**: `search`, `get`, `update`
- **Use cases**: Connection management
</details>

### self_service Toolset (6 Tools)

<details>
<summary><strong><code>vdb_tool</code></strong> - VDB operations (14 actions)</summary>

- **Actions**: `search`, `get`, `start`, `stop`, `enable`, `disable`, `refresh_by_timestamp`, `refresh_by_snapshot`, `refresh_from_bookmark`, `rollback_by_timestamp`, `rollback_by_snapshot`, `rollback_from_bookmark`, `list_snapshots`, `list_bookmarks`
- **Use cases**: VDB lifecycle management, refresh and rollback operations
</details>

<details>
<summary><strong><code>vdb_group_tool</code></strong> - VDB Group operations (14 actions)</summary>

- **Actions**: `search`, `get`, `refresh`, `refresh_from_bookmark`, `refresh_by_snapshot`, `refresh_by_timestamp`, `rollback`, `lock`, `unlock`, `start`, `stop`, `enable`, `disable`, `list_bookmarks`
- **Use cases**: Coordinated VDB group operations, bulk refresh/rollback
</details>

<details>
<summary><strong><code>dsource_tool</code></strong> - dSource operations (3 actions)</summary>

- **Actions**: `search`, `get`, `list_snapshots`
- **Use cases**: dSource discovery, snapshot listing
</details>

<details>
<summary><strong><code>snapshot_tool</code></strong> - Snapshot operations (6 actions)</summary>

- **Actions**: `search`, `get`, `get_timeflow_range`, `get_runtime`, `find_by_location`, `find_by_timestamp`
- **Use cases**: Point-in-time recovery, snapshot discovery
</details>

<details>
<summary><strong><code>bookmark_tool</code></strong> - Bookmark operations (6 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `get_vdb_groups`
- **Use cases**: Bookmark management, point-in-time markers
</details>

<details>
<summary><strong><code>job_tool</code></strong> - Job operations (3 actions)</summary>

- **Actions**: `search`, `get`, `abandon`
- **Use cases**: Job monitoring, operation tracking
</details>

### self_service_provision Toolset (12 Tools)

> Inherits all tools from `self_service` with extended capabilities, plus additional tools.

<details>
<summary><strong><code>vdb_tool</code></strong> - VDB operations with provisioning (28 actions)</summary>

- **Actions**: All self_service actions plus: `provision_by_timestamp`, `get_provision_by_timestamp_defaults`, `provision_by_snapshot`, `get_provision_by_snapshot_defaults`, `provision_from_bookmark`, `get_provision_from_bookmark_defaults`, `provision_by_location`, `get_provision_by_location_defaults`, `update`, `delete`, `switch_timeflow`, `undo_refresh`, `get_deletion_dependencies`, `add_tags`, `delete_tags`
- **Use cases**: VDB provisioning, lifecycle management, tagging
</details>

<details>
<summary><strong><code>vdb_group_tool</code></strong> - VDB Group operations with CRUD (21 actions)</summary>

- **Actions**: All self_service actions plus: `create`, `update`, `delete`, `provision_from_bookmark`, `get_latest_snapshots`, `add_tags`, `delete_tags`
- **Use cases**: VDB group management, provisioning from bookmarks
</details>

<details>
<summary><strong><code>dsource_tool</code></strong> - dSource operations (3 actions)</summary>

- **Actions**: `search`, `get`, `list_snapshots`
- **Use cases**: dSource discovery, snapshot listing
</details>

<details>
<summary><strong><code>snapshot_tool</code></strong> - Snapshot operations (6 actions)</summary>

- **Actions**: `search`, `get`, `get_timeflow_range`, `get_runtime`, `find_by_location`, `find_by_timestamp`
- **Use cases**: Point-in-time recovery, snapshot discovery
</details>

<details>
<summary><strong><code>bookmark_tool</code></strong> - Bookmark operations (6 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `get_vdb_groups`
- **Use cases**: Bookmark management, point-in-time markers
</details>

<details>
<summary><strong><code>job_tool</code></strong> - Job operations (3 actions)</summary>

- **Actions**: `search`, `get`, `abandon`
- **Use cases**: Job monitoring, operation tracking
</details>

<details>
<summary><strong><code>instance_tool</code></strong> - CDB/vCDB operations (4 actions)</summary>

- **Actions**: `search_cdbs`, `get_cdb`, `search_vcdbs`, `get_vcdb`
- **Use cases**: Oracle container database discovery
</details>

<details>
<summary><strong><code>database_template_tool</code></strong> - VDB Templates (7 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `add_tags`, `delete_tags`
- **Use cases**: Standardized VDB provisioning templates
</details>

<details>
<summary><strong><code>hook_template_tool</code></strong> - Hook Templates (7 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `add_tags`, `delete_tags`
- **Use cases**: Pre/post operation script management
</details>

<details>
<summary><strong><code>virtualization_policy_tool</code></strong> - Policies (3 actions)</summary>

- **Actions**: `search`, `get`, `search_targets`
- **Use cases**: Policy discovery and target lookup
</details>

<details>
<summary><strong><code>environment_tool</code></strong> - Environments (4 actions)</summary>

- **Actions**: `search`, `get`, `list_hosts`, `list_listeners`
- **Use cases**: Environment discovery and configuration
</details>

<details>
<summary><strong><code>tag_tool</code></strong> - Tags (4 actions)</summary>

- **Actions**: `search`, `get`, `create`, `delete`
- **Use cases**: Resource tagging and organization
</details>

### platform_admin Toolset (10 Tools)

<details>
<summary><strong><code>job_tool</code></strong> - Job operations (3 actions)</summary>

- **Actions**: `search`, `get`, `abandon`
- **Use cases**: Job monitoring, operation management
</details>

<details>
<summary><strong><code>engine_tool</code></strong> - CD Engine management (7 actions)</summary>

- **Actions**: `search`, `get`, `register`, `update`, `unregister`, `add_tags`, `delete_tags`
- **Use cases**: Engine registration, configuration, monitoring
</details>

<details>
<summary><strong><code>environment_tool</code></strong> - Environment management (12 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `enable`, `disable`, `refresh`, `list_hosts`, `list_listeners`, `add_tags`, `delete_tags`
- **Use cases**: Full environment lifecycle management
</details>

<details>
<summary><strong><code>source_tool</code></strong> - Source management (5 actions)</summary>

- **Actions**: `search`, `get`, `update`, `add_tags`, `delete_tags`
- **Use cases**: Source configuration and tagging
</details>

<details>
<summary><strong><code>replication_tool</code></strong> - Replication profiles (8 actions)</summary>

- **Actions**: `search`, `get`, `create`, `update`, `delete`, `execute`, `add_tags`, `delete_tags`
- **Use cases**: Data replication, disaster recovery
</details>

<details>
<summary><strong><code>reporting_tool</code></strong> - Reports and Analytics (17 actions)</summary>

- **Actions**: `search_storage_savings_report`, `get_storage_capacity_report`, `get_virtualization_storage_summary`, `get_vdb_inventory_report`, `search_vdb_inventory_report`, `get_dsource_consumption_report`, `get_engine_performance_report`, `get_dataset_performance_analytics`, `get_api_usage_report`, `get_audit_logs_summary_report`, `search_scheduled_reports`, `get_scheduled_report`, `create_scheduled_report`, `update_scheduled_report`, `delete_scheduled_report`, `get_license`, `change_license`
- **Use cases**: Capacity planning, usage reporting, license management
</details>

<details>
<summary><strong><code>iam_tool</code></strong> - Identity and Access Management (21 actions)</summary>

- **Actions**: `search_accounts`, `get_account`, `create_account`, `update_account`, `delete_account`, `enable_account`, `disable_account`, `reset_password`, `search_roles`, `get_role`, `create_role`, `update_role`, `delete_role`, `search_access_groups`, `get_access_group`, `create_access_group`, `update_access_group`, `delete_access_group`, `list_api_clients`, `create_api_client`, `delete_api_client`
- **Use cases**: User management, RBAC, API client management
</details>

<details>
<summary><strong><code>data_connection_tool</code></strong> - Data connections (5 actions)</summary>

- **Actions**: `search`, `get`, `update`, `add_tags`, `delete_tags`
- **Use cases**: Connection management and tagging
</details>

<details>
<summary><strong><code>tag_tool</code></strong> - Tag management (5 actions)</summary>

- **Actions**: `search`, `get`, `create`, `delete`, `get_usages`
- **Use cases**: Resource tagging, usage tracking
</details>

<details>
<summary><strong><code>admin_platform_tool</code></strong> - Platform administration (20 actions)</summary>

- **Actions**: `list_llm_models`, `get_llm_model`, `upload_llm_model`, `get_gateway_config`, `update_gateway_config`, `enable_ai`, `get_properties`, `update_properties`, `get_telemetry_config`, `update_telemetry_config`, `get_smtp_config`, `update_smtp_config`, `validate_smtp_config`, `get_ldap_config`, `update_ldap_config`, `validate_ldap_config`, `get_saml_config`, `update_saml_config`, `get_proxy_config`, `update_proxy_config`
- **Use cases**: AI services, SMTP, LDAP, SAML, proxy configuration
</details>

### reporting_insights Toolset (13 Tools)

> All tools in this toolset are read-only for monitoring and reporting.

<details>
<summary><strong><code>data_tool</code></strong> - VDB/VDB Group/dSources read-only (9 actions)</summary>

- **Actions**: `search_vdbs`, `get_vdb`, `list_vdb_snapshots`, `search_vdb_groups`, `get_vdb_group`, `list_vdb_group_bookmarks`, `search_dsources`, `get_dsource`, `list_dsource_snapshots`
- **Use cases**: Data asset inventory and monitoring
</details>

<details>
<summary><strong><code>snapshot_bookmark_tool</code></strong> - Snapshots and Bookmarks read-only (7 actions)</summary>

- **Actions**: `search_snapshots`, `get_snapshot`, `get_snapshot_capacity`, `get_snapshot_timeflow_range`, `search_bookmarks`, `get_bookmark`, `get_bookmark_vdb_groups`
- **Use cases**: Snapshot and bookmark reporting
</details>

<details>
<summary><strong><code>instance_tool</code></strong> - CDB/vCDB read-only (4 actions)</summary>

- **Actions**: `search_cdbs`, `get_cdb`, `search_vcdbs`, `get_vcdb`
- **Use cases**: Oracle container database inventory
</details>

<details>
<summary><strong><code>database_template_tool</code></strong> - VDB Templates read-only (2 actions)</summary>

- **Actions**: `search`, `get`
- **Use cases**: Template inventory
</details>

<details>
<summary><strong><code>hook_template_tool</code></strong> - Hook Templates read-only (2 actions)</summary>

- **Actions**: `search`, `get`
- **Use cases**: Hook template inventory
</details>

<details>
<summary><strong><code>virtualization_policy_tool</code></strong> - Policies read-only (2 actions)</summary>

- **Actions**: `search`, `get`
- **Use cases**: Policy inventory
</details>

<details>
<summary><strong><code>job_tool</code></strong> - Jobs read-only (3 actions)</summary>

- **Actions**: `search`, `get`, `get_result`
- **Use cases**: Job monitoring and result analysis
</details>

<details>
<summary><strong><code>engine_tool</code></strong> - Engines read-only (2 actions)</summary>

- **Actions**: `search`, `get`
- **Use cases**: Engine inventory and monitoring
</details>

<details>
<summary><strong><code>environment_tool</code></strong> - Environments read-only (4 actions)</summary>

- **Actions**: `search`, `get`, `list_hosts`, `list_listeners`
- **Use cases**: Environment inventory
</details>

<details>
<summary><strong><code>source_tool</code></strong> - Sources read-only (2 actions)</summary>

- **Actions**: `search`, `get`
- **Use cases**: Source inventory
</details>

<details>
<summary><strong><code>reporting_tool</code></strong> - Reports and Analytics (13 actions)</summary>

- **Actions**: `search_storage_savings_report`, `get_storage_capacity_report`, `get_virtualization_storage_summary`, `get_vdb_inventory_report`, `search_vdb_inventory_report`, `get_dsource_consumption_report`, `get_engine_performance_report`, `get_dataset_performance_analytics`, `get_api_usage_report`, `get_audit_logs_summary_report`, `search_scheduled_reports`, `get_scheduled_report`, `get_license`
- **Use cases**: Comprehensive reporting and analytics
</details>

<details>
<summary><strong><code>data_connection_tool</code></strong> - Connections read-only (2 actions)</summary>

- **Actions**: `search`, `get`
- **Use cases**: Connection inventory
</details>

<details>
<summary><strong><code>tag_tool</code></strong> - Tags read-only (3 actions)</summary>

- **Actions**: `search`, `get`, `get_usages`
- **Use cases**: Tag inventory and usage tracking
</details>

### Legacy Tool Reference

The following documents the individual endpoint tools (used in older versions):

#### Dataset Management Tools

<details>
<summary><strong><code>search_bookmarks</code></strong> - Search for bookmarks and point-in-time markers</summary>

- **Purpose**: Find bookmarks across datasets for point-in-time operations
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Bookmark discovery, point-in-time recovery, timeline navigation
</details>

<details>
<summary><strong><code>search_data_connections</code></strong> - Find and filter database connections</summary>

- **Purpose**: Discover database connections by platform, status, and capabilities
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Connection discovery, status monitoring, platform inventory
</details>

<details>
<summary><strong><code>search_dsources</code></strong> - Search for dSource objects (linked data sources)</summary>

- **Purpose**: Find linked data sources with filtering and pagination
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Data source management, capacity planning, source discovery
</details>

<details>
<summary><strong><code>search_snapshots</code></strong> - Locate specific snapshots across datasets</summary>

- **Purpose**: Find snapshots with time-based filtering
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Point-in-time recovery, backup verification, timeline analysis
</details>

<details>
<summary><strong><code>search_sources</code></strong> - Find source database objects and their configurations</summary>

- **Purpose**: Discover source databases and their settings
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Source inventory, configuration review, compliance checking
</details>

<details>
<summary><strong><code>search_timeflows</code></strong> - Search timeline flows for data history</summary>

- **Purpose**: Find timeline flows and recovery points
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Data lineage, recovery planning, timeline management
</details>

<details>
<summary><strong><code>search_vdb_groups</code></strong> - Locate virtual database groups</summary>

- **Purpose**: Find VDB groups and their member databases
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Group management, resource organization, bulk operations
</details>

<details>
<summary><strong><code>search_vdbs</code></strong> - Search virtual databases</summary>

- **Purpose**: Find virtual databases with status and environment filtering
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: VDB inventory, environment management, status monitoring
</details>

### Environment Management Tools

<details>
<summary><strong><code>search_environments</code></strong> - Find database environments</summary>

- **Purpose**: Discover environments by type, status, and configuration
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Environment discovery, capacity planning, status monitoring
</details>

### Engine Administration Tools

<details>
<summary><strong><code>search_engines</code></strong> - Locate Delphix engines</summary>

- **Purpose**: Find engines and check their operational status
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Engine monitoring, capacity management, health checking
</details>

### Compliance & Security Tools

<details>
<summary><strong><code>search_connectors</code></strong> - Find compliance connectors</summary>

- **Purpose**: Discover connectors for data governance workflows
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Compliance management, connector inventory, governance tracking
</details>

<details>
<summary><strong><code>search_executions</code></strong> - Search compliance execution history</summary>

- **Purpose**: Find compliance execution history and audit trails
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Audit trail analysis, compliance reporting, execution monitoring
</details>

### Job Monitoring Tools

<details>
<summary><strong><code>search_jobs</code></strong> - Search job execution history</summary>

- **Purpose**: Find jobs with status filtering and error details
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Job monitoring, error analysis, performance tracking
</details>

### Reporting & Analytics Tools

<details>
<summary><strong><code>search_storage_capacity_data</code></strong> - Get storage capacity metrics</summary>

- **Purpose**: Retrieve storage capacity and utilization data
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Capacity planning, storage optimization, usage reporting
</details>

<details>
<summary><strong><code>search_storage_savings_summary_report</code></strong> - Generate storage efficiency reports</summary>

- **Purpose**: Create storage efficiency and compression reports
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: Cost analysis, efficiency reporting, savings tracking
</details>

<details>
<summary><strong><code>search_virtualization_storage_summary_report</code></strong> - Create virtualization impact reports</summary>

- **Purpose**: Generate virtualization impact and savings reports
- **Parameters**: `filter_expression`, `limit`, `cursor`, `sort`
- **Use cases**: ROI analysis, virtualization benefits, impact assessment
</details>

### Common Tool Features

All tools support:
- **Advanced Filtering**: Complex filter expressions using comparison operators (EQ, NE, GT, LT, CONTAINS, IN) and logical operators (AND, OR, NOT)
- **Flexible Pagination**: Control result sets with `limit` and `cursor` parameters
- **Smart Sorting**: Sort results by any available field in ascending or descending order
- **Comprehensive Search**: Use the SEARCH operator to find items across multiple attributes
- **Error Handling**: Detailed error responses with actionable troubleshooting information

### Filter Expression Examples

```bash
# Find active Oracle databases
"filter_expression": "platform EQ 'oracle' AND status EQ 'ACTIVE'"

# Search for large datasets (> 100GB)
"filter_expression": "size GT 107374182400"

# Find resources with specific tags
"filter_expression": "tags CONTAINS 'production'"

# Complex logical expressions
"filter_expression": "NOT (status EQ 'INACTIVE') AND (platform IN ['oracle', 'postgresql'])"
```

## Privacy & Telemetry

When `IS_LOCAL_TELEMETRY_ENABLED` is set to `true`, the server collects anonymous usage analytics to improve functionality and user experience.

### What Data is Collected

- **Tool execution details**: Tool name, execution status (success or failure), and session duration
- **User identifier**: Operating system username (via `getpass.getuser()`) for usage analysis
- **Error context**: Anonymized error types and frequencies (no sensitive data)
- **Performance metrics**: Execution times and resource usage

### What is NOT Collected

- **Sensitive data**: No API keys, database content, or business data
- **Personal information**: No personally identifiable information beyond OS username
- **DCT data**: No data returned from DCT API calls
- **Network details**: No IP addresses or network configurations

### Data Storage & Privacy

- **Local only**: Telemetry data is stored in the `logs/sessions/` directory
- **No remote transmission**: Data never leaves your machine
- **User control**: Disable telemetry by setting `IS_LOCAL_TELEMETRY_ENABLED="false"`
- **Readable format**: Logs use human-readable JSON

### Sample Telemetry Entry

```json
{
  "session_id": "abc123",
  "timestamp": "2025-12-05T10:30:00Z",
  "user": "developer",
  "tool": "get_datasets",
  "status": "success",
  "duration_ms": 245,
  "args_count": 3
}
```

## Troubleshooting

### Common Issues

**Connection Errors**
```bash
# Check DCT connectivity
curl -k -H "Authorization: Bearer $DCT_API_KEY" "$DCT_BASE_URL/v1/about"

# Verify SSL settings
export DCT_VERIFY_SSL="false"  # For self-signed certificates
```

**Authentication Failures**
```bash
# Verify API key is set
echo $DCT_API_KEY  # Should be your DCT API key (do NOT add 'apk' prefix)

# Check API key permissions in DCT admin console
```

**Tool Generation Issues**
```bash
# Enable debug logging
export DCT_LOG_LEVEL="DEBUG"

# Check DCT API accessibility
curl -k "$DCT_BASE_URL/v1/about"
```

**MCP Client Connection Issues**
```bash
# Test server startup
./start_mcp_server_python.sh

# Verify Python path
export PYTHONPATH=src
python -c "import dct_mcp_server; print('Import successful')"
```

### Debug Mode

Enable comprehensive debugging:

```bash
export DCT_LOG_LEVEL="DEBUG"
export IS_LOCAL_TELEMETRY_ENABLED="true"
./start_mcp_server_python.sh 2>&1 | tee debug.log
```

### Log Analysis

By default, all log files are generated in a `logs` directory. The location depends on how the server is started:

- **Local development**: When you run the server from the cloned source code, the `logs` directory is created at the root of the project.
- **Client application**: When an MCP client starts the server, the `logs` directory is typically created at the root of the workspace or project folder you have open in that client.

Check these logs for issues:

```bash
# Main application logs
tail -f logs/dct_mcp_server.log

# Session telemetry
ls -la logs/sessions/

# Startup logs
cat logs/mcp_server_setup_logfile.txt
```

### "Server starting..." followed by "No such file or directory" or "command not found"

- **Cause**: This happens when the `command` path in your MCP client's JSON configuration is incorrect. The client optimistically reports that it is "starting" the server, but then the operating system immediately fails because it cannot find the script at the specified location.
- **Solution**: Ensure the `command` value is the **absolute path** to the correct startup script (e.g., `start_mcp_server_uv.sh` or `start_mcp_server_python.sh`). Verify that the file exists at that exact path and that it has execute permissions (`chmod +x <script_name>`).

## Project Structure

```
dxi-mcp-server/
├── README.md                   # This file
├── LICENSE.md                  # MIT license
├── pyproject.toml              # Python project configuration
├── requirements.txt            # Dependencies (legacy format)
├── uv.lock                     # Locked dependencies (uv format)
├── start_mcp_server_*.{sh,bat} # Cross-platform startup scripts
├── logs/                       # Runtime logs and telemetry
│   ├── dct_mcp_server.log      # Main application logs
│   └── sessions/               # Telemetry session logs
└── src/
    └── dct_mcp_server/
        ├── main.py             # Application entry point
        ├── config/
        │   ├── config.py       # Configuration management
        │   ├── loader.py       # Toolset configuration loader
        │   ├── toolsets/       # Toolset definitions
        │   │   ├── self_service.txt          # Default toolset (6 tools)
        │   │   ├── self_service_provision.txt
        │   │   ├── continuous_data_admin.txt
        │   │   ├── platform_admin.txt
        │   │   └── reporting_insights.txt
        │   └── mappings/       # Tool grouping & confirmation rules
        │       ├── tool_grouping.txt
        │       └── manual_confirmation.txt
        ├── core/
        │   ├── decorators.py   # Logging and telemetry decorators
        │   ├── exceptions.py   # Custom exception classes
        │   ├── logging.py      # Logging configuration
        │   └── session.py      # Session and telemetry management
        ├── dct_client/
        │   └── client.py       # DCT API HTTP client
        ├── tools/
        │   ├── core/           # Tool generation framework
        │   │   ├── meta_tools.py   # Auto mode meta-tools
        │   │   └── tool_factory.py # Dynamic tool generator
        │   ├── dataset_endpoints_tool.py   # Dataset endpoint tools
        │   └── job_endpoints_tool.py       # Job endpoint tools
        └── icons/
            └── logo-delphixmcp-reg.png
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Support & Contributing

### Getting Help

1. **Check the logs**: Review `logs/dct_mcp_server.log` for error details.
2. **Enable debug mode**: Set `DCT_LOG_LEVEL="DEBUG"` for verbose output.
3. **Search existing issues**: Check [GitHub Issues](https://github.com/delphix/dxi-mcp-server/issues) for similar problems.
4. **Create a new issue**: Provide DCT version, Python version, and error logs.

### Community Resources

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/delphix/dxi-mcp-server/issues)
- **Documentation**: Full documentation available in the [project wiki](https://github.com/delphix/dxi-mcp-server/wiki)
- **Community support**: ![Support](https://img.shields.io/badge/Support-Community-yellow.svg) - Community-driven support
- **Delphix DCT API documentation**: [Official API docs](https://help.delphix.com/dct/current/content/api_references.htm)

### Contributing

We welcome contributions! Please review our community documents:

- **[Community Guidelines](.github/COMMUNITY_GUIDELINES.md)**: An overview of how our community operates.
- **[Code of Conduct](.github/CODE_OF_CONDUCT.md)**: Our commitment to a respectful and inclusive environment.
- **[Contributing Guidelines](.github/CONTRIBUTING.md)**: The technical guide on how to contribute to this project.

When you are ready to submit a change, please use our [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).

---

*Enable your AI assistants to seamlessly manage your data infrastructure with Delphix DCT.*
