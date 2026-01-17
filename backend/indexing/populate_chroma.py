import os
import sys
import uuid
import shutil
from typing import List
from chromadb import PersistentClient

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

from loaders.pdf_loader import extract_text_from_pdf
from embeddings.ollama_embedding import get_embedding


# ======================= CONFIG ==============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
# ============================================================


def chunk_text(text: str) -> List[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def reset_chroma():
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        print("🧹 Chroma store reset.")


def index_pdf(pdf_path: str, collection):
    document_id = str(uuid.uuid4())
    filename = os.path.basename(pdf_path)

    print(f"📄 Indexing: {filename}")
    text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(text)

    for idx, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)

        collection.add(
            ids=[f"{document_id}_{idx}"],
            documents=[chunk],
            embeddings=[embedding],
            metadatas=[{
                "document_id": document_id,
                "filename": filename,
                "chunk_id": idx
            }]
        )

    print(f"✅ Indexed {len(chunks)} chunks | document_id={document_id}")


def main(reset: bool = False):
    if reset:
        reset_chroma()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    pdf_files = [
        f for f in os.listdir(DATA_DIR)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_files:
        print("⚠️ No PDFs found in data/uploads")
        return

    for pdf in pdf_files:
        pdf_path = os.path.join(DATA_DIR, pdf)
        index_pdf(pdf_path, collection)

    print("🎯 Chroma population complete.")


if __name__ == "__main__":
    main(reset=False)
