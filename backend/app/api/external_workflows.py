# -*- coding: utf-8 -*-
"""External workflow API endpoints for managing Docker-exported workflows."""

import logging
import uuid
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.external_workflow import ExternalWorkflow
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.core.database import get_db_session
from app.core.constants import API_START,API_VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

# ================================================================================
# PYDANTIC MODELS
# ================================================================================

class ExternalWorkflowConfig(BaseModel):
    """Configuration for registering an external workflow."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the external workflow")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the external workflow")
    host: str = Field(..., description="Host address of the external workflow")
    port: int = Field(..., ge=1, le=65535, description="Port number of the external workflow")
    is_secure: bool = Field(default=False, description="Whether to use HTTPS")
    api_key: Optional[str] = Field(None, description="API key for authentication")

class ExternalWorkflowInfo(BaseModel):
    """Information about an external workflow."""
    workflow_id: str
    name: str
    description: Optional[str]
    external_url: str
    api_key_required: bool
    connection_status: str
    capabilities: Dict[str, Any]
    created_at: Optional[str] = None
    last_health_check: Optional[str] = None

class ExternalWorkflowRegistration(BaseModel):
    """Response for external workflow registration."""
    workflow_id: str
    name: str
    description: Optional[str]
    external_url: str
    status: str

class ExternalWorkflowStatus(BaseModel):
    """Status of an external workflow."""
    workflow_id: str
    status: str
    last_checked: str
    connection_info: Dict[str, Any]

class ChatRequest(BaseModel):
    """Request for chatting with external workflow."""
    input: str = Field(..., min_length=1, description="User input message")
    session_id: Optional[str] = Field(None, description="Chat session ID")

class ChatResponse(BaseModel):
    """Response from external workflow chat."""
    workflow_id: str
    session_id: str
    user_input: str
    response: str
    status: str
    timestamp: str
    memory_enabled: bool = False
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

# ================================================================================
# HELPER FUNCTIONS
# ================================================================================

async def connect_and_validate_external_workflow(config: ExternalWorkflowConfig) -> Dict[str, Any]:
    """Connect to and validate an external workflow."""
    protocol = "https" if config.is_secure else "http"
    base_url = f"{protocol}://{config.host}:{config.port}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, check the external workflow info to see if API key is required
            headers = {}
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"
            
            # Try to get external workflow info first (this endpoint should not require auth)
            try:
                external_info_response = await client.get(f"{base_url}/{API_START}/workflow/external/info")
                if external_info_response.status_code == 200:
                    external_info = external_info_response.json()
                    api_key_required = external_info.get("api_key_required", False)
                    
                    # If API key is required by the workflow but not provided by user
                    if api_key_required and not config.api_key:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="API key is required for this workflow but was not provided"
                        )
            except httpx.RequestError:
                # If external info endpoint is not available, continue with normal flow
                pass
            
            # Test connection to the info endpoint
            info_response = await client.get(f"{base_url}/{API_START}/workflow/info", headers=headers)
            
            if info_response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key for external workflow"
                )
            elif info_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"External workflow returned status {info_response.status_code}"
                )
            
            workflow_info = info_response.json()
            
            # Extract capabilities
            capabilities = {
                "chat": len(workflow_info.get("llm_nodes", [])) > 0,
                "memory": workflow_info.get("memory_enabled", False),
                "info_access": True,
                "modification": False  # External workflows are read-only
            }
            
            # Get API key requirement from external info (if available)
            api_key_required = False
            try:
                external_info_response = await client.get(f"{base_url}/{API_START}/workflow/external/info")
                if external_info_response.status_code == 200:
                    external_info = external_info_response.json()
                    api_key_required = external_info.get("api_key_required", False)
            except httpx.RequestError:
                # If external info endpoint is not available, assume no API key required
                pass
            
            return {
                "workflow_info": workflow_info,
                "external_url": base_url,
                "capabilities": capabilities,
                "api_key_required": api_key_required,
                "connection_info": {
                    "response_time": "< 30s",
                    "api_version": workflow_info.get("api_version", "unknown"),
                    "nodes_count": workflow_info.get("nodes_count", 0),
                    "edges_count": workflow_info.get("edges_count", 0)
                }
            }
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to external workflow: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test failed: {str(e)}"
        )

def create_external_workflow_record(
    user_id: uuid.UUID,
    config: ExternalWorkflowConfig,
    validation_result: Dict[str, Any]
) -> ExternalWorkflow:
    """Create an external workflow record."""
    
    workflow_info = validation_result["workflow_info"]
    external_url = validation_result["external_url"]
    capabilities = validation_result["capabilities"]
    api_key_required = validation_result.get("api_key_required", False)
    
    # Create external workflow record
    external_workflow = ExternalWorkflow(
        user_id=user_id,
        name=config.name,
        description=config.description,
        host=config.host,
        port=config.port,
        is_secure=config.is_secure,
        api_key=config.api_key if config.api_key else None,
        api_key_required=api_key_required,
        external_workflow_id=workflow_info.get("workflow_id"),
        external_url=external_url,
        workflow_structure=workflow_info.get("workflow", {}),
        capabilities=capabilities,
        status="online",  # Since we just successfully connected
        last_health_check=datetime.utcnow()
    )
    
    return external_workflow

# ================================================================================
# EXTERNAL WORKFLOW API ENDPOINTS
# ================================================================================

@router.post("/external/register", response_model=ExternalWorkflowRegistration, tags=["External Workflows"])
async def register_external_workflow(
    config: ExternalWorkflowConfig,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Register an external Docker workflow with KAI-Flow."""
    logger.info(f"User {current_user.id} attempting to register external workflow: {config.name}")
    
    try:
        # Validate connection to external workflow
        validation_result = await connect_and_validate_external_workflow(config)
        workflow_info = validation_result["workflow_info"]
        external_url = validation_result["external_url"]
        
        # Check if this external workflow is already registered
        external_workflow_id = workflow_info.get("workflow_id")
        if external_workflow_id:
            existing_query = select(ExternalWorkflow).filter(
                ExternalWorkflow.user_id == current_user.id,
                ExternalWorkflow.external_workflow_id == external_workflow_id
            )
            result = await db.execute(existing_query)
            existing_workflow = result.scalars().first()
            
            if existing_workflow:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This external workflow is already registered"
                )
        
        # Create external workflow record
        external_workflow = create_external_workflow_record(
            current_user.id, config, validation_result
        )
        
        db.add(external_workflow)
        await db.commit()
        await db.refresh(external_workflow)
        
        logger.info(f"External workflow registered successfully: {external_workflow.id}")
        
        return ExternalWorkflowRegistration(
            workflow_id=str(external_workflow.id),
            name=external_workflow.name,
            description=external_workflow.description,
            external_url=external_url,
            status="registered"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"External workflow registration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="External workflow registration failed"
        )

@router.get("/external", response_model=List[ExternalWorkflowInfo], tags=["External Workflows"])
async def list_external_workflows(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """List all registered external workflows for the current user."""
    try:
        # Get external workflows for the user
        query = select(ExternalWorkflow).filter(
            ExternalWorkflow.user_id == current_user.id,
            ExternalWorkflow.is_active == True
        ).order_by(ExternalWorkflow.created_at.desc())
        
        result = await db.execute(query)
        external_workflows = result.scalars().all()
        
        # Format response with external workflow info
        workflows_info = []
        for workflow in external_workflows:
            workflows_info.append(ExternalWorkflowInfo(
                workflow_id=str(workflow.id),
                name=workflow.name,
                description=workflow.description,
                external_url=workflow.external_url,
                api_key_required=bool(workflow.api_key),
                connection_status=workflow.status,
                capabilities=workflow.capabilities or {},
                created_at=workflow.created_at.isoformat() if workflow.created_at else None,
                last_health_check=workflow.last_health_check.isoformat() if workflow.last_health_check else None
            ))
        
        return workflows_info
        
    except Exception as e:
        logger.error(f"Failed to list external workflows: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list external workflows"
        )

@router.get("/external/{workflow_id}/info", tags=["External Workflows"])
async def get_external_workflow_info(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get read-only information about an external workflow (nodes, structure, etc.)."""
    logger.info(f"User {current_user.id} getting info for external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Extract host and port from workflow
        host = workflow.host
        port = workflow.port
        
        try:
            headers = {}
            if workflow.api_key:
                headers["Authorization"] = f"Bearer {workflow.api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{workflow.external_url}/{API_START}/workflow/info", headers=headers)
                
                if response.status_code == 200:
                    workflow_info = response.json()
                    
                    # Update status in database
                    workflow.status = "online"
                    workflow.last_health_check = datetime.utcnow()
                    await db.commit()
                    
                    return {
                        "workflow_id": workflow_id,
                        "name": workflow.name,
                        "description": workflow.description,
                        "host": host,
                        "port": port,
                        "status": "online",
                        "read_only": True,
                        "workflow_structure": {
                            "nodes": workflow_info.get("workflow", {}).get("nodes", []),
                            "edges": workflow_info.get("workflow", {}).get("edges", []),
                            "nodes_count": workflow_info.get("nodes_count", 0),
                            "edges_count": workflow_info.get("edges_count", 0),
                            "llm_nodes": workflow_info.get("llm_nodes", []),
                            "memory_nodes": workflow_info.get("memory_nodes", []),
                            "memory_enabled": workflow_info.get("memory_enabled", False)
                        },
                        "capabilities": {
                            "chat": len(workflow_info.get("llm_nodes", [])) > 0,
                            "memory": workflow_info.get("memory_enabled", False),
                            "info_access": True,
                            "modification": False
                        },
                        "last_checked": datetime.utcnow().isoformat()
                    }
                else:
                    # Update status as offline
                    workflow.status = "offline"
                    workflow.last_error = f"External workflow returned status {response.status_code}"
                    await db.commit()
                    
                    return {
                        "workflow_id": workflow_id,
                        "name": workflow.name,
                        "description": workflow.description,
                        "host": host,
                        "port": port,
                        "status": "offline",
                        "read_only": True,
                        "error": f"External workflow returned status {response.status_code}",
                        "last_checked": datetime.utcnow().isoformat()
                    }
        except httpx.RequestError as e:
            logger.warning(f"Failed to connect to external workflow {workflow_id}: {e}")
            
            # Update status as offline
            workflow.status = "offline"
            workflow.last_error = f"Connection failed: {str(e)}"
            await db.commit()
            
            return {
                "workflow_id": workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "host": host,
                "port": port,
                "status": "offline",
                "read_only": True,
                "error": f"Connection failed: {str(e)}",
                "last_checked": datetime.utcnow().isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get external workflow info {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get external workflow info"
        )

@router.post("/external/{workflow_id}/chat", response_model=ChatResponse, tags=["External Workflows"])
async def chat_with_external_workflow(
    workflow_id: str,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Send a chat message to an external workflow (read-only interaction)."""
    logger.info(f"User {current_user.id} chatting with external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Generate session ID if not provided
        session_id = request.session_id or f"external_{current_user.id}_{workflow_id}_{int(datetime.utcnow().timestamp())}"
        
        # Prepare chat request
        chat_request = {

            "input": request.input,
            "session_id": session_id

        }
        
        # Check if the external workflow requires API key but we don't have one
        if workflow.api_key_required and not workflow.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This external workflow requires API key authentication, but no API key was provided during registration"
            )
        
        try:
            headers = {"Content-Type": "application/json"}
            if workflow.api_key:
                headers["Authorization"] = f"Bearer {workflow.api_key}"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{workflow.external_url}/{API_START}/workflow/execute",
                    json=chat_request,
                    headers=headers
                )
                
                if response.status_code == 200:
                    chat_response = response.json()
                    result = chat_response.get("result", {})
                    
                    # Update workflow status
                    workflow.status = "online"
                    workflow.last_health_check = datetime.utcnow()
                    await db.commit()
                    
                    return ChatResponse(
                        workflow_id=workflow_id,
                        session_id=session_id,
                        user_input=request.input,
                        response=result.get("response", "No response"),
                        status=chat_response.get("status", "unknown"),
                        model=result.get("model"),
                        memory_enabled=result.get("memory_enabled", False),
                        usage=result.get("usage"),
                        timestamp=datetime.utcnow().isoformat()
                    )
                else:
                    # Update workflow status
                    workflow.status = "error"
                    workflow.last_error = f"Chat failed with status {response.status_code}"
                    await db.commit()
                    
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"External workflow returned status {response.status_code}"
                    )
        except httpx.RequestError as e:
            logger.warning(f"Failed to chat with external workflow {workflow_id}: {e}")
            
            # Update workflow status
            workflow.status = "offline"
            workflow.last_error = f"Connection failed: {str(e)}"
            await db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to external workflow: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to chat with external workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to chat with external workflow"
        )

@router.get("/external/{workflow_id}/status", response_model=ExternalWorkflowStatus, tags=["External Workflows"])
async def check_external_workflow_status(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Check the status of an external workflow."""
    logger.info(f"User {current_user.id} checking status of external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Ping the external workflow
        try:
            headers = {}
            if workflow.api_key:
                headers["Authorization"] = f"Bearer {workflow.api_key}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{workflow.external_url}/health", headers=headers)
                
                if response.status_code == 200:
                    workflow.status = "online"
                    workflow.last_health_check = datetime.utcnow()
                    connection_status = "online"
                else:
                    workflow.status = "error"
                    workflow.last_error = f"Health check returned {response.status_code}"
                    connection_status = "error"
        except httpx.RequestError as e:
            workflow.status = "offline"
            workflow.last_error = f"Connection failed: {str(e)}"
            connection_status = "offline"
        
        await db.commit()
        
        return ExternalWorkflowStatus(
            workflow_id=workflow_id,
            status=connection_status,
            last_checked=datetime.utcnow().isoformat(),
            connection_info={
                "host": workflow.host,
                "port": workflow.port,
                "external_url": workflow.external_url,
                "last_error": workflow.last_error
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check external workflow status {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check external workflow status"
        )

@router.get("/external/{workflow_id}/sessions", tags=["External Workflows"])
async def list_external_workflow_sessions(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List all chat sessions for an external workflow."""
    logger.info(f"User {current_user.id} listing sessions for external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Get sessions from external workflow
        try:
            headers = {}
            if workflow.api_key:
                headers["Authorization"] = f"Bearer {workflow.api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{workflow.external_url}/{API_START}/workflow/sessions",
                    headers=headers
                )
                
                if response.status_code == 200:
                    sessions_data = response.json()
                    return {
                        "workflow_id": workflow_id,
                        "sessions": sessions_data.get("sessions", []),
                        "total_sessions": sessions_data.get("total_sessions", 0)
                    }
                else:
                    return {
                        "workflow_id": workflow_id,
                        "sessions": [],
                        "total_sessions": 0,
                        "error": f"External workflow returned status {response.status_code}"
                    }
        except httpx.RequestError as e:
            logger.warning(f"Failed to get sessions from external workflow {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "sessions": [],
                "total_sessions": 0,
                "error": f"Connection failed: {str(e)}"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list sessions for external workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list external workflow sessions"
        )

@router.get("/external/{workflow_id}/sessions/{session_id}/history", tags=["External Workflows"])
async def get_external_workflow_session_history(
    workflow_id: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get chat history for a specific session."""
    logger.info(f"User {current_user.id} getting history for session {session_id} in external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Get session history from external workflow
        try:
            headers = {}
            if workflow.api_key:
                headers["Authorization"] = f"Bearer {workflow.api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{workflow.external_url}/{API_START}/workflow/memory/{session_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    history_data = response.json()
                    return {
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "messages": history_data.get("messages", []),
                        "message_count": history_data.get("message_count", 0),
                        "memory_enabled": history_data.get("memory_enabled", False)
                    }
                else:
                    return {
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "messages": [],
                        "message_count": 0,
                        "memory_enabled": False,
                        "error": f"External workflow returned status {response.status_code}"
                    }
        except httpx.RequestError as e:
            logger.warning(f"Failed to get session history from external workflow {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "session_id": session_id,
                "messages": [],
                "message_count": 0,
                "memory_enabled": False,
                "error": f"Connection failed: {str(e)}"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session history for external workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session history"
        )

@router.delete("/external/{workflow_id}/sessions/{session_id}", tags=["External Workflows"])
async def clear_external_workflow_session(
    workflow_id: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Clear a specific chat session."""
    logger.info(f"User {current_user.id} clearing session {session_id} in external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Clear session on external workflow
        try:
            headers = {}
            if workflow.api_key:
                headers["Authorization"] = f"Bearer {workflow.api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{workflow.external_url}/{API_START}/workflow/memory/{session_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    clear_data = response.json()
                    return {
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "status": "cleared",
                        "message": clear_data.get("message", "Session cleared successfully")
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"External workflow returned status {response.status_code}"
                    )
        except httpx.RequestError as e:
            logger.warning(f"Failed to clear session on external workflow {workflow_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to external workflow: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear session for external workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear session"
        )

@router.delete("/external/{workflow_id}", tags=["External Workflows"])
async def unregister_external_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Unregister an external workflow."""
    logger.info(f"User {current_user.id} unregistering external workflow {workflow_id}")
    
    try:
        # Get external workflow record
        workflow = await db.get(ExternalWorkflow, uuid.UUID(workflow_id))
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="External workflow not found"
            )
        
        # Mark as inactive instead of deleting (soft delete)
        workflow.is_active = False
        await db.commit()
        
        logger.info(f"External workflow {workflow_id} unregistered successfully")
        
        return {
            "message": "External workflow unregistered successfully",
            "workflow_id": workflow_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister external workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister external workflow"
        )