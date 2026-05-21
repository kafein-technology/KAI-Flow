#!/bin/sh
# Generate config.js from environment variables at container startup
# This allows the same Docker image to be used across different environments

CONFIG_PATH="/app/dist/config.js"

echo "Generating runtime config.js from environment variables..."

cat > "$CONFIG_PATH" << EOF
// Runtime configuration - Generated at container startup
// DO NOT EDIT: This file is auto-generated from environment variables

window.VITE_BASE_PATH = "${VITE_BASE_PATH:-/kai}";
window.VITE_API_BASE_URL = "${VITE_API_BASE_URL:-//localhost:8000}";
window.VITE_KEYCLOAK_URL = "${VITE_KEYCLOAK_URL:-}";
window.VITE_KEYCLOAK_CLIENT_ID = "${VITE_KEYCLOAK_CLIENT_ID:-}";
window.VITE_KEYCLOAK_REALM = "${VITE_KEYCLOAK_REALM:-}";
window.VITE_API_START = "${VITE_API_START:-api}";
window.VITE_API_VERSION_ONLY = "${VITE_API_VERSION_ONLY:-v1}";
window.VITE_API_VERSION = "/${VITE_API_START:-api}/${VITE_API_VERSION_ONLY:-v1}";
window.VITE_APP_NAME = "${VITE_APP_NAME:-KAI Fusion}";
window.VITE_NODE_ENV = "${VITE_NODE_ENV:-production}";
window.VITE_ENABLE_LOGGING = "${VITE_ENABLE_LOGGING:-false}";
window.VITE_ENTERPRISE = "${VITE_ENTERPRISE:-false}";
EOF

echo "Config written to $CONFIG_PATH"
cat "$CONFIG_PATH"

# Execute the main container command
exec "$@"
