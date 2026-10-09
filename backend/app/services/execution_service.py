import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.execution import WorkflowExecution
from app.models.workflow import Workflow
from app.services.base import BaseService
from app.schemas.execution import WorkflowExecutionCreate, WorkflowExecutionUpdate


class ExecutionService(BaseService[WorkflowExecution]):
    def __init__(self):
        super().__init__(WorkflowExecution)

    def _history_filters(
        self,
        user_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID] = None,
        status_filter: Optional[str] = None,
        started_after: Optional[datetime] = None,
        search: Optional[str] = None,
    ):
        filters = [self.model.user_id == user_id]
        if workflow_id:
            filters.append(self.model.workflow_id == workflow_id)
        if status_filter:
            filters.append(self.model.status == status_filter)
        if started_after:
            filters.append(self.model.started_at >= started_after)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            filters.append(or_(
                Workflow.name.ilike(pattern, escape="\\"),
                cast(self.model.inputs, Text).ilike(pattern, escape="\\"),
                cast(self.model.id, Text).ilike(pattern, escape="\\"),
            ))
        return filters

    async def get_execution_page(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int,
        page_size: int = 10,
        workflow_id: Optional[uuid.UUID] = None,
        status_filter: Optional[str] = None,
        started_after: Optional[datetime] = None,
        search: Optional[str] = None,
        include_total: bool = True,
    ):
        filters = self._history_filters(user_id, workflow_id, status_filter, started_after, search)
        query = (
            select(
                self.model.id,
                self.model.workflow_id,
                Workflow.name.label("workflow_name"),
                self.model.status,
                self.model.started_at,
                self.model.completed_at,
                self.model.created_at,
                self.model.inputs.is_not(None).label("has_inputs"),
                self.model.outputs.is_not(None).label("has_outputs"),
            )
            .join(Workflow, Workflow.id == self.model.workflow_id)
            .where(*filters)
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        items = [dict(row._mapping) for row in result.all()]

        total = None
        if include_total:
            count_query = (
                select(func.count())
                .select_from(self.model)
                .join(Workflow, Workflow.id == self.model.workflow_id)
                .where(*filters)
            )
            total = (await db.execute(count_query)).scalar_one()
        return items, total

    async def get_filtered_executions_for_export(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID] = None,
        status_filter: Optional[str] = None,
        started_after: Optional[datetime] = None,
        search: Optional[str] = None,
        limit: int = 10000,
    ) -> List[WorkflowExecution]:
        filters = self._history_filters(user_id, workflow_id, status_filter, started_after, search)
        query = (
            select(self.model)
            .join(Workflow, Workflow.id == self.model.workflow_id)
            .where(*filters)
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def create_execution(
        self,
        db: AsyncSession,
        *,
        execution_in: WorkflowExecutionCreate,
    ) -> WorkflowExecution:
        """
        Create a new workflow execution.
        """
        execution = await self.create(db, obj_in=execution_in)
        return execution

    async def get_workflow_executions(
        self,
        db: AsyncSession,
        workflow_id: uuid.UUID,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowExecution]:
        """
        Get all executions for a specific workflow.
        """
        query = (
            select(self.model)
            .filter_by(workflow_id=workflow_id, user_id=user_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_all_user_executions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowExecution]:
        """
        Get all executions for a user across all workflows.
        """
        query = (
            select(self.model)
            .filter_by(user_id=user_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def update_execution(
        self,
        db: AsyncSession,
        execution_id: uuid.UUID,
        execution_in: WorkflowExecutionUpdate,
    ) -> WorkflowExecution:
        """
        Update a workflow execution.
        """
        execution = await self.get(db, execution_id)
        if not execution:
            raise Exception("Execution not found") # Replace with a proper HTTPException

        execution = await self.update(db, db_obj=execution, obj_in=execution_in)
        return execution

    async def get_execution(
        self,
        db: AsyncSession,
        execution_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkflowExecution:
        """
        Get a specific execution by ID.
        """
        query = (
            select(self.model)
            .filter_by(id=execution_id, user_id=user_id)
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def delete_execution(
        self,
        db: AsyncSession,
        execution_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Delete a specific execution by ID.
        """
        execution = await self.get_execution(db, execution_id=execution_id, user_id=user_id)
        if not execution:
            return False
        
        await self.remove(db, id=execution_id)
        return True
