import os
import sys
import uuid
import shutil
from typing import List
from chromadb import PersistentClient

# ============================================================
# PYTHON IMPORT PATH
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
from loaders.txt_loader import extract_text_from_txt  
from loaders.excel_loader import extract_text_from_excel  


# ======================= CONFIG ==============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 250


SUPPORTED_EXTS = {".pdf", ".txt", ".xlsx", ".xls"}  
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



def index_file(file_path: str, collection):  
    document_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename.lower())[1]  

    print(f"📄 Indexing: {filename}")

   
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
    elif ext == ".txt":
        text = extract_text_from_txt(file_path)
    elif ext in (".xlsx", ".xls"):
        text = extract_text_from_excel(file_path)
    else:
        print(f"⏭️ Skipped unsupported file type: {filename}")
        return

    # Optional safety: skip empty text
    if not text or not text.strip():  
        print(f"⚠️ No text extracted from: {filename}")
        return

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
                "chunk_id": idx,
                "file_ext": ext,  #  (helps debugging/filtering)
            }]
        )

    print(f"✅ Indexed {len(chunks)} chunks | document_id={document_id}")

def index_pdf(pdf_path: str, collection):
    # simply call the new generic indexer
    return index_file(pdf_path, collection)


def main(reset: bool = False):
    if reset:
        reset_chroma()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    #  CHANGED: scan for multiple file types (was only PDFs)
    files = [
        f for f in os.listdir(DATA_DIR)
        if os.path.splitext(f.lower())[1] in SUPPORTED_EXTS
    ]  

    if not files:  
        print("⚠️ No supported files found in data/uploads (.pdf, .txt, .xlsx, .xls)")
        return

    for f in files:  
        file_path = os.path.join(DATA_DIR, f)
        index_file(file_path, collection)  

    print("🎯 Chroma population complete.")


if __name__ == "__main__":
    main(reset=False)
