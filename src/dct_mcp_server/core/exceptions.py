class MCPError(Exception):
    """Base exception class for the MCP server."""

    pass


class DCTClientError(MCPError):
    """Raised for errors related to the DCT client."""

    pass


class ToolError(MCPError):
    """Raised for errors that occur within a tool."""

    pass
