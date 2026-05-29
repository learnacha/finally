#!/usr/bin/env bash
# start_mac.sh — Build and run the FinAlly container (macOS/Linux)
# Usage: ./scripts/start_mac.sh [--build]
#   --build  Force a Docker image rebuild even if it already exists

set -euo pipefail

CONTAINER_NAME="finally"
IMAGE_NAME="finally"
PORT=8000
APP_URL="http://localhost:${PORT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ──────────────────────────────────────────────────────────────────────────────
# Parse flags
# ──────────────────────────────────────────────────────────────────────────────
FORCE_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --build) FORCE_BUILD=true ;;
    *) echo "Unknown argument: $arg" && exit 1 ;;
  esac
done

# ──────────────────────────────────────────────────────────────────────────────
# Check prerequisites
# ──────────────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "Error: Docker is not installed or not in PATH."
  exit 1
fi

if [ ! -f "${PROJECT_ROOT}/.env" ]; then
  echo "Warning: .env file not found at ${PROJECT_ROOT}/.env"
  echo "         Copy .env.example to .env and fill in your API keys."
  echo "         Continuing anyway — the simulator will be used for market data."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Handle already-running container
# ──────────────────────────────────────────────────────────────────────────────
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Container '${CONTAINER_NAME}' is already running."
  echo "  App URL: ${APP_URL}"
  echo "  To stop: ./scripts/stop_mac.sh"
  echo "  To rebuild and restart: ./scripts/stop_mac.sh && ./scripts/start_mac.sh --build"
  exit 0
fi

# Remove stopped container with the same name if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Removing stopped container '${CONTAINER_NAME}'..."
  docker rm "${CONTAINER_NAME}"
fi

# ──────────────────────────────────────────────────────────────────────────────
# Build image if needed
# ──────────────────────────────────────────────────────────────────────────────
IMAGE_EXISTS=$(docker images -q "${IMAGE_NAME}" 2>/dev/null)

if [ "${FORCE_BUILD}" = "true" ] || [ -z "${IMAGE_EXISTS}" ]; then
  echo "Building Docker image '${IMAGE_NAME}'..."
  docker build -t "${IMAGE_NAME}" "${PROJECT_ROOT}"
else
  echo "Docker image '${IMAGE_NAME}' already exists. Use --build to rebuild."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Run the container
# ──────────────────────────────────────────────────────────────────────────────
ENV_FILE_ARG=""
if [ -f "${PROJECT_ROOT}/.env" ]; then
  ENV_FILE_ARG="--env-file ${PROJECT_ROOT}/.env"
fi

echo "Starting FinAlly..."
# shellcheck disable=SC2086
docker run -d \
  --name "${CONTAINER_NAME}" \
  -v finally-data:/app/db \
  -p "${PORT}:${PORT}" \
  ${ENV_FILE_ARG} \
  "${IMAGE_NAME}"

# ──────────────────────────────────────────────────────────────────────────────
# Wait for the container to be healthy
# ──────────────────────────────────────────────────────────────────────────────
echo "Waiting for FinAlly to start..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until curl -sf "${APP_URL}/api/health" &>/dev/null; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "${ATTEMPTS}" -ge "${MAX_ATTEMPTS}" ]; then
    echo "Error: FinAlly did not start within 30 seconds."
    echo "Check logs with: docker logs ${CONTAINER_NAME}"
    exit 1
  fi
  sleep 1
done

echo ""
echo "FinAlly is running!"
echo "  App URL:  ${APP_URL}"
echo "  Logs:     docker logs -f ${CONTAINER_NAME}"
echo "  Stop:     ./scripts/stop_mac.sh"
echo ""

# Open browser if available
if command -v open &>/dev/null; then
  open "${APP_URL}"
elif command -v xdg-open &>/dev/null; then
  xdg-open "${APP_URL}"
fi
