"""RAG query and document management endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query text")
    mode: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=50)


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    mode: str
    total_chunks: int = 0


class DocumentUploadRequest(BaseModel):
    title: str
    content: str
    doc_type: str = "txt"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentUploadResponse(BaseModel):
    doc_id: str
    title: str
    chunks_created: int
    message: str


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest, req: Request) -> RAGQueryResponse:
    """Query the RAG engine with hybrid search."""
    try:
        engine = getattr(req.app.state, "rag_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="RAG engine not available")

        result = engine.query(request.query)

        return RAGQueryResponse(
            query=request.query,
            answer=result.answer,
            chunks=[
                {
                    "content": c.chunk.content,
                    "doc_id": c.chunk.doc_id,
                    "score": c.score,
                }
                for c in result.retrieved_chunks
            ],
            scores=[c.score for c in result.retrieved_chunks],
            mode=request.mode,
            total_chunks=result.chunk_count,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(request: DocumentUploadRequest, req: Request) -> DocumentUploadResponse:
    """Ingest a document into the RAG pipeline."""
    try:
        import hashlib

        from rag.documents.models import Document, DocumentType

        pipeline = getattr(req.app.state, "document_pipeline", None)
        if pipeline is None:
            raise HTTPException(status_code=503, detail="Document pipeline not available")

        type_map = {
            "txt": DocumentType.TXT,
            "markdown": DocumentType.MARKDOWN,
            "html": DocumentType.HTML,
            "csv": DocumentType.CSV,
        }
        doc_type = type_map.get(request.doc_type, DocumentType.TXT)

        doc_id = hashlib.sha256(
            f"{request.title}:{request.content[:100]}".encode()
        ).hexdigest()[:16]

        doc = Document(
            doc_id=doc_id,
            title=request.title,
            content=request.content,
            doc_type=doc_type,
            metadata=request.metadata,
        )

        ingestion_result = pipeline.ingest_document(doc)

        return DocumentUploadResponse(
            doc_id=doc_id,
            title=request.title,
            chunks_created=ingestion_result.chunks_created,
            message="Document ingested successfully",
        )
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=503, detail="Document pipeline not available")
    except Exception as exc:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def rag_status() -> dict[str, Any]:
    """Check RAG engine status."""
    status: dict[str, Any] = {
        "available": False,
        "engine": "HybridRAGEngine",
        "retriever": "SimpleRetriever",
    }
    try:
        from rag.engines.orchestrator import HybridRAGEngine  # noqa: F401

        status["available"] = True
    except ImportError:  # noqa: S110
        pass
    return status
