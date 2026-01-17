import os
import sys
from typing import List, Dict, Any
from chromadb import PersistentClient
from embeddings.ollama_embedding import ensure_model
import requests
import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# FIX PYTHON IMPORT PATH
# ============================================================
BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
PROJECT_ROOT = os.path.abspath(
    os.path.join(BACKEND_ROOT, "..")
)
sys.path.insert(0, BACKEND_ROOT)
# ============================================================

from embeddings.ollama_embedding import get_embedding, get_ollama_base_url

# ======================= CONFIG ==============================
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

TOP_K = 5
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "mistral:7b-instruct-q4_K_M")
# ============================================================


def build_context(docs: List[str], max_chars: int = 12000) -> str:
    """
    Concatenate retrieved chunks into a single context window (simple MVP).
    """
    context = []
    total = 0
    for d in docs:
        if not d:
            continue
        if total + len(d) > max_chars:
            break
        context.append(d)
        total += len(d)
    return "\n\n---\n\n".join(context)

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

def ollama_generate(prompt: str) -> str:
    base_url = get_ollama_base_url()
    url = f"{base_url}/api/generate"
    timeout = int(os.getenv("OLLAMA_HTTP_TIMEOUT", "300"))

    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }

    t0 = time.time()
    r = _session.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()

def to_pointwise_answer(answer_text: str, citations: list) -> list:
    """
    Convert an LLM answer into pointwise JSON.
    MVP rule: each point receives the same citation list (TOP_K retrieved chunks),
    because we don't yet have deterministic per-point chunk attribution.
    """
    if not answer_text:
        return []

    lines = [ln.strip() for ln in answer_text.splitlines() if ln.strip()]

    # If model returned a single paragraph, convert to one point
    if len(lines) == 1:
        return [{
            "point_id": 1,
            "text": lines[0],
            "sources": citations or [],
        }]

    points = []
    point_id = 1
    for ln in lines:
        # Clean common bullet prefixes
        cleaned = ln.lstrip("-•*").strip()
        if not cleaned:
            continue
        points.append({
            "point_id": point_id,
            "text": cleaned,
            "sources": citations or [],
        })
        point_id += 1

    return points



def query_rag(question: str) -> Dict[str, Any]:
    """
    1) Embed question
    2) Query Chroma
    3) Build context
    4) Ask Ollama to answer strictly from context
    5) Return answer + citations
    """
    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    q_emb = get_embedding(question)
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"]
    )

    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]

    if not docs:
        return {"answer": [{
            "point_id": 1,
            "text": "No relevant context found.",
            "sources": []
        }]}

    context = build_context(docs)

    # Build citations (filename + chunk info). Page not available yet in current loader.
    citations = []
    for m in metas:
        if not m:
            continue
        citations.append({
            "filename": m.get("filename"),
            "document_id": m.get("document_id"),
            "chunk_id": m.get("chunk_id"),
        })

    prompt = f"""
        You are a helpful assistant.
        Answer using ONLY the provided context.
        If the answer is not in the context, say: "I don't know based on the provided documents."
        No introductions. No filler. Be precise.

        Output format:
        - Write the answer as bullet points.
        - Each bullet must be a complete, standalone point.
        - Keep it short (max 6 bullets).

        Context:
        {context}

        Question:
        {question}

        Answer:
        """.strip()


    answer = ollama_generate(prompt)

    points = to_pointwise_answer(answer, citations)
    return {"answer": points}


if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or type 'exit'): ").strip()
        if q.lower() in ("exit", "quit"):
            break

        out = query_rag(q)
        print("\nANSWER:\n", out["answer"])
        print("\nSOURCES:")
        for p in out["answer"]:
            for s in p.get("sources", []):
                print("-", s)
