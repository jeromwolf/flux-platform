"""Document upload and management routes."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    size: int
    content_type: str
    status: str = "uploaded"
    chunks: int = 0


class DocumentListResponse(BaseModel):
    documents: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# In-memory store (Y2: migrate to PostgreSQL/MinIO)
_documents: list[dict[str, Any]] = []


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    description: str = Form(""),  # noqa: B008
) -> DocumentUploadResponse:
    """Upload a document for RAG ingestion.

    Args:
        file: Multipart file upload.
        description: Optional text description for the document.

    Returns:
        DocumentUploadResponse with metadata and ingestion status.

    Raises:
        HTTPException: 413 if file exceeds 50 MB limit.
    """
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    doc_id = hashlib.sha256(content).hexdigest()[:16]

    doc_meta: dict[str, Any] = {
        "id": doc_id,
        "filename": file.filename or "unknown",
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "description": description,
        "status": "uploaded",
        "chunks": 0,
    }

    # Try RAG ingestion (best-effort; failures do not abort the upload)
    try:
        from rag.documents.models import DocumentType
        from rag.documents.pipeline import DocumentPipeline

        pipeline = DocumentPipeline()

        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        doc_type_map: dict[str, Any] = {
            "pdf": DocumentType.PDF,
            "hwp": DocumentType.HWP,
            "txt": DocumentType.TXT,
            "md": DocumentType.MARKDOWN,
            "html": DocumentType.HTML,
            "csv": DocumentType.CSV,
        }
        doc_type = doc_type_map.get(ext, DocumentType.TXT)

        result = pipeline.ingest_text(
            content.decode("utf-8", errors="replace"),
            doc_id=doc_id,
            title=file.filename or "unknown",
        )
        doc_meta["chunks"] = result.chunks_created
        doc_meta["status"] = "ingested"
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG ingestion skipped: %s", exc)

    _documents.append(doc_meta)
    return DocumentUploadResponse(**doc_meta)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(limit: int = 50, offset: int = 0) -> DocumentListResponse:
    """List uploaded documents with simple offset pagination.

    Args:
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.

    Returns:
        DocumentListResponse with document list and total count.
    """
    return DocumentListResponse(
        documents=_documents[offset : offset + limit],
        total=len(_documents),
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, str]:
    """Delete a document by its ID.

    Args:
        doc_id: SHA-256 prefix ID of the document to delete.

    Returns:
        Dict with ``deleted`` key containing the removed doc_id.

    Raises:
        HTTPException: 404 if no document with that ID exists.
    """
    global _documents  # noqa: PLW0603
    before = len(_documents)
    _documents = [d for d in _documents if d["id"] != doc_id]
    if len(_documents) == before:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {"deleted": doc_id}
