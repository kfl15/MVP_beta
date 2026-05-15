import os
import sys
import uuid
import shutil
import argparse
from typing import Any, Dict

from chromadb import PersistentClient

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
sys.path.insert(0, BACKEND_ROOT)

from embeddings.ollama_embedding import get_embedding
from loaders.ocr_loader import SUPPORTED_OCR_EXTS, extract_ocr_records


DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"


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
    print("Chroma store cleared.")


def _sanitize_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    clean = {}
    for k, v in (meta or {}).items():
        if v is None:
            continue
        if isinstance(v, (bool, int, float, str)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def index_file(file_path: str, collection) -> Dict[str, Any]:
    document_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename.lower())[1]

    if ext not in SUPPORTED_OCR_EXTS:
        return {
            "document_id": document_id,
            "filename": filename,
            "records_indexed": 0,
            "reason": "unsupported_extension",
        }

    print(f"OCR indexing: {filename}")
    records = extract_ocr_records(file_path)

    indexed = 0
    for idx, record in enumerate(records):
        text = (record.get("text") or "").strip()
        stored_text = text or "[No OCR text detected.]"
        embedding = get_embedding(stored_text)

        meta = _sanitize_meta({
            "document_id": document_id,
            "filename": filename,
            "image_name": record.get("image_name") or filename,
            "page_number": record.get("page_number"),
            "file_ext": ext,
            "source_type": record.get("source_type"),
            "ocr_engine": record.get("engine"),
            "ocr_avg_confidence": record.get("avg_confidence"),
            "ocr_record_id": idx,
        })

        collection.add(
            ids=[f"{document_id}_{idx}"],
            documents=[stored_text],
            embeddings=[embedding],
            metadatas=[meta],
        )
        indexed += 1

    print(f"Indexed {indexed} OCR records | document_id={document_id}")
    return {
        "document_id": document_id,
        "filename": filename,
        "records_indexed": indexed,
    }


def main(reset: bool = False):
    if reset:
        reset_chroma()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    files = [
        f for f in os.listdir(DATA_DIR)
        if os.path.splitext(f.lower())[1] in SUPPORTED_OCR_EXTS
    ]

    if not files:
        print("No supported files found in data/uploads (.pdf, .png, .jpg, .jpeg, .webp)")
        return

    for f in files:
        index_file(os.path.join(DATA_DIR, f), collection)

    print("Chroma OCR population complete.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Delete chroma_store and rebuild OCR embeddings")
    args = ap.parse_args()
    main(reset=args.reset)
