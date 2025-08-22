# Delphix DCT API MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with the Delphix Data Control Tower (DCT) API. This server enables AI assistants to manage Delphix data sources, virtual databases, and other DCT resources.

## Features

- **DSources Management**: Create, list, search, and manage data sources
- **Virtual Database Operations**: Create, refresh, snapshot, and manage VDBs
- **Snapshot Management**: Create and list snapshots for both dSources and VDBs
- **Tag Management**: Add, retrieve, and delete tags for resources
- **Async Operations**: Built with modern async/await patterns for performance
- **Error Handling**: Robust retry logic and error handling
- **SSL Support**: Configurable SSL verification
- **Logging**: Comprehensive logging with configurable levels

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
python -m delphixmcpserver.main
```

### Integration with Claude Desktop

Add this configuration to your Claude Desktop config file:

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "python",
      "args": ["-m", "delphixmcpserver.main"],
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
- `dct_dsources_get` - Get specific dSource details
- `dct_dsources_snapshots_list` - List snapshots for a dSource
- `dct_dsources_snapshot_create` - Create a snapshot
- `dct_dsources_tags_get` - Get tags for a dSource
- `dct_dsources_tags_create` - Create tags
- `dct_dsources_tags_delete` - Delete tags

#### Virtualization Tools
- `dct_vdb_list` - List all virtual databases
- `dct_vdb_search` - Search VDBs with filters
- `dct_vdb_get` - Get VDB details
- `dct_vdb_create` - Create a new VDB
- `dct_vdb_delete` - Delete a VDB
- `dct_vdb_refresh` - Refresh a VDB
- `dct_vdb_snapshot` - Create VDB snapshot
- `dct_vdb_snapshots_list` - List VDB snapshots

## Project Structure

```
src/
├── delphixmcpserver/
│   ├── __init__.py           # Package initialization
│   ├── main.py              # Main server entry point
│   ├── client.py            # DCT API client
│   ├── config.py            # Configuration management
│   └── tools/               # Tool implementations
│       ├── __init__.py      # Tools package
│       ├── dsources.py      # DSources API tools
│       └── virtualization.py # Virtualization API tools
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