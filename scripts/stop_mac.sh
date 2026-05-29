#!/usr/bin/env bash
# stop_mac.sh — Stop and remove the FinAlly container (macOS/Linux)
# NOTE: The Docker volume (finally-data) is NOT removed — your data persists.

set -euo pipefail

CONTAINER_NAME="finally"

# ──────────────────────────────────────────────────────────────────────────────
# Check prerequisites
# ──────────────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "Error: Docker is not installed or not in PATH."
  exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# Stop running container
# ──────────────────────────────────────────────────────────────────────────────
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Stopping container '${CONTAINER_NAME}'..."
  docker stop "${CONTAINER_NAME}"
else
  echo "Container '${CONTAINER_NAME}' is not running."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Remove container (but NOT the volume)
# ──────────────────────────────────────────────────────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Removing container '${CONTAINER_NAME}'..."
  docker rm "${CONTAINER_NAME}"
fi

echo "FinAlly stopped. Your portfolio data is preserved in the 'finally-data' volume."
echo "Run ./scripts/start_mac.sh to start again."
