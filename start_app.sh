#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/docker"
LLM_MODEL="${OLLAMA_LLM_MODEL:-qwen2.5:0.5b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required. Install the Docker Compose plugin or docker-compose."
  exit 1
fi

host_has_model() {
  local model="$1"
  curl -fsS http://localhost:11434/api/tags \
    | grep -Eq "\"name\":\"${model}\"|\"name\":\"${model}:latest\"|\"model\":\"${model}\"|\"model\":\"${model}:latest\""
}

check_local_ollama() {
  if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama is not reachable at http://localhost:11434."
    echo "Start local Ollama and run ./setup_models.sh first."
    exit 1
  fi

  if ! host_has_model "$LLM_MODEL"; then
    echo "Missing local Ollama LLM model: $LLM_MODEL"
    echo "Run: OLLAMA_LLM_MODEL=$LLM_MODEL ./setup_models.sh"
    exit 1
  fi

  if ! host_has_model "$EMBED_MODEL"; then
    echo "Missing local Ollama embedding model: $EMBED_MODEL"
    echo "Run: OLLAMA_EMBED_MODEL=$EMBED_MODEL ./setup_models.sh"
    exit 1
  fi
}

compose_up() {
  cd "$COMPOSE_DIR"
  OLLAMA_LLM_MODEL="$LLM_MODEL" \
    OLLAMA_EMBED_MODEL="$EMBED_MODEL" \
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
}

compose_up_prebuilt() {
  cd "$COMPOSE_DIR"
  OLLAMA_LLM_MODEL="$LLM_MODEL" \
    OLLAMA_EMBED_MODEL="$EMBED_MODEL" \
    "${COMPOSE[@]}" up -d --no-build
}

check_local_ollama

if compose_up; then
  echo
  echo "App started successfully."
else
  fallback_host_network_build
  compose_up_prebuilt
  echo
  echo "App started with fallback host-network build."
fi

echo
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/health"
