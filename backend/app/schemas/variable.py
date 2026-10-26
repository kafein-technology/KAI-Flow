import uuid
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# Base schema with common fields
class VariableBase(BaseModel):
    name: str
    value: str
    type: Optional[str] = "static"
    workflow_id: Optional[uuid.UUID] = None

# Schema for creating a variable
class VariableCreate(VariableBase):
    name: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(max_length=1000)
    type: Literal["static"] = "static"

# Schema for updating a variable
class VariableUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: Optional[str] = Field(default=None, max_length=1000)
    type: Optional[Literal["static"]] = None
    workflow_id: Optional[uuid.UUID] = None

# Schema for API responses
class VariableResponse(VariableBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
