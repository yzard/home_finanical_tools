FROM python:3.12-alpine

WORKDIR /app

# Install system dependencies
# - build-base: for compiling Python packages
# - su-exec: for dropping privileges to specified user
# - shadow: for usermod/groupmod commands
RUN apk add --no-cache \
    build-base \
    su-exec \
    shadow

# Copy project files
COPY . .

# Install uv for faster pip installations
RUN pip install --no-cache-dir uv

# Install Python dependencies using uv
RUN uv pip install --system --no-cache .

# Create data directory for volume mounting
RUN mkdir -p /data

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set default environment variables
ENV PUID=1000 \
    PGID=1000 \
    UMASK=022 \
    CONFIG_PATH=/data/config.yaml \
    PYTHONPATH=/app

# Expose port
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
