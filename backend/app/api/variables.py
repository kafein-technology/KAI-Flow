import uuid
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.variable import (
    VariableCreate,
    VariableUpdate,
    VariableResponse
)
from app.services.variable_service import VariableService
from app.services.dependencies import get_variable_service_dep

logger = logging.getLogger(__name__)
router = APIRouter()


async def ensure_workflow_access(db: AsyncSession, workflow_id: uuid.UUID | None, user_id: uuid.UUID) -> None:
    if workflow_id is None:
        return
    result = await db.execute(
        select(Workflow.id).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Workflow not found")


@router.get("", response_model=List[VariableResponse])
async def get_variables(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep),
    skip: int = 0,
    limit: int = 1000
):
    """
    Get list of all variables for the current user.
    """
    try:
        variables = await variable_service.get_all(db, skip=skip, limit=limit, user_id=current_user.id)
        return [variable_service.to_response(variable) for variable in variables]
    except Exception as e:
        logger.error(f"Error fetching variables: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{variable_id}", response_model=VariableResponse)
async def get_variable(
    variable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Get a specific variable by ID.
    """
    try:
        variable = await variable_service.get_for_user(db, variable_id, current_user.id)
        if not variable:
            raise HTTPException(status_code=404, detail="Variable not found")
        return variable_service.to_response(variable)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching variable {variable_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/name/{variable_name}", response_model=VariableResponse)
async def get_variable_by_name(
    variable_name: str,
    workflow_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Get a specific variable by name.
    """
    try:
        variable = await variable_service.get_by_name_and_user(db, variable_name, current_user.id, workflow_id)
        if not variable:
            raise HTTPException(status_code=404, detail="Variable not found")
        return variable_service.to_response(variable)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching variable {variable_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/type/{variable_type}", response_model=List[VariableResponse])
async def get_variables_by_type(
    variable_type: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Get all variables by type.
    """
    try:
        variables = await variable_service.get_by_type(db, variable_type, current_user.id)
        return [variable_service.to_response(variable) for variable in variables]
    except Exception as e:
        logger.error(f"Error fetching variables by type {variable_type}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=VariableResponse)
async def create_variable(
    variable_data: VariableCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Create a new variable.
    """
    try:
        await ensure_workflow_access(db, variable_data.workflow_id, current_user.id)
        # Check if variable with same name already exists for this user
        existing_variable = await variable_service.get_by_name_and_user(
            db, variable_data.name, current_user.id, variable_data.workflow_id
        )
        if existing_variable:
            raise HTTPException(
                status_code=400, 
                detail=f"Variable with name '{variable_data.name}' already exists"
            )
        
        variable = await variable_service.create_variable(db, variable_data, current_user.id)
        return variable_service.to_response(variable)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating variable: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{variable_id}", response_model=VariableResponse)
async def update_variable(
    variable_id: uuid.UUID,
    variable_data: VariableUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Update a variable.
    """
    try:
        variable = await variable_service.get_for_user(db, variable_id, current_user.id)
        if not variable:
            raise HTTPException(status_code=404, detail="Variable not found")
        
        target_scope = variable_data.workflow_id if "workflow_id" in variable_data.model_fields_set else variable.workflow_id
        await ensure_workflow_access(db, target_scope, current_user.id)
        target_name = variable_data.name if variable_data.name is not None else variable.name
        if target_name != variable.name or target_scope != variable.workflow_id:
            existing_variable = await variable_service.get_by_name_and_user(
                db, target_name, current_user.id, target_scope
            )
            if existing_variable:
                raise HTTPException(
                    status_code=400,
                    detail=f"Variable with name '{target_name}' already exists in this scope"
                )
        
        updated_variable = await variable_service.update_variable(db, variable, variable_data)
        return variable_service.to_response(updated_variable)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating variable {variable_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{variable_id}")
async def delete_variable(
    variable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Delete a variable.
    """
    try:
        variable = await variable_service.get_for_user(db, variable_id, current_user.id)
        if not variable:
            raise HTTPException(status_code=404, detail="Variable not found")
        
        await db.delete(variable)
        await db.commit()
        return {"message": "Variable deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting variable {variable_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/name/{variable_name}")
async def delete_variable_by_name(
    variable_name: str,
    workflow_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    variable_service: VariableService = Depends(get_variable_service_dep)
):
    """
    Delete a variable by name.
    """
    try:
        variable = await variable_service.delete_by_name(db, variable_name, current_user.id, workflow_id)
        if not variable:
            raise HTTPException(status_code=404, detail="Variable not found")
        
        return {"message": f"Variable '{variable_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting variable {variable_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
