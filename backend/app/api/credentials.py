"""User Credentials API endpoints"""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.credential_service import CredentialService
from app.services.dependencies import get_credential_service_dep, get_db_session
from app.auth.dependencies import get_current_user
from app.schemas.user_credential import (
    CredentialCreateRequest,
    CredentialUpdateRequest,
    CredentialDetailResponse,
    CredentialDeleteResponse,
    UserCredentialCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("", response_model=List[CredentialDetailResponse])
async def get_user_credentials(
    credential_name: Optional[str] = Query(None, alias="credentialName"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep)
):
    """
    Get all credentials for the current user.
    
    - **credential_name**: Optional query parameter to filter by credential name
    - **Returns**: List of user credentials (without sensitive data)
    """
    # Store user_id early to avoid lazy loading issues
    user_id = current_user.id
    
    try:
        if credential_name:
            # Filter by credential name
            credentials = await credential_service.get_by_user_id_and_name(
                db, user_id, credential_name
            )
        else:
            # Get all credentials for user
            credentials = await credential_service.get_by_user_id(db, user_id)
        
        # Convert to response schema
        response_credentials = [
            CredentialDetailResponse(
                id=cred.id,
                name=cred.name,
                service_type=cred.service_type,
                created_at=cred.created_at,
                updated_at=cred.updated_at
            )
            for cred in credentials
        ]
        
        return response_credentials
        
    except Exception as e:
        logger.error(f"Error retrieving credentials for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credentials"
        )

@router.get("/{credential_id}", response_model=CredentialDetailResponse)
async def get_credential_by_id(
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep)
):
    """
    Get a specific credential by ID.
    
    - **credential_id**: UUID of the credential to retrieve
    - **Returns**: Credential details (without sensitive data)
    """
    # Store user_id early to avoid lazy loading issues
    user_id = current_user.id
    
    try:
        credential = await credential_service.get_by_user_and_id(
            db, user_id, credential_id
        )
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )
        
        return CredentialDetailResponse(
            id=credential.id,
            name=credential.name,
            service_type=credential.service_type,
            created_at=credential.created_at,
            updated_at=credential.updated_at
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving credential {credential_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credential"
        )

@router.post("", response_model=CredentialDetailResponse)
async def create_credential(
    credential_data: CredentialCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep)
):
    """
    Create a new credential.
    
    - **credential_data**: Credential creation data with name and data fields
    - **Returns**: Created credential details
    """
    # Store user_id early to avoid lazy loading issues
    user_id = current_user.id
    
    try:
        # Detect service type from data structure unless explicitly provided by client
        service_type = credential_data.service_type or _detect_service_type(credential_data.data)
        
        # Create UserCredentialCreate schema
        create_schema = UserCredentialCreate(
            name=credential_data.name,
            service_type=service_type,
            secret=credential_data.data
        )
        
        # Create the credential
        credential = await credential_service.create_credential(
            db, user_id, create_schema
        )
        
        return CredentialDetailResponse(
            id=credential.id,
            name=credential.name,
            service_type=credential.service_type,
            created_at=credential.created_at,
            updated_at=credential.updated_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating credential for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create credential"
        )

@router.put("/{credential_id}", response_model=CredentialDetailResponse)
async def update_credential(
    credential_id: uuid.UUID,
    update_data: CredentialUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep)
):
    """
    Update an existing credential.
    
    - **credential_id**: UUID of the credential to update
    - **update_data**: Fields to update
    - **Returns**: Updated credential details
    """
    # Store user_id early to avoid lazy loading issues
    user_id = current_user.id
    
    try:
        # Check if credential exists and belongs to user
        existing_credential = await credential_service.get_by_user_and_id(
            db, user_id, credential_id
        )
        
        if not existing_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )
        
        # If data is provided, we need to re-encrypt the credential
        if update_data.data is not None:
            # Instead of delete/create, update the existing credential with new encrypted data
            # Determine service type (client overrides detection if provided)
            service_type = update_data.service_type or _detect_service_type(update_data.data)
            name = update_data.name if update_data.name is not None else existing_credential.name
            
            # Encrypt the new data
            from app.core.encryption import encrypt_data
            import base64
            
            encrypted_bytes = encrypt_data(update_data.data)
            encrypted_secret = base64.b64encode(encrypted_bytes).decode('utf-8')
            
            # Update the credential directly
            existing_credential.name = name
            existing_credential.service_type = service_type
            existing_credential.encrypted_secret = encrypted_secret
            
            await db.commit()
            await db.refresh(existing_credential)
            credential = existing_credential
            
        else:
            # Only update name if provided
            from app.schemas.user_credential import UserCredentialUpdate
            update_schema = UserCredentialUpdate(name=update_data.name)
            
            credential = await credential_service.update_credential(
                db, user_id, credential_id, update_schema
            )
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update credential"
            )
        
        return CredentialDetailResponse(
            id=credential.id,
            name=credential.name,
            service_type=credential.service_type,
            created_at=credential.created_at,
            updated_at=credential.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating credential {credential_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update credential"
        )

@router.delete("/{credential_id}", response_model=CredentialDeleteResponse)
async def delete_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep)
):
    """
    Delete a credential.
    
    - **credential_id**: UUID of the credential to delete
    - **Returns**: Success message with deleted credential ID
    """
    # Store user_id early to avoid lazy loading issues
    user_id = current_user.id
    
    try:
        # Check if credential exists and belongs to user
        existing_credential = await credential_service.get_by_user_and_id(
            db, user_id, credential_id
        )
        
        if not existing_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )
        
        # Delete the credential
        success = await credential_service.delete_credential(
            db, user_id, credential_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete credential"
            )
        
        return CredentialDeleteResponse(
            message="Credential deleted successfully",
            deleted_id=credential_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credential {credential_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete credential"
        )

def _detect_service_type(data: dict) -> str:
    """
    Detect service type from credential data structure.
    
    - **data**: Dictionary containing credential data
    - **Returns**: Detected service type
    """
    # Simple heuristics to detect service type
    # 1) PostgreSQL Vector Store (must be detected BEFORE generic username/password)
    if (
        # Connection string form (accept postgresql://, postgresql+asyncpg://, etc.)
        ("connection_string" in data and isinstance(data.get("connection_string"), str) and data.get("connection_string", "").lower().startswith("postgresql"))
        # Discrete fields form
        or (all(k in data for k in ["host", "port", "database", "username", "password"]))
    ):
        return "postgresql_vectorstore"

    if "api_key" in data:
        # Cohere API
        if data.get("provider") == "cohere" or data.get("cohere") is True:
            return "cohere"
        if "organization" in data or "project_id" in data:
            return "openai"
        elif "engine" in data or "model" in data:
            return "anthropic"
        elif "cse_id" in data or "search_engine_id" in data:
            return "google"
        else:
            return "generic_api"
    elif "access_token" in data:
        return "oauth"
    elif "username" in data and "password" in data:
        return "basic_auth"
    elif "private_key" in data or "certificate" in data:
        return "certificate"
    else:
        return "custom"