#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/docker"

LLM_MODEL="${OLLAMA_LLM_MODEL:-llama3.2:1b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required. Install the Docker Compose plugin or docker-compose."
  exit 1
fi

port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn | awk '{print $4}' | grep -Eq "[:.]$1$"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

if [ -z "${OLLAMA_HOST_PORT:-}" ]; then
  existing_port="$(docker port rag_ollama 11434/tcp 2>/dev/null | sed -n 's/.*:\([0-9][0-9]*\)$/\1/p' | head -n 1 || true)"
  if [ -n "$existing_port" ]; then
    OLLAMA_HOST_PORT="$existing_port"
  else
    OLLAMA_HOST_PORT=11434
    for candidate in 11434 11435 11436; do
      if ! port_in_use "$candidate"; then
        OLLAMA_HOST_PORT="$candidate"
        break
      fi
    done
  fi
fi

export OLLAMA_HOST_PORT

cd "$COMPOSE_DIR"

echo "Starting Ollama container on host port $OLLAMA_HOST_PORT..."
"${COMPOSE[@]}" up -d ollama

echo "Waiting for Ollama..."
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T ollama ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

"${COMPOSE[@]}" exec -T ollama ollama list >/dev/null

pull_model() {
  local model="$1"
  local label="$2"

  echo "Pulling $label model: $model"
  for attempt in 1 2 3; do
    if "${COMPOSE[@]}" exec -T ollama ollama pull "$model"; then
      return 0
    fi
    if [ "$attempt" -lt 3 ]; then
      echo "Pull failed for $model (attempt $attempt/3). Retrying in 10 seconds..."
      sleep 10
    fi
  done

  echo "Failed to pull $model after 3 attempts."
  return 1
}

pull_model "$LLM_MODEL" "LLM"
pull_model "$EMBED_MODEL" "embedding"

echo "Installed Ollama models:"
"${COMPOSE[@]}" exec -T ollama ollama list

echo "Model setup complete."
