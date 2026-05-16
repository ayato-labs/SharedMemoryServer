# Use a slim Python image
FROM python:3.11-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install the project as a package
COPY . .
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install .

# Final stage: Ultra-slim for production
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy the pre-built virtualenv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Data Persistence Directory
RUN mkdir -p /data
ENV RIPEN_HOME=/data
VOLUME /data

# SSE configuration
EXPOSE 8377

# Runtime optimizations
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Start the Ripen server in SSE mode by default
# This allows it to act as a centralized knowledge hub out of the box
ENTRYPOINT ["ripen", "--port", "8377"]
