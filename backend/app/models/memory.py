"""Memory database models for KAI Fusion."""

from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from .base import Base


class Memory(Base):
    """Enhanced memory storage with session-based priority."""

    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Made nullable for session-based
    session_id = Column(String(255), nullable=False, index=True)  #  PRIMARY KEY
    content = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    memory_metadata = Column(JSON, nullable=True)
    source_type = Column(String(50), default="chat", nullable=False)  # chat, webhook, api
    chatflow_id = Column(UUID(as_uuid=True), nullable=True)  # Link to chat conversations
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to user (optional for session-based)
    user = relationship("User", back_populates="memories")

    # Indexes for performance - session_id öncelikli
    __table_args__ = (
        Index("idx_memories_session_id", "session_id"),  #  PRIMARY INDEX
        Index("idx_memories_user_id", "user_id"),
        Index("idx_memories_created_at", "created_at"),
        Index("idx_memories_session_source", "session_id", "source_type"),
        Index("idx_memories_chatflow_id", "chatflow_id"),
        Index("idx_memories_session_chatflow", "session_id", "chatflow_id"),
    )

    def __repr__(self):
        return f"<Memory(id={self.id}, session_id={self.session_id}, source_type={self.source_type})>"

    def to_dict(self):
        """Convert memory to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": self.session_id,  #  PRIMARY FIELD
            "content": self.content,
            "context": self.context,
            "metadata": self.memory_metadata or {},
            "source_type": self.source_type,
            "chatflow_id": str(self.chatflow_id) if self.chatflow_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }