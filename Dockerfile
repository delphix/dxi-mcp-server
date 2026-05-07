# syntax=docker/dockerfile:1.7
#
# Delphix DCT API MCP Server
# Multi-stage build that produces a slim, non-root, deterministic runtime image.
#
# Build:
#     docker build -t dct-mcp-server:dev .
#
# Run (stdio transport — `-i`, no `-t`):
#     docker run --rm -i \
#         -e DCT_API_KEY="<your-api-key>" \
#         -e DCT_BASE_URL="https://your-dct-host.example.com" \
#         dct-mcp-server:dev
#
# See README.md "Run with Docker" for the full client-config recipe.

# -----------------------------------------------------------------------------
# Stage 1: builder — installs Python deps into a venv we copy into runtime.
# -----------------------------------------------------------------------------
# Pinned by digest for fully reproducible builds (FR-7).
FROM python:3.11-slim-bookworm@sha256:ee710afcfb733f4a750d9be683cf054b5cd247b6c5f5237a6849ea568b90ab15 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-essential is staged here so wheels that need compilation succeed in a
# future dependency bump. Currently none of our pinned deps require it on
# slim-bookworm + amd64 (httpx, pyyaml, urllib3, requests, fastmcp all ship
# manylinux wheels). Kept minimal and deliberately confined to the builder
# stage so it never reaches the runtime image (FR-6 / AC-6.5).
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy ONLY dependency manifests first → maximises Docker layer-cache reuse.
# Source changes will not bust this layer.
COPY requirements.txt ./

# Create a dedicated venv we copy verbatim into the runtime stage.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: runtime — slim image with only the venv + source + tini + non-root user.
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm@sha256:ee710afcfb733f4a750d9be683cf054b5cd247b6c5f5237a6849ea568b90ab15 AS runtime

# OCI labels (FR-6 / AC-6.8). Version mirrors pyproject.toml; bump in lockstep
# with the project version on each release.
LABEL org.opencontainers.image.title="dct-mcp-server" \
      org.opencontainers.image.source="https://github.com/delphix/dxi-mcp-server" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="2026.0.1.0-preview" \
      org.opencontainers.image.description="Delphix DCT API MCP Server" \
      org.opencontainers.image.documentation="https://github.com/delphix/dxi-mcp-server#run-with-docker"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1

# tini for proper PID-1 signal forwarding so `docker stop` triggers the
# existing FastMCP lifespan shutdown path (AC-3.4 / R1, R7 mitigation).
# Pinned via apt; this is the only runtime apt dep.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (FR-6 / AC-1.7 / AC-6.1). UID/GID 1000 is conventional and
# matches typical host-user UID on Linux, which keeps `-v` mounts of `logs/`
# writable without `--user` overrides on Linux hosts.
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 --home-dir /app --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy the venv from builder (no compilers, no caches, no apt lists).
COPY --from=builder /opt/venv /opt/venv

# Copy source. .dockerignore filters out everything we don't need.
# Single COPY for the source so it changes together → one layer to invalidate.
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser pyproject.toml requirements.txt /app/

# Pre-create the writable logs directory and chown to appuser so a bind-mount
# on Linux works without manual chown on the host.
RUN mkdir -p /app/logs/sessions \
    && chown -R appuser:appuser /app

USER appuser

# PYTHONPATH so `python -m dct_mcp_server.main` finds the src layout without
# needing an editable install. (We did NOT pip-install the package itself in
# the venv — only its deps — to keep the image small and deterministic.)
ENV PYTHONPATH=/app/src

# stdio transport: no EXPOSE, no HEALTHCHECK (AC-6.7 — intentional).
# tini handles SIGTERM/SIGINT correctly so `docker stop` triggers the existing
# lifespan shutdown path in main.py (AC-3.4 / R1).
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "dct_mcp_server.main"]

STOPSIGNAL SIGTERM
