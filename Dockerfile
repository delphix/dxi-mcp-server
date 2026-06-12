# ============================================================
# Stage 1: Build — install dependencies and package
# ============================================================
FROM python:3.11-slim AS build

WORKDIR /app

# Install build tools needed for pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a virtualenv in the build stage
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install pinned runtime dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source tree and install the package
COPY src/ src/
COPY pyproject.toml .
COPY README.md .
# NOTE: docs/api-external.yaml is NOT bundled in this repo.
# The server fetches the OpenAPI spec from DCT at startup and falls back to
# pre-built tools in tools/*_endpoints_tool.py if the download fails.

RUN pip install .

# ============================================================
# Stage 2: Runtime — minimal image with no build tools
# ============================================================
FROM python:3.11-slim AS runtime

LABEL maintainer="Delphix Engineering <support@delphix.com>" \
      version="2026.0.2.0-preview" \
      description="Delphix DCT API MCP Server — stdio MCP server for the Delphix Data Control Tower API"

WORKDIR /app

# Create non-root user (uid 1000)
RUN addgroup --gid 1000 appuser \
    && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" appuser

# Copy the virtualenv from the build stage
COPY --from=build /app/venv /app/venv

# Create the log directory and set ownership
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

ENV PATH="/app/venv/bin:$PATH"

# Switch to non-root user
USER appuser

# stdio MCP server — no ports to expose
CMD ["python", "-m", "dct_mcp_server.main"]
