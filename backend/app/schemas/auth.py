import uuid
import re
from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional
from datetime import datetime

# Schemas from the old app/api/auth.py moved here for consistency

# Centralized password validation function
def validate_password_strength(password: str) -> str:
    """
    Centralized password validation with clear error messages.
    Rules:
    - Minimum 6 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    """
    if not password or len(password.strip()) == 0:
        raise ValueError('Password cannot be empty')
    
    if len(password) < 6:
        raise ValueError('Password must be at least 6 characters')
    
    if not re.search(r'[A-Z]', password):
        raise ValueError('Password must contain at least 1 uppercase letter')
    
    if not re.search(r'[a-z]', password):
        raise ValueError('Password must contain at least 1 lowercase letter')
    
    return password

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters, 1 uppercase, 1 lowercase")
    full_name: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class UserSignUpData(BaseModel):
    email: EmailStr
    name: str
    credential: str = Field(..., min_length=6, description="Password must be at least 6 characters, 1 uppercase, 1 lowercase")
    tempToken: Optional[str] = None

    @field_validator('credential')
    @classmethod
    def validate_credential(cls, v: str) -> str:
        return validate_password_strength(v)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        if len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters')
        return v.strip()

class SignUpRequest(BaseModel):
    user: UserSignUpData

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserUpdateProfile(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, description="Password must be at least 6 characters, 1 uppercase, 1 lowercase")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_password_strength(v)
        return v

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# --- LoginMethod Schemas ---
class LoginMethodBase(BaseModel):
    name: str
    config: str
    status: str = 'ENABLE'

class LoginMethodCreate(LoginMethodBase):
    organization_id: uuid.UUID
    created_by: uuid.UUID

class LoginMethodUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[str] = None
    status: Optional[str] = None
    updated_by: uuid.UUID

class LoginMethodResponse(LoginMethodBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

# --- LoginActivity Schemas ---
class LoginActivityBase(BaseModel):
    username: str
    activity_code: int
    message: str

class LoginActivityCreate(LoginActivityBase):
    pass

class LoginActivityResponse(LoginActivityBase):
    id: uuid.UUID
    attempted_at: datetime
    class Config:
        from_attributes = True 