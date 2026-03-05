"""Workflow Executions API endpoints"""

import csv
import io
import json
import uuid
from typing import List, Any, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.dependencies import get_current_user
from app.core.database import get_db_session
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.execution import (
    WorkflowExecutionCreate,
    WorkflowExecutionResponse,
)
from app.services.execution_service import ExecutionService

router = APIRouter()


@router.get("/export/csv")
async def export_executions_csv(
    status_filter: Optional[str] = None,
    workflow_id: Optional[uuid.UUID] = None,
    date_range: Optional[str] = None,
    execution_ids: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    execution_service: ExecutionService = Depends(),
):

    if execution_ids:
        # Checkbox selection — fetch only selected executions
        ids = [uuid.UUID(eid.strip()) for eid in execution_ids.split(",") if eid.strip()]
        executions = []
        for eid in ids:
            execution = await execution_service.get_execution(
                db, execution_id=eid, user_id=current_user.id
            )
            if execution:
                executions.append(execution)
    else:
        # No checkbox selection — use filters (same as list_executions page)
        if workflow_id:
            executions = await execution_service.get_workflow_executions(
                db, workflow_id=workflow_id, user_id=current_user.id,
                skip=0, limit=10000,
            )
        else:
            executions = await execution_service.get_all_user_executions(
                db, user_id=current_user.id,
                skip=0, limit=10000,
            )

    # Apply status filter (same logic as frontend does client-side)
    if status_filter:
        executions = [e for e in executions if e.status == status_filter]

    # Apply date_range filter
    if date_range:
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if date_range == "today":
            cutoff = today
        elif date_range == "week":
            cutoff = today - timedelta(days=7)
        elif date_range == "month":
            cutoff = today - timedelta(days=30)
        else:
            cutoff = None
        if cutoff:
            executions = [
                e for e in executions
                if e.started_at and e.started_at >= cutoff
            ]

    # Build workflow name lookup dict (single query)
    wf_ids = list({e.workflow_id for e in executions})
    workflow_names = {}
    if wf_ids:
        wf_query = select(Workflow.id, Workflow.name).filter(Workflow.id.in_(wf_ids))
        wf_result = await db.execute(wf_query)
        workflow_names = {row.id: row.name for row in wf_result.all()}

    # Build CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Workflow", "Status", "Started", "Duration", "Input", "Output"])

    for execution in executions:
        wf_name = workflow_names.get(execution.workflow_id, "-")

        started = (
            execution.started_at.strftime("%d.%m.%Y %H:%M")
            if execution.started_at
            else "-"
        )

        if execution.started_at and execution.completed_at:
            delta = execution.completed_at - execution.started_at
            total_seconds = delta.total_seconds()
            if total_seconds < 60:
                duration = f"{total_seconds:.2f} s"
            elif total_seconds < 3600:
                minutes = int(total_seconds // 60)
                seconds = total_seconds % 60
                duration = f"{minutes} m {seconds:.0f} s"
            else:
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                duration = f"{hours} h {minutes} m"
        else:
            duration = "-"

        input_text = json.dumps(execution.inputs, ensure_ascii=False) if execution.inputs else "-"
        output_text = json.dumps(execution.outputs, ensure_ascii=False) if execution.outputs else "-"

        writer.writerow([
            wf_name,
            execution.status or "-",
            started,
            duration,
            input_text,
            output_text,
        ])

    # Build dynamic filename — only include active filters
    name_parts = ["KAI-Flow_Executions"]
    if workflow_id and workflow_names:
        wf_file_name = workflow_names.get(workflow_id, "")
        if wf_file_name:
            name_parts.append(wf_file_name.replace(" ", ""))
    if status_filter:
        name_parts.append(status_filter.capitalize())
    name_parts.append(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    filename = "_".join(name_parts) + ".csv"

    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_execution(
    workflow_id: uuid.UUID,
    inputs: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    execution_service: ExecutionService = Depends(),
):
    """
    Trigger a new workflow execution.
    """
    execution_in = WorkflowExecutionCreate(
        workflow_id=workflow_id, user_id=current_user.id, inputs=inputs
    )
    execution = await execution_service.create_execution(db, execution_in=execution_in)
    # Here you would typically trigger an async task to run the workflow
    # from app.tasks.workflow_tasks import run_workflow
    # run_workflow.delay(execution.id)
    return execution


@router.get("", response_model=List[WorkflowExecutionResponse])
async def list_executions(
    workflow_id: uuid.UUID = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    execution_service: ExecutionService = Depends(),
    skip: int = 0,
    limit: int = 100,
):
    """
    List executions. If workflow_id is provided, list executions for that workflow only.
    If workflow_id is not provided, list all executions for the current user.
    """
    if workflow_id:
        executions = await execution_service.get_workflow_executions(
            db, workflow_id=workflow_id, user_id=current_user.id, skip=skip, limit=limit
        )
    else:
        executions = await execution_service.get_all_user_executions(
            db, user_id=current_user.id, skip=skip, limit=limit
        )
    return executions


@router.get("/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    execution_service: ExecutionService = Depends(),
):
    """
    Get a specific workflow execution by its ID.
    """
    execution = await execution_service.get_execution(
        db, execution_id=execution_id, user_id=current_user.id
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found"
        )
    return execution


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    execution_service: ExecutionService = Depends(),
):
    """
    Delete a specific workflow execution by its ID.
    """
    execution = await execution_service.get_execution(
        db, execution_id=execution_id, user_id=current_user.id
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found"
        )
    
    await execution_service.delete_execution(db, execution_id=execution_id, user_id=current_user.id)
    return None