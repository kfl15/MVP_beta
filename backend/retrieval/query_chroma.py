import os
import sys
from typing import Any, Dict, List

import requests
from chromadb import PersistentClient
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)

from embeddings.ollama_embedding import get_embedding, get_ollama_base_url


CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

QUERY_TOP_K = int(os.getenv("RAG_QUERY_TOP_K", "5"))
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))
MAX_SOURCES = int(os.getenv("RAG_MAX_SOURCES", "10"))
INCLUDE_RAW_CHUNKS = os.getenv("RAG_INCLUDE_RAW_CHUNKS", "0").lower() in ("1", "true", "yes")

LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:0.5b")
UNKNOWN_ANSWER = "I don't know based on the OCR text."

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
        "options": {"temperature": float(os.getenv("RAG_TEMPERATURE", "0.1"))},
    }

    r = _session.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return (r.json().get("response") or "").strip()


def _source_label(meta: Dict[str, Any]) -> str:
    filename = meta.get("filename") or "unknown"
    page = meta.get("page_number")
    image_name = meta.get("image_name")
    if page:
        return f"{filename} page {page}"
    if image_name and image_name != filename:
        return f"{filename} / {image_name}"
    return filename


def _unique_sources(selected: List[Dict[str, Any]]) -> List[str]:
    seen = set()
    out = []
    for item in selected:
        label = _source_label(item.get("meta") or {})
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= MAX_SOURCES:
            break
    return out


def _ocr_items(selected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for item in selected:
        meta = item.get("meta") or {}
        items.append({
            "filename": meta.get("filename"),
            "image_name": meta.get("image_name"),
            "page_number": meta.get("page_number"),
            "text_file_name": meta.get("text_file_name"),
            "text_file_path": meta.get("text_file_path"),
            "text": item.get("doc") or "",
            "distance": item.get("dist"),
            "document_id": meta.get("document_id"),
            "ocr_avg_confidence": meta.get("ocr_avg_confidence"),
        })
    return items


def _read_saved_text(item: Dict[str, Any]) -> str:
    meta = item.get("meta") or {}
    text_file_path = meta.get("text_file_path")
    if text_file_path:
        path = os.path.join(PROJECT_ROOT, text_file_path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass
    return item.get("doc") or ""


def _build_ocr_context(selected: List[Dict[str, Any]]) -> str:
    parts = []
    total = 0
    for i, item in enumerate(selected, start=1):
        meta = item.get("meta") or {}
        text = _read_saved_text(item).strip()
        if not text:
            continue
        header = f"[OCR TEXT {i} | {_source_label(meta)}]"
        block = f"{header}\n{text}"
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total += len(block)
    return "\n\n---\n\n".join(parts).strip()


def _select_results(docs: List[str], metas: List[dict], dists: List[float]) -> List[Dict[str, Any]]:
    selected = []
    for doc, meta, dist in zip(docs or [], metas or [], dists or []):
        if not meta:
            continue
        selected.append({
            "doc": doc or "",
            "meta": meta,
            "dist": float(dist) if dist is not None else None,
        })
    return selected[:QUERY_TOP_K]


def _interpret_ocr(question: str, context: str) -> str:
    if not context.strip():
        return UNKNOWN_ANSWER

    prompt = f"""
You are reading OCR text extracted from uploaded images or PDF pages.
Write a useful short gist of what can be understood from the OCR text below.
Also answer the user's question when the OCR text gives enough evidence.

Rules:
- Do not invent missing words, numbers, dates, names, or amounts.
- Use only the OCR text as evidence.
- If OCR text is broken, uncertain, or incomplete, still explain the visible parts and clearly mark what is unclear.
- Do not assign meanings to numbers unless the OCR text clearly labels them.
- Prefer cautious prose over field extraction when the OCR text is noisy.
- Do not say "{UNKNOWN_ANSWER}" when OCR text exists and at least some meaning can be understood.
- Say "{UNKNOWN_ANSWER}" only when the OCR text is empty or has no understandable relevant content.
- Keep the answer concise and practical.

OCR text:
{context}

User question:
{question}

Answer:
""".strip()

    return ollama_generate(prompt).strip() or UNKNOWN_ANSWER


def query_rag(question: str) -> Dict[str, Any]:
    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    q_emb = get_embedding(question)
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=QUERY_TOP_K,
        where={"source_type": {"$in": ["image", "pdf_page"]}},
        include=["documents", "metadatas", "distances"],
    )

    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    dists = (results.get("distances") or [[]])[0]
    selected = _select_results(docs, metas, dists)

    if not selected:
        payload = {
            "answer": f"No OCR text found.\n\nLLM thinks:\n{UNKNOWN_ANSWER}",
            "ocr_text": "",
            "interpretation": UNKNOWN_ANSWER,
            "sources": [],
            "ocr_items": [],
        }
        if INCLUDE_RAW_CHUNKS:
            payload["raw_chunks"] = []
        return payload

    context = _build_ocr_context(selected)
    exact_text = _read_saved_text(selected[0])
    display_text = exact_text if exact_text else "No OCR text found."
    interpretation = _interpret_ocr(question, exact_text)
    answer = f"{display_text}\n\nLLM thinks:\n{interpretation}"

    payload = {
        "answer": answer,
        "ocr_text": display_text,
        "ocr_context": context,
        "interpretation": interpretation,
        "sources": _unique_sources(selected),
        "ocr_items": _ocr_items(selected),
    }

    if INCLUDE_RAW_CHUNKS:
        payload["raw_chunks"] = _ocr_items(selected)

    return payload


if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or type 'exit'): ").strip()
        if q.lower() in ("exit", "quit"):
            break
        out = query_rag(q)
        print("\nANSWER:\n", out.get("answer"))
        print("\nSOURCES:\n", out.get("sources"))
