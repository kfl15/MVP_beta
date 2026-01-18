import os
import sys
from typing import List, Dict, Any, Optional, Tuple
from chromadb import PersistentClient
from embeddings.ollama_embedding import ensure_model
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re

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

TOP_K = int(os.getenv("RAG_TOP_K", "20"))
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "mistral:7b-instruct-q4_K_M")

# >>> ADDED: limit how many distinct documents/files we show as sources (keep TOP_K high)
CITATION_DOC_LIMIT = int(os.getenv("CITATION_DOC_LIMIT", "5"))  # default 5

# >>> ADDED: how many top chunks to scan when extracting the "exact line"
EVIDENCE_SCAN_CHUNKS = int(os.getenv("EVIDENCE_SCAN_CHUNKS", "6"))
EVIDENCE_MAX_CHARS = int(os.getenv("EVIDENCE_MAX_CHARS", "400"))
# ============================================================


def build_context(docs: List[str], max_chars: int = 30000) -> str:
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

    r = _session.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


# >>> ADDED: simple keyword extraction + line scoring to pick an "exact line"
_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "by", "as",
    "is", "are", "was", "were", "be", "been", "it", "this", "that", "these", "those",
    "i", "you", "we", "they", "he", "she", "them", "his", "her", "our", "your",
    "from", "at", "into", "than", "then", "but", "not", "no", "yes"
}

def _question_tokens(question: str) -> List[str]:
    toks = re.findall(r"[a-zA-Z0-9]+", (question or "").lower())
    toks = [t for t in toks if len(t) >= 3 and t not in _STOPWORDS]
    return toks[:25]  # cap to keep scoring stable


def extract_best_line(
    question: str,
    docs: List[str],
    metas: List[dict],
    dists: List[float],
    scan_chunks: int = EVIDENCE_SCAN_CHUNKS,
    max_chars: int = EVIDENCE_MAX_CHARS,
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Pick the single best supporting *line* from the retrieved chunks.
    Deterministic heuristic (no LLM):
      - sort chunks by distance (best first)
      - scan first N chunks
      - split chunk into lines
      - score each line by keyword overlap with question tokens
      - return best line + its source (filename/document_id/chunk_id/distance)
    """
    if not docs or not metas or not dists:
        return None, None

    qtoks = _question_tokens(question)

    # Pair up, keep only non-empty docs
    triples = []
    for doc, m, dist in zip(docs, metas, dists):
        if not doc or not doc.strip() or not m:
            continue
        triples.append((dist, doc, m))

    if not triples:
        return None, None

    triples.sort(key=lambda x: x[0])  # smaller distance = closer
    triples = triples[: max(1, scan_chunks)]

    best = None  # (score, dist, line, meta)
    for dist, doc, m in triples:
        lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
        if not lines:
            continue

        for ln in lines:
            ln_l = ln.lower()
            if qtoks:
                score = sum(1 for t in qtoks if t in ln_l)
            else:
                # if question tokenization yields nothing, fallback to first good line of top chunk
                score = 0

            cand = (score, -dist, ln, m, dist)
            if best is None or cand > best:
                best = cand

    if best is None:
        # fallback: first line from best chunk
        dist, doc, m = triples[0]
        first_line = next((ln.strip() for ln in doc.splitlines() if ln.strip()), None)
        if not first_line:
            return None, None
        return first_line[:max_chars], {
            "filename": m.get("filename"),
            "document_id": m.get("document_id"),
            "chunk_id": m.get("chunk_id"),
            "distance": dist,
        }

    _, _, line, m, dist = best
    line = line.strip()
    if len(line) > max_chars:
        line = line[:max_chars].rstrip() + "..."
    return line, {
        "filename": m.get("filename"),
        "document_id": m.get("document_id"),
        "chunk_id": m.get("chunk_id"),
        "distance": dist,
    }


def to_pointwise_answer(answer_text: str, citations: list, evidence_line: Optional[str], evidence_source: Optional[dict]) -> list:
    """
    Convert an LLM answer into pointwise JSON.

    MVP rule: each point receives the same citation list (we don't have per-point attribution yet).

    >>> CHANGED: also attach the same evidence_line + evidence_source to each point,
    so UI can render: Answer -> Exact line -> Sources.
    """
    if not answer_text:
        return []

    lines = [ln.strip() for ln in answer_text.splitlines() if ln.strip()]

    def _mk_point(pid: int, txt: str) -> dict:
        return {
            "point_id": pid,
            "text": txt,
            "evidence_line": evidence_line or "",
            "evidence_source": evidence_source or {},
            "sources": citations or [],
        }

    if len(lines) == 1:
        return [_mk_point(1, lines[0])]

    points = []
    point_id = 1
    for ln in lines:
        cleaned = ln.lstrip("-•*").strip()
        if not cleaned:
            continue
        points.append(_mk_point(point_id, cleaned))
        point_id += 1

    return points


def query_rag(question: str) -> Dict[str, Any]:
    """
    1) Embed question
    2) Query Chroma
    3) Build context
    4) Ask Ollama to answer strictly from context
    5) Return answer + citations + exact supporting line
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
    dists = (results.get("distances") or [[]])[0]  # keep aligned with docs/metas

    docs_nonempty = [d for d in docs if d and d.strip()]
    if not docs_nonempty:
        return {"answer": [{
            "point_id": 1,
            "text": "No relevant context found.",
            "evidence_line": "",
            "evidence_source": {},
            "sources": []
        }]}

    context = build_context(docs_nonempty)

    # >>> ADDED: extract the "exact line" deterministically from retrieved chunks
    evidence_line, evidence_source = extract_best_line(
        question=question,
        docs=docs,
        metas=metas,
        dists=dists,
        scan_chunks=EVIDENCE_SCAN_CHUNKS,
        max_chars=EVIDENCE_MAX_CHARS,
    )

    # Citations limited to N distinct docs (as you already implemented)
    scored = []
    for m, dist in zip(metas, dists):
        if not m:
            continue
        scored.append((dist, m))

    scored.sort(key=lambda x: x[0])

    seen_docs = set()
    citations = []
    for dist, m in scored:
        doc_id = m.get("document_id")
        if not doc_id or doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)
        citations.append({
            "filename": m.get("filename"),
            "document_id": doc_id,
            "chunk_id": m.get("chunk_id"),
        })
        if len(citations) >= CITATION_DOC_LIMIT:
            break

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

    # >>> CHANGED: attach evidence_line + evidence_source to each point
    points = to_pointwise_answer(answer, citations, evidence_line, evidence_source)
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
