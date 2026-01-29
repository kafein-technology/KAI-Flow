from sqlalchemy import Column, String, UUID, Text, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from datetime import datetime, timezone
from .base import Base

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(50), nullable=False, default='pending')
    inputs = Column(JSONB)
    outputs = Column(JSONB)
    error_message = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    user = relationship("User", back_populates="executions")
    checkpoint = relationship("ExecutionCheckpoint", back_populates="execution", uselist=False)

class ExecutionCheckpoint(Base):
    __tablename__ = "execution_checkpoints"
    
    execution_id = Column(UUID(as_uuid=True), ForeignKey('workflow_executions.id', ondelete='CASCADE'), primary_key=True)
    checkpoint_data = Column(JSONB, nullable=False)
    parent_checkpoint_id = Column(UUID(as_uuid=True))
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationship
    execution = relationship("WorkflowExecution", back_populates="checkpoint") 