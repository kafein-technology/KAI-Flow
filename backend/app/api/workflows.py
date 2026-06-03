
import json
import logging
import uuid
from typing import Any, Dict, Optional, AsyncGenerator, List
from datetime import datetime, timedelta
from sqlalchemy import and_, func as sql_func

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc
from app.models.execution import WorkflowExecution
from app.core.engine import get_engine
from app.core.database import get_db_session
from app.auth.dependencies import get_current_user, get_optional_user, get_current_user_or_master_api_key
from app.models.user import User
from app.models.workflow import WorkflowTemplate
from app.schemas.workflow import (
    WorkflowCreate, 
    WorkflowUpdate, 
    WorkflowResponse,
    WorkflowTemplateCreate,
    WorkflowTemplateResponse,
    WorkflowVisibilityUpdate
)
from app.services.workflow_service import WorkflowService, WorkflowTemplateService
from app.services.dependencies import get_workflow_service_dep, get_workflow_template_service_dep, get_execution_service_dep
from app.services.execution_service import ExecutionService
from app.services.chat_service import ChatService
from app.schemas.chat import ChatMessageCreate
from app.schemas.execution import WorkflowExecutionCreate, WorkflowExecutionUpdate
from app.core.execution_queue import execution_queue
from app.models.workflow import Workflow
from app.services.workflow_executor import get_workflow_executor
from app.core.json_utils import make_json_serializable
from sqlalchemy.future import select

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=List[WorkflowResponse])
async def get_workflows(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep),
    skip: int = 0,
    limit: int = 100
):
    """
    Get list of workflows for the current user.
    """
    try:
        user_id = current_user.id  # Cache user ID
        # Get user's workflows, ordered by updated_at descending
        query = (
            select(Workflow)
            .filter_by(user_id=user_id)
            .order_by(desc(Workflow.updated_at))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        workflows = result.scalars().all()
        
        return [WorkflowResponse.model_validate(workflow) for workflow in workflows]
    except Exception as e:
        logger.error(f"Error fetching workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch workflows")


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user_or_master_api_key)
):
    """Create a new workflow"""
    try:
        user_id = current_user.id  # Cache user ID before potential session issues
        workflow = Workflow(
            user_id=user_id,
            name=workflow_data.name,
            description=workflow_data.description,
            is_public=workflow_data.is_public,
            error_workflow=workflow_data.error_workflow,
            flow_data=workflow_data.flow_data
        )
        
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        
        logger.info(f"Created workflow {workflow.id} for user {user_id}")
        return WorkflowResponse.model_validate(workflow)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create workflow")


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep)
):
    """Get specific workflow with full flow data"""
    try:
        workflow = await workflow_service.get_by_id(db, workflow_id, current_user.id)
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Check if user has access (owner or public workflow)
        user_id = current_user.id
        if workflow.user_id != user_id and not workflow.is_public:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Refresh sticky session ID for canvas testing when workflow is opened
        try:
            executor = get_workflow_executor()
            executor.refresh_canvas_session_id(user_id, workflow_id)
        except Exception as e:
            logger.warning(f"Failed to refresh canvas session on workflow load: {e}")
            
        return WorkflowResponse.model_validate(workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch workflow")


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    workflow_data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep)
):
    """Update an existing workflow"""
    try:
        user_id = current_user.id  # Cache user ID
        workflow = await workflow_service.get_by_id(db, workflow_id, user_id)
        
        if not workflow:
            logger.warning(f"Workflow {workflow_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Only owner can update
        if workflow.user_id != user_id:
            logger.warning(f"User {user_id} attempted to update workflow {workflow_id} owned by {workflow.user_id}")
            raise HTTPException(status_code=403, detail="Only workflow owner can update")
        
        # Update fields that are provided
        update_data = workflow_data.model_dump(exclude_unset=True)
        if "error_workflow" in update_data and update_data["error_workflow"] is not None:
            error_workflow_id = update_data["error_workflow"]
            if error_workflow_id == workflow_id:
                raise HTTPException(
                    status_code=400,
                    detail="A workflow cannot use itself as its error workflow",
                )
            error_wf = await workflow_service.get_accessible_workflow(db, error_workflow_id, user_id)
            if not error_wf:
                raise HTTPException(status_code=404, detail="Error workflow not found")
            nodes = error_wf.flow_data.get("nodes", []) if isinstance(error_wf.flow_data, dict) else []
            has_error_trigger = any(
                isinstance(n, dict) and n.get("type") in ("ErrorTrigger", "ErrorTriggerNode")
                for n in nodes
            )
            if not has_error_trigger:
                raise HTTPException(
                    status_code=400,
                    detail="Selected workflow must contain an Error Trigger node",
                )

        for field, value in update_data.items():
            setattr(workflow, field, value)
        
        # Increment version if flow_data is updated
        if 'flow_data' in update_data:
            workflow.version += 1
        
        try:
            await db.commit()
            await db.refresh(workflow)
        except Exception as commit_error:
            await db.rollback()
            logger.error(f"Database commit failed for workflow {workflow_id}: {commit_error}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to save workflow to database")
        
        logger.info(f"Successfully updated workflow {workflow_id} for user {user_id}")
        return WorkflowResponse.model_validate(workflow)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep)
):
    """Delete a workflow"""
    try:
        user_id = current_user.id  # Cache user ID
        workflow = await workflow_service.get_by_id(db, workflow_id, user_id)
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Only owner can delete
        if workflow.user_id != user_id:
            raise HTTPException(status_code=403, detail="Only workflow owner can delete")
        
        # First, delete all executions for this workflow
        from app.models.execution import WorkflowExecution, ExecutionCheckpoint
        from sqlalchemy import delete
        
        # Delete execution checkpoints first (due to foreign key)
        checkpoint_delete = delete(ExecutionCheckpoint).where(
            ExecutionCheckpoint.execution_id.in_(
                select(WorkflowExecution.id).where(WorkflowExecution.workflow_id == workflow_id)
            )
        )
        await db.execute(checkpoint_delete)
        
        # Delete executions
        execution_delete = delete(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        await db.execute(execution_delete)
        
        # Now delete the workflow
        await db.delete(workflow)
        await db.commit()
        
        logger.info(f"Successfully deleted workflow {workflow_id} for user {user_id}")
        return {"message": f"Workflow {workflow_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")


@router.post("/validate")
async def validate_workflow(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Validate workflow structure without executing"""
    engine = get_engine()
    
    # Extract flow_data from request
    flow_data = request_data.get("flow_data", request_data)
    
    try:
        validation_result = engine.validate(flow_data)
        return {
            "valid": validation_result["valid"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "node_count": len(flow_data.get("nodes", [])),
            "edge_count": len(flow_data.get("edges", []))
        }
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
            "node_count": 0,
            "edge_count": 0
        }


@router.get("/public/", response_model=List[WorkflowResponse])
async def get_public_workflows(
    db: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep),
    current_user: Optional[User] = Depends(get_optional_user),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
):
    """
    Get list of public workflows.
    """
    try:
        sanitized_search = None
        if search:
            # Sanitize search parameter to prevent injection attacks
            if len(search.strip()) == 0:
                sanitized_search = None
            elif len(search) > 200:
                raise HTTPException(status_code=400, detail="Search query too long")
            else:
                # Remove potentially dangerous characters
                import re
                sanitized_search = re.sub(r'[^\w\s\-_]', '', search.strip())
        
        workflows = await workflow_service.get_public_workflows(
            db, skip=skip, limit=limit, search=sanitized_search
        )
        return [WorkflowResponse.model_validate(workflow) for workflow in workflows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching public workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch public workflows")


@router.get("/search/", response_model=List[WorkflowResponse])
async def search_workflows(
    q: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep),
    skip: int = 0,
    limit: int = 100
):
    """
    Search user's workflows by name or description.
    """
    try:
        # Sanitize search parameter to prevent injection attacks
        if len(q.strip()) == 0:
            raise HTTPException(status_code=400, detail="Search query cannot be empty")
        if len(q) > 200:
            raise HTTPException(status_code=400, detail="Search query too long")
        
        # Remove potentially dangerous characters
        import re
        sanitized_q = re.sub(r'[^\w\s\-_]', '', q.strip())
        
        user_id = current_user.id  # Cache user ID
        workflows = await workflow_service.get_user_workflows(
            db, user_id, skip=skip, limit=limit, search=sanitized_q
        )
        return [WorkflowResponse.model_validate(workflow) for workflow in workflows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search workflows")


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse)
async def duplicate_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep),
    new_name: Optional[str] = None
):
    """
    Duplicate a workflow (accessible to user).
    """
    try:
        user_id = current_user.id  # Cache user ID
        duplicated = await workflow_service.duplicate_workflow(
            db, workflow_id, user_id, new_name
        )
        
        if not duplicated:
            raise HTTPException(status_code=404, detail="Workflow not found or not accessible")
        
        logger.info(f"Duplicated workflow {workflow_id} to {duplicated.id} for user {user_id}")
        return WorkflowResponse.model_validate(duplicated)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error duplicating workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to duplicate workflow")


@router.patch("/{workflow_id}/visibility")
async def update_workflow_visibility(
    workflow_id: uuid.UUID,
    visibility_data: WorkflowVisibilityUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep)
):
    """
    Update workflow visibility (public/private).
    """
    try:
        user_id = current_user.id  # Cache user ID
        is_public = visibility_data.is_public
        workflow = await workflow_service.update_workflow_visibility(
            db, workflow_id, user_id, is_public
        )
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
        from app.nodes.triggers.kafka_trigger import kafka_reconciliation_wakeup
        kafka_reconciliation_wakeup.set()
        
        logger.info(f"Updated workflow {workflow_id} visibility to {'public' if is_public else 'private'} and triggered reconciliation")
        return {"message": f"Workflow visibility updated to {'public' if is_public else 'private'}"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating workflow visibility {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update workflow visibility")


@router.get("/stats/")
async def get_workflow_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service_dep)
):
    """
    Get workflow statistics for the current user.
    """
    try:
        user_id = current_user.id  # Cache user ID
        total_count = await workflow_service.count_user_workflows(db, user_id)
        return {
            "total_workflows": total_count,
            "user_id": str(user_id)
        }
    except Exception as e:
        logger.error(f"Error fetching workflow stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch workflow statistics")


# Template endpoints
@router.get("/templates/", response_model=List[WorkflowTemplateResponse])
async def get_workflow_templates(
    db: AsyncSession = Depends(get_db_session),
    template_service: WorkflowTemplateService = Depends(get_workflow_template_service_dep),
    current_user: Optional[User] = Depends(get_optional_user),
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    search: Optional[str] = None
):
    """Get list of workflow templates"""
    try:
        # Sanitize search and category parameters
        sanitized_search = None
        sanitized_category = None
        
        if search:
            if len(search.strip()) == 0:
                sanitized_search = None
            elif len(search) > 200:
                raise HTTPException(status_code=400, detail="Search query too long")
            else:
                import re
                sanitized_search = re.sub(r'[^\w\s\-_]', '', search.strip())
        
        if category:
            if len(category) > 100:
                raise HTTPException(status_code=400, detail="Category name too long")
            import re
            sanitized_category = re.sub(r'[^\w\s\-_]', '', category.strip())
        
        if sanitized_search:
            templates = await template_service.search_templates(
                db, sanitized_search, skip=skip, limit=limit
            )
        elif sanitized_category:
            templates = await template_service.get_templates_by_category(
                db, sanitized_category, skip=skip, limit=limit
            )
        else:
            query = (
                select(WorkflowTemplate)
                .order_by(WorkflowTemplate.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            templates = result.scalars().all()
        
        return [WorkflowTemplateResponse.model_validate(template) for template in templates]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workflow templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch workflow templates")


@router.get("/templates/categories/")
async def get_template_categories(
    db: AsyncSession = Depends(get_db_session),
    template_service: WorkflowTemplateService = Depends(get_workflow_template_service_dep),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get list of template categories"""
    try:
        categories = await template_service.get_categories(db)
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching template categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch template categories")


@router.post("/templates/", response_model=WorkflowTemplateResponse)
async def create_workflow_template(
    template_data: WorkflowTemplateCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new workflow template"""
    try:
        template = WorkflowTemplate(
            name=template_data.name,
            description=template_data.description,
            category=template_data.category,
            flow_data=template_data.flow_data
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        user_id = current_user.id  # Cache user ID  
        logger.info(f"Created workflow template {template.id} by user {user_id}")
        return WorkflowTemplateResponse.model_validate(template)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating workflow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create workflow template")


@router.post("/{workflow_id}/create-template", response_model=WorkflowTemplateResponse)
async def create_template_from_workflow(
    workflow_id: uuid.UUID,
    template_name: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    template_service: WorkflowTemplateService = Depends(get_workflow_template_service_dep),
    template_description: Optional[str] = None,
    category: str = "User Created"
):
    """
    Create a template from an existing workflow.
    """
    try:
        template = await template_service.create_from_workflow(
            db, workflow_id, template_name, template_description, category
        )
        
        if not template:
            raise HTTPException(status_code=404, detail="Workflow not found or not accessible")
        
        logger.info(f"Created template {template.id} from workflow {workflow_id}")
        return WorkflowTemplateResponse.model_validate(template)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating template from workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create template from workflow")


class AdhocExecuteRequest(BaseModel):
    flow_data: Optional[Dict[str, Any]] = None
    input_text: str = "Hello"
    session_id: Optional[str] = None
    chatflow_id: Optional[str] = None  # Yeni eklenen alan
    workflow_id: Optional[str] = None  # Execution kaydı için workflow_id


# Use centralized JSON serialization utility
_make_chunk_serializable = make_json_serializable
@router.get("/dashboard/stats/")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard statistics for the current user for the last 7, 30, and 90 days.
    Returns daily production executions and failed executions for each day in the period.
    """
    user_id = current_user.id
    now = datetime.utcnow()
    today = now.date()
    periods = {
        "7days": 7,
        "30days": 30,
        "90days": 90,
    }
    stats = {}
    for label, days in periods.items():
        since = now - timedelta(days=days)
        # Use COALESCE to fallback to created_at when started_at is NULL
        effective_started_at = sql_func.coalesce(
            WorkflowExecution.started_at, 
            WorkflowExecution.created_at
        )
        # Get all executions for this user and period (include completed_at for runtime)
        executions_q = await db.execute(
            select(
                effective_started_at.label('effective_started_at'),
                WorkflowExecution.completed_at,
                WorkflowExecution.status,
            ).where(
                and_(
                    WorkflowExecution.user_id == user_id,
                    effective_started_at >= since,
                )
            )
        )
        executions = executions_q.all()
        # Build a dict of date -> aggregates
        # Use range(days + 1) to include today in the stats
        day_stats = {}
        for i in range(days + 1):
            day = (since + timedelta(days=i)).date()
            # Don't include future dates
            if day <= today:
                day_stats[day] = {"prodexec": 0, "failedprod": 0, "completed": 0, "runtime_sum": 0.0}
        
        for effective_started_at_val, completed_at, status in executions:
            if effective_started_at_val is None:
                continue  # Safety check for NULL values
            day = effective_started_at_val.date()
            if day in day_stats:
                day_stats[day]["prodexec"] += 1
                if status and status.lower() == "failed":
                    day_stats[day]["failedprod"] += 1
                elif status and status.lower() == "completed":
                    day_stats[day]["completed"] += 1
                    try:
                        if effective_started_at_val and completed_at:
                            delta = (completed_at - effective_started_at_val).total_seconds()
                            if delta and delta > 0:
                                day_stats[day]["runtime_sum"] += float(delta)
                    except Exception:
                        # ignore bad timestamps
                        pass
        # Convert to list for frontend
        stats[label] = [
            {
                "date": day.isoformat(),
                "prodexec": day_stats[day]["prodexec"],
                "failedprod": day_stats[day]["failedprod"],
                "completed": day_stats[day]["completed"],
                # average runtime in milliseconds for completed executions that day
                "avg_runtime_ms": round(
                    (day_stats[day]["runtime_sum"] / day_stats[day]["completed"] * 1000) if day_stats[day]["completed"] > 0 else 0.0,
                    0,
                ),
            }
            for day in sorted(day_stats.keys())
        ]
    return stats

@router.post("/execute")
async def execute_adhoc_workflow(
    req: AdhocExecuteRequest,
    request: Request,
    current_user: User = Depends(get_current_user_or_master_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Execute a workflow directly from flow data and stream the output.
    This is the primary endpoint for running workflows from the frontend.
    """
    # Check if this is an internal webhook call
    is_internal_call = request.headers.get("X-Internal-Call") == "true"
    
    # For internal calls, allow execution without authentication
    if not current_user and not is_internal_call:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    executor = get_workflow_executor()
    chat_service = ChatService(db)
    
    # Handle user for internal calls
    if is_internal_call:
        user = await executor.get_or_create_master_user(db)
        user_id = user.id
    else:
        user = current_user
        user_id = current_user.id

    chatflow_id = uuid.UUID(req.chatflow_id) if req.chatflow_id else None
    
    if req.session_id:
        session_id = req.session_id
    elif chatflow_id:
        session_id = str(chatflow_id)
    else:
        # Check for sticky canvas session (Test mode)
        session_id = executor.get_canvas_session_id(user_id, req.workflow_id or "adhoc")
    
    if not session_id or session_id == 'None' or len(str(session_id).strip()) == 0:
        session_id = str(uuid.uuid4())
        logger.warning(f"Invalid session_id in workflow execution, fallback to: {session_id}")
    
    # Get or create workflow object
    workflow = None
    if req.workflow_id:
        # Fetch workflow from database
        workflow_query = select(Workflow).filter(Workflow.id == uuid.UUID(req.workflow_id))
        workflow_result = await db.execute(workflow_query)
        workflow = workflow_result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {req.workflow_id} not found")
        
        # Check access
        if workflow.user_id != user_id and not workflow.is_public:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Use workflow's flow_data if not provided
        if not req.flow_data:
            req.flow_data = workflow.flow_data
        else:
            class _ExecutionWorkflow:
                """Use request flow_data for this run without persisting to the DB row."""

                __slots__ = ("id", "user_id", "name", "description", "is_public", "version", "error_workflow", "flow_data")

                def __init__(self, original: Workflow, flow_data: Dict[str, Any]):
                    self.id = original.id
                    self.user_id = original.user_id
                    self.name = original.name
                    self.description = original.description
                    self.is_public = original.is_public
                    self.version = getattr(original, "version", 1)
                    self.error_workflow = getattr(original, "error_workflow", None)
                    self.flow_data = flow_data

            workflow = _ExecutionWorkflow(workflow, req.flow_data)
    else:
        # Create temporary workflow object for adhoc execution
        # This allows us to use WorkflowExecutor even without a saved workflow
        if not req.flow_data:
            raise HTTPException(status_code=400, detail="Either flow_data or workflow_id must be provided")
        
        workflow = Workflow(
            id=uuid.uuid4(),
            name="Adhoc Execution",
            description="Temporary workflow for adhoc execution",
            flow_data=req.flow_data,
            user_id=user_id,
            is_public=False
        )
        # Save adhoc workflow to database so we can create execution records
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
    
    # Prepare execution context using WorkflowExecutor
    ctx = await executor.prepare_execution_context(
        db=db,
        workflow=workflow,
        execution_inputs={"input": req.input_text},
        user=user,
        session_id=session_id,
        is_webhook=is_internal_call,
        owner_id=workflow.user_id if req.workflow_id else user_id,
    )
    
    # Create chat message (skip for webhook calls)
    if not is_internal_call:
        try:
            await chat_service.create_chat_message(ChatMessageCreate(
                role="user",
                content=req.input_text,
                chatflow_id=chatflow_id,
                user_id=user_id,
                workflow_id=uuid.UUID(req.workflow_id) if req.workflow_id else None
            ))
        except Exception as e:
            logger.warning(f"Failed to create chat message: {e}")
    
    # Execute workflow - this will handle execution tracking automatically
    try:
        result_stream = await executor.execute_workflow(
            ctx=ctx,
            db=db,
            stream=True,  # Always stream for this endpoint
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to run workflow: {e}")
    
    # Stream the results
    async def event_generator():
        llm_output = ""
        final_outputs = {}
        
        try:
            if not hasattr(result_stream, "__aiter__"):
                raise TypeError("Expected an async iterable from the engine for streaming.")
            
            async for chunk in result_stream:
                if isinstance(chunk, dict):
                    if chunk.get("type") == "token":
                        llm_output += chunk.get("content", "")
                    elif chunk.get("type") == "output":
                        llm_output += chunk.get("output", "")
                    elif chunk.get("type") == "complete":
                        result = chunk.get("result")
                        if isinstance(result, str):
                            llm_output += result
                            final_outputs["output"] = result
                        elif isinstance(result, dict):
                            if "output" in result:
                                llm_output += result["output"]
                            final_outputs.update(result)
                
                # Make chunk serializable before JSON conversion
                try:
                    serialized_chunk = _make_chunk_serializable(chunk)
                    yield f"data: {json.dumps(serialized_chunk, ensure_ascii=False)}\n\n"
                except (TypeError, ValueError) as e:
                    logger.warning(f"Non-serializable chunk: {e}")
                    safe_chunk = {"type": "error", "error": f"Serialization error: {str(e)}", "original_type": type(chunk).__name__}
                    yield f"data: {json.dumps(safe_chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Streaming execution error: {e}", exc_info=True)
            error_data = {"event": "error", "data": str(e)}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        finally:
            # Save LLM output to chat - skip for webhook calls
            if llm_output and not is_internal_call:
                try:
                    await chat_service.create_chat_message(
                        ChatMessageCreate(
                            role="assistant",
                            content=llm_output,
                            chatflow_id=chatflow_id,
                            user_id=user_id,
                            workflow_id=uuid.UUID(req.workflow_id) if req.workflow_id else None
                        )
                    )
                except Exception as chat_error:
                    logger.warning(f"Failed to create assistant chat message: {chat_error}")
                
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Encoding": "utf-8"
        }
    )

@router.get("/queue/status")
async def get_execution_queue_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current execution queue status.
    """
    running_executions = execution_queue.get_running_executions()
    
    # Clean up stale executions
    execution_queue.cleanup_stale_executions()
    
    return {
        "running_executions": running_executions,
        "total_running": len(running_executions)
    }

@router.get("/debug/workflow/{workflow_id}")
async def debug_workflow_status(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Debug endpoint to check workflow and execution status.
    """
    try:
        from app.models.workflow import Workflow
        from app.models.execution import WorkflowExecution
        from sqlalchemy.future import select
        
        # Workflow'ü kontrol et
        workflow_query = select(Workflow).filter(Workflow.id == uuid.UUID(workflow_id))
        workflow_result = await db.execute(workflow_query)
        workflow = workflow_result.scalar_one_or_none()
        
        # Execution'ları kontrol et
        execution_query = select(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == uuid.UUID(workflow_id),
            WorkflowExecution.user_id == current_user.id
        ).order_by(WorkflowExecution.created_at.desc())
        
        execution_result = await db.execute(execution_query)
        executions = execution_result.scalars().all()
        
        return {
            "workflow_exists": workflow is not None,
            "workflow_user_id": str(workflow.user_id) if workflow else None,
            "current_user_id": str(current_user.id),
            "user_has_access": workflow.user_id == current_user.id if workflow else False,
            "executions_count": len(executions),
            "pending_executions": [str(e.id) for e in executions if e.status == "pending"],
            "running_executions": [str(e.id) for e in executions if e.status == "running"],
            "completed_executions": [str(e.id) for e in executions if e.status == "completed"],
            "failed_executions": [str(e.id) for e in executions if e.status == "failed"]
        }
        
    except Exception as e:
        logger.error(f"Debug error: {e}", exc_info=True)
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.post("/{workflow_id}/execute-timer-node")
async def execute_timer_node_manually(
    workflow_id: str,
    node_id: str,
    trigger_data: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    execution_service: ExecutionService = Depends(get_execution_service_dep)
):
    """
    Execute a TimerStartNode manually.
    
    This endpoint allows manual execution of TimerStartNode nodes,
    bypassing their normal scheduling mechanism.
    """
    try:
        from app.models.workflow import Workflow
        from sqlalchemy.future import select
        
        # Get the workflow
        workflow_query = select(Workflow).filter(Workflow.id == uuid.UUID(workflow_id))
        workflow_result = await db.execute(workflow_query)
        workflow = workflow_result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Check user access
        if workflow.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Validate that the node exists and is a TimerStartNode
        flow_data = workflow.flow_data
        nodes = flow_data.get("nodes", [])
        target_node = None
        
        for node in nodes:
            if node.get("id") == node_id and node.get("type") == "TimerStartNode":
                target_node = node
                break
        
        if not target_node:
            raise HTTPException(status_code=404, detail="TimerStartNode not found in workflow")
        
        # Update the node data to indicate manual execution
        node_data = target_node.get("data", {})
        node_data["manual_execution"] = True
        
        # If trigger_data is provided, merge it with existing trigger_data
        if trigger_data:
            existing_trigger_data = node_data.get("trigger_data", {})
            node_data["trigger_data"] = {**existing_trigger_data, **trigger_data}
        
        # Update the flow_data with the modified node
        flow_data["nodes"] = [
            node if node.get("id") != node_id else {**node, "data": node_data}
            for node in nodes
        ]
        
        # Execute the workflow with the modified flow_data
        engine = get_engine()
        chatflow_id = uuid.uuid4()
        session_id = str(chatflow_id)
        user_id = current_user.id
        user_email = current_user.email
        user_context = {
            "session_id": session_id,
            "user_id": str(user_id),
            "owner_id": str(workflow.user_id), # Workflow owner
            "user_email": user_email
        }
        
        # Create execution record
        execution_create = WorkflowExecutionCreate(
            workflow_id=uuid.UUID(workflow_id),
            user_id=user_id,
            status="pending",
            inputs={"input": "Manual TimerStartNode execution", "flow_data": flow_data}
        )
        
        execution = await execution_service.create_execution(db, execution_in=execution_create)
        
        # Update execution to running
        await execution_service.update_execution(
            db,
            execution.id,
            WorkflowExecutionUpdate(status="running", started_at=datetime.utcnow())
        )
        
        # Build and execute the workflow
        engine.build(flow_data=flow_data, user_context=user_context)
        result_stream = await engine.execute(
            inputs={"input": "Manual TimerStartNode execution"},
            stream=True,
            user_context=user_context,
        )
        
        # Process the result to get final output
        final_output = ""
        async for chunk in result_stream:
            if isinstance(chunk, dict):
                if chunk.get("type") == "token":
                    final_output += chunk.get("content", "")
                elif chunk.get("type") == "output":
                    final_output += chunk.get("output", "")
                elif chunk.get("type") == "complete":
                    result = chunk.get("result")
                    if isinstance(result, str):
                        final_output += result
                    elif isinstance(result, dict):
                        if "output" in result:
                            final_output += result["output"]
        
        # Update execution to completed
        await execution_service.update_execution(
            db,
            execution.id,
            WorkflowExecutionUpdate(
                status="completed",
                outputs={"output": final_output},
                completed_at=datetime.utcnow()
            )
        )
        
        logger.info(f"Manual TimerStartNode execution completed for workflow {workflow_id}, node {node_id}")
        
        return {
            "status": "success",
            "message": "TimerStartNode executed successfully",
            "execution_id": str(execution.id),
            "output": final_output
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during manual TimerStartNode execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute TimerStartNode: {str(e)}")


@router.get("/error-trigger/{workflow_id}/stream")
async def stream_error_trigger_execution(workflow_id: str):
    """Stream error-trigger workflow execution events for the canvas UI."""
    from app.services.error_handler_service import error_trigger_subscribers
    
    async def event_stream():
        import asyncio
        import json
        from datetime import datetime, timezone
        from app.core.json_utils import make_json_serializable
        
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        error_trigger_subscribers.setdefault(workflow_id, []).append(queue)
        
        try:
            yield f"data: {json.dumps({'type': 'connected', 'workflow_id': workflow_id, 'timestamp': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"
            
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    serializable_event = make_json_serializable(event)
                    yield f"data: {json.dumps(serializable_event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            subscribers = error_trigger_subscribers.get(workflow_id, [])
            if queue in subscribers:
                subscribers.remove(queue)
                
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )