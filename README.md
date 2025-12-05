![Support](https://img.shields.io/badge/Support-Community-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

<div style="text-align: right; width: 100%;">
  <img src="src/dct_mcp_server/icons/logo-delphixmcp-reg.png" alt="Perforce Delphix Logo" width="200" />
</div>

# Delphix DCT API MCP Server

A comprehensive Model Context Protocol (MCP) server for interacting with the Delphix Data Control Tower (DCT) API. This server provides AI assistants with structured access to Delphix's data management capabilities through a robust, auto-generated tool interface.

## Overview

The Delphix DCT MCP Server bridges AI assistants with Delphix's Data Control Tower, enabling natural language interactions with your data infrastructure. The server provides tools that offer access to datasets, environments, engines, compliance, jobs, and reporting capabilities.

## Features

- **🔧 Comprehensive Tools**: MCP tools providing access to DCT endpoints across 6 main categories:
  - **Dataset Operations**: Manage data sources, snapshots, and refreshes
  - **Environment Management**: Configure and monitor database environments
  - **Engine Administration**: Control Delphix engines and their resources
  - **Compliance & Security**: Handle data governance and compliance workflows
  - **Job Monitoring**: Track and manage data operations and workflows
  - **Reporting & Analytics**: Access operational reports and metrics
- **🔒 Robust API Client**: Asynchronous HTTP client with retry logic, exponential backoff, and SSL configuration
- **⚙️ Flexible Configuration**: Environment-based configuration with comprehensive validation
- **📝 Structured Logging**: Configurable logging with session tracking and telemetry
- **🛡️ Error Handling**: Clear exception hierarchy with detailed error context
- **🔄 Graceful Operations**: Clean startup/shutdown with proper resource management
- **📈 Optional Telemetry**: Local, anonymous usage tracking for improvement insights

## Prerequisites

- **Python 3.11+**: Required for modern async features and type hints
- **Delphix DCT Instance**: Access to a running Delphix Data Control Tower
- **API Key**: Valid DCT API key with appropriate permissions
- **Network Access**: Connectivity to your DCT instance (typically port 8083)

## Quick Start

### 1. Installation

Clone and install the server:

```bash
# Clone the repository
git clone https://github.com/delphix/dxi-mcp-server.git
cd dxi-mcp-server

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with pip (development mode)
pip install -e .

# Or install with uv (recommended for faster, deterministic builds)
pip install uv
uv sync
```

### 2. Configuration

Set up your environment variables. Create a `.env` file in the project root:

```bash
# Required Configuration
DCT_API_KEY="apk1.your-api-key-here"
DCT_BASE_URL="https://your-dct-host.company.com:8083"

# Optional Configuration
DCT_VERIFY_SSL="true"
DCT_LOG_LEVEL="INFO"
DCT_TIMEOUT="30"
DCT_MAX_RETRIES="3"
IS_LOCAL_TELEMETRY_ENABLED="false"
```

### 3. Run the Server

Start the MCP server using the provided script:

```bash
./start_mcp_server_python.sh
```

The server will automatically:
- Load and validate the DCT API configuration
- Initialize tools for all available API endpoints
- Start the MCP server on stdio transport
- Log startup information and available tools

## Architecture

### Tool Organization

The server organizes DCT API endpoints into logical tool categories:

| Tool Category | Description | Example Operations |
|---------------|-------------|-------------------|
| **Dataset Tools** | Manage data sources and snapshots | Create snapshots, refresh datasets, manage data sources |
| **Environment Tools** | Database environment operations | Configure environments, manage connections, monitor health |
| **Engine Tools** | Delphix engine administration | Engine status, resource management, system configuration |
| **Compliance Tools** | Data governance and security | Policy enforcement, audit trails, compliance reporting |
| **Job Tools** | Operation monitoring and control | Job status, execution history, workflow management |
| **Reports Tools** | Analytics and operational insights | Performance metrics, usage reports, system analytics |

### Tool Implementation

The server uses a well-structured tool system:

1. **API Integration**: Connects to DCT API endpoints using authenticated requests
2. **Tool Registration**: Registers available tools with the FastMCP framework
3. **Parameter Validation**: Validates tool parameters before API calls
4. **Error Handling**: Provides clear error messages and proper exception handling
5. **Logging & Telemetry**: Tracks tool usage and performance metrics

## Configuration Reference

The server uses environment variables for all configuration. All settings can be provided via system environment variables or a `.env` file in the project root.

### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `DCT_API_KEY` | Your Delphix DCT API key | `apk1.a1b2c3d4e5f6...` |
| `DCT_BASE_URL` | DCT instance base URL | `https://dct.company.com:8083` |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DCT_VERIFY_SSL` | `false` | Enable SSL certificate verification |
| `DCT_TIMEOUT` | `30` | Request timeout in seconds |
| `DCT_MAX_RETRIES` | `3` | Maximum retry attempts for failed requests |
| `DCT_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `IS_LOCAL_TELEMETRY_ENABLED` | `false` | Enable anonymous usage tracking |

### Configuration Examples

**Development Environment (`.env` file):**
```bash
DCT_API_KEY="apk1.your-development-key"
DCT_BASE_URL="https://dct-dev.company.com:8083"
DCT_VERIFY_SSL="false"
DCT_LOG_LEVEL="DEBUG"
IS_LOCAL_TELEMETRY_ENABLED="true"
```

**Production Environment (system variables):**
```bash
export DCT_API_KEY="apk1.your-production-key"
export DCT_BASE_URL="https://dct-prod.company.com:8083"
export DCT_VERIFY_SSL="true"
export DCT_LOG_LEVEL="INFO"
export DCT_TIMEOUT="60"
export DCT_MAX_RETRIES="5"
```

## Deployment Options

### Local Development

For local development and testing:

```bash
# Using the convenience script
./start_mcp_server_python.sh

# Or run directly with proper Python path
export PYTHONPATH=src
python -m dct_mcp_server.main

# Or use the installed console script
dct-mcp-server
```

### Container Deployment

Create a Dockerfile for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install .

ENV PYTHONPATH=/app/src
CMD ["dct-mcp-server"]
```

### Cross-Platform Scripts

The project includes platform-specific startup scripts:

- **Unix/Linux/macOS**: `start_mcp_server_python.sh`, `start_mcp_server_uv.sh`
- **Windows**: `start_mcp_server_windows_python.bat`, `start_mcp_server_windows_uv.bat`

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

## MCP Client Integration

The Delphix DCT MCP Server integrates with various AI assistants and development environments that support the Model Context Protocol.

### Claude Desktop

Configure in your Claude Desktop settings (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host.company.com:8083",
        "DCT_VERIFY_SSL": "true",
        "DCT_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Cursor IDE

Add to your Cursor settings (`~/.cursor/settings.json`):

```json
{
  "mcpServers": [
    {
      "name": "delphix-dct",
      "command": "/path/to/dxi-mcp-server/start_mcp_server_python.sh",
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host.company.com:8083",
        "DCT_VERIFY_SSL": "true"
      }
    }
  ]
}
```

### VS Code with Continue

Configure in your Continue extension settings:

```json
{
  "mcpServers": [
    {
      "name": "delphix-dct",
      "command": "dct-mcp-server",
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host.company.com:8083"
      }
    }
  ]
}
```

### Generic MCP Client

For any MCP-compatible client, you can use:

```bash
# Run from Git repository
uvx --from git+https://github.com/delphix/dxi-mcp-server.git dct-mcp-server

# Run locally installed version
dct-mcp-server

# Run with custom Python path
PYTHONPATH=src python -m dct_mcp_server.main
```

**Note**: For private repositories, use SSH authentication: `git+ssh://git@github.com/delphix/dxi-mcp-server.git`

## Usage Examples

### Basic Dataset Operations

```python
# AI Assistant interaction examples

# List all datasets
"Show me all datasets in my DCT environment"

# Get dataset details
"Get detailed information about the 'HR_Database' dataset"

# Create a snapshot
"Create a snapshot of the 'Production_DB' dataset with the name 'pre_upgrade_backup'"

# Refresh a dataset
"Refresh the 'Dev_Environment' dataset with the latest snapshot"
```

### Environment Management

```python
# Check environment status
"What's the status of all database environments?"

# Configure a new environment
"Help me set up a new PostgreSQL environment named 'staging_env'"

# Monitor environment health
"Show me any health issues with the 'prod_oracle_env' environment"
```

### Job Monitoring

```python
# Check recent jobs
"Show me all jobs that ran in the last 24 hours"

# Monitor specific job
"What's the status of job ID 'job_12345'?"

# Check failed operations
"Show me any failed jobs and their error details"
```

### Compliance & Reporting

```python
# Generate compliance report
"Create a compliance report for all production datasets"

# Check data masking status
"Show me the masking status for sensitive datasets"

# Performance metrics
"Generate a performance report for the last week"
```

## Development

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
│   ├── dct_mcp_server.log     # Main application logs
│   └── sessions/              # Telemetry session logs
└── src/
    └── dct_mcp_server/
        ├── main.py            # Application entry point
        ├── config/
        │   └── config.py      # Configuration management
        ├── core/
        │   ├── decorators.py  # Logging and telemetry decorators
        │   ├── exceptions.py  # Custom exception classes
        │   ├── logging.py     # Logging configuration
        │   └── session.py     # Session and telemetry management
        ├── dct_client/
        │   └── client.py      # DCT API HTTP client
        ├── tools/             # MCP tools for DCT endpoints
        │   ├── dataset_endpoints_tool.py
        │   ├── environment_endpoints_tool.py
        │   ├── engine_endpoints_tool.py
        │   ├── compliance_endpoints_tool.py
        │   ├── job_endpoints_tool.py
        │   └── reports_endpoints_tool.py
        └── icons/
            └── logo-delphixmcp-reg.png
```

### Contributing Guidelines

1. **Fork the repository** and create a feature branch
2. **Follow code style**: Use black formatting and type hints
3. **Add tests**: Include unit tests for new functionality
4. **Update documentation**: Keep README and docstrings current
5. **Test thoroughly**: Verify with multiple DCT environments
6. **Submit PR**: Include clear description and test results

### Code Quality Standards

- **Python 3.11+**: Use modern Python features and syntax
- **Type Hints**: All functions should have proper type annotations
- **Async/Await**: Use async patterns for all I/O operations  
- **Error Handling**: Implement comprehensive error handling with custom exceptions
- **Logging**: Use structured logging with appropriate levels
- **Documentation**: Maintain clear docstrings and README updates

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
cat mcp_server_setup_logfile.txt
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
5. **Documentation**: Update README and code documentation for changes

---

**Made with ❤️ by the Delphix Community**

*Enable your AI assistants to seamlessly manage your data infrastructure with Delphix DCT.*

For issues and questions:
- Check the [Delphix DCT API documentation](https://docs.delphix.com/)
- Open an issue in this repository
- Contact the Delphix support team