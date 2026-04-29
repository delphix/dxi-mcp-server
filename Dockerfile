FROM python:3.11-slim

WORKDIR /app

# Stage 1: install third-party dependencies only (maximises Docker layer cache).
# This layer is only invalidated when requirements.txt changes, not on source edits.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: copy project manifests and source, then install the package itself.
# hatchling (the build backend) needs both pyproject.toml, README.md, and src/
# to build the wheel — all three must be present before pip install runs.
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the dct-mcp-server package (registers the console script entry point).
RUN pip install --no-cache-dir --no-deps .

# Runtime credentials — do NOT bake in values.
# DCT_API_KEY and DCT_BASE_URL must be supplied at docker run time via -e flags.
# Example:
#   docker run -e DCT_API_KEY=<your-key> -e DCT_BASE_URL=https://your-dct-instance dct-mcp-server

# No EXPOSE directive: the server uses stdio transport by default.
# For HTTP/SSE mode use: docker run -p 6790:6790 ...

ENTRYPOINT ["dct-mcp-server"]
