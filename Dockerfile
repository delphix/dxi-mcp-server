FROM python:3.11-slim

WORKDIR /app

# Copy source into the working directory
COPY . .

# Install the package in editable mode so the source tree stays at /app/src.
# This ensures that logging.py's _get_project_root() (parents[3] from
# src/dct_mcp_server/core/logging.py) resolves to /app, placing log files
# under /app/logs instead of inside site-packages.
RUN pip install --no-cache-dir -e .

# Create the logs directory that the logging module writes to
RUN mkdir -p /app/logs

# The server communicates over stdio — no port to expose
CMD ["dct-mcp-server"]
