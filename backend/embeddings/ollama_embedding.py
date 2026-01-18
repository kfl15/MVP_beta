import os
import requests
from typing import List, Optional
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OllamaEmbeddingError(RuntimeError):
    pass


def get_ollama_base_url() -> str:
    # Docker compose will use http://ollama:11434 inside the backend container.
    # Local dev on host will typically use http://localhost:11434.
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def get_embedding_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


# def _post_json(url: str, payload: dict, timeout: int = 120) -> dict:
#     try:
#         r = requests.post(url, json=payload, timeout=timeout)
#         r.raise_for_status()
#         return r.json()
#     except requests.exceptions.RequestException as e:
#         raise OllamaEmbeddingError(
#             f"Failed to call Ollama at {url}. "
#             f"Check OLLAMA_BASE_URL and that Ollama is running. Error: {e}"
#         ) from e

# Create one session for the whole module (reuses connections + retries)
_session = requests.Session()
_retry = Retry(
    total=int(os.getenv("OLLAMA_HTTP_RETRIES", "3")),
    backoff_factor=float(os.getenv("OLLAMA_HTTP_BACKOFF", "0.5")),
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET", "POST"),
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)

def _post_json(url: str, payload: dict, timeout: int = 180) -> dict:
    timeout = int(os.getenv("OLLAMA_HTTP_TIMEOUT", str(timeout)))
    try:
        t0 = time.time()
        r = _session.post(url, json=payload, timeout=timeout)
        # If still not OK after retries, raise here
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        raise OllamaEmbeddingError(
            f"Failed to call Ollama at {url}. "
            f"Check OLLAMA_BASE_URL and that Ollama is running. Error: {e}"
        ) from e

_ensured = set()

def ensure_model(model: str):
    if model in _ensured:
        return
    base_url = get_ollama_base_url()
    requests.post(
        f"{base_url}/api/pull",
        json={"name": model},
        timeout=600,
    )
    _ensured.add(model)


def get_embedding(text: str, model: Optional[str] = None) -> List[float]:
    """
    Returns a single embedding vector for the given text using Ollama embeddings API.
    Interface intentionally matches your previous get_openai_embedding.get_embedding(text).
    """
    base_url = get_ollama_base_url()
    embed_model = model or get_embedding_model()

    ensure_model(embed_model)

    # Ollama embeddings endpoint
    # Docs: /api/embeddings  payload: { "model": "...", "prompt": "..." }
    url = f"{base_url}/api/embeddings"
    payload = {"model": embed_model, "prompt": text}

    data = _post_json(url, payload)

    emb = data.get("embedding")
    if not emb or not isinstance(emb, list):
        raise OllamaEmbeddingError(
            f"Ollama returned no embedding. Response keys: {list(data.keys())}"
        )
    return emb


def get_embeddings(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    """
    Convenience helper to embed many texts. Ollama embeddings API is single-prompt,
    so we call it in a loop (kept simple for MVP).
    """
    vectors: List[List[float]] = []
    for t in texts:
        vectors.append(get_embedding(t, model=model))
    return vectors


def healthcheck() -> str:
    """
    Lightweight check that Ollama server is reachable.
    """
    base_url = get_ollama_base_url()
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=20)
        r.raise_for_status()
        return "ok"
    except requests.exceptions.RequestException as e:
        raise OllamaEmbeddingError(
            f"Ollama healthcheck failed at {base_url}. Error: {e}"
        ) from e


if __name__ == "__main__":
    # Quick local test:
    # 1) Start Ollama
    # 2) Run: python backend/embeddings/ollama_embedding.py
    print("Ollama base URL:", get_ollama_base_url())
    print("Ollama embed model:", get_embedding_model())
    print("Health:", healthcheck())

    v = get_embedding("hello from local rag mvp")
    print("Embedding length:", len(v))
