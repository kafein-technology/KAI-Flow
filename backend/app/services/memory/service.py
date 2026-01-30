"""Memory service for complex business logic operations."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from .repo import MemoryRepo
from app.models.memory import Memory

logger = logging.getLogger(__name__)


class MemoryItem:
    """Memory item data transfer object."""
    def __init__(self, id: str, content: str, context: str, timestamp: datetime, 
                 user_id: str, session_id: str, metadata: Dict[str, Any] = None):
        self.id = id
        self.content = content
        self.context = context
        self.timestamp = timestamp
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = metadata or {}


class MemoryService:
    """Service layer for memory operations with business logic."""
    
    def __init__(self):
        self.memory_repo = MemoryRepo()
    
    def save_memory(self, db: Session, user_id: str, session_id: str, content: str, 
                   context: str = "", metadata: Dict[str, Any] = None, 
                   source_type: str = "chat", chatflow_id: str = None) -> str:
        """Save memory and return ID."""
        memory = self.memory_repo.save_memory(
            db, user_id, session_id, content, context, metadata, source_type, chatflow_id
        )
        return str(memory.id)
    
    def retrieve_memories(self, db: Session, user_id: str, query: str = "", 
                         limit: int = 10, semantic_search: bool = True) -> List[MemoryItem]:
        """Retrieve memories with optional semantic search."""
        if query:
            memories = self.memory_repo.search_memories_by_content(db, user_id, query, limit)
        else:
            memories = self.memory_repo.get_memories_by_user(db, user_id, limit)
        
        # Convert to MemoryItem objects
        memory_items = self._convert_to_memory_items(memories)
        
        # Apply semantic search if enabled and query provided
        if query and semantic_search and memory_items:
            return self._apply_semantic_search(memory_items, query, limit)
        
        return memory_items
    
    def get_memory_stats(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Get detailed memory statistics."""
        memories = self.memory_repo.get_memories_by_user(db, user_id, limit=1000)
        
        if not memories:
            return {
                "total_memories": 0, 
                "sessions": 0, 
                "oldest_memory": None, 
                "newest_memory": None
            }
        
        # Calculate statistics
        sessions = set(m.session_id for m in memories)
        oldest = min(memories, key=lambda x: x.created_at)
        newest = max(memories, key=lambda x: x.created_at)
        avg_length = sum(len(m.content) for m in memories) / len(memories)
        
        return {
            "total_memories": len(memories),
            "sessions": len(sessions),
            "oldest_memory": oldest.created_at.isoformat(),
            "newest_memory": newest.created_at.isoformat(),
            "average_content_length": avg_length
        }
    
    def get_memory_analytics(self, db: Session, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get memory analytics for a user."""
        try:
            # Calculate date range
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            end_date = datetime.utcnow()
            
            # Get memories within date range
            memories = self.memory_repo.get_memories_by_date_range(db, user_id, cutoff_date, end_date)
            
            # Calculate analytics
            total_memories = len(memories)
            sessions = set(m.session_id for m in memories)
            
            # Daily memory counts
            daily_counts = {}
            for memory in memories:
                date_key = memory.created_at.date().isoformat()
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
            
            # Content analysis
            content_lengths = [len(m.content) for m in memories]
            avg_content_length = sum(content_lengths) / len(content_lengths) if content_lengths else 0
            
            # Word frequency analysis
            top_words = self._analyze_word_frequency(memories)
            
            return {
                "period_days": days,
                "total_memories": total_memories,
                "total_sessions": len(sessions),
                "daily_counts": daily_counts,
                "average_content_length": avg_content_length,
                "top_words": top_words,
                "analytics_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "period_days": days,
                "total_memories": 0,
                "total_sessions": 0,
                "daily_counts": {},
                "average_content_length": 0,
                "top_words": [],
                "analytics_timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    def clear_memories(self, db: Session, user_id: str, session_id: str = None) -> int:
        """Clear memories for a user or specific session."""
        if session_id:
            return self.memory_repo.delete_memories_by_session(db, session_id)
        else:
            return self.memory_repo.delete_memories_by_user(db, user_id)
    
    def get_memory_count(self, db: Session, user_id: str) -> int:
        """Get total memory count for a user."""
        return self.memory_repo.get_memory_count_by_user(db, user_id)
    
    def get_session_memories(self, db: Session, session_id: str, limit: int = 10) -> List[MemoryItem]:
        """Get memories for a specific session."""
        memories = self.memory_repo.get_memories_by_session(db, session_id, limit)
        return self._convert_to_memory_items(memories)
    
    def _convert_to_memory_items(self, memories: List[Memory]) -> List[MemoryItem]:
        """Convert Memory models to MemoryItem objects."""
        memory_items = []
        for memory in memories:
            memory_item = MemoryItem(
                id=str(memory.id),
                content=memory.content,
                context=memory.context or "",
                timestamp=memory.created_at,
                user_id=str(memory.user_id) if memory.user_id else "",
                session_id=memory.session_id,
                metadata=memory.memory_metadata or {}
            )
            memory_items.append(memory_item)
        return memory_items
    
    def _apply_semantic_search(self, memories: List[MemoryItem], query: str, limit: int) -> List[MemoryItem]:
        """Apply semantic search using TF-IDF."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            memory_texts = [f"{m.content} {m.context}" for m in memories]
            
            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            tfidf_matrix = vectorizer.fit_transform(memory_texts + [query])
            
            # Calculate cosine similarity
            query_vector = tfidf_matrix[-1]
            memory_vectors = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vector, memory_vectors).flatten()
            
            # Get top similar memories
            similar_indices = np.argsort(similarities)[::-1]
            
            # Filter memories with similarity > 0.1
            relevant_memories = []
            for idx in similar_indices:
                if similarities[idx] > 0.1:
                    memory = memories[idx]
                    memory.metadata['similarity_score'] = float(similarities[idx])
                    relevant_memories.append(memory)
            
            return relevant_memories[:limit]

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return memories[:limit]
    
    def _analyze_word_frequency(self, memories: List[Memory]) -> List[Dict[str, Any]]:
        """Analyze word frequency in memories."""
        all_content = " ".join(m.content.lower() for m in memories)
        words = all_content.split()
        word_counts = {}
        
        for word in words:
            if len(word) > 3:  # Skip short words
                # Basic word cleaning
                clean_word = ''.join(c for c in word if c.isalnum())
                if clean_word:
                    word_counts[clean_word] = word_counts.get(clean_word, 0) + 1
        
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{"word": word, "count": count} for word, count in top_words]


# Service instance
memory_service = MemoryService()