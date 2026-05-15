import os
import sys
import math
import re
from typing import List, Dict, Any, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from chromadb import PersistentClient

# ============================================================
# FIX PYTHON IMPORT PATH
# retrieval/query_chroma.py -> ../ = backend
# ============================================================
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)
# ============================================================

from embeddings.ollama_embedding import get_embedding, get_ollama_base_url

# ======================= CONFIG ==============================
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

QUERY_TOP_K = int(os.getenv("RAG_QUERY_TOP_K", "30"))

MAX_CONTEXT_CHUNKS = int(os.getenv("RAG_MAX_CHUNKS", "2"))
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "18000"))

MAX_SOURCES = int(os.getenv("RAG_MAX_SOURCES", "10"))
INCLUDE_RAW_CHUNKS = os.getenv("RAG_INCLUDE_RAW_CHUNKS", "0").lower() in ("1", "true", "yes")

MIN_TOKEN_COVERAGE = float(os.getenv("RAG_MIN_TOKEN_COVERAGE", "0.12"))
REQUIRE_QUOTED_PHRASE = os.getenv("RAG_REQUIRE_QUOTED_PHRASE", "1").lower() in ("1", "true", "yes")

LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2:1b")

UNKNOWN_ANSWER = "I don't know based on the provided documents."

ENFORCE_UNKNOWN_AND_HIDE_SOURCES = os.getenv("RAG_HIDE_SOURCES_ON_NO_ANSWER", "1").lower() in ("1", "true", "yes")

FALLBACK_SEARCH = os.getenv("RAG_FALLBACK_SEARCH", "1").lower() in ("1", "true", "yes")
FALLBACK_MATCHES_N = int(os.getenv("RAG_FALLBACK_MATCHES_N", "3"))
FALLBACK_LINES_PER_MATCH = int(os.getenv("RAG_FALLBACK_LINES_PER_MATCH", "3"))
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

_ws = re.compile(r"\s+")
_word_re = re.compile(r"[A-Za-z0-9_]+", re.UNICODE)

_STOPWORDS = {
    "the","a","an","and","or","but","if","then","else","when","while",
    "is","are","was","were","be","been","being",
    "to","of","in","on","for","with","as","at","by","from","into","about",
    "this","that","these","those","it","its","their","they","we","you","i",
    "can","could","should","would","may","might","will","just","only",
}


def ollama_generate(prompt: str) -> str:
    base_url = get_ollama_base_url()
    url = f"{base_url}/api/generate"
    timeout = int(os.getenv("OLLAMA_HTTP_TIMEOUT", "300"))

    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": float(os.getenv("RAG_TEMPERATURE", "0.2"))},
    }

    r = _session.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return (r.json().get("response") or "").strip()


def _norm(s: str) -> str:
    # normalize whitespace + NBSP + lower
    return _ws.sub(" ", (s or "").replace("\u00A0", " ")).strip().lower()


def _tokenize(s: str) -> List[str]:
    if not s:
        return []
    toks = [t.lower() for t in _word_re.findall(s)]
    return [t for t in toks if len(t) >= 3 and t not in _STOPWORDS]


def _extract_quoted_phrases(q: str) -> List[str]:
    if not q:
        return []
    phrases = re.findall(r'"([^"]+)"', q) + re.findall(r"'([^']+)'", q)
    return [p.strip() for p in phrases if p.strip()]


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
        if not fn or fn in seen:
            continue
        seen.add(fn)
        out.append(fn)
        if len(out) >= MAX_SOURCES:
            break
    return out


def _raw_chunks_payload(selected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for t in selected:
        m = t.get("meta") or {}
        out.append({
            "text": (t.get("doc") or "").strip(),
            "distance": t.get("dist"),
            "filename": m.get("filename"),
            "document_id": m.get("document_id"),
            "chunk_id": m.get("chunk_id"),
            "page": m.get("page") or m.get("page_number"),
            "sheet_name": m.get("sheet_name") or m.get("sheet"),
        })
    return out


def _best_token_coverage(question: str, texts: List[str]) -> float:
    q_tokens = set(_tokenize(question))
    if not q_tokens:
        return 0.0
    best = 0.0
    for t in texts:
        t_tokens = set(_tokenize(t))
        if not t_tokens:
            continue
        cov = len(q_tokens.intersection(t_tokens)) / max(1, len(q_tokens))
        best = max(best, cov)
    return best


# ------------------- lightweight BM25 rerank -------------------

class _BM25:
    def __init__(self, corpus_tokens: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus_tokens
        self.N = len(corpus_tokens)
        self.avgdl = (sum(len(d) for d in corpus_tokens) / self.N) if self.N else 0.0
        self.df = {}
        for doc in corpus_tokens:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1
        self.idf = {}
        for term, df in self.df.items():
            self.idf[term] = math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: List[str]) -> List[float]:
        if not self.N:
            return []
        scores = [0.0] * self.N
        for i, doc in enumerate(self.corpus):
            if not doc:
                continue
            dl = len(doc)
            freqs = {}
            for t in doc:
                freqs[t] = freqs.get(t, 0) + 1
            s = 0.0
            for term in query_tokens:
                if term not in freqs:
                    continue
                f = freqs[term]
                idf = self.idf.get(term, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * (dl / (self.avgdl or 1.0)))
                s += idf * (f * (self.k1 + 1) / (denom or 1.0))
            scores[i] = s
        return scores


def _rrf_rank_fusion(emb_dists: List[float], bm25_scores: List[float], k: int = 60) -> List[float]:
    n = len(emb_dists)
    if n == 0:
        return []
    emb_rank = sorted(range(n), key=lambda i: emb_dists[i])                 # lower dist better
    bm_rank = sorted(range(n), key=lambda i: bm25_scores[i], reverse=True)  # higher better

    rank_pos_emb = {idx: r + 1 for r, idx in enumerate(emb_rank)}
    rank_pos_bm = {idx: r + 1 for r, idx in enumerate(bm_rank)}

    fused = [0.0] * n
    for i in range(n):
        fused[i] = (1.0 / (k + rank_pos_emb.get(i, n))) + (1.0 / (k + rank_pos_bm.get(i, n)))
    return fused


def _select_deduped_top_chunks_hybrid(
    docs: List[str],
    metas: List[dict],
    dists: List[float],
    max_chunks: int,
    question: str,
) -> List[Dict[str, Any]]:
    triples = []
    for doc, m, dist in zip(docs or [], metas or [], dists or []):
        if not doc or not doc.strip() or not m:
            continue
        triples.append({"doc": doc, "meta": m, "dist": float(dist)})

    if not triples:
        return []

    # MUST-MATCH FILTER: if quotes exist, only keep chunks containing the phrase(s)
    phrases = _extract_quoted_phrases(question)
    if phrases:
        wanted = [_norm(p) for p in phrases]
        filtered = []
        for t in triples:
            dl = _norm(t["doc"])
            if all(w in dl for w in wanted):
                filtered.append(t)
        triples = filtered or triples
    else:
        q_tokens = _tokenize(question)
        qset = set(q_tokens)
        if qset:
            # Prefer matching "strong" tokens to prevent cross-document mixing.
            # Strong token heuristic: length >= 5 OR contains any digit
            strong = {t for t in qset if len(t) >= 5 or any(ch.isdigit() for ch in t)}

            filtered = []
            for t in triples:
                dset = set(_tokenize(t["doc"]))
                if strong:
                    # require at least one strong token match
                    if strong.intersection(dset):
                        filtered.append(t)
                else:
                    # fallback: any overlap (for very short/generic queries)
                    if qset.intersection(dset):
                        filtered.append(t)

            triples = filtered or triples

    corpus_tokens = [_tokenize(t["doc"]) for t in triples]
    bm25 = _BM25(corpus_tokens)
    q_tokens = _tokenize(question)
    bm_scores = bm25.score(q_tokens) if q_tokens else [0.0] * len(triples)

    emb_dists = [t["dist"] for t in triples]
    fused = _rrf_rank_fusion(emb_dists, bm_scores)

    for t, s in zip(triples, fused):
        t["fused"] = float(s)

    triples.sort(key=lambda x: x["fused"], reverse=True)

    seen = set()
    selected = []
    for t in triples:
        key = _dedup_key(t["meta"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(t)
        if len(selected) >= max_chunks:
            break
    return selected


def _passes_confidence_gate(question: str, selected: List[Dict[str, Any]]) -> bool:
    texts = [(t.get("doc") or "") for t in selected]
    phrases = _extract_quoted_phrases(question)

    # Gate is only meaningful for non-quoted mode; quoted mode is handled separately
    if REQUIRE_QUOTED_PHRASE and phrases:
        return True

    cov = _best_token_coverage(question, texts)
    return cov >= MIN_TOKEN_COVERAGE


def _is_no_answer_text(answer: str) -> bool:
    if answer is None:
        return True
    a = answer.strip()
    if not a:
        return True
    if a == UNKNOWN_ANSWER or a.startswith(UNKNOWN_ANSWER):
        return True

    al = a.lower()
    patterns = [
        "no answer", "no relevant information", "no relevant data",
        "not present", "not available", "not mentioned", "not referenced",
        "no mention", "no reference", "no direct reference",
        "does not include", "do not include", "doesn't include", "don't include",
        "no information", "not found", "cannot find", "can't find",
        "insufficient information", "no specific", "no details",
        "unable to provide", "unable to determine", "unknown based on",
    ]
    return any(p in al for p in patterns)


def _summary_from_exact_line_answer(answer_text: str) -> str:
    """
    Creates a tiny, non-hallucinated summary from the exact matched ROW-style line.
    Works best for Excel row lines like:
    ROW=5: Transaction_Date=...; Description=...; Debit (£)=...; ...; Account_Category=...
    """
    lines = [ln.strip() for ln in (answer_text or "").splitlines() if ln.strip()]
    if not lines:
        return ""

    first = lines[0]

    # Remove leading "ROW=...:" if present
    if first.upper().startswith("ROW=") and ":" in first:
        first = first.split(":", 1)[1].strip()

    # Parse key=value; pairs separated by ';'
    kv = {}
    for part in first.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        kv[k.strip()] = v.strip()

    date = kv.get("Transaction_Date") or kv.get("Date") or ""
    desc = kv.get("Description") or kv.get("Narration") or ""
    debit = kv.get("Debit (£)") or kv.get("Debit") or ""
    credit = kv.get("Credit (£)") or kv.get("Credit") or ""
    cat = kv.get("Account_Category") or kv.get("Category") or ""

    # Build a short factual sentence (no extra info)
    head = cat + " transaction" if cat else "Transaction"
    if date:
        head += f" on {date}"
    if desc:
        head += f" for {desc}"

    money_bits = []
    if debit:
        money_bits.append(f"debit £{debit}")
    if credit:
        money_bits.append(f"credit £{credit}")

    if money_bits:
        head += f" ({', '.join(money_bits)})."
    else:
        head += "."

    if len(lines) > 1:
        head += f" {len(lines)} matching lines found."

    return head


def _best_lines_for_query(doc: str, query: str, max_lines: int = 3) -> str:
    q = set(_tokenize(query))
    lines = [ln.strip() for ln in (doc or "").splitlines() if ln.strip()]
    scored = []
    for ln in lines:
        s = len(q.intersection(set(_tokenize(ln))))
        if s > 0:
            scored.append((s, ln))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [ln for _, ln in scored[:max_lines]]
    if not top:
        top = lines[:max_lines]
    return "\n".join(top)


def _fallback_matches(selected: List[Dict[str, Any]], question: str, n: int) -> List[Dict[str, Any]]:
    out = []
    for t in (selected or [])[:n]:
        m = t.get("meta") or {}
        out.append({
            "filename": m.get("filename"),
            "snippet": _best_lines_for_query(t.get("doc") or "", question, FALLBACK_LINES_PER_MATCH),
            "distance": t.get("dist"),
            "document_id": m.get("document_id"),
            "page": m.get("page") or m.get("page_number"),
            "sheet_name": m.get("sheet_name") or m.get("sheet"),
        })
    return out

def _llm_summary_for_exact_line(answer_text: str) -> str:
    answer_text = (answer_text or "").strip()
    if not answer_text:
        return ""

    prompt = f"""
Convert this extracted transaction row into a 1–2 sentence summary.
Rules:
- Use ONLY the information in the row.
- Do NOT ask for more text.
- Do NOT mention sources/filenames/chunks/ROW.
Row:
{answer_text}

Summary:
""".strip()

    s = ollama_generate(prompt).strip()

    bad = (s or "").lower()
    if ("no extracted text" in bad) or ("please provide" in bad):
        return ""

    return s




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

    selected = _select_deduped_top_chunks_hybrid(docs, metas, dists, MAX_CONTEXT_CHUNKS, question)
    if not selected:
        return {"answer": UNKNOWN_ANSWER, "sources": [], **({"raw_chunks": []} if INCLUDE_RAW_CHUNKS else {})}

    # QUOTED MODE: deterministic extraction + (optional) fallback matches; NEVER call LLM here
    phrases = _extract_quoted_phrases(question)
    if phrases:
        target = _norm(phrases[0])
        kept = []
        for t in selected:
            lines = (t["doc"] or "").splitlines()
            hit_lines = [ln for ln in lines if target in _norm(ln)]
            if hit_lines:
                kept.append({"doc": "\n".join(hit_lines), "meta": t["meta"], "dist": t["dist"]})

        if kept:
            answer_text = "\n".join(k["doc"] for k in kept)
            summary_text = _llm_summary_for_exact_line(answer_text)

            payload = {
                "answer": answer_text,
                "sources": _unique_sources(kept),
            }

            # Only include summary when we actually have one
            if summary_text:
                payload["summary"] = summary_text

            if INCLUDE_RAW_CHUNKS:
                payload["raw_chunks"] = _raw_chunks_payload(kept)

            return payload

        if FALLBACK_SEARCH:
            return {
                "answer": UNKNOWN_ANSWER,
                "sources": [],
                "matches": _fallback_matches(selected, question, FALLBACK_MATCHES_N),
                **({"raw_chunks": []} if INCLUDE_RAW_CHUNKS else {}),
            }

        return {"answer": UNKNOWN_ANSWER, "sources": [], **({"raw_chunks": []} if INCLUDE_RAW_CHUNKS else {})}

    # NON-QUOTED MODE: apply confidence gate before calling LLM
    if not _passes_confidence_gate(question, selected):
        return {"answer": UNKNOWN_ANSWER, "sources": [], **({"raw_chunks": []} if INCLUDE_RAW_CHUNKS else {})}

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

    answer = ollama_generate(prompt).strip() or UNKNOWN_ANSWER
    is_no_answer = _is_no_answer_text(answer)

    if ENFORCE_UNKNOWN_AND_HIDE_SOURCES and is_no_answer:
        answer = UNKNOWN_ANSWER

    resp = {
        "answer": answer,
        "sources": [] if (ENFORCE_UNKNOWN_AND_HIDE_SOURCES and is_no_answer) else _unique_sources(selected),
    }

    if INCLUDE_RAW_CHUNKS:
        resp["raw_chunks"] = [] if (ENFORCE_UNKNOWN_AND_HIDE_SOURCES and is_no_answer) else _raw_chunks_payload(selected)

    return resp


if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or type 'exit'): ").strip()
        if q.lower() in ("exit", "quit"):
            break
        out = query_rag(q)
        print("\nANSWER:\n", out.get("answer"))
        print("\nSOURCES:\n", out.get("sources"))
        if "matches" in out:
            print("\nMATCHES:\n", out.get("matches"))
