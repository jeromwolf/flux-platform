"""Document upload and management routes."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from kg.api.deps import get_document_repo
from kg.db.protocols import DocumentRepository

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


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    description: str = Form(""),  # noqa: B008
    repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentUploadResponse:
    """Upload a document for RAG ingestion.

    Args:
        file: Multipart file upload.
        description: Optional text description for the document.
        repo: Injected document repository.

    Returns:
        DocumentUploadResponse with metadata and ingestion status.

    Raises:
        HTTPException: 413 if file exceeds 50 MB limit.
    """
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    doc_id = hashlib.sha256(content).hexdigest()[:16]
    size = len(content)
    chunk_count = 0
    status = "uploaded"

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
        chunk_count = result.chunks_created
        status = "ingested"
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG ingestion skipped: %s", exc)

    doc = await repo.create(
        doc_id=doc_id,
        filename=file.filename or "unknown",
        size=size,
        content_type=file.content_type or "application/octet-stream",
        description=description,
        status=status,
        chunks=chunk_count,
    )
    return DocumentUploadResponse(**doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentListResponse:
    """List uploaded documents with simple offset pagination.

    Args:
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.
        repo: Injected document repository.

    Returns:
        DocumentListResponse with document list and total count.
    """
    docs, total = await repo.list(limit=limit, offset=offset)
    return DocumentListResponse(documents=docs, total=total)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    repo: DocumentRepository = Depends(get_document_repo),
) -> dict[str, str]:
    """Delete a document by its ID.

    Args:
        doc_id: SHA-256 prefix ID of the document to delete.
        repo: Injected document repository.

    Returns:
        Dict with ``deleted`` key containing the removed doc_id.

    Raises:
        HTTPException: 404 if no document with that ID exists.
    """
    deleted = await repo.delete(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {"deleted": doc_id}
