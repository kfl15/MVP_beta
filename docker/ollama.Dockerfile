# docker/ollama.Dockerfile
FROM ollama/ollama:latest

# Bake models into the image at build time
RUN set -eux; \
    ollama serve & \
    pid=$!; \
    for i in $(seq 1 60); do \
      ollama list >/dev/null 2>&1 && break; \
      sleep 1; \
    done; \
    ollama pull llama3.2:1b-instruct-q4_K_M; \
    ollama pull nomic-embed-text; \
    kill $pid; \
    wait $pid || true
