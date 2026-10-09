import uuid
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.auth.dependencies import get_current_user, get_optional_user
from app.models.user import User
from app.models.vector_collection import VectorCollection
from app.models.vector_document import VectorDocument
from app.models.workflow import Workflow
from app.api.schemas import (
    VectorCollectionCreate, VectorCollectionUpdate, VectorCollectionResponse,
    VectorCollectionStats, VectorDocumentCreate, VectorDocumentResponse,
    VectorSearchRequest, VectorSearchResponse, VectorSearchResult,
    VectorDocumentsCreate, VectorDocumentsResponse, VectorDocumentsDeleteResponse
)

router = APIRouter()

# Vector Collections API
@router.get("/collections", response_model=List[VectorCollectionResponse])
async def get_vector_collections(
    workflow_id: Optional[uuid.UUID] = Query(None, description="Filter by workflow ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return")
):
    """Get vector collections with optional workflow filtering."""
    try:
        query = select(VectorCollection).options(selectinload(VectorCollection.workflow))
        
        if workflow_id:
            query = query.where(VectorCollection.workflow_id == workflow_id)
        
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        collections = result.scalars().all()
        
        return [
            VectorCollectionResponse(
                id=collection.id,
                workflow_id=collection.workflow_id,
                collection_name=collection.collection_name,
                embedding_dimension=collection.embedding_dimension,
                distance_strategy=collection.distance_strategy,
                index_type=collection.index_type,
                index_params=collection.index_params,
                document_count=collection.document_count,
                created_at=collection.created_at,
                updated_at=collection.updated_at
            )
            for collection in collections
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve vector collections: {str(e)}"
        )

@router.post("/collections", response_model=VectorCollectionResponse)
async def create_vector_collection(
    collection_data: VectorCollectionCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new vector collection."""
    try:
        # Verify workflow exists and user has access
        workflow_query = select(Workflow).where(
            and_(
                Workflow.id == collection_data.workflow_id,
                Workflow.user_id == current_user.id
            )
        )
        workflow_result = await db.execute(workflow_query)
        workflow = workflow_result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found or access denied"
            )
        
        # Check if collection name already exists for this workflow
        existing_query = select(VectorCollection).where(
            and_(
                VectorCollection.workflow_id == collection_data.workflow_id,
                VectorCollection.collection_name == collection_data.collection_name
            )
        )
        existing_result = await db.execute(existing_query)
        existing_collection = existing_result.scalar_one_or_none()
        
        if existing_collection:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Collection with this name already exists for this workflow"
            )
        
        # Create new collection
        new_collection = VectorCollection(
            workflow_id=collection_data.workflow_id,
            collection_name=collection_data.collection_name,
            embedding_dimension=collection_data.embedding_dimension,
            distance_strategy=collection_data.distance_strategy,
            index_type=collection_data.index_type,
            index_params=collection_data.index_params
        )
        
        db.add(new_collection)
        await db.commit()
        await db.refresh(new_collection)
        
        return VectorCollectionResponse(
            id=new_collection.id,
            workflow_id=new_collection.workflow_id,
            collection_name=new_collection.collection_name,
            embedding_dimension=new_collection.embedding_dimension,
            distance_strategy=new_collection.distance_strategy,
            index_type=new_collection.index_type,
            index_params=new_collection.index_params,
            document_count=new_collection.document_count,
            created_at=new_collection.created_at,
            updated_at=new_collection.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create vector collection: {str(e)}"
        )

@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector_collection(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a vector collection and all its documents."""
    try:
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        # Delete collection (cascade will delete documents)
        await db.delete(collection)
        await db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector collection: {str(e)}"
        )

@router.get("/collections/{collection_id}/stats", response_model=VectorCollectionStats)
async def get_collection_stats(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Get statistics for a vector collection."""
    try:
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        # Get document count and size statistics
        doc_count_query = select(func.count(VectorDocument.id)).where(
            VectorDocument.collection_id == collection_id
        )
        doc_count_result = await db.execute(doc_count_query)
        doc_count = doc_count_result.scalar()
        
        # Calculate total size (approximate)
        total_size = doc_count * collection.embedding_dimension * 4  # 4 bytes per float
        
        return VectorCollectionStats(
            id=collection.id,
            collection_name=collection.collection_name,
            document_count=doc_count,
            total_size_bytes=total_size,
            avg_embedding_dimension=collection.embedding_dimension,
            created_at=collection.created_at,
            last_updated=collection.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection statistics: {str(e)}"
        )

# Vector Documents API
@router.post("/collections/{collection_id}/documents", response_model=VectorDocumentsResponse)
async def create_vector_documents(
    collection_id: uuid.UUID,
    documents_data: VectorDocumentsCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Create multiple vector documents in a collection."""
    try:
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        created_ids = []
        failed_count = 0
        
        for doc_data in documents_data.documents:
            try:
                # Validate embedding dimension if provided
                if doc_data.embedding and len(doc_data.embedding) != collection.embedding_dimension:
                    failed_count += 1
                    continue
                
                # Create document
                new_document = VectorDocument(
                    collection_id=collection_id,
                    content=doc_data.content,
                    document_metadata=doc_data.document_metadata or {},
                    embedding=str(doc_data.embedding) if doc_data.embedding else None,
                    source_url=doc_data.source_url,
                    source_type=doc_data.source_type,
                    chunk_index=doc_data.chunk_index
                )
                
                db.add(new_document)
                # Flush to get the ID
                await db.flush()
                created_ids.append(new_document.id)
                
            except Exception as e:
                failed_count += 1
                logger.error("Error creating vector document: %s", e)
        
        # Update collection document count
        collection.document_count += len(created_ids)
        
        await db.commit()
        
        return VectorDocumentsResponse(
            created_ids=created_ids,
            total_created=len(created_ids),
            failed_count=failed_count
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create vector documents: {str(e)}"
        )

@router.post("/collections/{collection_id}/search", response_model=VectorSearchResponse)
async def search_vector_documents(
    collection_id: uuid.UUID,
    search_request: VectorSearchRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Search vector documents using semantic similarity."""
    try:
        start_time = time.time()
        
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        # Build search query
        query = select(VectorDocument).where(VectorDocument.collection_id == collection_id)
        
        # Apply metadata filters if provided
        if search_request.filter_metadata:
            # This is a simplified filter - in production you'd want more sophisticated filtering
            for key, value in search_request.filter_metadata.items():
                query = query.where(VectorDocument.document_metadata.contains({key: value}))
        
        # Execute query
        result = await db.execute(query)
        documents = result.scalars().all()
        
        # Simple similarity calculation (in production, use proper vector similarity)
        search_results = []
        for doc in documents:
            # Placeholder similarity score - replace with actual vector similarity calculation
            similarity_score = 0.8  # Placeholder
            
            if similarity_score >= search_request.threshold:
                search_results.append(VectorSearchResult(
                    id=doc.id,
                    content=doc.content,
                    document_metadata=doc.document_metadata,
                    similarity_score=similarity_score,
                    source_url=doc.source_url,
                    source_type=doc.source_type,
                    chunk_index=doc.chunk_index
                ))
        
        # Sort by similarity score and limit results
        search_results.sort(key=lambda x: x.similarity_score, reverse=True)
        search_results = search_results[:search_request.k]
        
        query_time_ms = (time.time() - start_time) * 1000
        
        return VectorSearchResponse(
            results=search_results,
            total_found=len(search_results),
            query_time_ms=query_time_ms
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search vector documents: {str(e)}"
        )

@router.get("/collections/{collection_id}/documents", response_model=List[VectorDocumentResponse])
async def get_vector_documents(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return")
):
    """Get vector documents from a collection."""
    try:
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        # Get documents
        documents_query = select(VectorDocument).where(
            VectorDocument.collection_id == collection_id
        ).offset(skip).limit(limit)
        
        result = await db.execute(documents_query)
        documents = result.scalars().all()
        
        return [
            VectorDocumentResponse(
                id=doc.id,
                collection_id=doc.collection_id,
                content=doc.content,
                document_metadata=doc.document_metadata,
                embedding=doc.embedding,
                source_url=doc.source_url,
                source_type=doc.source_type,
                chunk_index=doc.chunk_index,
                created_at=doc.created_at
            )
            for doc in documents
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vector documents: {str(e)}"
        )

@router.delete("/collections/{collection_id}/documents", response_model=VectorDocumentsDeleteResponse)
async def delete_vector_documents(
    collection_id: uuid.UUID,
    document_ids: Optional[str] = Query(None, description="Comma-separated list of document IDs"),
    all_documents: bool = Query(False, description="Delete all documents in collection"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Delete vector documents from a collection."""
    try:
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        # Parse document IDs if provided
        doc_ids = []
        if document_ids:
            try:
                doc_ids = [uuid.UUID(id.strip()) for id in document_ids.split(",")]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid document ID format"
                )
        
        # Build delete query
        if all_documents:
            # Delete all documents in collection
            delete_query = select(VectorDocument).where(
                VectorDocument.collection_id == collection_id
            )
        elif doc_ids:
            # Delete specific documents
            delete_query = select(VectorDocument).where(
                and_(
                    VectorDocument.collection_id == collection_id,
                    VectorDocument.id.in_(doc_ids)
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either document_ids or all_documents=true must be provided"
            )
        
        # Get documents to delete
        result = await db.execute(delete_query)
        documents_to_delete = result.scalars().all()
        
        if not documents_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No documents found to delete"
            )
        
        # Store document info before deletion
        deleted_ids = []
        deleted_contents = []
        
        for doc in documents_to_delete:
            deleted_ids.append(doc.id)
            deleted_contents.append(doc.content)
            await db.delete(doc)
        
        # Update collection document count
        collection.document_count -= len(documents_to_delete)
        
        await db.commit()
        
        return VectorDocumentsDeleteResponse(
            deleted_ids=deleted_ids,
            deleted_contents=deleted_contents,
            total_deleted=len(documents_to_delete),
            collection_id=collection_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector documents: {str(e)}"
        )

@router.delete("/collections/{collection_id}/documents/{document_id}", response_model=VectorDocumentsDeleteResponse)
async def delete_single_vector_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a single vector document from a collection."""
    try:
        # Verify collection exists and user has access
        collection_query = select(VectorCollection).options(
            selectinload(VectorCollection.workflow)
        ).where(VectorCollection.id == collection_id)
        
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()
        
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vector collection not found"
            )
        
        # Check if user owns the workflow
        if collection.workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this collection"
            )
        
        # Get specific document
        document_query = select(VectorDocument).where(
            and_(
                VectorDocument.id == document_id,
                VectorDocument.collection_id == collection_id
            )
        )
        
        result = await db.execute(document_query)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Store document info before deletion
        deleted_content = document.content
        
        # Delete document
        await db.delete(document)
        
        # Update collection document count
        collection.document_count -= 1
        
        await db.commit()
        
        return VectorDocumentsDeleteResponse(
            deleted_ids=[document_id],
            deleted_contents=[deleted_content],
            total_deleted=1,
            collection_id=collection_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector document: {str(e)}"
        )
