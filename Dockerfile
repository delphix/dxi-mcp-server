FROM python:3.11-slim

# Prevents Python from buffering stdout/stderr (critical for MCP stdio transport)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy dependency manifests and README first to leverage layer caching
# README.md is required by pyproject.toml (readme = "README.md") for hatchling metadata validation
COPY requirements.txt pyproject.toml README.md ./

# Copy source code
COPY src/ ./src/

# Install the package and its dependencies in editable mode so the CLI entry point works
RUN pip install --no-cache-dir -e .

# Create logs directory for runtime log output
RUN mkdir -p /app/logs

# Default entrypoint: run the MCP server via the installed CLI entry point
ENTRYPOINT ["dct-mcp-server"]
