#!/usr/bin/env bash
set -euo pipefail

LLM_MODEL="${OLLAMA_LLM_MODEL:-qwen2.5:0.5b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required but was not found."
  echo "Install Ollama locally first: https://ollama.com/download"
  exit 1
fi

if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama is not reachable at http://localhost:11434."
  echo "Start Ollama first, then rerun this script."
  exit 1
fi

echo "Pulling LLM model: $LLM_MODEL"
ollama pull "$LLM_MODEL"

echo "Pulling embedding model: $EMBED_MODEL"
ollama pull "$EMBED_MODEL"

echo "Installed Ollama models:"
ollama list

echo "Local Ollama model setup complete."
