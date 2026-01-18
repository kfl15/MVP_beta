import os
from fastapi import HTTPException
from chromadb import PersistentClient

# ============================================================
# PATHS (must match app.py)
# ============================================================
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_store")
COLLECTION_NAME = "rag_documents"
# ============================================================


def delete_document(document_id: str):
    """
    Deletes ALL data associated with a document_id:
    - embeddings from Chroma (filtered by document_id)
    - original uploaded file(s) (via filename metadata)
    """

    if not document_id or not document_id.strip():
        raise HTTPException(status_code=400, detail="document_id is required")

    client = PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    # Get all chunks for this document_id
    results = collection.get(
        where={"document_id": document_id},
        include=["metadatas"]
    )

    ids = results.get("ids", [])
    metas = results.get("metadatas", [])

    if not ids:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for document_id={document_id}"
        )

    # Collect filenames safely
    filenames = set()
    for m in metas:
        if m and m.get("filename"):
            filenames.add(m.get("filename"))

    # Delete original files from uploads directory
    deleted_files = []
    for fname in filenames:
        safe_name = os.path.basename(fname or "")
        if not safe_name:
            continue
        file_path = os.path.join(DATA_DIR, safe_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted_files.append(safe_name)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete file '{safe_name}': {e}"
                )


    # Delete all vectors for this document
    collection.delete(where={"document_id": document_id})

    return {
        "status": "deleted",
        "document_id": document_id,
        "chunks_deleted": len(ids),
        "files_deleted": deleted_files,
        "deleted_from_chroma": True
    }
