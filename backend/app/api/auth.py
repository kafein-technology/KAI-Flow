"""Authentication API endpoints"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from jose import JWTError

from app.core.constants import SECRET_KEY, ALGORITHM
from app.core.database import get_db_session
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.services.user_service import UserService
from app.services.dependencies import get_user_service_dep
from app.auth.dependencies import get_current_user, get_current_user_or_master_api_key
from app.models.user import User
from app.schemas.auth import (
    SignUpRequest, 
    UserSignUpData,
    TokenResponse, 
    UserResponse, 
    RefreshTokenRequest,
    UserUpdateProfile
)
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# Request/Response Models
class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

def create_user_response(user: User) -> UserResponse:
    """Convert User model to UserResponse schema"""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name or ""
    )

@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignUpRequest,
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service_dep)
):
    """Register a new user"""
    try:
        import os
        if os.getenv("ENTERPRISE", "false").lower() == "true":
            raise HTTPException(status_code=403, detail="Sign up is disabled in enterprise mode")
            
        user_data = request.user
        
        if not user_data.email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        # Check if user already exists
        existing_user = await user_service.get_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create new user
        new_user = await user_service.create_user(db, user_data)
        
        # Generate tokens
        access_token = create_access_token({"sub": new_user.email, "user_id": str(new_user.id)})
        refresh_token = create_refresh_token({"sub": new_user.email, "user_id": str(new_user.id)})
        
        user_response = create_user_response(new_user)
        
        return AuthResponse(
            user=user_response,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/signin", response_model=AuthResponse)
async def signin(
    request: SignInRequest,
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service_dep)
):
    """Authenticate user and return tokens"""
    user = await user_service.authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Generate tokens
    access_token = create_access_token({"sub": user.email, "user_id": str(user.id)})
    refresh_token = create_refresh_token({"sub": user.email, "user_id": str(user.id)})
    
    user_response = create_user_response(user)
    
    return AuthResponse(
        user=user_response,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

@router.post("/signout")
async def signout():
    """Sign out user (token invalidation would be handled client-side for now)"""
    return {"message": "Successfully signed out"}

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service_dep)
):
    """Refresh access token using refresh token"""
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        
        if email is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Verify user still exists and is active
        user = await user_service.get_by_email(db, email)
        if not user or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new tokens
        new_access_token = create_access_token({"sub": email, "user_id": user_id})
        new_refresh_token = create_refresh_token({"sub": email, "user_id": user_id})
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user_or_master_api_key)):
    """Get current user profile"""
    return create_user_response(current_user)

@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdateProfile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service_dep)
):
    """Update current user profile"""
    try:
        updated_user = await user_service.update_user(db, current_user, user_update)
        return create_user_response(updated_user)
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Profile update failed")

# Development/Testing endpoints
@router.get("/test/users")
async def list_test_users(
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service_dep)
):
    """List all users (development only)"""
    try:
        users = await user_service.get_all(db, limit=50)
        user_list = []
        for user in users:
            user_list.append({
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status,
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None
            })
        
        return {
            "message": "Database integration active",
            "total_users": len(user_list),
            "users": user_list,
            "endpoints": {
                "signup": "POST /auth/signup",
                "signin": "POST /auth/signin", 
                "me": "GET /auth/me",
                "refresh": "POST /auth/refresh",
                "update_profile": "PUT /auth/me"
            }
        }
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch users")
