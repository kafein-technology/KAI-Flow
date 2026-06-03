
from sqlalchemy import Column, String, UUID, Text, Boolean, Integer, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from .base import Base

class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=False, index=True)
    version = Column(Integer, default=1)
    error_workflow = Column(
        "error_workflow_id",
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    flow_data = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), index=True)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now(), index=True)
    
    # Relationship
    user = relationship("User", back_populates="workflows")
    executions = relationship("WorkflowExecution", back_populates="workflow")
    node_configurations = relationship("NodeConfiguration", back_populates="workflow", cascade="all, delete-orphan")
    variables = relationship("Variable", back_populates="workflow", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="workflow", cascade="all, delete-orphan")
    scheduled_jobs = relationship("ScheduledJob", back_populates="workflow", cascade="all, delete-orphan")
    webhook_endpoints = relationship("WebhookEndpoint", back_populates="workflow", cascade="all, delete-orphan")
    vector_collections = relationship("VectorCollection", back_populates="workflow", cascade="all, delete-orphan")
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_workflows_user_created', 'user_id', 'created_at'),
        Index('idx_workflows_public_created', 'is_public', 'created_at'),
        Index('idx_workflows_user_public', 'user_id', 'is_public'),
    )

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), default='General')
    flow_data = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now()) 