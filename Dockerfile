FROM python:3.11-slim

WORKDIR /app

# Copy project metadata and source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package and its dependencies
RUN pip install --no-cache-dir .

# Create logs directory (can be bind-mounted to persist logs on the host)
RUN mkdir -p /app/logs

CMD ["dct-mcp-server"]
