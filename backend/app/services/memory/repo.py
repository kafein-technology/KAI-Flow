"""Memory repository for pure database operations."""

from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from app.models.memory import Memory


class MemoryRepo:
    """Repository for memory database operations."""
    
    def save_memory(self, db: Session, user_id: str, session_id: str, content: str, 
                   context: str = "", metadata: dict = None, source_type: str = "chat", 
                   chatflow_id: str = None) -> Memory:
        """Save a new memory to database."""
        memory = Memory(
            user_id=UUID(user_id) if user_id else None,
            session_id=session_id,
            content=content,
            context=context,
            memory_metadata=metadata or {},
            source_type=source_type,
            chatflow_id=UUID(chatflow_id) if chatflow_id else None
        )
        
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory
    
    def get_memories_by_user(self, db: Session, user_id: str, limit: int = 10, 
                            offset: int = 0) -> List[Memory]:
        """Get memories for a user."""
        return db.query(Memory).filter(
            Memory.user_id == UUID(user_id)
        ).order_by(desc(Memory.created_at)).offset(offset).limit(limit).all()
    
    def get_memories_by_session(self, db: Session, session_id: str, limit: int = 10, 
                               offset: int = 0) -> List[Memory]:
        """Get memories for a session."""
        memories = db.query(Memory).filter(
            Memory.session_id == session_id
        ).order_by(desc(Memory.created_at)).offset(offset).limit(limit).all()
        
        # DEBUG: Log what we found
        if memories:
            first_content = memories[0].content[:100] + "..." if len(memories[0].content) > 100 else memories[0].content
        else:
            logger.info(f"[REPO DEBUG] get_memories_by_session('{session_id}', limit={limit}) -> Found 0 records.")
            
        return memories
    
    def search_memories_by_content(self, db: Session, user_id: str, query: str, 
                                  limit: int = 10) -> List[Memory]:
        """Search memories by content using basic text search."""
        search_filter = func.lower(Memory.content).contains(query.lower()) | \
                       func.lower(Memory.context).contains(query.lower())
        
        return db.query(Memory).filter(
            Memory.user_id == UUID(user_id),
            search_filter
        ).order_by(desc(Memory.created_at)).limit(limit).all()
    
    def get_memory_by_id(self, db: Session, memory_id: str) -> Optional[Memory]:
        """Get a specific memory by ID."""
        return db.query(Memory).filter(Memory.id == UUID(memory_id)).first()
    
    def get_memory_count_by_user(self, db: Session, user_id: str) -> int:
        """Get total memory count for a user."""
        return db.query(func.count(Memory.id)).filter(
            Memory.user_id == UUID(user_id)
        ).scalar()
    
    def get_memory_count_by_session(self, db: Session, session_id: str) -> int:
        """Get total memory count for a session."""
        return db.query(func.count(Memory.id)).filter(
            Memory.session_id == session_id
        ).scalar()
    
    def get_memories_by_date_range(self, db: Session, user_id: str, 
                                  start_date: datetime, end_date: datetime) -> List[Memory]:
        """Get memories within a date range."""
        return db.query(Memory).filter(
            Memory.user_id == UUID(user_id),
            Memory.created_at >= start_date,
            Memory.created_at <= end_date
        ).order_by(desc(Memory.created_at)).all()
    
    def get_memories_by_source_type(self, db: Session, user_id: str, 
                                   source_type: str, limit: int = 10) -> List[Memory]:
        """Get memories by source type."""
        return db.query(Memory).filter(
            Memory.user_id == UUID(user_id),
            Memory.source_type == source_type
        ).order_by(desc(Memory.created_at)).limit(limit).all()
    
    def get_memories_by_chatflow(self, db: Session, chatflow_id: str, 
                                limit: int = 10) -> List[Memory]:
        """Get memories by chatflow ID."""
        return db.query(Memory).filter(
            Memory.chatflow_id == UUID(chatflow_id)
        ).order_by(desc(Memory.created_at)).limit(limit).all()
    
    def update_memory(self, db: Session, memory_id: str, content: str = None, 
                     context: str = None, metadata: dict = None) -> Optional[Memory]:
        """Update a memory."""
        memory = db.query(Memory).filter(Memory.id == UUID(memory_id)).first()
        if not memory:
            return None
        
        if content is not None:
            memory.content = content
        if context is not None:
            memory.context = context
        if metadata is not None:
            memory.memory_metadata = metadata
        
        memory.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(memory)
        return memory
    
    def delete_memory(self, db: Session, memory_id: str) -> bool:
        """Delete a specific memory."""
        deleted_count = db.query(Memory).filter(
            Memory.id == UUID(memory_id)
        ).delete()
        db.commit()
        return deleted_count > 0
    
    def delete_memories_by_user(self, db: Session, user_id: str) -> int:
        """Delete all memories for a user."""
        deleted_count = db.query(Memory).filter(
            Memory.user_id == UUID(user_id)
        ).delete(synchronize_session=False)
        db.commit()
        return deleted_count
    
    def delete_memories_by_session(self, db: Session, session_id: str) -> int:
        """Delete all memories for a session."""
        deleted_count = db.query(Memory).filter(
            Memory.session_id == session_id
        ).delete(synchronize_session=False)
        db.commit()
        return deleted_count
    
    def get_session_list_by_user(self, db: Session, user_id: str) -> List[str]:
        """Get unique session IDs for a user."""
        sessions = db.query(Memory.session_id).filter(
            Memory.user_id == UUID(user_id)
        ).distinct().all()
        return [session[0] for session in sessions]
    
    def get_oldest_memory_by_user(self, db: Session, user_id: str) -> Optional[Memory]:
        """Get the oldest memory for a user."""
        return db.query(Memory).filter(
            Memory.user_id == UUID(user_id)
        ).order_by(Memory.created_at).first()
    
    def get_newest_memory_by_user(self, db: Session, user_id: str) -> Optional[Memory]:
        """Get the newest memory for a user."""
        return db.query(Memory).filter(
            Memory.user_id == UUID(user_id)
        ).order_by(desc(Memory.created_at)).first()

    def get_active_session_id(self, db: Session, user_id: str, chatflow_id: str = None) -> Optional[str]:
        """Get the newest session ID, optionally filtered by chatflow (workflow).
        
        When chatflow_id is provided, queries by workflow first. This ensures
        webhook-triggered sessions (saved under master user) are also found.
        Falls back to user-based lookup if no chatflow match.
        """
        if chatflow_id:
            # Query by chatflow (workflow), ignoring user_id filter
            # This catches webhook sessions saved under master user
            newest = db.query(Memory).filter(
                Memory.chatflow_id == UUID(chatflow_id)
            ).order_by(desc(Memory.created_at)).first()
            if newest:
                return newest.session_id
        # Fallback to user-based lookup
        newest = self.get_newest_memory_by_user(db, user_id)
        return newest.session_id if newest else None