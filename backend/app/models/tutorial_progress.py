from sqlalchemy import Column, String, Integer, UUID, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from .base import Base


class TutorialProgress(Base):
    __tablename__ = "tutorial_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    tutorial_id = Column(String, nullable=False)
    current_step = Column(Integer, nullable=False, default=0)
    completed_steps = Column(JSONB, nullable=False, default=list)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'tutorial_id', name='uq_user_tutorial'),
    )

    user = relationship("User", back_populates="tutorial_progress")
