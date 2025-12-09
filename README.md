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
- [Installation](#installation)
- [Configuration](#configuration)
- [MCP Client Configuration](#mcp-client-configuration)
- [Available Tools](#available-tools)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Privacy & Telemetry](#privacy--telemetry)
- [Troubleshooting](#troubleshooting)
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

## Installation

<details><summary><b>Development Installation</b></summary>

For development or customization:

```bash
# Clone the repository
git clone https://github.com/delphix/dxi-mcp-server.git
cd dxi-mcp-server

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with uv (recommended for faster, deterministic builds)
pip install uv
uv sync

# Or install with pip (development mode)
pip install -e .
```

</details>

<details><summary><b>Production Installation</b></summary>

For production deployments:

```bash
# Install from GitHub release
pip install git+https://github.com/delphix/dxi-mcp-server.git

# Verify installation
dct-mcp-server --help
```

</details>

<details><summary><b>Using Cross-Platform Scripts</b></summary>

The project includes ready-to-use startup scripts for all platforms:

```bash
# Clone the repository first
git clone https://github.com/delphix/dxi-mcp-server.git
cd dxi-mcp-server

# Unix/Linux/macOS users:
chmod +x start_mcp_server_python.sh
./start_mcp_server_python.sh

# Or with uv:
chmod +x start_mcp_server_uv.sh
./start_mcp_server_uv.sh

# Windows users:
start_mcp_server_windows_python.bat

# Or with uv:
start_mcp_server_windows_uv.bat
```

These scripts automatically handle environment setup and dependencies.

</details>

<details><summary><b>Container Installation</b></summary>

Using Docker for isolated deployment:

```bash
# Build the container
git clone https://github.com/delphix/dxi-mcp-server.git
cd dxi-mcp-server
docker build -t dxi-mcp-server .

# Run with environment variables
docker run -e DCT_API_KEY="your-key" -e DCT_BASE_URL="https://your-dct-host.com" dxi-mcp-server
```

</details>

## Configuration

### Environment Variables

Set up your environment variables. Create a `.env` file in the project root:

```bash
# Required Configuration
DCT_API_KEY="apk1.your-api-key-here"
DCT_BASE_URL="https://your-dct-host.company.com"

# Optional Configuration
DCT_VERIFY_SSL="true"
DCT_LOG_LEVEL="INFO"
DCT_TIMEOUT="30"
DCT_MAX_RETRIES="3"
IS_LOCAL_TELEMETRY_ENABLED="false"
```

### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `DCT_API_KEY` | Your Delphix DCT API key | `apk1.a1b2c3d4e5f6...` |
| `DCT_BASE_URL` | DCT instance base URL | `https://dct.company.com` |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DCT_VERIFY_SSL` | `false` | Enable SSL certificate verification |
| `DCT_TIMEOUT` | `30` | Request timeout in seconds |
| `DCT_MAX_RETRIES` | `3` | Maximum retry attempts for failed requests |
| `DCT_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `IS_LOCAL_TELEMETRY_ENABLED` | `false` | Enable anonymous usage tracking |

### Starting the Server

Start the MCP server using the provided script:

```bash
./start_mcp_server_python.sh
```

The server will automatically:
- Load and validate the DCT API configuration
- Initialize tools for all available API endpoints
- Start the MCP server on stdio transport
- Log startup information and available tools

## MCP Client Configuration

> **Note:** Use absolute paths for the `command` field in all configurations. Ensure environment variables are properly set for each host. Different hosts may have different argument parsing. Refer to the host's documentation.

### Environment Variables

All configurations support these environment variables:
- `DCT_API_KEY` - Your Delphix DCT API key (required)
- `DCT_BASE_URL` - Your DCT instance URL (required)  
- `DCT_VERIFY_SSL` - Enable SSL verification (`true`/`false`, default: `false`)
- `DCT_LOG_LEVEL` - Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `DCT_TIMEOUT` - Request timeout in seconds (default: `30`)
- `DCT_MAX_RETRIES` - Maximum retry attempts (default: `3`)
- `IS_LOCAL_TELEMETRY_ENABLED` - Enable telemetry (`true`/`false`, default: `false`)

<details>
<summary><strong>Claude Desktop</strong></summary>

Configure in your Claude Desktop settings (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

**Option 1: Using uvx (Recommended)**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
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
        "DCT_API_KEY": "apk1.your-api-key-here",
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

Add to your Cursor settings (`~/.cursor/settings.json`):

**Option 1: Using uvx (Recommended)**
```json
{
  "mcpServers": [
    {
      "name": "delphix-dct", 
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
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
        "DCT_API_KEY": "apk1.your-api-key-here",
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
<summary><strong>VS Code with Continue</strong></summary>

Configure in your Continue extension settings:

**Option 1: Using uvx (Recommended)**
```json
{
  "mcpServers": [
    {
      "name": "delphix-dct",
      "command": "uvx", 
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  ]
}
```

</details>

<details>
<summary><strong>Eclipse</strong></summary>

Configure in your Eclipse MCP settings:

**Option 1: Using uvx (Recommended)**
```json
{
  "servers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
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
        "DCT_API_KEY": "apk1.your-api-key-here",
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
```json
{
  "servers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true",
        "DCT_TIMEOUT": "60"
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
        "DCT_API_KEY": "apk1.your-api-key-here",
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
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
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
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

**Option 3: Using shell scripts**
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "/absolute/path/to/dxi-mcp-server/start_mcp_server_uv.sh",
      "env": {
        "DCT_API_KEY": "apk1.your-api-key-here",
        "DCT_BASE_URL": "https://your-dct-host.company.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Generic MCP Client</strong></summary>

For any MCP-compatible client, you can use:

```bash
# Run from Git repository with uvx
uvx --from git+https://github.com/delphix/dxi-mcp-server.git dct-mcp-server

# Run locally installed version
/absolute/path/to/dxi-mcp-server/start_mcp_server_python.sh

# Run with custom Python path
PYTHONPATH=/absolute/path/to/dxi-mcp-server/src python -m dct_mcp_server.main
```

**For private repositories:** Use SSH authentication: `git+ssh://git@github.com/delphix/dxi-mcp-server.git`

</details>

### Configuration Examples

<details>
<summary><strong>Development Environment</strong></summary>

```json
{
  "env": {
    "DCT_API_KEY": "apk1.your-development-key",
    "DCT_BASE_URL": "https://dct-dev.company.com",
    "DCT_VERIFY_SSL": "false",
    "DCT_LOG_LEVEL": "DEBUG",
    "DCT_TIMEOUT": "30",
    "IS_LOCAL_TELEMETRY_ENABLED": "true"
  }
}
```

</details>

<details>
<summary><strong>Production Environment</strong></summary>

```json
{
  "env": {
    "DCT_API_KEY": "apk1.your-production-key",
    "DCT_BASE_URL": "https://dct-prod.company.com",
    "DCT_VERIFY_SSL": "true",
    "DCT_LOG_LEVEL": "INFO",
    "DCT_TIMEOUT": "60",
    "DCT_MAX_RETRIES": "5"
  }
}
```

</details>

<details>
<summary><strong>Testing Environment</strong></summary>

```json
{
  "env": {
    "DCT_API_KEY": "apk1.your-test-key", 
    "DCT_BASE_URL": "https://dct-test.company.com",
    "DCT_VERIFY_SSL": "false",
    "DCT_LOG_LEVEL": "WARNING",
    "DCT_TIMEOUT": "45"
  }
}
```

</details>

### Required Configurations

- Use absolute paths for the `command` field in all configurations
- Ensure environment variables are properly set for each host
- Different hosts may have different argument parsing - refer to the host's documentation

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
# Verify API key format
echo $DCT_API_KEY  # Should start with 'apk1.'

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

Check logs for issues:

```bash
# Main application logs
tail -f logs/dct_mcp_server.log

# Session telemetry
ls -la logs/sessions/

# Startup logs
cat logs/mcp_server_setup_logfile.txt
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Support & Community

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/delphix/dxi-mcp-server/issues)
- **Discussions**: Join the conversation in [GitHub Discussions](https://github.com/delphix/dxi-mcp-server/discussions)  
- **Documentation**: Full documentation available in the [project wiki](https://github.com/delphix/dxi-mcp-server/wiki)
- **Community Support**: ![Support](https://img.shields.io/badge/Support-Community-yellow.svg) - Community-driven support

### Getting Help

1. **Check the logs**: Review `logs/dct_mcp_server.log` for error details
2. **Enable debug mode**: Set `DCT_LOG_LEVEL="DEBUG"` for verbose output
3. **Search existing issues**: Check [GitHub Issues](https://github.com/delphix/dxi-mcp-server/issues) for similar problems
4. **Create a new issue**: Provide DCT version, Python version, and complete error logs

### Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Code of Conduct**: Be respectful and inclusive in all interactions
2. **Issue First**: For significant changes, create an issue to discuss the approach
3. **Development Setup**: Follow the development setup in the [Development](#development) section
4. **Testing**: Ensure all tests pass and add tests for new functionality
5. **Documentation**: Update README for changes

---

*Enable your AI assistants to seamlessly manage your data infrastructure with Delphix DCT.*

For issues and questions:
- Check the [Delphix DCT API documentation](https://docs.delphix.com/)
- Open an issue in this repository