"""User Credentials API endpoints"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
import httpx
from pydantic import BaseModel
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
        # Use get_decrypted_credential to return secret data for editing
        decrypted = await credential_service.get_decrypted_credential(
            db, user_id, credential_id
        )
        if not decrypted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )
        
        return CredentialDetailResponse(
            id=decrypted["id"],
            name=decrypted["name"],
            service_type=decrypted["service_type"],
            created_at=decrypted["created_at"],
            updated_at=decrypted["updated_at"],
            secret=decrypted.get("secret", {})
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

class CredentialTestResponse(BaseModel):
    success: bool
    message: str


class CredentialTestRawRequest(BaseModel):
    service_type: str
    data: Dict[str, Any]


async def _test_openai(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=secret.get("api_key", ""))
        await asyncio.wait_for(client.models.list(), timeout=10)
        return CredentialTestResponse(success=True, message="Connected to OpenAI successfully.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower() or "auth" in msg.lower():
            msg += (
                " Note: If this key is for an OpenAI-compatible provider "
                "(OpenRouter, vLLM, etc.), it may still be valid for that provider."
            )
        return CredentialTestResponse(success=False, message=msg)


async def _test_openai_compatible(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        from openai import AsyncOpenAI

        # Use dummy key for local servers that don't need auth, so client doesn't complain about empty key
        api_key = secret.get("api_key", "")
        if not api_key:
            api_key = "dummy_for_local"

        # Check if SSL verification should be skipped
        skip_ssl = secret.get("skip_ssl_verify", False)
        if isinstance(skip_ssl, str):
            skip_ssl = skip_ssl.lower() in ("true", "1", "yes", "on")
        skip_ssl = bool(skip_ssl)

        client_kwargs = {
            "api_key": api_key,
            "base_url": secret.get("base_url", "")
        }

        # Inject custom HTTP client to bypass SSL verification
        if skip_ssl:
            logger.info("SSL verification disabled for test connection.")
            client_kwargs["http_client"] = httpx.AsyncClient(verify=False)

        client = AsyncOpenAI(**client_kwargs)
        
        # 1. Ensure the endpoint exists and responds to OpenAI format
        await asyncio.wait_for(client.models.list(), timeout=10)
        
        # 2. Force an authentication check
        # Some providers (like OpenRouter) have a completely public /models endpoint.
        # Sending a dummy chat request with empty messages usually fails fast on Auth (401)
        # BEFORE it fails on missing messages (400), letting us verify the API key!
        try:
            await asyncio.wait_for(
                client.chat.completions.create(
                    model="test-auth",
                    messages=[],
                    max_tokens=1
                ),
                timeout=10
            )
        except Exception as auth_test_e:
            err_msg = str(auth_test_e).lower()
            if "401" in err_msg or "unauthorized" in err_msg or "invalid" in err_msg:
                return CredentialTestResponse(success=False, message="Invalid API Key or Unauthorized.")
            # If it's a 400 Bad Request or 404 Model Not Found, it means authentication passed!
            pass

        msg = "Connected to OpenAI Compatible provider successfully."
        if skip_ssl:
            msg += " (SSL verification was skipped)"
        return CredentialTestResponse(success=True, message=msg)
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e))


async def _test_cohere(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        import cohere

        client = cohere.AsyncClientV2(api_key=secret.get("api_key", ""))
        await asyncio.wait_for(
            client.embed(texts=["test"], model="embed-english-v3.0", input_type="search_query"),
            timeout=10,
        )
        return CredentialTestResponse(success=True, message="Connected to Cohere successfully.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e))


async def _test_tavily(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=secret.get("api_key", ""))
        await asyncio.wait_for(client.search("test"), timeout=10)
        return CredentialTestResponse(success=True, message="Connected to Tavily successfully.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e))


async def _test_postgresql(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        import psycopg2

        def _connect():
            conn = psycopg2.connect(
                host=secret.get("host", "localhost"),
                port=int(secret.get("port", 5432)),
                dbname=secret.get("database", ""),
                user=secret.get("username", ""),
                password=secret.get("password", ""),
                connect_timeout=10,
            )
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()

        await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, _connect), timeout=15)
        return CredentialTestResponse(success=True, message="Connected to PostgreSQL successfully.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e))


async def _test_kafka(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        from confluent_kafka.admin import AdminClient

        conf: Dict[str, Any] = {
            "bootstrap.servers": secret.get("brokers", ""),
            "socket.timeout.ms": 10000,
        }
        security_protocol = secret.get("security_protocol", "PLAINTEXT")
        if security_protocol:
            conf["security.protocol"] = security_protocol
        if security_protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
            conf["sasl.mechanism"] = secret.get("sasl_mechanism", "PLAIN")
            conf["sasl.username"] = secret.get("sasl_username", "")
            conf["sasl.password"] = secret.get("sasl_password", "")

        def _connect():
            admin = AdminClient(conf)
            metadata = admin.list_topics(timeout=10)
            return metadata

        await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, _connect), timeout=15)
        return CredentialTestResponse(success=True, message="Connected to Kafka successfully.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e))


def _test_webhook_auth(secret: Dict[str, Any], service_type: str) -> CredentialTestResponse:
    if service_type == "basic_auth":
        if secret.get("username") and secret.get("password"):
            return CredentialTestResponse(success=True, message="Credentials format is valid.")
        return CredentialTestResponse(success=False, message="Username and password are required.")
    if service_type == "header_auth":
        if secret.get("header_name") and secret.get("header_value"):
            return CredentialTestResponse(success=True, message="Credentials format is valid.")
        return CredentialTestResponse(success=False, message="Header name and value are required.")
    return CredentialTestResponse(success=False, message="Unknown credential type.")


async def _run_test(service_type: str, secret: Dict[str, Any]) -> CredentialTestResponse:
    """Route a test request to the appropriate handler based on service type."""
    if service_type == "openai":
        return await _test_openai(secret)
    elif service_type == "openai_compatible":
        return await _test_openai_compatible(secret)
    elif service_type == "cohere":
        return await _test_cohere(secret)
    elif service_type == "tavily_search":
        return await _test_tavily(secret)
    elif service_type == "postgresql_vectorstore":
        return await _test_postgresql(secret)
    elif service_type == "kafka":
        return await _test_kafka(secret)
    elif service_type in ("basic_auth", "header_auth"):
        return _test_webhook_auth(secret, service_type)
    else:
        return CredentialTestResponse(
            success=False, message=f"Test not supported for service type: {service_type}"
        )


@router.post("/test-raw", response_model=CredentialTestResponse)
async def test_credential_raw(
    request: CredentialTestRawRequest,
    current_user=Depends(get_current_user),
):
    """Test credentials before saving, using raw data from the form."""
    try:
        return await _run_test(request.service_type, request.data)
    except Exception as e:
        logger.error(f"Unexpected error testing raw credential: {e}")
        return CredentialTestResponse(success=False, message=f"Unexpected error: {e}")


@router.post("/{credential_id}/test", response_model=CredentialTestResponse)
async def test_credential(
    credential_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    """Test whether a saved credential can successfully connect to its service."""
    user_id = current_user.id

    decrypted = await credential_service.get_decrypted_credential(db, user_id, credential_id)
    if not decrypted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    service_type: str = decrypted.get("service_type", "")
    secret: Dict[str, Any] = decrypted.get("secret", {})

    try:
        return await _run_test(service_type, secret)
    except Exception as e:
        logger.error(f"Unexpected error testing credential {credential_id}: {e}")
        return CredentialTestResponse(success=False, message=f"Unexpected error: {e}")


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
        if "base_url" in data:
            return "openai_compatible"
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