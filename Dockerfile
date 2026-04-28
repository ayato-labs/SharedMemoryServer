# Use a slim Python image
FROM python:3.11-slim-bookworm AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml .
# If there is a lock file, copy it too.
# COPY uv.lock .

# Install dependencies into a virtualenv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install .

# Final stage
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy the virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Default port for SSE hub
EXPOSE 8377

# Run the server in SSE mode by default
# --host 0.0.0.0 is crucial for Docker
ENTRYPOINT ["python", "-m", "shared_memory.server", "--sse", "--port", "8377"]
