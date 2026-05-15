#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/docker"
LLM_MODEL="${OLLAMA_LLM_MODEL:-llama3.2:1b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

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

host_has_model() {
  local model="$1"
  curl -fsS http://localhost:11434/api/tags \
    | grep -Eq "\"name\":\"${model}\"|\"name\":\"${model}:latest\"|\"model\":\"${model}\"|\"model\":\"${model}:latest\""
}

host_ollama_ready() {
  curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 \
    && host_has_model "$LLM_MODEL" \
    && host_has_model "$EMBED_MODEL"
}

fallback_host_network_build() {
  cd "$SCRIPT_DIR"

  echo
  echo "Normal Docker Compose build failed."
  echo "Trying fallback build with Docker host networking..."
  echo

  docker build --network host -f docker/backend.Dockerfile -t docker_backend:latest .
  docker build --network host -f docker/frontend.Dockerfile -t docker_frontend:latest .
}

compose_up_prebuilt() {
  cd "$COMPOSE_DIR"
  "${COMPOSE[@]}" up -d --no-build
}

compose_up_host_ollama_prebuilt() {
  cd "$COMPOSE_DIR"
  OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    OLLAMA_LLM_MODEL="$LLM_MODEL" \
    OLLAMA_EMBED_MODEL="$EMBED_MODEL" \
    "${COMPOSE[@]}" up -d --no-deps --no-build backend frontend
}

start_with_host_ollama() {
  echo
  echo "Using host Ollama at http://localhost:11434."
  echo "Model: $LLM_MODEL"
  echo "Embedding: $EMBED_MODEL"
  echo

  if compose_up_host_ollama_prebuilt; then
    return 0
  fi

  fallback_host_network_build
  compose_up_host_ollama_prebuilt
}

if [ "${USE_HOST_OLLAMA:-0}" = "1" ]; then
  start_with_host_ollama
  echo
  echo "App started with host Ollama."
elif compose_up; then
  echo
  echo "App started successfully."
else
  fallback_host_network_build
  if compose_up_prebuilt; then
    echo
    echo "App started with fallback host-network build."
  elif host_ollama_ready; then
    start_with_host_ollama
    echo
    echo "App started with fallback host-network build and host Ollama."
  else
    echo
    echo "Could not start the app."
    echo "If Docker model download is failing but host Ollama has the models, run:"
    echo "  USE_HOST_OLLAMA=1 ./start_app.sh"
    exit 1
  fi
  echo
fi

echo
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/health"
