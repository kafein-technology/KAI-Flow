"""
KAI-Flow Embedding Models - Text Vectorization & Semantic Search
================================================================

This module provides enterprise-grade text embedding capabilities for the KAI-Flow platform,
offering seamless integration with various embedding models and vectorization providers.

Available Embedding Models:
- OpenAI Embeddings (text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large)
- Cohere Embeddings (embed-english-v3.0, embed-multilingual-v3.0)
- HuggingFace Embeddings (sentence-transformers)

Features:
- Batch processing for efficiency
- Cost optimization and tracking
- Multiple embedding dimensions
- Semantic similarity search
- Vector normalization options
"""

from .openai_embeddings_provider import OpenAIEmbeddingsProvider

__all__ = [
    "OpenAIEmbeddingsProvider"
]