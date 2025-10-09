# Project Overview
This is a model context server that is built for the purpose of communicating with delphix engines with agents. It provides a RESTful API to manage and interact with these engines.

## Folder Structure
- `src/`: Contains the source code for the server.
- `tests/`: Contains unit and integration tests for the server.
- `docs/`: Contains documentation related to the project.
- `src/dxi_mcp_server/`: Contains the main application code for the server.
- `src/dxi_mcp_server/guards`: Contains the code for rail guards and safety checks.
- `src/dxi_mcp_server/api/`: Contains the code for http api interactions for delphix engines.
- `src/dxi_mcp_server/api/client/`: Contains the base client code for http requests.
- `src/dxi_mcp_server/config`: Contains the code configuration of the mcp server


## Libraries and Frameworks
- **MCP Server**: The main framework used for building the server.
- **asyncio**: For handling asynchronous operations.
- **aiohttp**: For making asynchronous HTTP requests.
- **pytest**: For testing the application.
- **pydantic**: For data validation and settings management using Python type annotations.
