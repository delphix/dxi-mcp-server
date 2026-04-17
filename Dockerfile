FROM python:3.11-slim

WORKDIR /app

# Layer caching: install dependencies before copying source
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["dct-mcp-server"]
