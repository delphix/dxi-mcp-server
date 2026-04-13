# syntax=docker/dockerfile:1
# Supports linux/amd64 and linux/arm64 via docker buildx.
# Build: docker buildx build --platform linux/amd64,linux/arm64 -t dct-mcp-server .
# Run:  docker run --rm -i -e DCT_API_KEY=<key> -e DCT_BASE_URL=<url> dct-mcp-server

FROM python:3.11-slim

# ── Non-root user ────────────────────────────────────────────────────────────
RUN groupadd --gid 1000 mcpuser && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/sh mcpuser

WORKDIR /app

# ── Dependencies (cached layer — only re-runs when pyproject.toml changes) ──
COPY pyproject.toml README.md ./

# ── Source ───────────────────────────────────────────────────────────────────
COPY src/ src/

# ── Install & prepare runtime directories ────────────────────────────────────
RUN pip install --no-cache-dir . && \
    mkdir -p /app/logs && \
    chown -R mcpuser:mcpuser /app

# ── Drop privileges ──────────────────────────────────────────────────────────
USER mcpuser

# stdio transport — no port exposed, no HEALTHCHECK (not applicable)
CMD ["dct-mcp-server"]
