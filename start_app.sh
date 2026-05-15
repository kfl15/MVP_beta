#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/docker"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required. Install the Docker Compose plugin or docker-compose."
  exit 1
fi

compose_up() {
  cd "$COMPOSE_DIR"
  "${COMPOSE[@]}" up -d --build
}

fallback_host_network_build() {
  cd "$SCRIPT_DIR"

  echo
  echo "Normal Docker Compose build failed."
  echo "Trying fallback build with Docker host networking..."
  echo

  docker build --network host -f docker/backend.Dockerfile -t docker_backend:latest .
  docker build --network host -f docker/frontend.Dockerfile -t docker_frontend:latest .

  cd "$COMPOSE_DIR"
  "${COMPOSE[@]}" up -d --no-build
}

if compose_up; then
  echo
  echo "App started successfully."
else
  fallback_host_network_build
  echo
  echo "App started with fallback host-network build."
fi

echo
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/health"
