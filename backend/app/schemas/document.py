"""
KAI-Flow Document Schemas - API Request/Response Models
========================================================

This module implements comprehensive Pydantic schemas for document management API
endpoints, providing type-safe request/response models with validation, serialization,
and comprehensive documentation for the KAI-Flow platform's document management system.

AUTHORS: KAI-Flow API Development Team
VERSION: 2.1.0
LAST_UPDATED: 2025-07-29
LICENSE: Proprietary - KAI-Flow Platform
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

class DocumentFormat(str, Enum):
    """Supported document formats."""
    TXT = "txt"
    JSON = "json"
    DOCX = "docx"
    PDF = "pdf"
    WEB = "web"

class SourceType(str, Enum):
    """Document source types."""
    WEB = "web"
    FILE = "file"
    UPLOAD = "upload"
    UNKNOWN = "unknown"

class ProcessingStatus(str, Enum):
    """Document processing status."""
    COMPLETED = "completed"
    PROCESSING = "processing"
    FAILED = "failed"

# Collection Schemas
class CollectionCreate(BaseModel):
    """Schema for creating a new document collection."""
    name: str = Field(..., min_length=1, max_length=255, description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Research Papers",
                "description": "Collection of academic research papers",
                "metadata": {
                    "category": "research",
                    "retention_policy": "long_term"
                }
            }
        }

class CollectionResponse(BaseModel):
    """Schema for collection response."""
    id: UUID = Field(..., description="Collection ID")
    name: str = Field(..., description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    metadata: Dict[str, Any] = Field(..., description="Collection metadata")
    is_active: bool = Field(..., description="Collection active status")
    document_count: int = Field(..., description="Number of documents in collection")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Research Papers",
                "description": "Collection of academic research papers",
                "metadata": {"category": "research"},
                "is_active": True,
                "document_count": 42,
                "created_at": "2025-07-29T10:00:00Z",
                "updated_at": "2025-07-29T15:30:00Z"
            }
        }

# Document Schemas
class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    content: str = Field(..., min_length=1, description="Document content")
    document_format: DocumentFormat = Field(..., description="Document format")
    source_url: Optional[str] = Field(None, description="Source URL for web documents")
    file_path: Optional[str] = Field(None, description="File path for local documents")
    source_type: Optional[SourceType] = Field(None, description="Source type")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Document metadata")
    tags: Optional[List[str]] = Field(default=[], description="Document tags")
    is_public: Optional[bool] = Field(default=False, description="Public visibility")
    collection_id: Optional[UUID] = Field(None, description="Collection ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "AI Research Methodology",
                "content": "This document outlines the methodology for AI research...",
                "document_format": "txt",
                "source_url": "https://example.com/research.txt",
                "source_type": "web",
                "metadata": {"author": "Dr. Smith", "year": 2025},
                "tags": ["ai", "research", "methodology"],
                "is_public": False,
                "collection_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }

class DocumentResponse(BaseModel):
    """Schema for document response."""
    id: UUID = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    document_format: DocumentFormat = Field(..., description="Document format")
    source_url: Optional[str] = Field(None, description="Source URL")
    file_path: Optional[str] = Field(None, description="File path")
    source_type: Optional[SourceType] = Field(None, description="Source type")
    content_length: Optional[int] = Field(None, description="Content length in characters")
    word_count: Optional[int] = Field(None, description="Word count")
    quality_score: Optional[float] = Field(None, description="Quality score (0.0-1.0)")
    processing_status: ProcessingStatus = Field(..., description="Processing status")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    tags: List[str] = Field(..., description="Document tags")
    is_public: bool = Field(..., description="Public visibility")
    collection_id: Optional[UUID] = Field(None, description="Collection ID")
    collection_name: Optional[str] = Field(None, description="Collection name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Search Schemas
class DocumentSearchRequest(BaseModel):
    """Schema for document search requests."""
    query: Optional[str] = Field(None, description="Full-text search query")
    collection_id: Optional[UUID] = Field(None, description="Filter by collection")
    document_format: Optional[List[DocumentFormat]] = Field(None, description="Filter by format")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    min_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum quality score")
    source_type: Optional[SourceType] = Field(None, description="Filter by source type")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date")
    include_archived: Optional[bool] = Field(False, description="Include archived documents")
    
    # Ordering
    order_by: Optional[str] = Field("updated_at", description="Sort field")
    order_direction: Optional[str] = Field("desc", description="Sort direction")
    
    # Pagination
    limit: Optional[int] = Field(50, ge=1, le=1000, description="Maximum results")
    offset: Optional[int] = Field(0, ge=0, description="Results offset")
    
    @validator('order_by')
    def validate_order_by(cls, v):
        allowed_fields = ['created_at', 'updated_at', 'quality_score', 'relevance', 'title']
        if v not in allowed_fields:
            raise ValueError(f"order_by must be one of: {allowed_fields}")
        return v
    
    @validator('order_direction')
    def validate_order_direction(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError("order_direction must be 'asc' or 'desc'")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "machine learning algorithms",
                "document_format": ["txt", "pdf"],
                "tags": ["ai", "research"],
                "min_quality_score": 0.7,
                "created_after": "2025-01-01T00:00:00Z",
                "order_by": "relevance",
                "order_direction": "desc",
                "limit": 50,
                "offset": 0
            }
        }

class DocumentSearchResponse(BaseModel):
    """Schema for document search responses."""
    documents: List[DocumentResponse] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total matching documents")
    returned_count: int = Field(..., description="Number of documents returned")
    limit: int = Field(..., description="Query limit")
    offset: int = Field(..., description="Query offset")
    search_params: Dict[str, Any] = Field(..., description="Search parameters used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "documents": [],
                "total_count": 156,
                "returned_count": 50,
                "limit": 50,
                "offset": 0,
                "search_params": {"query": "machine learning", "order_by": "relevance"}
            }
        }

# Analytics Schemas
class FormatDistribution(BaseModel):
    """Format distribution statistics."""
    txt: int = Field(default=0, description="Number of TXT documents")
    json_format: int = Field(default=0, description="Number of JSON documents")
    docx: int = Field(default=0, description="Number of DOCX documents")
    pdf: int = Field(default=0, description="Number of PDF documents")
    web: int = Field(default=0, description="Number of web documents")

class QualityDistribution(BaseModel):
    """Quality distribution statistics."""
    excellent: int = Field(default=0, description="Documents with quality >= 0.9")
    good: int = Field(default=0, description="Documents with quality 0.7-0.9")
    fair: int = Field(default=0, description="Documents with quality 0.5-0.7")
    poor: int = Field(default=0, description="Documents with quality < 0.5")

class TagFrequency(BaseModel):
    """Tag frequency statistics."""
    tag: str = Field(..., description="Tag name")
    frequency: int = Field(..., description="Usage frequency")

class DocumentSummary(BaseModel):
    """Document collection summary statistics."""
    total_documents: int = Field(..., description="Total number of documents")
    average_quality: float = Field(..., description="Average quality score")
    total_content_size: int = Field(..., description="Total content size in characters")
    format_count: int = Field(..., description="Number of different formats")
    date_range: Dict[str, Optional[datetime]] = Field(..., description="Date range")

class DocumentAnalyticsResponse(BaseModel):
    """Schema for document analytics responses."""
    summary: DocumentSummary = Field(..., description="Summary statistics")
    format_distribution: Dict[str, int] = Field(..., description="Format distribution")
    tag_distribution: List[TagFrequency] = Field(..., description="Tag frequency")
    quality_distribution: QualityDistribution = Field(..., description="Quality distribution")
    generated_at: str = Field(..., description="Analytics generation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary": {
                    "total_documents": 150,
                    "average_quality": 0.785,
                    "total_content_size": 2500000,
                    "format_count": 4,
                    "date_range": {
                        "first_document": "2025-01-15T10:00:00Z",
                        "last_updated": "2025-07-29T15:30:00Z"
                    }
                },
                "format_distribution": {"txt": 80, "pdf": 40, "json": 20, "docx": 10},
                "tag_distribution": [{"tag": "research", "frequency": 45}],
                "quality_distribution": {"excellent": 30, "good": 80, "fair": 35, "poor": 5},
                "generated_at": "2025-07-29T16:00:00Z"
            }
        }

# Chunk Schemas
class DocumentChunkCreate(BaseModel):
    """Schema for creating document chunks."""
    content: str = Field(..., description="Chunk content")
    chunk_index: int = Field(..., description="Chunk position in document")
    splitter_strategy: Optional[str] = Field(None, description="Splitting strategy used")
    chunk_size_config: Optional[int] = Field(None, description="Configured chunk size")
    chunk_overlap_config: Optional[int] = Field(None, description="Configured chunk overlap")
    quality_score: Optional[float] = Field(None, description="Chunk quality score")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Chunk metadata")

class DocumentChunkResponse(BaseModel):
    """Schema for document chunk responses."""
    id: UUID = Field(..., description="Chunk ID")
    document_id: UUID = Field(..., description="Parent document ID")
    content: str = Field(..., description="Chunk content")
    chunk_index: int = Field(..., description="Chunk position")
    content_length: Optional[int] = Field(None, description="Content length")
    splitter_strategy: Optional[str] = Field(None, description="Splitting strategy")
    quality_score: Optional[float] = Field(None, description="Quality score")
    metadata: Dict[str, Any] = Field(..., description="Chunk metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True

# Bulk Operations Schemas
class BulkDocumentStore(BaseModel):
    """Schema for bulk document storage."""
    documents_data: List[Dict[str, Any]] = Field(..., description="Documents to store")
    collection_id: Optional[UUID] = Field(None, description="Target collection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "documents_data": [
                    {
                        "title": "Document 1",
                        "content": "Content of document 1...",
                        "format": "txt",
                        "source": "https://example.com/doc1.txt",
                        "metadata": {"quality_score": 0.8}
                    }
                ],
                "collection_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }

class BulkStoreResponse(BaseModel):
    """Schema for bulk store responses."""
    message: str = Field(..., description="Success message")
    stored_count: int = Field(..., description="Number of documents stored")
    document_ids: List[str] = Field(..., description="IDs of stored documents")
    collection_id: Optional[str] = Field(None, description="Collection ID")

# Export all schemas
__all__ = [
    "DocumentFormat",
    "SourceType", 
    "ProcessingStatus",
    "CollectionCreate",
    "CollectionResponse",
    "DocumentCreate",
    "DocumentResponse",
    "DocumentSearchRequest",
    "DocumentSearchResponse",
    "DocumentAnalyticsResponse",
    "DocumentChunkCreate",
    "DocumentChunkResponse",
    "BulkDocumentStore",
    "BulkStoreResponse"
]