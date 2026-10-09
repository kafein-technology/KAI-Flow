"""Database metadata for application-managed model artifacts and scan leases."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UUID,
)
from sqlalchemy.sql import func

from .base import Base


class ManagedModelArtifact(Base):
    """Lifecycle metadata for a browser upload owned by this application.

    ``storage_key`` is always relative to the configured managed-artifact root.
    Local/shared paths and customer-owned MinIO objects are deliberately never
    represented by this table and therefore cannot be removed by its cleanup job.
    """

    __tablename__ = "managed_model_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_key = Column(String(64), nullable=False, index=True)
    storage_backend = Column(String(32), nullable=False, default="filesystem")
    storage_key = Column(Text, nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    sha256 = Column(String(64), nullable=True)
    format_hint = Column(String(64), nullable=True)
    source_kind = Column(String(32), nullable=False, default="file")
    source_file_count = Column(Integer, nullable=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    node_id = Column(String(128), nullable=True)
    state = Column(String(32), nullable=False, default="uploading", index=True)
    scan_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    last_scanned_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_error = Column(String(320), nullable=True)

    __table_args__ = (
        Index("ix_managed_model_artifacts_owner_state", "owner_key", "state"),
        Index("ix_managed_model_artifacts_cleanup", "state", "expires_at"),
    )


class ManagedModelArtifactLease(Base):
    """Crash-recoverable protection for an artifact used by an active scan."""

    __tablename__ = "managed_model_artifact_leases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("managed_model_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    acquired_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index(
            "ix_managed_model_artifact_leases_artifact_expiry",
            "artifact_id",
            "expires_at",
        ),
    )


__all__ = ["ManagedModelArtifact", "ManagedModelArtifactLease"]
