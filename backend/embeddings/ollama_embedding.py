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
        r = _session.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        raise OllamaEmbeddingError(
            f"Failed to call Ollama at {url}. "
            f"Check OLLAMA_BASE_URL and that Ollama is running. Error: {e}"
        ) from e


_ensured = set()


def _is_installed(requested: str, installed: set[str]) -> bool:
    if requested in installed:
        return True
    # handle "nomic-embed-text" vs "nomic-embed-text:latest"
    if ":" not in requested and f"{requested}:latest" in installed:
        return True
    return False


def ensure_model(model: str):
    """
    IMPORTANT:
    - This does NOT pull models.
    - It only verifies that the model already exists in Ollama.
    """
    if model in _ensured:
        return

    base_url = get_ollama_base_url()

    try:
        r = _session.get(f"{base_url}/api/tags", timeout=20)
        r.raise_for_status()
        tags = r.json()
        installed = set(
            m.get("name") for m in (tags.get("models") or []) if m and m.get("name")
        )
    except requests.exceptions.RequestException as e:
        raise OllamaEmbeddingError(
            f"Could not list Ollama models at {base_url}. Error: {e}"
        ) from e

    if not _is_installed(model, installed):
        raise OllamaEmbeddingError(
            f"Ollama embedding model missing (expected pre-bundled): {model}"
        )

    _ensured.add(model)


def get_embedding(text: str, model: Optional[str] = None) -> List[float]:
    """
    Returns a single embedding vector for the given text using Ollama embeddings API.
    """
    base_url = get_ollama_base_url()
    embed_model = model or get_embedding_model()

    ensure_model(embed_model)

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
    vectors: List[List[float]] = []
    for t in texts:
        vectors.append(get_embedding(t, model=model))
    return vectors


def healthcheck() -> str:
    base_url = get_ollama_base_url()
    try:
        r = _session.get(f"{base_url}/api/tags", timeout=20)
        r.raise_for_status()
        return "ok"
    except requests.exceptions.RequestException as e:
        raise OllamaEmbeddingError(
            f"Ollama healthcheck failed at {base_url}. Error: {e}"
        ) from e


if __name__ == "__main__":
    print("Ollama base URL:", get_ollama_base_url())
    print("Ollama embed model:", get_embedding_model())
    print("Health:", healthcheck())

    v = get_embedding("hello from local rag mvp")
    print("Embedding length:", len(v))
