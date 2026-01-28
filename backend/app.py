import os
import sys
import shutil
import requests
import time
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from chromadb import PersistentClient

# ============================================================
# FIX PYTHON IMPORT PATH
# ============================================================
BACKEND_ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)
# ============================================================

from indexing.populate_chroma import index_file
from retrieval.query_chroma import query_rag
from deletion.delete_document import delete_document

# ======================= CONFIG ==============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"
ALLOWED_EXTS = {".pdf", ".txt", ".xlsx", ".xls", ".docx"}

# Ollama config

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
# OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "gemma2:2b")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2:1b-instruct-q4_K_M")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_REQUIRE_MODELS = os.getenv("OLLAMA_REQUIRE_MODELS", "1").lower() in ("1", "true", "yes")

# ============================================================

app = FastAPI(title="Local RAG MVP")


@app.on_event("startup")
def verify_ollama_models_present():
    """
    IMPORTANT:
    - This does NOT pull models.
    - It only verifies that the models already exist in Ollama.
    """
    # Give Ollama a moment to start
    time.sleep(3)

    required = [OLLAMA_EMBED_MODEL, OLLAMA_LLM_MODEL]

    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=60)
        r.raise_for_status()
        tags = r.json()
        installed = set(
            m.get("name")
            for m in (tags.get("models") or [])
            if m and m.get("name")
        )
    except Exception as e:
        msg = f"[ERROR] Could not reach Ollama at {OLLAMA_BASE_URL} (/api/tags). Error: {e}"
        if OLLAMA_REQUIRE_MODELS:
            raise RuntimeError(msg)
        print(msg)
        return

    def _is_installed(requested: str, installed_set: set[str]) -> bool:
        if requested in installed_set:
            return True
        # allow "nomic-embed-text" to match "nomic-embed-text:latest"
        if ":" not in requested and f"{requested}:latest" in installed_set:
            return True
        return False

    missing = [m for m in required if not _is_installed(m, installed)]

    if missing:
        msg = (
            "[ERROR] Ollama is running but required models are missing:\n"
            + "\n".join([f" - {m}" for m in missing])
            + "\n\nFix: inside docker folder run:\n"
              "  docker compose exec ollama ollama pull <MODEL_NAME>\n"
            + "Example:\n"
              f"  docker compose exec ollama ollama pull {missing[0]}\n"
        )
        if OLLAMA_REQUIRE_MODELS:
            raise RuntimeError(msg)
        print(msg)
        return

    print("[INFO] Ollama models verified (no auto-pull):", required)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    os.makedirs(DATA_DIR, exist_ok=True)

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    indexed = []
    skipped = []

    for file in files:
        safe_name = os.path.basename(file.filename or "")
        ext = os.path.splitext(safe_name.lower())[1]

        if ext not in ALLOWED_EXTS:
            skipped.append({"filename": safe_name, "reason": "unsupported_extension"})
            continue

        file_path = os.path.join(DATA_DIR, safe_name)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        index_file(file_path, collection)
        indexed.append(safe_name)

    return {"indexed_files": indexed, "skipped_files": skipped}


@app.post("/chat")
def chat(body: ChatRequest):
    return query_rag(body.question)


@app.get("/documents")
def list_documents():
    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    data = collection.get(include=["metadatas"])
    metas = data.get("metadatas", []) or []

    docs = {}
    cleaned = set()  # avoid repeated deletes for the same document_id

    for m in metas:
        if not m:
            continue

        doc_id = m.get("document_id")
        filename = m.get("filename") or ""

        if not doc_id:
            continue

        safe_name = os.path.basename(filename)
        file_path = os.path.join(DATA_DIR, safe_name)

        # If file missing -> remove vectors from Chroma
        if not safe_name or not os.path.exists(file_path):
            if doc_id not in cleaned:
                try:
                    collection.delete(where={"document_id": doc_id})
                except Exception as e:
                    print(f"[WARN] Could not auto-clean doc_id={doc_id}: {e}")
                cleaned.add(doc_id)
            continue

        if doc_id not in docs:
            docs[doc_id] = {"document_id": doc_id, "filename": safe_name}

    return list(docs.values())


@app.delete("/documents/{document_id}")
def delete_doc(document_id: str):
    return delete_document(document_id)
