"""User Credentials API endpoints"""

import asyncio
import logging
import time
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
    CredentialWorkflowUsageResponse,
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


@router.get("/{credential_id}/workflows", response_model=CredentialWorkflowUsageResponse)
async def get_credential_workflows(
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    """
    List workflows that use the given credential in node configuration.

    Returns minimal workflow metadata and node usage details (no full flow_data).
    """
    user_id = current_user.id

    try:
        usage = await credential_service.get_workflows_using_credential(
            db, user_id, credential_id
        )
        if not usage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found",
            )
        return usage
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error retrieving workflow usage for credential {credential_id} "
            f"and user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credential workflow usage",
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


class CredentialModelOption(BaseModel):
    id: str
    owned_by: Optional[str] = None


class CredentialModelsResponse(BaseModel):
    models: List[CredentialModelOption]
    source: str  # "provider" | "empty"
    message: Optional[str] = None


_MODELS_CACHE: Dict[str, tuple[float, List[CredentialModelOption]]] = {}
_CACHE_TTL_SECONDS = 60.0


async def _list_openai_models(api_key: str) -> List[CredentialModelOption]:
    """Query official OpenAI /models endpoint."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    response = await asyncio.wait_for(client.models.list(), timeout=10)
    raw_items = getattr(response, "data", None) or []

    seen: set[str] = set()
    models: List[CredentialModelOption] = []
    for item in raw_items:
        model_id = str(getattr(item, "id", "") or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        owned_by = getattr(item, "owned_by", None)
        models.append(CredentialModelOption(id=model_id, owned_by=str(owned_by) if owned_by else None))

    models.sort(key=lambda m: m.id.lower())
    return models


def _is_html_response(content_type: str = "", body: str = "") -> bool:
    """Check if an HTTP response is an HTML web page rather than API JSON."""
    ct = (content_type or "").lower()
    if "text/html" in ct or "application/xhtml" in ct:
        return True
    body_strip = (body or "").strip().lower()
    if body_strip.startswith("<!doctype html") or body_strip.startswith("<html") or "<title>" in body_strip:
        return True
    return False


def _format_error_text(text: str, status_code: Optional[int] = None) -> str:
    """Sanitize error text to avoid dumping massive HTML documents or empty messages in the UI."""
    text_strip = (text or "").strip()
    if not text_strip:
        code_str = f" (HTTP {status_code})" if status_code else ""
        return f"Connection failed{code_str}. Please check your connection details."
    if _is_html_response(body=text_strip):
        code_str = f" (HTTP {status_code})" if status_code else ""
        return f"Server returned an HTML page instead of API response{code_str}. Please check your Base URL."
    if len(text_strip) > 500:
        return text_strip[:500] + "..."
    return text_strip


async def _list_openai_compatible_models(
    base_url: str,
    api_key: str = "",
    skip_ssl: bool = False,
) -> List[CredentialModelOption]:
    """Query an OpenAI Compatible endpoint's /models API."""
    url = f"{base_url.rstrip('/')}/models"
    headers: Dict[str, str] = {
        "User-Agent": "KAI-Flow/1.0",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(verify=not skip_ssl, timeout=httpx.Timeout(10.0, connect=4.0)) as http_client:
        resp = await http_client.get(url, headers=headers)
        if _is_html_response(resp.headers.get("content-type"), resp.text):
            raise ValueError(
                f"Server returned an HTML page (HTTP {resp.status_code}) instead of API response. Please check your Base URL."
            )
        if resp.status_code >= 400:
            raise ValueError(f"HTTP {resp.status_code}: {_format_error_text(resp.text, resp.status_code)}")

        json_data = resp.json()
        raw_items = None
        if isinstance(json_data, dict):
            raw_items = json_data.get("data") or json_data.get("models") or []
        elif isinstance(json_data, list):
            raw_items = json_data

    seen: set[str] = set()
    models: List[CredentialModelOption] = []
    for item in (raw_items or []):
        model_id = (
            getattr(item, "id", None)
            or (item.get("id") if isinstance(item, dict) else None)
            or (item.get("name") if isinstance(item, dict) else None)
            or (str(item) if isinstance(item, str) else None)
        )
        if not model_id or not str(model_id).strip():
            continue
        model_id_str = str(model_id).strip()
        if model_id_str in seen:
            continue

        seen.add(model_id_str)
        owned_by = getattr(item, "owned_by", None) or (item.get("owned_by") if isinstance(item, dict) else None)
        models.append(
            CredentialModelOption(
                id=model_id_str,
                owned_by=str(owned_by) if owned_by else None,
            )
        )

    models.sort(key=lambda m: m.id.lower())
    return models


async def _list_models_response(
    service_type: str,
    secret: Dict[str, Any],
) -> CredentialModelsResponse:
    """Query a provider's /models API with caching and error handling."""
    if service_type == "openai":
        api_key = str(secret.get("api_key") or "").strip()
        if not api_key:
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message="Enter your API key to load available models.",
            )

        cache_key = f"openai::{api_key}"
        now = time.time()
        if cache_key in _MODELS_CACHE:
            cached_time, cached_models = _MODELS_CACHE[cache_key]
            if now - cached_time < _CACHE_TTL_SECONDS:
                return CredentialModelsResponse(models=cached_models, source="provider")

        try:
            models = await _list_openai_models(api_key)
            if models:
                _MODELS_CACHE[cache_key] = (now, models)
                return CredentialModelsResponse(models=models, source="provider")
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message="Provider returned no models. You can type a model name manually.",
            )
        except asyncio.TimeoutError:
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message="Connection timed out. You can type a model name manually.",
            )
        except Exception as e:
            logger.warning(f"Failed to list OpenAI models: {e}")
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message=f"Could not fetch models: {_format_error_text(str(e))}",
            )

    elif service_type == "openai_compatible":
        base_url = str(secret.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message="Enter a Base URL to load available models.",
            )

        api_key = str(secret.get("api_key") or "").strip()
        skip_ssl = secret.get("skip_ssl_verify", False)
        if isinstance(skip_ssl, str):
            skip_ssl = skip_ssl.lower() in ("true", "1", "yes", "on")
        skip_ssl = bool(skip_ssl)

        cache_key = f"openai_compatible:{base_url}:{api_key}"
        now = time.time()
        if cache_key in _MODELS_CACHE:
            cached_time, cached_models = _MODELS_CACHE[cache_key]
            if now - cached_time < _CACHE_TTL_SECONDS:
                return CredentialModelsResponse(models=cached_models, source="provider")

        try:
            models = await _list_openai_compatible_models(base_url, api_key=api_key, skip_ssl=skip_ssl)
            if models:
                _MODELS_CACHE[cache_key] = (now, models)
                return CredentialModelsResponse(models=models, source="provider")
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message="Provider returned no models. You can type a model name manually.",
            )
        except asyncio.TimeoutError:
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message="Connection timed out. You can type a model name manually.",
            )
        except Exception as e:
            logger.warning(f"Failed to list OpenAI Compatible models: {e}")
            return CredentialModelsResponse(
                models=[],
                source="empty",
                message=f"Could not fetch models: {_format_error_text(str(e))}",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Model listing is not supported for service type: {service_type}",
    )


@router.post("/list-models", response_model=CredentialModelsResponse)
async def list_models_raw(
    request: CredentialTestRawRequest,
    current_user: User = Depends(get_current_user),
):
    """List models from unsaved credential form data (base URL / API key)."""
    return await _list_models_response(request.service_type, request.data or {})


@router.get("/{credential_id}/models", response_model=CredentialModelsResponse)
async def list_credential_models(
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    """
    List available LLM models for a credential by querying the provider's /models API.
    """
    user_id = current_user.id
    decrypted = await credential_service.get_decrypted_credential(db, user_id, credential_id)
    if not decrypted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    return await _list_models_response(
        decrypted.get("service_type", ""),
        decrypted.get("secret", {}) or {},
    )


async def _test_openai(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        api_key = str(secret.get("api_key") or "").strip()
        if not api_key:
            return CredentialTestResponse(success=False, message="API key is required.")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        await asyncio.wait_for(client.models.list(), timeout=10)
        return CredentialTestResponse(success=True, message="Connected to OpenAI successfully.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e) or "Connection failed. Please check your API key.")


async def _test_openai_compatible(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        base_url = str(secret.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            return CredentialTestResponse(success=False, message="Base URL is required.")

        api_key = str(secret.get("api_key") or "").strip()
        model_name = str(secret.get("model_name") or "").strip()
        skip_ssl = secret.get("skip_ssl_verify", False)
        if isinstance(skip_ssl, str):
            skip_ssl = skip_ssl.lower() in ("true", "1", "yes", "on")
        skip_ssl = bool(skip_ssl)

        headers: Dict[str, str] = {
            "User-Agent": "KAI-Flow/1.0",
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(verify=not skip_ssl, timeout=httpx.Timeout(10.0, connect=4.0)) as http_client:
            # 1. Connectivity check via /models
            models_url = f"{base_url}/models"
            try:
                models_resp = await http_client.get(models_url, headers=headers)
                if _is_html_response(models_resp.headers.get("content-type"), models_resp.text):
                    return CredentialTestResponse(
                        success=False,
                        message=f"Server returned an HTML page (HTTP {models_resp.status_code}) instead of API response. Please check your Base URL.",
                    )
                if models_resp.status_code >= 400:
                    return CredentialTestResponse(
                        success=False,
                        message=_format_error_text(models_resp.text, models_resp.status_code),
                    )
            except httpx.RequestError as req_err:
                return CredentialTestResponse(success=False, message=str(req_err) or "Connection failed. Please check your Base URL.")

            # 2. Authentication probe: if API key is provided, test it with a lightweight POST request
            if api_key:
                chat_url = f"{base_url}/chat/completions"
                probe_model = model_name
                try:
                    chat_resp = await http_client.post(
                        chat_url,
                        headers=headers,
                        json={
                            "model": probe_model,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1,
                        },
                    )
                    if _is_html_response(chat_resp.headers.get("content-type"), chat_resp.text):
                        return CredentialTestResponse(
                            success=False,
                            message=f"Server returned an HTML page (HTTP {chat_resp.status_code}) instead of API response. Please check your Base URL.",
                        )
                    if chat_resp.status_code >= 400:
                        return CredentialTestResponse(
                            success=False,
                            message=_format_error_text(chat_resp.text, chat_resp.status_code),
                        )
                except httpx.RequestError as req_err:
                    logger.debug(f"Chat probe request error: {req_err}")

        msg = "Connected to OpenAI Compatible provider successfully."
        if skip_ssl:
            msg += " (SSL verification was skipped)"
        return CredentialTestResponse(success=True, message=msg)
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="Connection timed out.")
    except Exception as e:
        return CredentialTestResponse(success=False, message=str(e) or "Connection failed. Please check your connection details.")


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
    api_key = str(secret.get("api_key", "")).strip()
    if not api_key:
        return CredentialTestResponse(success=False, message="API key is required.")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": "ping", "max_results": 1},
            )
            response.raise_for_status()
        return CredentialTestResponse(success=True, message="Connected to Tavily successfully.")
    except (asyncio.TimeoutError, httpx.TimeoutException):
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


async def _test_mongodb(secret: Dict[str, Any]) -> CredentialTestResponse:
    """Test MongoDB in a worker thread so the async API remains responsive."""
    from app.nodes.databases.mongo_node import MongoNode, _build_mongodb_uri

    database = str(secret.get("database") or "").strip()
    if not database:
        return CredentialTestResponse(
            success=False, message="MongoDB Database Name is required."
        )

    try:
        connection_string = _build_mongodb_uri(secret)
    except ValueError as exc:
        return CredentialTestResponse(success=False, message=str(exc))

    try:
        from pymongo import MongoClient
    except ImportError:
        return CredentialTestResponse(
            success=False,
            message="The pymongo package is not installed on the server.",
        )

    def check_connection() -> int:
        client = MongoClient(
            connection_string,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        try:
            client.admin.command("ping")
            return len(client[database].list_collection_names())
        finally:
            client.close()

    try:
        collection_count = await asyncio.wait_for(
            asyncio.to_thread(check_connection), timeout=15
        )
        return CredentialTestResponse(
            success=True,
            message=(
                "MongoDB connection successful. "
                f"The selected database has {collection_count} collection(s)."
            ),
        )
    except asyncio.TimeoutError:
        return CredentialTestResponse(
            success=False, message="MongoDB connection timed out."
        )
    except Exception as exc:
        message = MongoNode._database_error(exc)
        logger.warning("MongoDB credential test failed: %s", message)
        return CredentialTestResponse(
            success=False, message=message
        )

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


async def _test_minio(secret: Dict[str, Any]) -> CredentialTestResponse:
    try:
        from app.services.minio_service import minio_service
        import asyncio
        import boto3
        from botocore.exceptions import ClientError, EndpointConnectionError
        
        endpoint = secret.get("endpoint", "").strip()
        # Strip protocols if user entered them
        if endpoint.startswith("http://"):
            endpoint = endpoint[7:]
        elif endpoint.startswith("https://"):
            endpoint = endpoint[8:]
            
        if not endpoint:
            return CredentialTestResponse(success=False, message="Endpoint URL is required (e.g. host.docker.internal:9000).")
            
        access_key = secret.get("access_key") or secret.get("username", "")
        secret_key = secret.get("secret_key") or secret.get("password", "")
        
        if not access_key or not secret_key:
            return CredentialTestResponse(success=False, message="Access Key and Secret Key are required.")

        use_ssl_val = secret.get('use_ssl', False)
        use_ssl = use_ssl_val is True or str(use_ssl_val).lower() in ['true', '1', 'yes']

        def _connect():
            logger.info(f"Testing MinIO connection to {endpoint} (SSL: {use_ssl})")
            # Force path-style for MinIO
            client = minio_service.get_client(endpoint, access_key, secret_key, use_ssl=use_ssl)
            # Try to list buckets to verify credentials and connectivity
            client.list_buckets()

        await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, _connect), timeout=12)
        return CredentialTestResponse(success=True, message="Connected to MinIO/S3 successfully.")
    except asyncio.TimeoutError:
        logger.error("MinIO test timed out")
        return CredentialTestResponse(success=False, message="Connection timed out. Check your Endpoint URL and Firewall.")
    except EndpointConnectionError as e:
        logger.error(f"MinIO endpoint error: {e}")
        return CredentialTestResponse(success=False, message=f"Could not connect to endpoint: {e}")
    except ClientError as e:
        logger.error(f"MinIO client error: {e}")
        return CredentialTestResponse(success=False, message=f"Authentication failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected MinIO test error: {type(e).__name__}: {e}")
        return CredentialTestResponse(success=False, message=f"Connection failed: {str(e)}")


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


async def _test_mysql(secret: Dict[str, Any]) -> CredentialTestResponse:
    """Test a MySQL credential without exposing connection details."""
    from app.nodes.databases.mysql_node import MySQLNode, mysql_connection

    def check_connection() -> None:
        with mysql_connection(secret) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    try:
        await asyncio.wait_for(asyncio.to_thread(check_connection), timeout=15)
        return CredentialTestResponse(success=True, message="MySQL connection successful.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="MySQL connection timed out.")
    except Exception as exc:
        message = MySQLNode._database_error(exc)
        logger.warning("MySQL credential test failed: %s", message)
        return CredentialTestResponse(success=False, message=message)


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
    elif service_type == "mongodb":
        return await _test_mongodb(secret)
    elif service_type == "kafka":
        return await _test_kafka(secret)
    elif service_type == "minio":
        return await _test_minio(secret)
    elif service_type == "mysql":
        return await _test_mysql(secret)
    elif service_type == "sqlite":
        return await _test_sqlite(secret)
    elif service_type in ("basic_auth", "header_auth"):
        return _test_webhook_auth(secret, service_type)
    else:
        return CredentialTestResponse(
            success=False, message=f"Test not supported for service type: {service_type}"
        )


async def _test_sqlite(secret: Dict[str, Any]) -> CredentialTestResponse:
    """Test a SQLite credential without exposing its filesystem path."""
    from app.nodes.databases.sqlite_node import SQLiteNode, sqlite_connection

    def check_connection() -> None:
        with sqlite_connection(secret) as connection:
            connection.execute("SELECT 1").fetchone()

    try:
        await asyncio.wait_for(asyncio.to_thread(check_connection), timeout=15)
        return CredentialTestResponse(success=True, message="SQLite connection successful.")
    except asyncio.TimeoutError:
        return CredentialTestResponse(success=False, message="SQLite connection timed out.")
    except Exception as exc:
        message = SQLiteNode._database_error(exc)
        logger.warning("SQLite credential test failed: %s", message)
        return CredentialTestResponse(
            success=False,
            message=message,
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
    # Simple heuristics to detect service type. Ambiguous host/database/user
    # combinations are intentionally not guessed; normal clients send the
    # explicit service_type alongside credential data.
    if "database_path" in data:
        return "sqlite"

    connection_string = data.get("connection_string")
    if isinstance(connection_string, str) and connection_string.lower().startswith(
        ("mongodb://", "mongodb+srv://")
    ):
        return "mongodb"

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
    elif ("access_key" in data and "secret_key" in data) or "endpoint" in data:
        return "minio"
    elif "private_key" in data or "certificate" in data:
        return "certificate"
    else:
        return "custom"
