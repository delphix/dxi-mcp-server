# syntax=docker/dockerfile:1.7
#
# Delphix DCT MCP Server — container image
#
# Multi-stage build:
#   1. builder  — installs uv, materialises a frozen virtualenv from uv.lock
#   2. runtime  — non-root user (UID 1000), copies the venv + src, runs over stdio
#
# Build:        docker build -t dct-mcp-server:latest .
# Multi-arch:   docker buildx build --platform linux/amd64,linux/arm64 \
#                                   -t dct-mcp-server:latest .
#
# Run (stdio — invoked by an MCP client, not as a daemon):
#   docker run --rm -i \
#     -e DCT_API_KEY="..." \
#     -e DCT_BASE_URL="https://your-dct-host.example.com" \
#     -e DCT_TOOLSET="self_service" \
#     dct-mcp-server:latest
#
# See the README "Docker" section for full client-side configuration examples.

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Pin uv so builds are reproducible. Bump deliberately when needed.
RUN pip install --no-cache-dir "uv==0.5.31"

# Build the virtualenv at the same path it will live in the runtime stage
# (/app/.venv). uv writes absolute paths into console-script shebangs at
# install time, so the builder and runtime venv paths must match exactly.
WORKDIR /app

# Copy dependency manifests first (better layer cache when source changes)
COPY pyproject.toml uv.lock README.md LICENSE.md ./
COPY src ./src

# Frozen install — exact resolution from uv.lock; no dev groups in the image.
RUN uv sync --frozen --no-dev


# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="dct-mcp-server" \
      org.opencontainers.image.description="Delphix DCT API MCP Server (stdio transport)" \
      org.opencontainers.image.source="https://github.com/delphix/dxi-mcp-server" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="2026.0.1.0-preview"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DCT_LOG_DIR=/app/logs

# Create non-root user/group and prepare the app directory.
RUN groupadd -g 1000 app \
 && useradd  -u 1000 -g 1000 -m -s /bin/false app \
 && mkdir -p /app/logs \
 && chown -R app:app /app

WORKDIR /app

# Copy the materialised virtualenv from the builder stage,
# then copy the project source. All owned by the non-root user.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app pyproject.toml uv.lock README.md LICENSE.md ./
COPY --chown=app:app src ./src

USER app

# Documented runtime env vars (consumed by the server, not declared here):
#   DCT_API_KEY                 (required)
#   DCT_BASE_URL                (required)
#   DCT_TOOLSET                 (default: self_service)
#   DCT_VERIFY_SSL              (default: false)
#   DCT_LOG_LEVEL               (default: INFO)
#   DCT_TIMEOUT                 (default: 30)
#   DCT_MAX_RETRIES             (default: 3)
#   DCT_LOG_DIR                 (default: /app/logs — set above)
#   IS_LOCAL_TELEMETRY_ENABLED  (default: false)
#
# Transport is stdio — no port is exposed. The MCP client invokes
# `docker run --rm -i …` and pipes JSON-RPC frames over stdin/stdout.
ENTRYPOINT ["dct-mcp-server"]
