import os
import sys
import shutil
import requests
import time
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# ============================================================
# FIX PYTHON IMPORT PATH
# ============================================================
BACKEND_ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)
# ============================================================

# from indexing.populate_chroma import index_pdf
from indexing.populate_chroma import index_file
from retrieval.query_chroma import query_rag
from deletion.delete_document import delete_document
from chromadb import PersistentClient

# ======================= CONFIG ==============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"
ALLOWED_EXTS = {".pdf", ".txt", ".xlsx", ".xls"}  # <<< ADDED

# ============================================================

app = FastAPI(title="Local RAG MVP")


@app.on_event("startup")
def ensure_ollama_models():
    ollama_url = "http://ollama:11434"

    # get current runtime model (from docker-compose env)
    llm_model = os.getenv("OLLAMA_LLM_MODEL", "gemma2:2b")
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    models = [embed_model, llm_model]

    # Give Ollama a moment to start
    time.sleep(3)

    try:
        tags = requests.get(f"{ollama_url}/api/tags", timeout=60).json()
        installed = set(m.get("name") for m in (tags.get("models") or []) if m.get("name"))
    except Exception as e:
        print(f"[WARN] Could not list Ollama tags: {e}")
        installed = set()

    for model in models:
        if model in installed:
            print(f"[INFO] Ollama model already present: {model}")
            continue

        try:
            print(f"[INFO] Pulling Ollama model (missing): {model}")
            requests.post(
                f"{ollama_url}/api/pull",
                json={"name": model},
                timeout=600,
            )
        except Exception as e:
            print(f"[WARN] Could not pull model {model}: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- MODELS ----------------
class ChatRequest(BaseModel):
    question: str


# ---------------- ROUTES ----------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    os.makedirs(DATA_DIR, exist_ok=True)

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    indexed = []
    skipped = []  # <<< ADDED

    for file in files:
        # <<< ADDED: basic filename hardening
        safe_name = os.path.basename(file.filename)
        ext = os.path.splitext(safe_name.lower())[1]

        if ext not in ALLOWED_EXTS:  # <<< ADDED
            skipped.append({"filename": safe_name, "reason": "unsupported_extension"})
            continue

        file_path = os.path.join(DATA_DIR, safe_name)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # <<< CHANGED: index based on extension (pdf/txt/excel)
        index_file(file_path, collection)
        indexed.append(safe_name)

    return {"indexed_files": indexed, "skipped_files": skipped}  # <<< CHANGED



@app.post("/chat")
def chat(body: ChatRequest):
    result = query_rag(body.question)
    return result

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
        filename = m.get("filename")

        if not doc_id:
            continue

        # Build expected path in uploads directory
        safe_name = os.path.basename(filename or "")
        file_path = os.path.join(DATA_DIR, safe_name)

        # OPTION B (strong): if file missing -> remove vectors from Chroma
        if not safe_name or not os.path.exists(file_path):
            if doc_id not in cleaned:
                try:
                    collection.delete(where={"document_id": doc_id})
                except Exception as e:
                    # don't crash listing if delete fails
                    print(f"[WARN] Could not auto-clean doc_id={doc_id}: {e}")
                cleaned.add(doc_id)
            continue

        # keep only unique doc_id in response
        if doc_id not in docs:
            docs[doc_id] = {
                "document_id": doc_id,
                "filename": safe_name,
            }

    return list(docs.values())



@app.delete("/documents/{document_id}")
def delete_doc(document_id: str):
    return delete_document(document_id)
