import os
import sys
from typing import List, Dict, Any, Tuple
from chromadb import PersistentClient
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# FIX PYTHON IMPORT PATH
# ============================================================
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)
# ============================================================

from embeddings.ollama_embedding import get_embedding, get_ollama_base_url

# ======================= CONFIG ==============================
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

QUERY_TOP_K = int(os.getenv("RAG_QUERY_TOP_K", "12"))
MAX_CONTEXT_CHUNKS = int(os.getenv("RAG_MAX_CHUNKS", "4"))
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "18000"))

MAX_SOURCES = int(os.getenv("RAG_MAX_SOURCES", "10"))

INCLUDE_RAW_CHUNKS = os.getenv("RAG_INCLUDE_RAW_CHUNKS", "0").lower() in ("1", "true", "yes")

LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "mistral:7b-instruct-q4_K_M")

UNKNOWN_ANSWER = "I don't know based on the provided documents."
# ============================================================


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
        "options": {
            "temperature": float(os.getenv("RAG_TEMPERATURE", "0.2")),
        },
    }

    r = _session.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


def _dedup_key(meta: dict) -> Tuple[str, str]:
    doc_id = str(meta.get("document_id") or "")
    page = meta.get("page") or meta.get("page_number")
    if page is not None:
        return (doc_id, f"page:{page}")

    sheet = meta.get("sheet_name") or meta.get("sheet")
    if sheet:
        return (doc_id, f"sheet:{sheet}")

    chunk_id = meta.get("chunk_id")
    return (doc_id, f"chunk:{chunk_id}")


def _select_deduped_top_chunks(
    docs: List[str],
    metas: List[dict],
    dists: List[float],
    max_chunks: int,
) -> List[Dict[str, Any]]:
    triples = []
    for doc, m, dist in zip(docs or [], metas or [], dists or []):
        if not doc or not doc.strip() or not m:
            continue
        triples.append({"doc": doc, "meta": m, "dist": float(dist)})

    if not triples:
        return []

    triples.sort(key=lambda x: x["dist"])

    seen = set()
    deduped = []
    for t in triples:
        key = _dedup_key(t["meta"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
        if len(deduped) >= max_chunks:
            break

    return deduped


def _build_context(selected: List[Dict[str, Any]], max_chars: int) -> str:
    parts = []
    total = 0
    for i, t in enumerate(selected, start=1):
        doc = (t.get("doc") or "").strip()
        if not doc:
            continue
        if total + len(doc) > max_chars:
            break
        parts.append(f"[CHUNK {i}]\n{doc}")
        total += len(doc)
    return "\n\n---\n\n".join(parts)


def _unique_sources(selected: List[Dict[str, Any]]) -> List[str]:
    seen = set()
    out = []
    for t in selected:
        m = t.get("meta") or {}
        fn = (m.get("filename") or "").strip()
        if not fn:
            continue
        if fn in seen:
            continue
        seen.add(fn)
        out.append(fn)
        if len(out) >= MAX_SOURCES:
            break
    return out


def _raw_chunks_payload(selected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks = []
    for t in selected:
        m = t.get("meta") or {}
        chunks.append({
            "text": (t.get("doc") or "").strip(),
            "distance": t.get("dist"),
            "filename": m.get("filename"),
            "document_id": m.get("document_id"),
            "chunk_id": m.get("chunk_id"),
            "page": m.get("page") or m.get("page_number"),
            "sheet_name": m.get("sheet_name") or m.get("sheet"),
        })
    return chunks


def query_rag(question: str) -> Dict[str, Any]:
    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    q_emb = get_embedding(question)

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=QUERY_TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    dists = (results.get("distances") or [[]])[0]

    selected = _select_deduped_top_chunks(docs, metas, dists, MAX_CONTEXT_CHUNKS)
    if not selected:
        return {
            "answer": UNKNOWN_ANSWER,
            "sources": [],
            **({"raw_chunks": []} if INCLUDE_RAW_CHUNKS else {}),
        }

    context = _build_context(selected, MAX_CONTEXT_CHARS)

    prompt = f"""
You are a private-business assistant for firms (e.g., accounting/bookkeeping).
Answer using ONLY the provided context.

CRITICAL RULES:
- Produce ONE final answer (single coherent response).
- Synthesize and summarize; DO NOT repeat or quote large chunks verbatim.
- DO NOT mention filenames, sources, or "chunks" in the answer.
- DO NOT add headings like "Answer:".
- If the answer is not explicitly supported by the context, reply EXACTLY:
{UNKNOWN_ANSWER}

STYLE:
- Clear, concise, professional.
- 3-6 sentences maximum unless the user asks for more detail.
- Avoid redundancy.

Context:
{context}

Question:
{question}

Final Answer:
""".strip()

    answer = ollama_generate(prompt).strip()
    if not answer:
        answer = UNKNOWN_ANSWER

    # ✅ KEY FIX: if answer is "I don't know", then NO SOURCES
    is_unknown = answer.strip() == UNKNOWN_ANSWER

    resp = {
        "answer": answer,
        "sources": [] if is_unknown else _unique_sources(selected),
    }

    if INCLUDE_RAW_CHUNKS:
        resp["raw_chunks"] = [] if is_unknown else _raw_chunks_payload(selected)

    return resp


if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or type 'exit'): ").strip()
        if q.lower() in ("exit", "quit"):
            break

        out = query_rag(q)
        print("\nANSWER:\n", out.get("answer"))
        print("\nSOURCES:\n", out.get("sources"))
        if "raw_chunks" in out:
            print("\nRAW_CHUNKS:\n", len(out["raw_chunks"]))
