import uuid
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# --- Workflow Execution Schemas ---

class WorkflowExecutionBase(BaseModel):
    status: str = 'pending'
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class WorkflowExecutionCreate(WorkflowExecutionBase):
    workflow_id: uuid.UUID
    user_id: uuid.UUID
    started_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

class WorkflowExecutionUpdate(BaseModel):
    status: Optional[str] = None
    outputs: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class WorkflowExecutionResponse(WorkflowExecutionBase):
    id: uuid.UUID
    workflow_id: uuid.UUID
    user_id: uuid.UUID
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowExecutionSummary(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    has_inputs: bool
    has_outputs: bool


class WorkflowExecutionPageResponse(BaseModel):
    items: List[WorkflowExecutionSummary]
    total: Optional[int] = None
    page: int
    page_size: int


class ExecutionWorkflowOption(BaseModel):
    id: uuid.UUID
    name: str

# --- Execution Checkpoint Schemas ---

class ExecutionCheckpointBase(BaseModel):
    checkpoint_data: Dict[str, Any]
    parent_checkpoint_id: Optional[uuid.UUID] = None

class ExecutionCheckpointCreate(ExecutionCheckpointBase):
    execution_id: uuid.UUID

class ExecutionCheckpointResponse(ExecutionCheckpointBase):
    execution_id: uuid.UUID
    updated_at: datetime

    class Config:
        from_attributes = True
