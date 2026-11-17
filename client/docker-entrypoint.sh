#!/bin/sh
set -eu

# Generate config.js from environment variables at container startup
# This allows the same Docker image to be used across different environments

CONFIG_PATH="/app/dist/config.js"

echo "Generating runtime config.js from environment variables..."

node /app/runtime-config.mjs "$CONFIG_PATH"

echo "Config written to $CONFIG_PATH"

# Execute the main container command
exec "$@"
