# Delphix DCT API MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with the Delphix Data Control Tower (DCT) API. This server enables AI assistants to manage Delphix data sources, virtual databases, and other DCT resources.

## Features

- **DSources Management**: Create, list, search, and manage data sources
- **Virtual Database Operations**: Provision, refresh, rollback, snapshot, and manage VDBs
- **Environment Management**: List, search, and manage DCT environments
- **Engine Management**: List, search, and manage DCT engines
- **Bookmark Management**: Create, search, and manage bookmarks for point-in-time operations
- **Snapshot Management**: Create, search, and manage snapshots for data sources and VDBs
- **Tag Management**: Add, retrieve, and delete tags for resources
- **Async Operations**: Built with modern async/await patterns for performance
- **Error Handling**: Robust retry logic and error handling
- **SSL Support**: Configurable SSL verification
- **Logging**: Comprehensive logging with configurable levels
- **API Compliance**: Full compliance with DCT API v3 specification

## Installation

### Prerequisites

- Python 3.11 or higher
- Access to a Delphix DCT instance
- DCT API key

### Install Dependencies

```bash
# Using uv (recommended)
uv add "mcp[cli]>=1.13.0" httpx>=0.24.0

# Or using pip
pip install "mcp[cli]>=1.13.0" httpx>=0.24.0
```

## Configuration

The server is configured using environment variables. Set the following environment variables in your shell or use them directly in your MCP client configuration:

### Required Environment Variables

```bash
# Required: Your DCT API Key
export DCT_API_KEY="your-api-key-here"

# Required: DCT instance URL
export DCT_BASE_URL="https://your-dct-host:8083"
```

### Optional Environment Variables

```bash
# Optional: SSL verification (default: false)
export DCT_VERIFY_SSL="true"

# Optional: Request timeout in seconds (default: 30)
export DCT_TIMEOUT="30"

# Optional: Maximum retry attempts (default: 3)
export DCT_MAX_RETRIES="3"

# Optional: Log level (default: INFO)
export DCT_LOG_LEVEL="DEBUG"
```

You can add these to your shell profile (`~/.zshrc`, `~/.bashrc`) for persistence.

## Usage

### Running the Server

After setting up your environment variables, run the server:

```bash
# Using the startup script (recommended)
./start_mcp_server_python.sh

# Or run directly
python -m dxi_mcp_server.main
```

### Integration with Claude Desktop

Add this configuration to your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json`):

#### Option 1: Using Startup Script (Recommended for Local Development)
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "/path/to/your/project/start_mcp_server_python.sh",
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host:8083",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

#### Option 2: Using uvx from Git Repository (Recommended for Production)
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dxi-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host:8083",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

#### Option 3: Direct Python Module
```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "python",
      "args": ["-m", "dxi_mcp_server.main"],
      "cwd": "/path/to/your/project",
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host:8083",
        "DCT_VERIFY_SSL": "true",
        "PYTHONPATH": "src"
      }
    }
  }
}
```

**Note**: For private repositories, use SSH authentication: `git+ssh://git@github.com/delphix/dxi-mcp-server.git`

### Available Tools

The server provides the following categories of tools:

#### DSources Tools
- `list_dsources` - List all dSources
- `search_dsources` - Search dSources with filters
- `get_dsource` - Get specific dSource details
- `list_snapshots` - List snapshots for a dSource
- `create_snapshot` - Create a snapshot for a dSource
- `get_tags` - Get tags for a dSource
- `create_tags` - Create tags for a dSource
- `delete_tags` - Delete tags from a dSource

#### VDB (Virtual Database) Tools
- `list_vdbs` - List all virtual databases
- `search_vdbs` - Search VDBs with filters
- `get_vdb` - Get VDB details
- `provision_vdb_by_timestamp` - Provision VDB by timestamp
- `provision_vdb_by_snapshot` - Provision VDB by snapshot
- `provision_vdb_from_bookmark` - Provision VDB from bookmark
- `delete_vdb` - Delete a VDB
- `refresh_vdb_by_timestamp` - Refresh VDB by timestamp
- `refresh_vdb_by_snapshot` - Refresh VDB by snapshot
- `refresh_vdb_from_bookmark` - Refresh VDB from bookmark
- `refresh_vdb_by_location` - Refresh VDB by location/SCN
- `rollback_vdb_by_timestamp` - Rollback VDB by timestamp
- `rollback_vdb_by_snapshot` - Rollback VDB by snapshot
- `rollback_vdb_from_bookmark` - Rollback VDB from bookmark
- `start_vdb` - Start a VDB
- `stop_vdb` - Stop a VDB
- `enable_vdb` - Enable a VDB
- `disable_vdb` - Disable a VDB
- `lock_vdb` - Lock a VDB
- `unlock_vdb` - Unlock a VDB
- `snapshot_vdb` - Create VDB snapshot
- `list_vdb_snapshots` - List VDB snapshots

#### Environment Tools
- `search_environments` - Search environments with filters
- `get_environment` - Get environment details
- `enable_environment` - Enable an environment
- `disable_environment` - Disable an environment
- `refresh_environment` - Refresh environment (discover changes)
- `list_environment_users` - List users for an environment
- `compatible_repos_by_snapshot` - Get compatible repositories by snapshot
- `compatible_repos_by_timestamp` - Get compatible repositories by timestamp
- `compatible_repos_from_bookmark` - Get compatible repositories from bookmark

#### Engine Tools
- `list_engines` - List all engines
- `search_engines` - Search engines with filters
- `get_engine` - Get engine details

#### Bookmark Tools
- `list_bookmarks` - List all bookmarks
- `search_bookmarks` - Search bookmarks with filters
- `get_bookmark` - Get bookmark details
- `create_bookmark` - Create a bookmark
- `delete_bookmark` - Delete a bookmark
- `update_bookmark` - Update a bookmark

#### Snapshot Tools
- `list_snapshots` - List all snapshots
- `search_snapshots` - Search snapshots with filters
- `get_snapshot` - Get snapshot details
- `delete_snapshot` - Delete a snapshot
- `dct_snapshots_find_by_timestamp` - Find snapshots by timestamp
- `dct_snapshots_find_by_location` - Find snapshots by location/SCN

## Project Structure

```
src/
├── dxi_mcp_server/
│   ├── __init__.py           # Package initialization
│   ├── main.py              # Main server entry point
│   ├── client.py            # DCT API client
│   ├── config.py            # Configuration management
│   └── tools/               # Tool implementations
│       ├── __init__.py      # Tools package
│       ├── dsources.py      # DSources API tools
│       ├── vdb.py           # Virtual Database API tools
│       ├── environments.py  # Environment API tools
│       ├── engines.py       # Engine API tools
│       ├── bookmarks.py     # Bookmark API tools
│       └── snapshots.py     # Snapshot API tools
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the [Delphix DCT API documentation](https://docs.delphix.com/)
- Open an issue in this repository
- Contact the Delphix support team