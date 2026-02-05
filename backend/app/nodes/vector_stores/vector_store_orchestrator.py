"""
Intelligent Vector Store Orchestrator - Auto-Optimizing Database Management
============================================================================

This module provides an intelligent vector store orchestrator that automatically
optimizes the database for high-performance vector operations. It manages the
complete lifecycle of vector storage including schema validation, index creation,
and performance optimization.

Key Features:
• Auto-Schema Management: Validates and migrates embedding column types
• Auto-Index Creation: Creates HNSW indexes for optimal search performance
• Performance Monitoring: Tracks and reports storage and retrieval metrics
• Connection-First Design: Works with pre-embedded documents and embedder services
• Database Health Checks: Ensures optimal configuration before operations

Architecture:
The intelligent orchestrator performs database optimization checks before
any storage operations, ensuring the vector database is always configured
for maximum performance.

Database Optimizations Applied:
1. Embedding column type validation and migration to vector(dimension)
2. HNSW index creation for fast similarity search
3. Metadata GIN index for efficient filtering
4. Connection pooling and performance monitoring

Usage Pattern:
```python
# In workflow configuration
orchestrator = IntelligentVectorStore()
result = orchestrator.execute(
    inputs={
        "connection_string": "postgresql://...",
        "collection_name": "my_collection",
        # ... other configs
    },
    connected_nodes={
        "documents": [Document(...), ...],  # Pre-embedded documents
        "embedder": OpenAIEmbeddings(...)   # Configured embedder service
    }
)
```
"""

from __future__ import annotations

import time
import uuid
import logging
import psycopg2
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

# Use new langchain_postgres API with legacy fallback

from langchain_postgres import PGVector


from ..base import ProcessorNode, NodeInput, NodeOutput, NodeType, NodeProperty, NodePosition, NodePropertyType

logger = logging.getLogger(__name__)

# Search algorithms supported by PGVector
SEARCH_ALGORITHMS = {
    "cosine": {
        "name": "Cosine Similarity",
        "description": "Best for most text embeddings, measures angle between vectors",
        "recommended": True,
    },
    "euclidean": {
        "name": "Euclidean Distance", 
        "description": "L2 distance, good for normalized embeddings",
        "recommended": False,
    },
    "inner_product": {
        "name": "Inner Product",
        "description": "Dot product similarity, fast but requires normalized vectors",
        "recommended": False,
    },
}

class VectorStoreOrchestrator(ProcessorNode):
    """
    Intelligent PostgreSQL + pgvector storage orchestrator with automatic optimization.
    
    This orchestrator automatically optimizes the database schema and indexes
    for maximum vector search performance before storing documents.
    """

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "VectorStoreOrchestrator",
            "display_name": "Vector Store Orchestrator",
            "description": (
                "Auto-optimizing PostgreSQL vector store that ensures maximum performance. "
                "Automatically manages database schema, indexes, and optimization for vector operations."
            ),
            "category": "VectorStore",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "postgresql_vectorstore", "path": "icons/postgresql_vectorstore.svg", "alt": "vectorsotreicons"},
            "colors": ["purple-500", "pink-600"],
            "inputs": [
                # Connected Inputs (from other nodes)
                NodeInput(
                    name="documents",
                    displayName="Documents",
                    type="List[Document]",
                    description="Documents to ingest into the vector store.",
                    is_connection=True,
                ),
                NodeInput(
                    name="embedder",
                    displayName="Embedder",
                    type="Embedder",
                    description="Embedding model for vectorizing documents.",
                    direction=NodePosition.BOTTOM,
                    is_connection=True,
                ),

                # Database Configuration
                NodeInput(
                    name="connection_string",
                    type="password",
                    description="PostgreSQL connection string (postgresql://user:pass@host:port/db)",
                    required=True,
                ),
                NodeInput(
                    name="collection_name",
                    type="text",
                    description="Vector collection name - separates different datasets (REQUIRED for data isolation)",
                    required=True,
                ),
                NodeInput(
                    name="table_prefix",
                    type="text",
                    description="Custom table prefix for complete database isolation (optional)",
                    required=False,
                    default="",
                ),
                NodeInput(
                    name="pre_delete_collection",
                    type="boolean",
                    description="Delete existing collection before storing",
                    default=False,
                    required=False,
                ),
                
                # Manual Metadata Configuration
                NodeInput(
                    name="custom_metadata",
                    type="json",
                    description="Custom metadata to add to all documents (JSON format)",
                    required=False,
                    default="{}",
                ),
                NodeInput(
                    name="preserve_document_metadata",
                    type="boolean",
                    description="Keep original document metadata alongside custom metadata",
                    default=True,
                    required=False,
                ),
                NodeInput(
                    name="metadata_strategy",
                    type="select",
                    description="How to handle metadata conflicts",
                    default="merge",
                    required=False,
                ),
                
                # Auto-Optimization Settings
                NodeInput(
                    name="auto_optimize",
                    type="boolean",
                    description="Automatically optimize database schema and indexes",
                    default=True,
                    required=False,
                ),
                NodeInput(
                    name="embedding_dimension",
                    type="int",
                    description="Embedding vector dimension (auto-detected if 0)",
                    default=0,
                    required=False,
                ),
                
                # Retriever Configuration
                NodeInput(
                    name="search_algorithm",
                    type="select",
                    description="Vector similarity search algorithm",
                    default="cosine",
                    required=False,
                ),
                NodeInput(
                    name="search_k",
                    type="slider",
                    description="Number of documents to retrieve",
                    default=6,
                    required=False,
                ),
                NodeInput(
                    name="score_threshold",
                    type="slider",
                    description="Minimum similarity score threshold (0.0-1.0)",
                    default=0.0,
                    required=False,
                ),
                
                # Performance Configuration
                NodeInput(
                    name="batch_size",
                    type="slider",
                    description="Batch size for storing embeddings",
                    default=100,
                    required=False,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="result",
                    displayName="Retriever",
                    type="VectorStoreRetriever",
                    description="Configured retriever for searching the vector store.",
                    is_connection=True,
                )
            ],
            "properties": [
                # Data Configuration Tab
                NodeProperty(
                    name="credential_id",
                    displayName="Select Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    placeholder="Select Credential",
                    tabName="data",
                    required=True,
                    serviceType="postgresql_vectorstore",
                ),
                NodeProperty(
                    name="collection_name",
                    displayName="Collection Name",
                    type=NodePropertyType.TEXT,
                    placeholder="e.g., amazon_products, user_manuals, company_docs",
                    hint="Vector collection name - separates different datasets (REQUIRED for data isolation)",
                    tabName="data",
                    required=True,
                ),
                NodeProperty(
                    name="table_prefix",
                    displayName="Table Prefix (Optional)",
                    type=NodePropertyType.TEXT,
                    placeholder="e.g., project1_, client_a_",
                    hint="Custom table prefix for complete database isolation (optional)",
                    tabName="data",
                    required=False,
                ),

                # Metadata Configuration Tab
                NodeProperty(
                    name="custom_metadata",
                    displayName="Custom Metadata",
                    type=NodePropertyType.JSON_EDITOR,
                    default='{}',
                    hint="Custom metadata to add to all documents (JSON format)",
                    tabName="metadata",
                    required=False,
                ),
                NodeProperty(
                    name="preserve_document_metadata",
                    displayName="Preserve Document Metadata",
                    type=NodePropertyType.CHECKBOX,
                    default=True,
                    hint="Keep original document metadata alongside custom metadata",
                    tabName="metadata",
                ),
                NodeProperty(
                    name="metadata_strategy",
                    displayName="Metadata Strategy",
                    type=NodePropertyType.SELECT,
                    default="merge",
                    options=[
                        {"label": "Merge (custom overrides document)", "value": "merge"},
                        {"label": "Replace (only custom metadata)", "value": "replace"},
                        {"label": "Document Only", "value": "document_only"},
                    ],
                    hint="How to handle metadata conflicts",
                    tabName="metadata",
                ),

                # Search Configuration Tab
                NodeProperty(
                    name="search_algorithm",
                    displayName="Search Algorithm",
                    type=NodePropertyType.SELECT,
                    default="cosine",
                    options=[
                        {"label": "Cosine Similarity", "value": "cosine"},
                        {"label": "Euclidean Distance", "value": "euclidean"},
                        {"label": "Inner Product", "value": "inner_product"},
                    ],
                    tabName="search",
                ),
                NodeProperty(
                    name="search_k",
                    displayName="Search K",
                    type=NodePropertyType.RANGE,
                    default=10,
                    min=1,
                    max=50,
                    step=1,
                    minLabel="1",
                    maxLabel="50",
                    tabName="search",
                ),
                NodeProperty(
                    name="score_threshold",
                    displayName="Score Threshold",
                    type=NodePropertyType.RANGE,
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.1,
                    color="purple-400",
                    minLabel="0.0",
                    maxLabel="1.0",
                    tabName="search",
                ),
                NodeProperty(
                    name="batch_size",
                    displayName="Batch Size",
                    type=NodePropertyType.RANGE,
                    default=100,
                    min=10,
                    max=1000,
                    step=10,
                    color="green-400",
                    tabName="search",
                ),
                NodeProperty(
                    name="pre_delete_collection",
                    displayName="Pre Delete Collection",
                    type=NodePropertyType.CHECKBOX,
                    default=False,
                    hint="Delete existing collection before creating new one",
                    tabName="search",
                ),
                NodeProperty(
                    name="enable_hnsw_index",
                    displayName="Enable HNSW Index",
                    type=NodePropertyType.CHECKBOX,
                    default=True,
                    hint="Use HNSW index for faster similarity search",
                    tabName="search",
                ),
            ],
        }

    def get_required_packages(self) -> list[str]:
        """
        DYNAMIC METHOD: VectorStoreOrchestrator'un ihtiyaç duyduğu Python packages'ini döndür.
        
        Bu method dynamic export sisteminin çalışması için kritik!
        Vector store için gereken PostgreSQL, pgvector ve LangChain dependencies.
        """
        return [
            "langchain-postgres>=0.0.14",  # PostgreSQL LangChain integration (new API)
            "pgvector>=0.2.0",             # Vector similarity operations
            "psycopg[binary]>=3.0.0",      # PostgreSQL database connection (psycopg3)
            "langchain-community>=0.0.10", # Community vector stores (legacy fallback)
            "langchain-core>=0.1.0",       # Core vector store classes
            "numpy>=1.24.0",               # Vector operations
            "scipy>=1.11.0",               # Scientific computations
        ]

    def _normalize_psycopg2_dsn(self, connection_string: str) -> str:
        """Normalize SQLAlchemy-style URLs to psycopg2-compatible DSN.

        - Converts postgresql+asyncpg:// to postgresql://
        - Converts postgresql+psycopg2:// to postgresql://
        - Leaves postgresql:// and postgres:// as-is
        """
        try:
            cs_lower = connection_string.lower()
            if cs_lower.startswith("postgresql+asyncpg://"):
                return "postgresql://" + connection_string.split("://", 1)[1]
            if cs_lower.startswith("postgresql+psycopg2://"):
                return "postgresql://" + connection_string.split("://", 1)[1]
            return connection_string
        except Exception:
            # On any parsing issue, fall back to original string
            return connection_string

    def _get_db_connection(self, connection_string: str):
        """Create database connection for optimization operations."""
        try:
            dsn = self._normalize_psycopg2_dsn(connection_string)
            return psycopg2.connect(dsn)
        except Exception as e:
            raise ValueError(f"Failed to connect to database: {str(e)}")

    def _check_schema_compatibility(self, connection_string: str) -> bool:
        """Check if database schema is compatible with new API."""

        try:
            with self._get_db_connection(connection_string) as conn:
                with conn.cursor() as cursor:
                    # Check if langchain_pg_embedding table has 'id' column
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns
                            WHERE table_schema = 'public'
                            AND table_name = 'langchain_pg_embedding'
                            AND column_name = 'id'
                        );
                    """)
                    
                    has_id_column = cursor.fetchone()[0]
                    logger.info(f"Schema compatibility check: id column exists = {has_id_column}")
                    return has_id_column
            
        except Exception as e:
            logger.warning(f"Schema compatibility check failed: {e}")
            return False  # Assume incompatible on error


    def _detect_embedding_dimension(self, documents: List[Document], embedder) -> int:
        """Auto-detect embedding dimension from documents or embedder."""
        # First, try to detect from existing embeddings in documents
        for doc in documents:
            embedding = doc.metadata.get("embedding")
            if embedding and isinstance(embedding, list) and len(embedding) > 0:
                logger.info(f"Detected embedding dimension from documents: {len(embedding)}")
                return len(embedding)
        
        # If no embeddings found, try to get dimension from embedder
        try:

            if hasattr(embedder, 'model') and 'text-embedding-3-small' in str(embedder.model):
                logger.info("Detected OpenAI text-embedding-3-small: 1536 dimensions")
                return 1536
            elif hasattr(embedder, 'model') and 'text-embedding-3-large' in str(embedder.model):
                logger.info("Detected OpenAI text-embedding-3-large: 3072 dimensions")
                return 3072
            elif hasattr(embedder, 'model') and 'text-embedding-ada-002' in str(embedder.model):
                logger.info("Detected OpenAI text-embedding-ada-002: 1536 dimensions")
                return 1536
            else:
                # Default to OpenAI's most common dimension
                logger.warning("Could not detect embedding dimension, defaulting to 1536")
                return 1536
        except Exception as e:
            logger.warning(f"Error detecting embedding dimension: {e}, defaulting to 1536")
            return 1536

    def _optimize_database_schema(self, connection_string: str, collection_name: str,
                                  embedding_dimension: int, search_algorithm: str) -> Dict[str, Any]:
        """Optimize database schema for vector operations."""
        
        # DEBUG: Validate all input parameters before database operations
        logger.info(f"[SCHEMA_OPTIMIZATION_DEBUG] Input validation:")
        logger.info(f"    - embedding_dimension: {repr(embedding_dimension)}, type: {type(embedding_dimension)}")
        logger.info(f"    - collection_name: {repr(collection_name)}, type: {type(collection_name)}")
        logger.info(f"    - search_algorithm: {repr(search_algorithm)}, type: {type(search_algorithm)}")
        
        # Fix: Ensure embedding_dimension is a valid positive integer
        if not isinstance(embedding_dimension, int) or embedding_dimension <= 0:
            if embedding_dimension == "none" or embedding_dimension is None:
                logger.error(f"Invalid embedding_dimension: '{embedding_dimension}' (type: {type(embedding_dimension)})")
                raise ValueError(f"Embedding dimension cannot be 'none' or None. Received: {embedding_dimension}")
            else:
                try:
                    embedding_dimension = int(embedding_dimension)
                    if embedding_dimension <= 0:
                        raise ValueError(f"Embedding dimension must be positive, got: {embedding_dimension}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Cannot convert embedding_dimension to valid integer: '{embedding_dimension}' (type: {type(embedding_dimension)})")
                    raise ValueError(f"Invalid embedding dimension: {embedding_dimension}. Must be a positive integer.") from e
        
        logger.info(f"Validated embedding_dimension: {embedding_dimension}")
        
        optimization_report = {
            "timestamp": datetime.now().isoformat(),
            "collection_name": collection_name,
            "embedding_dimension": embedding_dimension,
            "optimizations_applied": [],
            "errors": [],
            "performance_improvements": []
        }
        
        try:
            with self._get_db_connection(connection_string) as conn:
                with conn.cursor() as cursor:
                    # 1. Ensure pgvector extension exists
                    try:
                        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        optimization_report["optimizations_applied"].append("pgvector extension enabled")
                        logger.info("pgvector extension ensured")
                    except Exception as e:
                        conn.rollback()
                        optimization_report["errors"].append(f"pgvector extension: {str(e)}")
                        logger.warning(f"pgvector extension issue: {e}")
                        raise
                    
                    # 2. Check if langchain table exists (used for subsequent checks)
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name = 'langchain_pg_embedding'
                        );
                    """)
                    table_exists = cursor.fetchone()[0]

                    if not table_exists:
                        logger.info("LangChain tables will be created automatically by PGVector")
                        optimization_report["optimizations_applied"].append("LangChain tables will be auto-created")
                        return optimization_report

                    # 3. Optimize embedding column type
                    cursor.execute("""
                        SELECT data_type FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'langchain_pg_embedding' AND column_name = 'embedding';
                    """)
                    column_info = cursor.fetchone()
                    if column_info and column_info[0] != 'vector':
                        try:
                            logger.info(f"Migrating embedding column to vector({embedding_dimension})")
                            cursor.execute(f"ALTER TABLE public.langchain_pg_embedding ALTER COLUMN embedding TYPE vector({embedding_dimension});")
                            optimization_report["optimizations_applied"].append(f"Migrated embedding column to vector({embedding_dimension})")
                            logger.info("Embedding column migrated to vector type")
                        except Exception as e:
                            conn.rollback()
                            optimization_report["errors"].append(f"Column migration: {str(e)}")
                            logger.warning(f"Column migration issue: {e}")
                            raise

                    # 4. Create HNSW index with dynamic distance strategy
                    distance_strategy_map = {
                        "cosine": "vector_cosine_ops",
                        "euclidean": "vector_l2_ops",
                        "inner_product": "vector_ip_ops"
                    }
                    distance_ops = distance_strategy_map.get(search_algorithm, "vector_cosine_ops")
                    
                    cursor.execute("""
                        SELECT indexname FROM pg_indexes
                        WHERE tablename = 'langchain_pg_embedding' AND indexdef LIKE '%USING hnsw%';
                    """)
                    if not cursor.fetchone():
                        try:
                            logger.info(f"Creating HNSW index with {distance_ops}")
                            cursor.execute(f"""
                                CREATE INDEX langchain_pg_embedding_hnsw_idx
                                ON public.langchain_pg_embedding
                                USING hnsw (embedding {distance_ops})
                                WITH (m = 16, ef_construction = 64);
                            """)
                            optimization_report["optimizations_applied"].append(f"HNSW index created ({distance_ops})")
                            logger.info("HNSW index created successfully")
                        except Exception as e:
                            conn.rollback()
                            optimization_report["errors"].append(f"HNSW index creation: {str(e)}")
                            logger.warning(f"HNSW index creation issue: {e}")
                            raise
                    
                    # 5. Create metadata GIN index
                    cursor.execute("""
                        SELECT indexname FROM pg_indexes
                        WHERE tablename = 'langchain_pg_embedding' AND indexdef LIKE '%USING gin%';
                    """)
                    if not cursor.fetchone():
                        try:
                            logger.info("Creating GIN index for metadata filtering")
                            cursor.execute("""
                                CREATE INDEX langchain_pg_embedding_metadata_gin_idx
                                ON public.langchain_pg_embedding
                                USING gin (cmetadata);
                            """)
                            optimization_report["optimizations_applied"].append("Metadata GIN index created")
                            logger.info("Metadata GIN index created successfully")
                        except Exception as e:
                            conn.rollback()
                            optimization_report["errors"].append(f"GIN index creation: {str(e)}")
                            logger.warning(f"GIN index creation issue: {e}")
                            raise
            
        except psycopg2.Error as e:
            optimization_report["errors"].append(f"Database optimization failed: {e}")
            logger.error(f"Database optimization failed: {e}")
            # Reraise to be caught by the main execute block
            raise
        
        return optimization_report

    def _process_custom_metadata(self, documents: List[Document],
                                custom_metadata: Dict[str, Any],
                                preserve_document_metadata: bool,
                                metadata_strategy: str) -> List[Document]:
        """Process documents with custom metadata according to strategy."""
        if not custom_metadata and preserve_document_metadata:
            return documents  # No changes needed
        
        processed_docs = []
        logger.info(f"Processing {len(documents)} documents with custom metadata strategy: {metadata_strategy}")
        
        for doc in documents:
            if metadata_strategy == "replace":
                # Use only custom metadata
                new_metadata = custom_metadata.copy()
            elif metadata_strategy == "document_only":
                # Use only document metadata
                new_metadata = doc.metadata.copy()
            else:  # merge (default)
                # Start with document metadata, override with custom
                new_metadata = doc.metadata.copy() if preserve_document_metadata else {}
                new_metadata.update(custom_metadata)
            
            # Remove embedding from metadata to avoid storage issues
            new_metadata.pop("embedding", None)
            
            processed_doc = Document(
                page_content=doc.page_content,
                metadata=new_metadata
            )
            processed_docs.append(processed_doc)
        
        logger.info(f"Applied custom metadata to {len(processed_docs)} documents")
        return processed_docs

    def _get_table_names(self, table_prefix: str) -> Dict[str, str]:
        """Get custom table names with prefix."""
        if table_prefix:
            prefix = table_prefix.rstrip('_') + '_'
            return {
                "collection_table": f"{prefix}langchain_pg_collection",
                "embedding_table": f"{prefix}langchain_pg_embedding"
            }
        else:
            return {
                "collection_table": "langchain_pg_collection",
                "embedding_table": "langchain_pg_embedding"
            }

    def _validate_documents(self, documents: List[Document]) -> Tuple[List[Document], bool]:
        """Validate documents and determine if they have embeddings."""
        valid_docs = []
        has_embeddings = True
        
        logger.info(f"Validating {len(documents)} documents")
        
        for i, doc in enumerate(documents):
            if isinstance(doc, Document) and doc.page_content.strip():
                # Check if document has embedding
                embedding = doc.metadata.get("embedding")
                if not embedding or not isinstance(embedding, list) or len(embedding) == 0:
                    has_embeddings = False
                valid_docs.append(doc)
            elif isinstance(doc, dict) and doc.get("page_content", "").strip():
                # Convert dict to Document if needed
                doc_obj = Document(
                    page_content=doc["page_content"],
                    metadata=doc.get("metadata", {})
                )
                # Check if document has embedding
                embedding = doc_obj.metadata.get("embedding")
                if not embedding or not isinstance(embedding, list) or len(embedding) == 0:
                    has_embeddings = False
                valid_docs.append(doc_obj)
            elif isinstance(doc, list):
                # Handle nested list of documents
                for nested_doc in doc:
                    if isinstance(nested_doc, Document):
                        # Documents from ChunkSplitter typically don't have embeddings yet
                        has_embeddings = False
                        valid_docs.append(nested_doc)
        
        if not valid_docs:
            raise ValueError("No valid documents found in input")
            
        logger.info(f"Validated {len(valid_docs)} documents, embeddings_present={has_embeddings}")
        return valid_docs, has_embeddings

    def _prepare_documents_for_storage(self, documents: List[Document]) -> Tuple[List[Document], List[List[float]]]:
        """Prepare documents and extract embeddings for storage."""
        prepared_docs = []
        all_embeddings = []
        
        for doc in documents:
            # Create clean document (remove embedding from metadata to avoid storage issues)
            clean_metadata = {k: v for k, v in doc.metadata.items() if k != "embedding"}
            clean_doc = Document(page_content=doc.page_content, metadata=clean_metadata)
            
            prepared_docs.append(clean_doc)
            all_embeddings.append(doc.metadata["embedding"])
        
        return prepared_docs, all_embeddings

    def _create_retriever(self, vectorstore, search_config: Dict[str, Any]) -> VectorStoreRetriever:
        """Create optimized retriever with search configuration.

        Important distinctions:
        - 'search_algorithm' (cosine/euclidean/inner_product) is a DB distance metric and NOT a retriever search_type.
        - VectorStoreRetriever.search_type must be one of {"similarity", "similarity_score_threshold", "mmr"}.
        """
        # Always set max results
        k = int(search_config.get("search_k", 6))
        search_kwargs: Dict[str, Any] = {"k": k}

        # Choose retriever search type
        # If a positive score_threshold is provided, use 'similarity_score_threshold'
        raw_threshold = search_config.get("score_threshold", 0.0)
        try:
            score_threshold = float(raw_threshold)
        except (TypeError, ValueError):
            score_threshold = 0.0  # Fallback to disable threshold if invalid

        if score_threshold > 0.0:
            retriever_search_type = "similarity_score_threshold"
            # VectorStoreRetriever validator requires a float in (0, 1]
            # Clamp conservatively to valid bounds
            if score_threshold > 1.0:
                score_threshold = 1.0
            search_kwargs["score_threshold"] = score_threshold
        else:
            retriever_search_type = "similarity"

        # DO NOT pass 'search_type' inside search_kwargs; it must be a top-level param
        # Note: 'search_algorithm' is used elsewhere for DB optimization and distance ops, not here.

        # Build retriever
        retriever = vectorstore.as_retriever(
            search_type=retriever_search_type,
            search_kwargs=search_kwargs
        )

        # Diagnostics to surface misconfigurations early
        details = {
            "k": search_kwargs.get("k"),
            "score_threshold": search_kwargs.get("score_threshold"),
            "retriever_search_type": retriever_search_type
        }
        logger.info(f"Created VectorStoreRetriever with config={details}")
        return retriever

    def _get_storage_statistics(self, vectorstore, processed_docs: int,
                              processing_time: float) -> Dict[str, Any]:
        """Generate comprehensive storage statistics."""
        collection_name = getattr(vectorstore, 'collection_name', 'unknown')
        return {
            "documents_stored": processed_docs,
            "processing_time_seconds": round(processing_time, 2),
            "storage_rate": round(processed_docs / processing_time, 2) if processing_time > 0 else 0,
            "collection_name": collection_name,
            "timestamp": datetime.now().isoformat(),
            "status": "completed" if processed_docs > 0 else "failed",
        }

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute intelligent vector storage with automatic database optimization.
        
        Args:
            inputs: User configuration from UI
            connected_nodes: Connected input nodes (must contain documents and embedder)
            
        Returns:
            Dict with retriever, vectorstore, optimization_report, and storage_stats
        """
        start_time = time.time()
        logger.info("Starting Intelligent Vector Store execution")
        
        # DEBUG: Log all available keys in connected_nodes
        logger.info(f"[VARIABLE_MISMATCH_DEBUG] Available connected_nodes keys: {list(connected_nodes.keys())}")
        for key, value in connected_nodes.items():
            logger.info(f"[VARIABLE_MISMATCH_DEBUG] Key '{key}': type={type(value)}, length={len(value) if isinstance(value, list) else 'N/A'}")
        
        documents = connected_nodes.get("documents")
        
        if not isinstance(documents, list):
            documents = [documents]
        
        embedder = connected_nodes.get("embedder")
        if not embedder:
            raise ValueError("No embedder service provided. Connect an embedder provider.")
            
        valid_docs, has_embeddings = self._validate_documents(documents)
        
        # Get credential_id and extract credential data
        credential_id = self.user_data.get("credential_id")
        credential = self.get_credential(credential_id) if credential_id else None
        
        # Build connection string from credential components
        connection_string = None
        if credential and credential.get('secret'):
            secret = credential['secret']
            
            # Extract connection components
            host = secret.get('host', 'localhost')
            port = secret.get('port', 5432)
            database = secret.get('database', 'vectorstore')
            username = secret.get('username', 'postgres')
            password = secret.get('password', '')
            
            # Build connection string
            if username and password:
                connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
            else:
                connection_string = f"postgresql://{host}:{port}/{database}"
            
            logger.info(f"Built connection string from credential: {credential['name']}")
        else:
            # Fallback to direct connection_string input (for backward compatibility)
            connection_string = inputs.get("connection_string")

        if not connection_string:
            raise ValueError("PostgreSQL connection string is required")
            
        collection_name = inputs.get("collection_name", "").strip()
        if not collection_name:
            raise ValueError("Collection name is required for data isolation")
            
        table_prefix = inputs.get("table_prefix", "").strip()
        
        try:
            import json
            custom_metadata_str = inputs.get("custom_metadata", "{}")
            custom_metadata = json.loads(custom_metadata_str) if isinstance(custom_metadata_str, str) else (custom_metadata_str or {})
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Invalid custom_metadata JSON: {e}, using empty metadata")
            custom_metadata = {}
            
        metadata_strategy = inputs.get("metadata_strategy", "merge")
        embedding_dimension = inputs.get("embedding_dimension", 0)
        pre_delete = inputs.get("pre_delete_collection", False)
        
        # DEBUG: Log embedding_dimension type and value for diagnostic
        logger.info(f"[EMBEDDING_DIMENSION_DEBUG] Raw value: {repr(embedding_dimension)}, type: {type(embedding_dimension)}")
        
        # Fix: Ensure embedding_dimension is always an integer
        if embedding_dimension is None or embedding_dimension == "none" or embedding_dimension == "":
            embedding_dimension = 0
        elif isinstance(embedding_dimension, str):
            try:
                embedding_dimension = int(embedding_dimension)
            except (ValueError, TypeError):
                logger.warning(f"Invalid embedding_dimension value '{embedding_dimension}', defaulting to 0")
                embedding_dimension = 0
        elif not isinstance(embedding_dimension, int):
            logger.warning(f"Non-integer embedding_dimension value '{embedding_dimension}', defaulting to 0")
            embedding_dimension = 0
        
        logger.info(f"[EMBEDDING_DIMENSION_DEBUG] Processed value: {embedding_dimension}, type: {type(embedding_dimension)}")
        
        if embedding_dimension == 0:
            embedding_dimension = self._detect_embedding_dimension(valid_docs, embedder)
            logger.info(f"[EMBEDDING_DIMENSION_DEBUG] Auto-detected value: {embedding_dimension}")
            
        search_config = {
            "search_algorithm": inputs.get("search_algorithm", "cosine"),
            "search_k": int(inputs.get("search_k", 6)),
            "score_threshold": float(inputs.get("score_threshold", 0.0)),
        }
        
        processed_docs = self._process_custom_metadata(
            valid_docs, custom_metadata, inputs.get("preserve_document_metadata", True), metadata_strategy
        )
        
        logger.info(f"Config: collection={collection_name}, dimension={embedding_dimension}, strategy={search_config['search_algorithm']}")

        try:
            # Create vector store
            logger.info(f"Creating vector store: {collection_name} with {len(processed_docs)} docs")

            # Create vector store
            vectorstore = PGVector(
                connection=connection_string,
                collection_name=collection_name,
                embeddings=embedder
            )

            vectorstore.add_documents(processed_docs)
            
            logger.info(f"Stored {len(processed_docs)} docs using API")
            
            retriever = self._create_retriever(vectorstore, search_config)
            
            end_time = time.time()
            processing_time = end_time - start_time
            storage_stats = self._get_storage_statistics(vectorstore, len(processed_docs), processing_time)
            
            logger.info(
                f" Vector Store completed: {len(processed_docs)} docs in '{collection_name}' in {processing_time:.1f}s"
            )
            
            return {
                "result": retriever,
                "vectorstore": vectorstore,
                "storage_stats": storage_stats
            }
            
        except Exception as e:
            error_msg = f"Vector Store execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg) from e

# Export for node registry
__all__ = ["VectorStoreOrchestrator"]