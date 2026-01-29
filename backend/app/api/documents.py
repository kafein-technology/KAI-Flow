"""
KAI-Fusion Document Management API - Enterprise Document Operations & Management
==============================================================================

This module implements comprehensive document management API endpoints for the KAI-Fusion platform,
providing enterprise-grade document storage, retrieval, search, and analytics capabilities.
Built for production environments with advanced authentication, comprehensive validation,
and intelligent document operations with full-text search and analytics integration.

ARCHITECTURAL OVERVIEW:
======================

The Document Management API provides a sophisticated REST interface for document operations,
abstracting complex business logic and providing secure, scalable document management
with enterprise-grade features, performance optimization, and comprehensive analytics.

┌─────────────────────────────────────────────────────────────────┐
│                   Document API Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HTTP Requests → [API Router] → [Auth & Validation] → [Service]│
│       ↓             ↓               ↓                    ↓      │
│  [Request Processing] → [Business Logic] → [Database] → [Response]│
│       ↓             ↓               ↓                    ↓      │
│  [Error Handling] → [Analytics] → [Monitoring] → [JSON Output] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

KEY FEATURES:
============

1. **Document Management**:
   - Document storage with comprehensive metadata management
   - Collection-based organization with hierarchical structure
   - Advanced search with full-text search and filtering capabilities
   - Document retrieval with access control and analytics tracking

2. **Enterprise Security**:
   - User-based authentication with JWT token validation
   - Row-level security with user-scoped document access
   - Comprehensive audit logging with access tracking
   - Input validation with security-aware parameter handling

3. **Advanced Search & Analytics**:
   - Full-text search with PostgreSQL advanced search capabilities
   - Multi-dimensional filtering with query optimization
   - Collection analytics with comprehensive reporting
   - Usage analytics with performance insights

4. **Production API Features**:
   - RESTful design with consistent endpoint patterns
   - Comprehensive error handling with detailed diagnostics
   - Request validation with schema enforcement
   - Response pagination with performance optimization

5. **Integration Capabilities**:
   - DocumentLoader integration for automated storage
   - ChunkSplitter integration for document processing
   - Workflow integration with node-based processing
   - Analytics integration with business intelligence

AUTHORS: KAI-Fusion API Development Team
VERSION: 2.1.0
LAST_UPDATED: 2025-07-29
LICENSE: Proprietary - KAI-Fusion Platform
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.document_service import DocumentService
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentCollection
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    CollectionCreate,
    CollectionResponse,
    DocumentAnalyticsResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/collections", response_model=CollectionResponse)
async def create_collection(
    collection_data: CollectionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Create a new document collection.
    
    Creates a new document collection for organizing documents with
    comprehensive metadata and enterprise features.
    """
    try:
        document_service = DocumentService(session)
        
        collection = await document_service.create_collection(
            user_id=current_user.id,
            collection_data=collection_data.dict()
        )
        
        logger.info(f"Created collection '{collection.name}' for user {current_user.id}")
        
        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            metadata=collection.metadata,
            is_active=collection.is_active,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            document_count=0  # New collection has no documents
        )
        
    except Exception as e:
        logger.error(f"Failed to create collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@router.get("/collections", response_model=List[CollectionResponse])
async def list_collections(
    limit: int = Query(default=50, le=1000, description="Maximum number of collections to return"),
    offset: int = Query(default=0, ge=0, description="Number of collections to skip"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    List user's document collections.
    
    Retrieves a paginated list of document collections for the current user
    with comprehensive metadata and document counts.
    """
    try:
        document_service = DocumentService(session)
        
        # Get collections with document counts
        collections_query = await session.execute(
            select(DocumentCollection, func.count(Document.id).label('doc_count'))
            .outerjoin(Document)
            .filter(DocumentCollection.user_id == current_user.id)
            .group_by(DocumentCollection.id)
            .order_by(desc(DocumentCollection.updated_at))
            .limit(limit)
            .offset(offset)
        )
        
        collections_data = collections_query.all()
        
        collections = [
            CollectionResponse(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                metadata=collection.metadata,
                is_active=collection.is_active,
                created_at=collection.created_at,
                updated_at=collection.updated_at,
                document_count=doc_count
            )
            for collection, doc_count in collections_data
        ]
        
        logger.info(f"Listed {len(collections)} collections for user {current_user.id}")
        return collections
        
    except Exception as e:
        logger.error(f"Failed to list collections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")

@router.get("/collections/{collection_id}/analytics", response_model=DocumentAnalyticsResponse)
async def get_collection_analytics(
    collection_id: UUID = Path(..., description="Collection ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get comprehensive analytics for a document collection.
    
    Provides detailed analytics including document counts, quality metrics,
    format distribution, and tag frequency analysis.
    """
    try:
        document_service = DocumentService(session)
        
        analytics = await document_service.get_collection_analytics(
            user_id=current_user.id,
            collection_id=collection_id
        )
        
        logger.info(f"Generated analytics for collection {collection_id}")
        
        return DocumentAnalyticsResponse(**analytics)
        
    except Exception as e:
        logger.error(f"Failed to generate analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate analytics: {str(e)}")

@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    search_request: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Advanced document search with full-text search and filtering.
    
    Provides comprehensive document search capabilities including full-text search,
    metadata filtering, quality filtering, and intelligent ranking.
    """
    try:
        document_service = DocumentService(session)
        
        documents, search_metadata = await document_service.search_documents(
            user_id=current_user.id,
            search_params=search_request.dict(exclude_none=True)
        )
        
        # Convert to response format
        document_responses = [
            DocumentResponse(
                id=doc.id,
                title=doc.title,
                content=doc.content,
                document_format=doc.document_format,
                source_url=doc.source_url,
                file_path=doc.file_path,
                source_type=doc.source_type,
                content_length=doc.content_length,
                word_count=doc.word_count,
                quality_score=doc.quality_score,
                processing_status=doc.processing_status,
                metadata=doc.metadata,
                tags=doc.tags,
                is_public=doc.is_public,
                collection_id=doc.collection_id,
                collection_name=doc.collection.name if doc.collection else None,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )
            for doc in documents
        ]
        
        logger.info(f"Search completed: {len(documents)}/{search_metadata['total_count']} documents")
        
        return DocumentSearchResponse(
            documents=document_responses,
            total_count=search_metadata["total_count"],
            returned_count=search_metadata["returned_count"],
            limit=search_metadata["limit"],
            offset=search_metadata["offset"],
            search_params=search_metadata["search_params"],
        )
        
    except Exception as e:
        logger.error(f"Document search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Document search failed: {str(e)}")

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID = Path(..., description="Document ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific document by ID.
    
    Retrieves a document with comprehensive metadata and access logging.
    """
    try:
        document_service = DocumentService(session)
        
        document = await document_service.get_document_by_id(
            user_id=current_user.id,
            document_id=document_id
        )
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"Retrieved document {document_id} for user {current_user.id}")
        
        return DocumentResponse(
            id=document.id,
            title=document.title,
            content=document.content,
            document_format=document.document_format,
            source_url=document.source_url,
            file_path=document.file_path,
            source_type=document.source_type,
            content_length=document.content_length,
            word_count=document.word_count,
            quality_score=document.quality_score,
            processing_status=document.processing_status,
            metadata=document.metadata,
            tags=document.tags,
            is_public=document.is_public,
            collection_id=document.collection_id,
            collection_name=document.collection.name if document.collection else None,
            created_at=document.created_at,
            updated_at=document.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {str(e)}")

@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID = Path(..., description="Document ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Delete a document.
    
    Deletes a document with proper cleanup and audit logging.
    """
    try:
        document_service = DocumentService(session)
        
        success = await document_service.delete_document(
            user_id=current_user.id,
            document_id=document_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"Deleted document {document_id} for user {current_user.id}")
        
        return {"message": "Document deleted successfully", "document_id": str(document_id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Failed to delete document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.post("/bulk-store")
async def bulk_store_documents(
    documents_data: List[Dict[str, Any]] = Body(..., description="List of documents to store"),
    collection_id: Optional[UUID] = Body(None, description="Collection ID for organizing documents"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Bulk store documents from DocumentLoader processing.
    
    Stores multiple documents in batch with comprehensive metadata
    and automatic collection management.
    """
    try:
        document_service = DocumentService(session)
        
        stored_documents = await document_service.store_documents(
            user_id=current_user.id,
            documents_data=documents_data,
            collection_id=collection_id
        )
        
        logger.info(f"Bulk stored {len(stored_documents)} documents for user {current_user.id}")
        
        return {
            "message": f"Successfully stored {len(stored_documents)} documents",
            "stored_count": len(stored_documents),
            "document_ids": [str(doc.id) for doc in stored_documents],
            "collection_id": str(stored_documents[0].collection_id) if stored_documents else None
        }
        
    except Exception as e:
        logger.error(f"Bulk document storage failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk storage failed: {str(e)}")

@router.post("/{document_id}/chunks")
async def store_document_chunks(
    document_id: UUID = Path(..., description="Document ID"),
    chunks_data: List[Dict[str, Any]] = Body(..., description="List of document chunks"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Store processed document chunks from ChunkSplitter.
    
    Stores document chunks with comprehensive metadata for
    vector embedding and retrieval workflows.
    """
    try:
        document_service = DocumentService(session)
        
        # Verify document ownership
        document = await document_service.get_document_by_id(
            user_id=current_user.id,
            document_id=document_id
        )
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        stored_chunks = await document_service.store_document_chunks(
            user_id=current_user.id,
            document_id=document_id,
            chunks_data=chunks_data
        )
        
        logger.info(f"Stored {len(stored_chunks)} chunks for document {document_id}")
        
        return {
            "message": f"Successfully stored {len(stored_chunks)} chunks",
            "document_id": str(document_id),
            "chunks_count": len(stored_chunks),
            "chunk_ids": [str(chunk.id) for chunk in stored_chunks]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store chunks for document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to store chunks: {str(e)}")

@router.get("/stats/overview")
async def get_document_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get comprehensive document statistics for the user.
    
    Provides overview statistics including document counts,
    collection metrics, and quality distribution.
    """
    try:
        # Get overall statistics
        from sqlalchemy import select, func
        from app.models.document import Document, DocumentCollection
        
        # Total documents
        total_docs = await session.scalar(
            select(func.count(Document.id)).filter(Document.user_id == current_user.id)
        )
        
        # Total collections
        total_collections = await session.scalar(
            select(func.count(DocumentCollection.id)).filter(DocumentCollection.user_id == current_user.id)
        )
        
        # Average quality score
        avg_quality = await session.scalar(
            select(func.avg(Document.quality_score)).filter(Document.user_id == current_user.id)
        )
        
        # Format distribution
        format_stats = await session.execute(
            select(Document.document_format, func.count(Document.id))
            .filter(Document.user_id == current_user.id)
            .group_by(Document.document_format)
        )
        
        format_distribution = {row[0]: row[1] for row in format_stats}
        
        # Recent activity (documents created in last 7 days)
        recent_docs = await session.scalar(
            select(func.count(Document.id))
            .filter(
                Document.user_id == current_user.id,
                Document.created_at >= datetime.now() - timedelta(days=7)
            )
        )
        
        stats = {
            "total_documents": total_docs or 0,
            "total_collections": total_collections or 0,
            "average_quality_score": round(float(avg_quality or 0), 3),
            "format_distribution": format_distribution,
            "recent_documents": recent_docs or 0,
            "generated_at": datetime.now().isoformat()
        }
        
        logger.info(f"Generated document stats for user {current_user.id}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to generate document stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate statistics: {str(e)}")

# Export router
__all__ = ["router"]