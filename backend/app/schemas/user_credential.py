import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

# Base schema with common fields
class UserCredentialBase(BaseModel):
    name: str
    service_type: str

# Schema for creating a credential
class UserCredentialCreate(UserCredentialBase):
    secret: Dict[str, Any]  # The unencrypted secret data, will be encrypted in the service layer

# Schema for updating a credential
class UserCredentialUpdate(BaseModel):
    name: Optional[str] = None

# Schema for API responses (without sensitive data)
class UserCredentialResponse(UserCredentialBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Schema for API credential creation with flexible data structure
class CredentialCreateRequest(BaseModel):
    name: str
    data: Dict[str, Any]  # Flexible data structure for different credential types
    service_type: Optional[str] = None  # Optional explicit service type from client

# Schema for API credential update
class CredentialUpdateRequest(BaseModel):
    name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    service_type: Optional[str] = None  # Allow updating service type explicitly

# Schema for detailed API responses including the service type and metadata
class CredentialDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    service_type: str
    created_at: datetime
    updated_at: datetime
    secret: Optional[Dict[str, Any]] = None  # Only included when fetching single credential for editing

    class Config:
        from_attributes = True

# Schema for API responses with success message
class CredentialDeleteResponse(BaseModel):
    message: str
    deleted_id: uuid.UUID 