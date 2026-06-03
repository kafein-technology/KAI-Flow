
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Boolean, TIMESTAMP, BigInteger, Integer, 
    Text, JSON, ForeignKey, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship

from .base import Base


class WebhookEndpoint(Base):
    """
    Webhook endpoint configuration and management model.
    
    This model represents a webhook endpoint with comprehensive configuration
    options, security settings, and performance tracking capabilities.
    """
    __tablename__ = "webhook_endpoints"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core identification
    webhook_id = Column(String(255), unique=True, nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('workflows.id', ondelete='CASCADE'), nullable=True)
    node_id = Column(String(255), nullable=False)
    endpoint_path = Column(String(500), nullable=False)
    secret_token = Column(String(255), nullable=False)
    
    # Unified configuration
    config = Column(JSONB, nullable=False, default={
        "authentication_required": True,
        "allowed_event_types": [],
        "max_payload_size": 1024,
        "rate_limit_per_minute": 60,
        "webhook_timeout": 30,
        "enable_cors": True,
        "node_behavior": "auto"
    })
    
    # Status and metadata
    is_active = Column(Boolean, default=True, index=True)
    node_behavior = Column(String(20), default='auto', index=True)  # auto, start_only, trigger_only
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    last_triggered = Column(TIMESTAMP(timezone=True), nullable=True)
    trigger_count = Column(BigInteger, default=0)
    
    # Performance tracking
    avg_response_time_ms = Column(Integer, default=0)
    error_count = Column(BigInteger, default=0)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="webhook_endpoints")
    events = relationship("WebhookEvent", back_populates="endpoint", cascade="all, delete-orphan")
    
    # Indexes for performance optimization
    __table_args__ = (
        Index('idx_webhook_workflow', 'workflow_id'),
        Index('idx_webhook_active', 'is_active'),
        Index('idx_webhook_behavior', 'node_behavior'),
        Index('idx_webhook_created', 'created_at'),
    )
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary representation."""
        return {
            'id': str(self.id),
            'webhook_id': self.webhook_id,
            'workflow_id': str(self.workflow_id) if self.workflow_id else None,
            'node_id': self.node_id,
            'endpoint_path': self.endpoint_path,
            'secret_token': self.secret_token,
            'config': self.config,
            'is_active': self.is_active,
            'node_behavior': self.node_behavior,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'trigger_count': self.trigger_count,
            'avg_response_time_ms': self.avg_response_time_ms,
            'error_count': self.error_count
        }
    
    def update_trigger_stats(self, response_time_ms: int, success: bool = True):
        """Update trigger statistics."""
        self.trigger_count += 1
        self.last_triggered = datetime.utcnow()
        
        # Update average response time
        if self.avg_response_time_ms == 0:
            self.avg_response_time_ms = response_time_ms
        else:
            self.avg_response_time_ms = (self.avg_response_time_ms + response_time_ms) // 2
        
        # Update error count
        if not success:
            self.error_count += 1
    
    def is_rate_limited(self) -> bool:
        """Check if webhook is currently rate limited."""
        if not self.last_triggered:
            return False
        
        rate_limit = self.config.get('rate_limit_per_minute', 60)
        time_diff = (datetime.utcnow() - self.last_triggered).total_seconds()
        
        return time_diff < (60 / rate_limit)


class WebhookEvent(Base):
    """
    Webhook event logging and tracking model.
    
    This model represents individual webhook events with comprehensive
    request/response data, performance metrics, and error tracking.
    """
    __tablename__ = "webhook_events"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Webhook reference
    webhook_id = Column(String(255), ForeignKey('webhook_endpoints.webhook_id'), nullable=False)
    
    # Event data
    event_type = Column(String(100), default='webhook.received')
    payload = Column(JSONB, nullable=False)
    correlation_id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    
    # Request metadata
    source_ip = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_method = Column(String(10), default='POST')
    request_headers = Column(JSONB, nullable=True)
    request_ip = Column(INET, nullable=True)
    
    # Response data
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSONB, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), index=True)
    
    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="events")
    
    # Indexes for performance optimization
    __table_args__ = (
        Index('idx_webhook_logs_webhook', 'webhook_id'),
        Index('idx_webhook_logs_created', 'created_at'),
        Index('idx_webhook_logs_status', 'response_status'),
        Index('idx_webhook_logs_type', 'event_type'),
        Index('idx_webhook_logs_correlation', 'correlation_id'),
    )
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary representation."""
        return {
            'id': str(self.id),
            'webhook_id': self.webhook_id,
            'event_type': self.event_type,
            'payload': self.payload,
            'correlation_id': str(self.correlation_id),
            'source_ip': str(self.source_ip) if self.source_ip else None,
            'user_agent': self.user_agent,
            'request_method': self.request_method,
            'request_headers': self.request_headers,
            'request_ip': str(self.request_ip) if self.request_ip else None,
            'response_status': self.response_status,
            'response_body': self.response_body,
            'execution_time_ms': self.execution_time_ms,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def is_successful(self) -> bool:
        """Check if the webhook event was successful."""
        return self.response_status and 200 <= self.response_status < 300
    
    def is_error(self) -> bool:
        """Check if the webhook event resulted in an error."""
        return self.response_status is None or self.response_status >= 400
    
    def get_error_category(self) -> str:
        """Get the category of error if any."""
        if not self.is_error():
            return "success"
        
        if self.response_status is None:
            return "timeout"
        elif self.response_status >= 500:
            return "server_error"
        elif self.response_status >= 400:
            return "client_error"
        else:
            return "unknown" 