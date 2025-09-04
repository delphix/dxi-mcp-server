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

The server is configured using environment variables. Copy the template configuration:

```bash
cp .env.template .env
```

Edit `.env` with your DCT instance details:

```bash
# Required: Your DCT API Key
DCT_API_KEY=apk1.your-api-key-here

# Optional: DCT instance URL (default: https://localhost:8083)
DCT_BASE_URL=https://your-dct-host:8083

# Optional: SSL verification (default: false)
DCT_VERIFY_SSL=true

# Optional: Request timeout in seconds (default: 30)
DCT_TIMEOUT=30

# Optional: Maximum retry attempts (default: 3)
DCT_MAX_RETRIES=3

# Optional: Log level (default: INFO)
DCT_LOG_LEVEL=DEBUG
```

## Usage

### Running the Server

After configuration, run the server:

```bash
# Load your environment variables
source .env

# Run the server
python -m dxi_mcp_server.main
```

### Integration with Claude Desktop

Add this configuration to your Claude Desktop config file:

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "python",
      "args": ["-m", "dxi_mcp_server.main"],
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host:8083",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

### Available Tools

The server provides the following categories of tools:

#### DSources Tools
- `dct_dsources_list` - List all dSources
- `dct_dsources_search` - Search dSources with filters
- `dct_dsource_get` - Get specific dSource details
- `dct_dsource_snapshots_list` - List snapshots for a dSource
- `dct_dsource_snapshot_create` - Create a snapshot
- `dct_dsource_tags_get` - Get tags for a dSource
- `dct_dsource_tags_create` - Create tags
- `dct_dsource_tags_delete` - Delete tags

#### VDB (Virtual Database) Tools
- `dct_vdb_list` - List all virtual databases
- `dct_vdb_search` - Search VDBs with filters
- `dct_vdb_get` - Get VDB details
- `dct_vdb_provision_by_timestamp` - Provision VDB by timestamp
- `dct_vdb_provision_by_snapshot` - Provision VDB by snapshot
- `dct_vdb_provision_from_bookmark` - Provision VDB from bookmark
- `dct_vdb_delete` - Delete a VDB
- `dct_vdb_refresh_by_timestamp` - Refresh VDB by timestamp
- `dct_vdb_refresh_by_snapshot` - Refresh VDB by snapshot
- `dct_vdb_refresh_from_bookmark` - Refresh VDB from bookmark
- `dct_vdb_refresh_by_location` - Refresh VDB by location/SCN
- `dct_vdb_rollback_by_timestamp` - Rollback VDB by timestamp
- `dct_vdb_rollback_by_snapshot` - Rollback VDB by snapshot
- `dct_vdb_rollback_from_bookmark` - Rollback VDB from bookmark
- `dct_vdb_start` - Start a VDB
- `dct_vdb_stop` - Stop a VDB
- `dct_vdb_enable` - Enable a VDB
- `dct_vdb_disable` - Disable a VDB
- `dct_vdb_lock` - Lock a VDB
- `dct_vdb_unlock` - Unlock a VDB
- `dct_vdb_snapshot` - Create VDB snapshot
- `dct_vdb_snapshots_list` - List VDB snapshots

#### Environment Tools
- `dct_environments_list` - List all environments
- `dct_environments_search` - Search environments with filters
- `dct_environment_get` - Get environment details
- `dct_environment_enable` - Enable an environment
- `dct_environment_disable` - Disable an environment
- `dct_environment_refresh` - Refresh environment (discover changes)
- `dct_environment_users_list` - List users for an environment
- `dct_environments_compatible_repositories_by_snapshot` - Get compatible repositories by snapshot
- `dct_environments_compatible_repositories_by_timestamp` - Get compatible repositories by timestamp
- `dct_environments_compatible_repositories_from_bookmark` - Get compatible repositories from bookmark

#### Engine Tools
- `dct_engines_list` - List all engines
- `dct_engines_search` - Search engines with filters
- `dct_engine_get` - Get engine details

#### Bookmark Tools
- `dct_bookmarks_list` - List all bookmarks
- `dct_bookmarks_search` - Search bookmarks with filters
- `dct_bookmark_get` - Get bookmark details
- `dct_bookmark_create` - Create a bookmark
- `dct_bookmark_delete` - Delete a bookmark
- `dct_bookmark_update` - Update a bookmark

#### Snapshot Tools
- `dct_snapshots_list` - List all snapshots
- `dct_snapshots_search` - Search snapshots with filters
- `dct_snapshot_get` - Get snapshot details
- `dct_snapshot_delete` - Delete a snapshot
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