FROM python:3.11-slim

WORKDIR /app

# Copy project metadata and source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package and its dependencies, create logs dir, add non-root user
RUN pip install --no-cache-dir . && \
    mkdir -p /app/logs && \
    useradd --no-create-home --shell /bin/false dct && \
    chown dct:dct /app/logs

# Set log directory so logs write to /app/logs (not the pip install tree)
ENV DCT_LOG_DIR=/app/logs

USER dct

CMD ["dct-mcp-server"]
