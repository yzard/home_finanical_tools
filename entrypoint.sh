#!/bin/sh

# Set default values if not provided
PUID=${PUID:-1000}
PGID=${PGID:-1000}
UMASK=${UMASK:-022}

echo "Starting with PUID=$PUID, PGID=$PGID, UMASK=$UMASK"

# Create group if it doesn't exist
if ! getent group abc > /dev/null 2>&1; then
    addgroup -g "$PGID" abc
fi

# Create user if it doesn't exist
if ! id abc > /dev/null 2>&1; then
    adduser -D -u "$PUID" -G abc -h /app abc
fi

# Set umask
umask "$UMASK"

# Change ownership of data directory (app is owned by root, which is fine)
chown -R abc:abc /data 2>/dev/null || true

echo "Running as user abc ($(id abc))"

# Execute the application as the specified user
exec su-exec abc:abc python -m home_financial_tools.server.main --config "${CONFIG_PATH:-sample/config.yaml}"
