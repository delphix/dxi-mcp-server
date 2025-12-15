![Support](https://img.shields.io/badge/Support-Community-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

<div style="text-align: right; width: 100%;">
  <img src="src/dct_mcp_server/icons/logo-delphixmcp-reg.png" alt="Perforce Delphix Logo" width="200" />
</div>

# Delphix DCT API MCP Server

A comprehensive Model Context Protocol (MCP) server for interacting with the Delphix Data Control Tower (DCT) API. This server provides AI assistants with structured access to Delphix's data management capabilities through a robust tool interface.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [MCP Client Configuration](#mcp-client-configuration)
- [Installation](#installation)
- [Available Tools](#available-tools)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Privacy & Telemetry](#privacy--telemetry)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

- **Comprehensive DCT integration**: Specialized tools across datasets, environments, engines, compliance, jobs, and reporting
- **Safety first**: Robust API client with retry logic, exponential backoff, and SSL configuration  
- **Flexible configuration**: Environment-based setup with comprehensive validation
- **Cross-platform support**: Ready-to-use startup scripts for Windows, macOS, and Linux
- **Optional telemetry**: Consent-gated usage analytics. Disabled by default.
- **Structured logging**: Application and session logging with telemetry tracking

## Prerequisites

- **Python 3.11+**: Required for modern async features and type hints
- **Delphix DCT Instance**: Access to a running Delphix Data Control Tower
- **API Key**: Valid DCT API key with read-only permissions
- **Network Access**: Connectivity to your DCT instance

## MCP Client Configuration

> **Note:** Use absolute paths for the `command` field in all configurations. Ensure the correct environment variables are provided for each client application, as the server process relies on them. Different client applications may have different argument parsing. Refer to the client application's documentation.

### Environment Variables

All configurations support these environment variables:
- `DCT_API_KEY` - Your Delphix DCT API key (required)
  > **⚠️ Important**: Do NOT prefix your API key with `apk.` - use the key exactly as provided by DCT
- `DCT_BASE_URL` - Your DCT instance URL (required)  
- `DCT_VERIFY_SSL` - Enable SSL verification (`true`/`false`, default: `false`)
- `DCT_LOG_LEVEL` - Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `DCT_TIMEOUT` - Request timeout in seconds (default: `30`)
- `DCT_MAX_RETRIES` - Maximum retry attempts (default: `3`)
- `IS_LOCAL_TELEMETRY_ENABLED` - Enable telemetry (`true`/`false`, default: `false`)

<details>
<summary><strong>Claude Desktop</strong></summary>

Configure in your Claude Desktop settings file:

**Option 1: Using uvx (Recommended)**
> **Note**: This option requires [uv](https://github.com/astral-sh/uv) to be installed on your system.
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
        "DCT_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

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
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

**Option 3: Using shell/batch scripts**
> **Note**: The `command` path should point to the startup script that matches your system. Scripts are provided for different platforms (`.sh` for Linux/macOS, `.bat` for Windows). If you choose a `_uv` script (e.g., `start_mcp_server_uv.sh`), you must have [uv](https://github.com/astral-sh/uv) installed.
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Cursor IDE</strong></summary>

Add to your Cursor settings:

**Option 1: Using uvx (Recommended)**
> **Note**: This option requires [uv](https://github.com/astral-sh/uv) to be installed on your system.
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
        "DCT_LOG_LEVEL": "INFO"
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
        "DCT_VERIFY_SSL": "true"
      }
    }
  ]
}
```

**Option 3: Using shell scripts**
> **Note**: The `command` path should point to the startup script that matches your system. Scripts are provided for different platforms (`.sh` for Linux/macOS, `.bat` for Windows). If you choose a `_uv` script (e.g., `start_mcp_server_uv.sh`), you must have [uv](https://github.com/astral-sh/uv) installed.
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
        "DCT_LOG_LEVEL": "INFO"
      }
    }
  ]
}
```

</details>

<details>
<summary><strong>VS Code</strong></summary>

Configure in your VS Code settings:

**Option 1: Using uvx (Recommended)**
> **Note**: This option requires [uv](https://github.com/astral-sh/uv) to be installed on your system.
```json
{
  "servers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
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
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

**Option 3: Using shell scripts**
> **Note**: The `command` path should point to the startup script that matches your system. Scripts are provided for different platforms (`.sh` for Linux/macOS, `.bat` for Windows). If you choose a `_uv` script (e.g., `start_mcp_server_uv.sh`), you must have [uv](https://github.com/astral-sh/uv) installed.
```json
{
  "servers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Eclipse</strong></summary>

Configure in your Eclipse MCP settings:

**Option 1: Using uvx (Recommended)**
> **Note**: This option requires [uv](https://github.com/astral-sh/uv) to be installed on your system.
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
        "DCT_LOG_LEVEL": "INFO"
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
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

**Option 3: Using shell scripts**
> **Note**: The `command` path should point to the startup script that matches your system. Scripts are provided for different platforms (`.sh` for Linux/macOS, `.bat` for Windows). If you choose a `_uv` script (e.g., `start_mcp_server_uv.sh`), you must have [uv](https://github.com/astral-sh/uv) installed.
```json
{
  "servers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>IntelliJ IDEA</strong></summary>

Configure in your IntelliJ MCP settings:

**Option 1: Using uvx (Recommended)**
> **Note**: This option requires [uv](https://github.com/astral-sh/uv) to be installed on your system.
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
        "DCT_LOG_LEVEL": "DEBUG",
        "DCT_TIMEOUT": "60"
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
        "DCT_TIMEOUT": "60"
      }
    }
  }
}
```

**Option 3: Using shell scripts**
> **Note**: The `command` path should point to the startup script that matches your system. Scripts are provided for different platforms (`.sh` for Linux/macOS, `.bat` for Windows). If you choose a `_uv` script (e.g., `start_mcp_server_uv.sh`), you must have [uv](https://github.com/astral-sh/uv) installed.
```json
{
  "servers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_LOG_LEVEL": "DEBUG",
        "DCT_TIMEOUT": "60"
      }
    }
  }
}
```

</details>
<details>
<summary><strong>Windsurf</strong></summary>

Configure in your Windsurf MCP settings:

**Option 1: Using uvx (Recommended)**
> **Note**: This option requires [uv](https://github.com/astral-sh/uv) to be installed on your system.
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

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
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

**Option 3: Using shell scripts**
> **Note**: The `command` path should point to the startup script that matches your system. Scripts are provided for different platforms (`.sh` for Linux/macOS, `.bat` for Windows). If you choose a `_uv` script (e.g., `start_mcp_server_uv.sh`), you must have [uv](https://github.com/astral-sh/uv) installed.
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

</details>



## Installation

This section is for users who want to run the server as a standalone command-line tool or contribute to its development. If you only plan to use this server within a specific client application, the `uvx` method in the [MCP Client Configuration](#mcp-client-configuration) section is recommended and does not require a separate installation.

The server is configured by setting environment variables. Below are examples for setting these variables on different platforms.

> **⚠️ Important**: Do NOT prefix your API key with `apk.` - use the key exactly as provided by DCT

<details>
<summary><strong>Command-Line (Linux/macOS)</strong></summary>

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
<summary><strong>Command-Line (Windows)</strong></summary>

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

Choose the installation method that best suits your needs.

### Quick Start: As a Command-Line Tool

This is the recommended method for users who want to use the server without modifying its code.

**Prerequisites**:
- Python 3.11+
- `pip` and `git` installed on your system.
- Your DCT API Key and DCT Base URL must be provided as environment variables. See the command-line examples in the [Installation](#installation) section for details.

Install the server directly from GitHub using `pip`:
```bash
pip install git+https://github.com/delphix/dxi-mcp-server.git

# Verify the installation
dct-mcp-server --help
```
This makes the `dct-mcp-server` command available globally in your environment.


### For Developers: Local Setup from Source

This method is for developers who want to modify the code or run it from a local clone.

**Prerequisites**:
- Python 3.11+
- `git` installed on your system.
- Your DCT API Key and DCT Base URL must be provided as environment variables. See the command-line examples in the [Installation](#installation) section for details.


**Steps**:
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/delphix/dxi-mcp-server.git
    cd dxi-mcp-server
    ```

2.  **Set up the environment and install dependencies:**
    The included scripts handle environment setup automatically. We recommend using `uv` for the best performance. On macOS or Linux, run:
    ```bash
    chmod +x start_mcp_server_uv.sh
    ./start_mcp_server_uv.sh
    ```
    > **Note**: Other startup scripts are available. For Windows, use `start_mcp_server_windows_uv.bat`. If you prefer not to use `uv`, scripts for standard Python with `venv` are also provided (`start_mcp_server_python.sh` and `start_mcp_server_windows_python.bat`).

### Connecting a Client to a Running Server

Once the server is running (either via the command-line tool or from the source), it will print the port it is listening on to the console (e.g., `INFO:     Uvicorn running on http://127.0.0.1:6790 (Press CTRL+C to quit)`). To connect your client, you only need to specify this port number. You do not need to provide environment variables in the client configuration, as the server already has them from your terminal session.

**Example for Claude Desktop:**
Configure your Claude Desktop settings to connect to the running server by specifying the port.

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



## Available Tools

The server provides specialized tools for interacting with different aspects of the Delphix DCT API:

### Dataset Management Tools

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

## Usage Examples

### Project Structure

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
        │   └── config.py       # Configuration management
        ├── core/
        │   ├── decorators.py   # Logging and telemetry decorators
        │   ├── exceptions.py   # Custom exception classes
        │   ├── logging.py      # Logging configuration
        │   └── session.py      # Session and telemetry management
        ├── dct_client/
        │   └── client.py       # DCT API HTTP client
        ├── tools/              # MCP tools for DCT endpoints
        │   ├── dataset_endpoints_tool.py
        │   ├── environment_endpoints_tool.py
        │   ├── engine_endpoints_tool.py
        │   ├── compliance_endpoints_tool.py
        │   ├── job_endpoints_tool.py
        │   └── reports_endpoints_tool.py
        └── icons/
            └── logo-delphixmcp-reg.png
```

## Privacy & Telemetry

When `IS_LOCAL_TELEMETRY_ENABLED` is set to `true`, the server collects anonymous usage analytics to help improve functionality and user experience.

### What Data is Collected

- **Tool Execution Metadata**: Tool name, execution status (success/failure), and session duration
- **User Identification**: Operating system username (via `getpass.getuser()`) for usage pattern analysis
- **Error Context**: Anonymized error types and frequencies (no sensitive data)
- **Performance Metrics**: Tool execution times and system resource usage

### What is NOT Collected

- **Sensitive Data**: No API keys, database content, or business data
- **Personal Information**: No personally identifiable information beyond OS username
- **DCT Data**: No data returned from DCT API calls
- **Network Information**: No IP addresses or network configurations

### Data Storage & Privacy

- **Local Storage Only**: All telemetry data is stored locally in `logs/sessions/` directory
- **No Remote Transmission**: Data never leaves your local machine
- **User Control**: Easily disabled by setting `IS_LOCAL_TELEMETRY_ENABLED="false"`
- **Transparent Format**: Log files use human-readable JSON format

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

**Connection Errors**:
```bash
# Check DCT connectivity
curl -k -H "Authorization: Bearer $DCT_API_KEY" "$DCT_BASE_URL/v1/about"

# Verify SSL settings
export DCT_VERIFY_SSL="false"  # For self-signed certificates
```

**Authentication Failures**:
```bash
# Verify API key is set
echo $DCT_API_KEY  # Should be your DCT API key (do NOT add 'apk.' prefix)

# Check API key permissions in DCT admin console
```

**Tool Generation Issues**:
```bash
# Enable debug logging
export DCT_LOG_LEVEL="DEBUG"

# Check DCT API accessibility
curl -k "$DCT_BASE_URL/v1/about"
```

**MCP Client Connection Issues**:
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

- **Local Development**: When you run the server from the cloned source code, the `logs` directory is created at the root of the project.
- **Client Application**: When an MCP client starts the server, the `logs` directory is typically created at the root of the workspace or project folder you have open in that client.

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

-   **Cause:** This happens when the `command` path in your MCP client's JSON configuration is incorrect. The client optimistically reports that it is "starting" the server, but then the operating system immediately fails because it cannot find the script at the specified location.
-   **Solution:** Ensure the `command` value is the **absolute path** to the correct startup script (e.g., `start_mcp_server_uv.sh` or `start_mcp_server_python.sh`). Verify that the file exists at that exact path and that it has execute permissions (`chmod +x <script_name>`).

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Support & Community

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/delphix/dxi-mcp-server/issues)
- **Documentation**: Full documentation available in the [project wiki](https://github.com/delphix/dxi-mcp-server/wiki)
- **Community Support**: ![Support](https://img.shields.io/badge/Support-Community-yellow.svg) - Community-driven support

### Getting Help

1. **Check the logs**: Review `logs/dct_mcp_server.log` for error details
2. **Enable debug mode**: Set `DCT_LOG_LEVEL="DEBUG"` for verbose output
3. **Search existing issues**: Check [GitHub Issues](https://github.com/delphix/dxi-mcp-server/issues) for similar problems
4. **Create a new issue**: Provide DCT version, Python version, and complete error logs

### Contributing

We welcome contributions from the community! Before you start, please take a moment to review our community documents:

- **[Community Guidelines](.github/COMMUNITY_GUIDELINES.md)**: An overview of how our community operates.
- **[Code of Conduct](.github/CODE_OF_CONDUCT.md)**: Our commitment to a respectful and inclusive environment.
- **[Contributing Guidelines](.github/CONTRIBUTING.md)**: The technical guide on how to contribute to this project.

When you are ready to submit a change, please use our [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).

---

*Enable your AI assistants to seamlessly manage your data infrastructure with Delphix DCT.*

For issues and questions:
- Check the [Delphix DCT API documentation](https://help.delphix.com/dct/current/content/home.htm)
- Open an issue in this repository