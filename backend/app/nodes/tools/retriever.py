"""
KAI-Fusion Retriever Provider - Agent-Ready Vector Search Tool Creator
=====================================================================

This module implements a RetrieverProvider node that creates retriever tools
for agents from existing vector databases. It connects to PostgreSQL+pgvector
databases and creates LangChain Tools that agents can use for document search.

Key Features:
- Connects to existing vector databases (no document storage)
- Creates retriever tools for agent integration
- Supports multiple LangChain search algorithms and strategies
- Advanced metadata filtering and search optimization
- Performance monitoring and configuration validation

LangChain Search Algorithms Supported:
=====================================

1. **similarity**: Default cosine similarity search
   - Fast, works well for most text embeddings
   - Returns k most similar documents

2. **similarity_score_threshold**: Similarity with minimum score
   - Only returns documents above threshold score
   - Good for quality filtering

3. **mmr**: Maximum Marginal Relevance
   - Balances relevance and diversity
   - Reduces redundant results

4. **similarity_with_score**: Returns documents with scores
   - Provides similarity scores for ranking
   - Useful for confidence analysis

Authors: KAI-Fusion Development Team
Version: 1.0.0
Last Updated: 2025-01-13
"""

from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime

from langchain_core.tools import Tool
from langchain_core.retrievers import BaseRetriever
from langchain_postgres import PGVector
from langchain.retrievers import ContextualCompressionRetriever

from app.nodes.base import ProviderNode, NodeInput, NodeOutput, NodeType, NodeProperty, NodePosition, NodePropertyType

logger = logging.getLogger(__name__)

# LangChain Vector Search Algorithms (for search_type configuration)
SEARCH_ALGORITHMS = {
    "similarity": {
        "name": "Similarity Search",
        "description": "Default cosine similarity search - fast and efficient for most text embeddings",
        "parameters": ["k"],
        "recommended": True
    },
    "similarity_score_threshold": {
        "name": "Similarity with Score Threshold",
        "description": "Only returns documents above minimum similarity score - good for quality filtering",
        "parameters": ["k", "score_threshold"],
        "recommended": True
    },
    "mmr": {
        "name": "Maximum Marginal Relevance",
        "description": "Balances relevance and diversity to reduce redundant results",
        "parameters": ["k", "fetch_k", "lambda_mult"],
        "recommended": False
    },
    "similarity_with_score": {
        "name": "Similarity with Scores",
        "description": "Returns documents with similarity scores for confidence analysis",
        "parameters": ["k"],
        "recommended": False
    }
}

# Filter strategies for metadata filtering
FILTER_STRATEGIES = {
    "exact": {
        "name": "Exact Match",
        "description": "Exact match for all metadata fields"
    },
    "partial": {
        "name": "Partial Match",
        "description": "Partial/contains match for text fields"
    },
    "range": {
        "name": "Range Filtering",
        "description": "Range filtering for numeric fields"
    }
}


class RetrieverProvider(ProviderNode):
    """
    Retriever Provider - Creates Agent-Ready Vector Search Tools
    ===========================================================

    This provider node connects to existing vector databases and creates
    retriever tools that agents can use. Designed according to the provided JSON configuration.
    """

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "RetrieverProvider",
            "display_name": "Retriever Provider",
            "description": "Provider node that creates configured retriever tools for agents. Connect to a vector database and embeddings provider to create a search tool for your agents.",
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "file-stack", "path": None, "alt": None},
            "colors": ["indigo-500", "purple-600"],
            "version": "1.0.0",
            "tags": [],
            "documentation_url": None,
            "examples": [],
            "inputs": [
                NodeInput(
                    name="collection_name",
                    type="str",
                    description="Vector collection name in the database",
                    required=True,
                    is_connection=False,
                    default=None,
                    ui_config=None,
                    validation_rules=None
                ),

                # Search Configuration
                NodeInput(
                    name="search_k",
                    type="int",
                    description="Number of documents to retrieve",
                    required=False,
                    is_connection=False,
                    default=6,
                    ui_config=None,
                    validation_rules=None
                ),
                NodeInput(
                    name="search_type",
                    type="str",
                    description="Search type for retrieval",
                    required=False,
                    is_connection=False,
                    default="similarity",
                    ui_config=None,
                    validation_rules=None
                ),
                NodeInput(
                    name="score_threshold",
                    type="float",
                    description="Minimum similarity score threshold (0.0-1.0)",
                    required=False,
                    is_connection=False,
                    default=0,
                    ui_config=None,
                    validation_rules=None
                ),

                # Metadata Filtering (from JSON config)
                NodeInput(
                    name="metadata_filter",
                    type="json",
                    description="Filter documents by metadata (JSON format)",
                    required=False,
                    is_connection=False,
                    default="{}",
                    ui_config=None,
                    validation_rules=None
                ),
                NodeInput(
                    name="filter_strategy",
                    type="select",
                    description="How to apply metadata filters",
                    required=False,
                    is_connection=False,
                    default="exact",
                    ui_config=None,
                    validation_rules=None
                ),
                NodeInput(
                    name="enable_metadata_filtering",
                    type="boolean",
                    description="Enable metadata-based filtering for search results",
                    required=False,
                    is_connection=False,
                    default=False,
                    ui_config=None,
                    validation_rules=None
                ),

                # Connected Inputs (from JSON config)
                NodeInput(
                    name="embedder",
                    displayName="Embedder",
                    type="embedder",
                    description="Embedder service for retrieval (OpenAIEmbeddings, etc.)",
                    required=True,
                    default=None,
                    ui_config=None,
                    validation_rules=None,
                    direction=NodePosition.BOTTOM,
                    is_connection=True,
                ),
                NodeInput(
                    name="reranker",
                    displayName="Reranker",
                    type="reranker",
                    description="Optional reranker service for enhanced retrieval (CohereReranker, etc.)",
                    required=False,
                    default=None,
                    ui_config=None,
                    direction=NodePosition.BOTTOM,
                    is_connection=True,
                    validation_rules=None
                )
            ],
            "outputs": [
                NodeOutput(
                    name="retriever_tool",
                    displayName="Retriever Tool",
                    type="BaseTool",
                    format=None,
                    description="Configured retriever tool ready for use with agents",
                    direction=NodePosition.TOP,
                    is_connection=True,
                )
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="Select Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    placeholder="Select Credential",
                    required=False
                ),
                NodeProperty(
                    name="collection_name",
                    displayName="Collection Name",
                    type=NodePropertyType.TEXT,
                    placeholder="e.g., documents, products, knowledge_base",
                    required=True
                ),
                NodeProperty(
                    name="search_type",
                    displayName="Search Type",
                    type=NodePropertyType.SELECT,
                    default="similarity",
                    options=[
                        {"label": "Similarity Search", "value": "similarity"},
                        {"label": "MMR (Maximal Marginal Relevance)", "value": "mmr"}
                    ],
                    hint="Similarity search for exact matches, MMR for diverse results",
                    required=True
                ),
                NodeProperty(
                    name="search_k",
                    displayName="Search K",
                    type=NodePropertyType.RANGE,
                    default=6,
                    min=1,
                    max=50,
                    minLabel="Few Results",
                    maxLabel="Many Results",
                    required=True
                ),
                NodeProperty(
                    name="score_threshold",
                    displayName="Score Threshold",
                    type=NodePropertyType.RANGE,
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.05,
                    minLabel="Inclusive",
                    maxLabel="Strict",
                    required=True
                ),
                NodeProperty(
                    name="enable_metadata_filtering",
                    displayName="Enable Metadata Filtering",
                    hint="Enable metadata-based filtering for search results",
                    type=NodePropertyType.CHECKBOX,
                    default=False
                ),
                NodeProperty(
                    name="metadata_filter",
                    displayName="Metadata Filter",
                    type=NodePropertyType.JSON_EDITOR,
                    description="Filter documents by metadata (JSON format)",
                    displayOptions={
                        "show": {
                            "enable_metadata_filtering": True
                        } 
                    }
                ),
                NodeProperty(
                    name="filter_strategy",
                    displayName="Filter Strategy",
                    type=NodePropertyType.SELECT,
                    default="exact",
                    options=[
                        {"label": "Exact Match", "value": "exact"},
                        {"label": "Contains", "value": "contains"},
                        {"label": "Any Match (OR)", "value": "or"}
                    ],
                    hint="How to apply metadata filters",
                    displayOptions={
                        "show": {
                            "enable_metadata_filtering": True
                        }
                    }
                )
            ],
        }

    def execute(self, **inputs) -> Dict[str, Any]:
        """
        Create retriever tool from existing vector database.

        Follows the VectorStoreOrchestrator credential pattern.
        """
        logger.info("[RETRIEVER] Creating Retriever Tool from existing vector database")

        try:
            # Extract configuration from inputs
            collection_name = inputs.get("collection_name")
            search_k = inputs.get("search_k", 6)
            search_type = inputs.get("search_type", "similarity")
            score_threshold = inputs.get("score_threshold", 0)
            metadata_filter_str = inputs.get("metadata_filter", "{}")
            filter_strategy = inputs.get("filter_strategy", "exact")
            enable_metadata_filtering = inputs.get("enable_metadata_filtering", False)
            embedder = inputs.get("embedder")
            reranker = inputs.get("reranker")  # Optional

            # Get credential_id and extract credential data (like VectorStoreOrchestrator)
            credential_id = self.user_data.get("credential_id")
            credential = self.get_credential(credential_id) if credential_id else None
            
            # Extract database connection from credential (with null safety)
            database_connection = None
            if credential and credential.get('secret'):
                secret = credential['secret']
                
                # Extract connection components
                host = secret.get('host', 'localhost')
                port = secret.get('port', 5432)
                database = secret.get('database')
                username = secret.get('username')
                password = secret.get('password')
                
                if database and username and password:
                    # Build connection string
                    database_connection = f"postgresql://{username}:{password}@{host}:{port}/{database}"
                    logger.info(f"Connected to vector database: {host}:{port}/{database}")
                else:
                    logger.warning("Missing required database credentials (database, username, or password)")

            # Validation
            if not database_connection:
                raise ValueError("Database connection is required. Please provide database credentials.")
            if not collection_name:
                raise ValueError("Collection name is required")
            if not embedder:
                raise ValueError("Embedder service is required - connect an embeddings provider")

            # Parse metadata filter
            try:
                if isinstance(metadata_filter_str, str):
                    metadata_filter = json.loads(metadata_filter_str)
                else:
                    metadata_filter = metadata_filter_str or {}
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid metadata filter JSON: {e}, using empty filter")
                metadata_filter = {}

            # Create vector store connection
            retriever = self._create_vectorstore_connection(
                database_connection, collection_name, embedder
            )

            # Build search configuration
            search_config = {
                "search_type": search_type,
                "search_k": int(search_k),
                "score_threshold": float(score_threshold),
                "metadata_filter": metadata_filter,
                "filter_strategy": filter_strategy,
                "enable_metadata_filtering": enable_metadata_filtering,
                "reranker": reranker
            }

            # Create retriever with configuration
            retriever = self._create_configured_retriever(retriever, search_config)
            if reranker:
                retriever=ContextualCompressionRetriever(
                    base_compressor=reranker,
                    base_retriever=retriever,
                )
            # Create agent-ready tool
            retriever_tool = self._create_retriever_tool(
                retriever, collection_name, search_config
            )

            logger.info(f"Retriever tool created for collection '{collection_name}' with {search_type}")

            return {
                "pg_retriever":{"tool": retriever_tool}
            }

        except Exception as e:
            error_msg = f"RetrieverProvider execution failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _create_vectorstore_connection(self, connection_string: str, collection_name: str, embedder) -> PGVector:
        """Create connection to existing vector database."""
        try:
            ## Convert to async connection string for new API
            #if connection_string.startswith('postgresql://'):
            #    async_connection_string = connection_string.replace('postgresql://', 'postgresql+asyncpg://')
            #else:
            #    async_connection_string = connection_string

            # Create engine
            #engine = PGEngine.from_connection_string(async_connection_string)
            
            # Connect to existing vector store (don't create new tables)
            retriever = PGVector(
                connection=connection_string,
                collection_name=collection_name,
                embeddings=embedder,
            )

            logger.info(f"Connected to vector database collection: {collection_name}")
            return retriever

        except Exception as e:
            raise ValueError(f"Failed to connect to vector database: {str(e)}")

    def _create_configured_retriever(self, retreiver: PGVector, search_config: Dict[str, Any]) -> BaseRetriever:
        """Create retriever with search configuration.

        Notes:
        - For 'similarity_score_threshold', LangChain requires a float score_threshold in (0, 1].
          Passing 0 disables filtering and effectively returns up to k results.
        - We validate and coerce types defensively to avoid silent misconfiguration.
        - Auto-converts 'similarity' to 'similarity_score_threshold' if score_threshold > 0.
        """
        search_type = search_config["search_type"]
        raw_threshold = search_config.get("score_threshold", 0)

        # Auto-convert similarity to similarity_score_threshold if threshold is provided
        if search_type == "similarity" and raw_threshold and float(raw_threshold) > 0:
            search_type = "similarity_score_threshold"
            logger.info(f"Auto-converted search_type from 'similarity' to 'similarity_score_threshold' due to score_threshold={raw_threshold}")

        # Always cap returned results by k unless the underlying retriever ignores it
        k = int(search_config.get("search_k", 4))
        search_kwargs: Dict[str, Any] = {"k": k}

        # Configure based on search type (LangChain search algorithms)
        if search_type == "similarity_score_threshold":
            # Defensive coercion and validation
            if raw_threshold is None:
                raise ValueError("score_threshold must be provided for 'similarity_score_threshold' search_type")

            # Allow str inputs like "0.7" while ensuring float
            try:
                score_threshold = float(raw_threshold)
            except (TypeError, ValueError):
                raise ValueError(f"score_threshold must be a float in (0, 1], got {raw_threshold!r}")

            if not (0.0 < score_threshold <= 1.0):
                raise ValueError(f"score_threshold must be within (0, 1], got {score_threshold}")

            search_kwargs["score_threshold"] = score_threshold

            # Optionally allow fetch_k to broaden candidate set before thresholding
            fetch_k = search_config.get("fetch_k", None)
            if isinstance(fetch_k, int) and fetch_k > 0:
                search_kwargs["fetch_k"] = fetch_k

        elif search_type == "mmr":
            search_kwargs["fetch_k"] = search_config.get("fetch_k", 20)
            search_kwargs["lambda_mult"] = search_config.get("lambda_mult", 0.5)

        # Add metadata filtering if enabled
        if search_config.get("enable_metadata_filtering") and search_config.get("metadata_filter"):
            search_kwargs["filter"] = search_config["metadata_filter"]

        # Create retriever with specified search algorithm
        retriever = retreiver.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )

        # Rich diagnostics to verify effective config at runtime
        details = {
            "k": search_kwargs.get("k"),
            "score_threshold": search_kwargs.get("score_threshold"),
            "fetch_k": search_kwargs.get("fetch_k"),
            "lambda_mult": search_kwargs.get("lambda_mult"),
            "has_filter": "filter" in search_kwargs
        }
        logger.info(f"Created retriever search_type={search_type} details={details}")
        return retriever

    def _create_retriever_tool(self, retriever: BaseRetriever, collection_name: str, search_config: Dict[str, Any]) -> Tool:
        """Create LangChain Tool that agents can use."""

        def retriever_search(query: str) -> str:
            """Search function that the agent will call."""
            try:
                logger.info(f"[SEARCH] Agent searching '{collection_name}' for: {query}")

                # Perform search using configured retriever
                docs = retriever.invoke(query)

                if not docs:
                    return f"""[SEARCH] SEARCH RESULTS - {collection_name}
    Query: No documents found for '{query}'.
    
    SEARCH SUMMARY:
    - Search completed but no relevant documents were found
    - You may try using more specific search terms
    - Collection: {collection_name}
    - Search Algorithm: {search_config['search_type']}"""

                # Format results for agent consumption
                result_parts = [
                    f"[SEARCH] SEARCH RESULTS - {collection_name}",
                    f"Total documents found: {len(docs)}",
                    f"Search Algorithm: {search_config['search_type']}",
                    f"Documents displayed: {min(len(docs), search_config['search_k'])}",
                    ""
                ]

                # Limit results for readability (max 5 documents)


                for i, doc in enumerate(docs, 1):
                    content = doc.page_content
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}

                    # Extract source information
                    source = metadata.get('source', 'unknown')
                    if isinstance(source, str) and len(source) > 50:
                        source = source[-50:]
                    relevance_score= 'n/A'
                    if 'relevance_score' in doc.metadata:
                        relevance_score = str(doc.metadata['relevance_score'])
                    result_parts.extend([
                        f"=== DOCUMENT {i} === (Source: {source})",
                        "CONTENT:",
                        content,
                        "RELEVANCE SCORE",
                        relevance_score,
                        "---",
                        ""
                    ])

                result_parts.extend([
                    "",
                    "SEARCH SUMMARY:",
                    f"- These results contain the most relevant documents for the query '{query}'",
                    f"- Collection: {collection_name}",
                    f"- Search Algorithm: {search_config['search_type']}",
                    f"- Documents are sorted by relevance"
                ])

                return "\n".join(result_parts)

            except Exception as e:
                error_msg = str(e)
                return f"""[SEARCH] SEARCH RESULTS - {collection_name}
    Query: A technical issue occurred while searching for '{query}'.
    
    # WARNING: ERROR DETAILS:
<<<<<<< HEAD
=======
    logger.warning("ERROR DETAILS:")
>>>>>>> serialization_fixes
    {error_msg}
    
    SEARCH SUMMARY:
    - Search could not be completed due to technical issues
    - Collection: {collection_name}
    - Please try again with different search terms"""

        # Create tool with descriptive name
        tool_name = f"search_{collection_name}"
        tool_description = f"Search the {collection_name} knowledge base for relevant information. Use this tool when you need to find specific documents or information from the {collection_name} collection."

        return Tool(
            name=tool_name,
            description=tool_description,
            func=retriever_search
        )

    def get_required_packages(self) -> List[str]:
        """Required packages for RetrieverProvider."""
        return [
            "langchain-postgres==0.0.15",
            "langchain-core>=0.1.0",
            "psycopg[binary]>=3.0.0",
            "pgvector>=0.2.0"
        ]


# Export for node registry
__all__ = ["RetrieverProvider"]