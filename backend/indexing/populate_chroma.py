import os
import sys
import uuid
import shutil
import argparse
from typing import List, Dict, Any, Tuple
from chromadb import PersistentClient

# ============================================================
# PYTHON IMPORT PATH
# ============================================================
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)
# ============================================================

from loaders.pdf_loader import extract_pages_from_pdf
from loaders.txt_loader import extract_text_from_txt
from loaders.excel_loader import extract_excel_chunks
from loaders.docx_loader import load_docx
from embeddings.ollama_embedding import get_embedding

# ======================= CONFIG ==============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

# Generic chunking for txt/docx/pdf-page
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1400"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))

# Excel-specific
EXCEL_ROWS_PER_CHUNK = int(os.getenv("RAG_EXCEL_ROWS_PER_CHUNK", "100"))
EXCEL_MAX_ROWS_PER_SHEET = int(os.getenv("RAG_EXCEL_MAX_ROWS_PER_SHEET", "0"))  # 0 = no cap

SUPPORTED_EXTS = {".pdf", ".txt", ".xlsx", ".xls", ".docx"}
# ============================================================


def chunk_text(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start += max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    return chunks


def reset_chroma():
    if not os.path.exists(CHROMA_DIR):
        return
    for name in os.listdir(CHROMA_DIR):
        p = os.path.join(CHROMA_DIR, name)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
    print("🧹 Chroma store cleared (volume kept).")



def _sanitize_meta(meta: dict) -> dict:
    clean = {}
    for k, v in (meta or {}).items():
        if v is None:
            continue
        if isinstance(v, (bool, int, float, str)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def _add_chunks(collection, document_id: str, filename: str, ext: str, chunk_records):
    for idx, (chunk_text_str, extra_meta) in enumerate(chunk_records):
        embedding = get_embedding(chunk_text_str)

        meta = {
            "document_id": document_id,
            "filename": filename,
            "chunk_id": idx,
            "file_ext": ext,
        }
        meta.update(extra_meta or {})
        meta = _sanitize_meta(meta)

        collection.add(
            ids=[f"{document_id}_{idx}"],
            documents=[chunk_text_str],
            embeddings=[embedding],
            metadatas=[meta],
        )

def index_file(file_path: str, collection):
    document_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename.lower())[1]

    print(f"📄 Indexing: {filename}")

    chunk_records: List[Tuple[str, Dict[str, Any]]] = []

    if ext == ".pdf":
        pages = extract_pages_from_pdf(file_path)
        if not pages:
            print(f"⚠️ No text extracted from: {filename}")
            return

        for page_num, page_text in pages:
            page_chunks = chunk_text(page_text)
            for j, c in enumerate(page_chunks):
                chunk_records.append((c, {"page_number": page_num, "page_chunk": j}))

    elif ext == ".txt":
        text = extract_text_from_txt(file_path)
        for j, c in enumerate(chunk_text(text)):
            chunk_records.append((c, {"page_number": None, "page_chunk": j}))

    elif ext in (".xlsx", ".xls"):
        excel_chunks = extract_excel_chunks(
            file_path,
            rows_per_chunk=EXCEL_ROWS_PER_CHUNK,
            max_rows_per_sheet=EXCEL_MAX_ROWS_PER_SHEET,
        )
        for j, item in enumerate(excel_chunks):
            txt = (item.get("text") or "").strip()
            meta = item.get("meta") or {}
            if txt:
                meta["excel_chunk"] = j
                chunk_records.append((txt, meta))

    elif ext == ".docx":
        text = load_docx(file_path)
        for j, c in enumerate(chunk_text(text)):
            chunk_records.append((c, {"page_number": None, "page_chunk": j}))

    else:
        print(f"⏭️ Skipped unsupported file type: {filename}")
        return

    if not chunk_records:
        print(f"⚠️ No chunks produced for: {filename}")
        return

    _add_chunks(collection, document_id, filename, ext, chunk_records)
    print(f"✅ Indexed {len(chunk_records)} chunks | document_id={document_id}")


def main(reset: bool = False):
    if reset:
        reset_chroma()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    files = [
        f for f in os.listdir(DATA_DIR)
        if os.path.splitext(f.lower())[1] in SUPPORTED_EXTS
    ]

    if not files:
        print("⚠️ No supported files found in data/uploads (.pdf, .txt, .xlsx, .xls, .docx)")
        return

    for f in files:
        index_file(os.path.join(DATA_DIR, f), collection)

    print("🎯 Chroma population complete.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Delete chroma_store and rebuild embeddings")
    args = ap.parse_args()
    main(reset=args.reset)
