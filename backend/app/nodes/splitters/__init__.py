"""
KAI-Flow Text Splitters - Document Segmentation & Preprocessing
===============================================================

This module provides intelligent document splitting capabilities for the KAI-Flow platform,
offering various strategies for optimal text segmentation for RAG pipelines and vector embeddings.

Available Splitters:
- Chunk Splitter (RecursiveCharacterTextSplitter, CharacterTextSplitter)
- Token Splitter (tiktoken-based splitting)
- Semantic Splitter (embedding-based semantic segmentation)
- Document-specific splitters (PDF, HTML, Markdown)

Features:
- Multiple splitting strategies
- Chunk overlap optimization
- Metadata preservation
- Quality analytics
- Performance monitoring
"""

from .chunk_splitter import ChunkSplitterNode

__all__ = [
    "ChunkSplitterNode"
]