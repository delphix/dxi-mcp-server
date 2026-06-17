# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

# Create a non-root user and group (UID/GID 1000)
RUN groupadd --gid 1000 mcpuser \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/false mcpuser

WORKDIR /app

# Copy project files needed for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package, create the logs directory, and set ownership in one layer
RUN pip install --no-cache-dir . \
    && mkdir -p /app/logs \
    && chown -R mcpuser:mcpuser /app

USER mcpuser

# MCP server uses stdio transport; clients must pass -i to keep stdin open
CMD ["dct-mcp-server"]
