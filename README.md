# Delphix DCT API MCP Server

A streamlined Model Context Protocol (MCP) server for interacting with the Delphix Data Control Tower (DCT) API.


## Features

- **Robust API Client**: A resilient, asynchronous client for interacting with the DCT API, featuring retry logic and exponential backoff.
- **Centralized Configuration**: Easy setup via environment variables.
- **Structured Logging**: Centralized and configurable logging for better observability.
- **Custom Exceptions**: A clear and specific exception hierarchy for predictable error handling.
- **Graceful Shutdown**: Handles `SIGINT` and `SIGTERM` for a clean shutdown process.
- **Local Telemetry**: Optional, opt-in anonymous usage tracking stored locally.

## Prerequisites

- Python 3.11+
- Access to a Delphix DCT instance and an API key.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/delphix/dxi-mcp-server.git
    cd dxi-mcp-server
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**

    You can install the project dependencies using either `pip` or `uv`.

    #### Option 1: Using pip
    Install the dependencies using `pip` and the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

    To install the project in editable mode, which is useful for development:
    ```bash
    pip install -e .
    ```

    #### Option 2: Using uv (Recommended)
    For a faster and more deterministic installation, you can use `uv`. The `uv.lock` file ensures a consistent, reproducible environment.
    ```bash
    pip install uv
    uv sync
    ```

## Configuration

The server is configured using environment variables. For local development, you can create a `.env` file in the project root.

**Required:**
- `DCT_API_KEY`: Your DCT API key.
- `DCT_BASE_URL`: The base URL of your DCT instance (e.g., `https://your-dct-host.delphix.com`).

**Optional:**
- `DCT_VERIFY_SSL`: Set to `true` to enable SSL certificate verification (default: `false`).
- `DCT_TIMEOUT`: Request timeout in seconds (default: `30`).
- `DCT_MAX_RETRIES`: Number of retry attempts for failed API requests (default: `3`).
- `DCT_LOG_LEVEL`: Logging level (e.g., `DEBUG`, `INFO`, `WARNING`; default: `INFO`).
- `IS_LOCAL_TELEMETRY_ENABLED`: Set to `true` to enable the collection of anonymous usage data (default: `false`). See the Telemetry section for more details.

### Example `.env` file:
```
DCT_API_KEY="apk1.your-api-key-here"
DCT_BASE_URL="https://your-dct-host.delphix.com"
DCT_LOG_LEVEL="DEBUG"
IS_LOCAL_TELEMETRY_ENABLED="true"
```

## Running the Server

The easiest way to run the server is with the provided shell script:

```bash
./start_mcp_server_python.sh
```

This script ensures the virtual environment is used and all necessary dependencies are available.

## Telemetry

When `IS_LOCAL_TELEMETRY_ENABLED` is set to `true`, this server collects anonymous usage data to help us improve its functionality.

- **What is collected?**: We log metadata about which tools are executed, including the tool name, arguments, and execution status (success or failure). We do not log any sensitive data returned by the tools.
- **User Identification**: To distinguish usage between different users, the server uses the operating system's logged-in username (`getpass.getuser()`). This helps us understand usage patterns without collecting personal information.
- **Storage**: Telemetry logs are stored locally in the `logs/sessions/` directory. No data is uploaded or sent to any remote server.
- **Disabling Telemetry**: You can disable this feature at any time by setting `IS_LOCAL_TELEMETRY_ENABLED="false"` in your environment or `.env` file.


### Advanced Usage: Running from a Git Repository

You can run the MCP server directly from a Git repository using a tool like `uvx`. This is useful for deployments or for running the server without cloning it locally.

Here is an example of how you might configure this in a `settings.json` file for an application that consumes MCP servers:

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/delphix/dxi-mcp-server.git", "dct-mcp-server"],
      "env": {
        "DCT_API_KEY": "your-api-key",
        "DCT_BASE_URL": "https://your-dct-host.delphix.com",
        "DCT_VERIFY_SSL": "true"
      }
    }
  }
}
```

**Note**: For private repositories, use SSH authentication: `git+ssh://git@github.com/delphix/dxi-mcp-server.git`




## Project Structure

```
src/
├── dct_mcp_server/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── decorators.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── dct_client/
│   │   ├── __init__.py
│   │   └── client.py
│   └── tools/
│       └── __init__.py
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