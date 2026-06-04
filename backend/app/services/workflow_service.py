
from app.models.workflow import Workflow, WorkflowTemplate
from app.models.user import User
from app.services.base import BaseService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import desc, or_, and_, func
from typing import Optional, List
import uuid


class WorkflowService(BaseService[Workflow]):
    def __init__(self):
        super().__init__(Workflow)

    async def get_by_id(
        self, db: AsyncSession, workflow_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Workflow]:
        """
        Get a workflow by its ID.
        If user_id is provided, it also filters by user.
        """
        query = select(self.model).filter_by(id=workflow_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        result = await db.execute(query)
        return result.scalars().first()

    async def get_user_workflows(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> List[Workflow]:
        """
        Get all workflows for a specific user with optional search.
        """
        query = select(self.model).filter_by(user_id=user_id)
        
        # Add search filter if provided
        if search:
            search_filter = or_(
                self.model.name.icontains(search),
                self.model.description.icontains(search)
            )
            query = query.filter(search_filter)
        
        query = query.order_by(desc(self.model.updated_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    async def get_public_workflows(
        self, 
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> List[Workflow]:
        """
        Get all public workflows with optional search, including user information.
        """
        query = select(self.model).options(selectinload(self.model.user)).filter_by(is_public=True)
        
        # Add search filter if provided
        if search:
            search_filter = or_(
                self.model.name.icontains(search),
                self.model.description.icontains(search)
            )
            query = query.filter(search_filter)
        
        query = query.order_by(desc(self.model.updated_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    async def get_accessible_workflow(
        self, db: AsyncSession, workflow_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Workflow]:
        """
        Get a workflow that the user can access (owns or is public).
        """
        if user_id:
            # User can access their own workflows or public ones
            query = select(self.model).filter(
                and_(
                    self.model.id == workflow_id,
                    or_(
                        self.model.user_id == user_id,
                        self.model.is_public == True
                    )
                )
            )
        else:
            # Non-authenticated users can only access public workflows
            query = select(self.model).filter(
                and_(
                    self.model.id == workflow_id,
                    self.model.is_public == True
                )
            )
        
        result = await db.execute(query)
        return result.scalars().first()

    async def count_user_workflows(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Count the total number of workflows for a user.
        """
        query = select(func.count(self.model.id)).filter_by(user_id=user_id)
        result = await db.execute(query)
        return result.scalar() or 0

    async def duplicate_workflow(
        self, 
        db: AsyncSession, 
        source_workflow_id: uuid.UUID, 
        target_user_id: uuid.UUID,
        new_name: Optional[str] = None
    ) -> Optional[Workflow]:
        """
        Duplicate a workflow for a user.
        """
        # Get the source workflow
        source = await self.get_accessible_workflow(db, source_workflow_id, target_user_id)
        if not source:
            return None
        
        # Create a new workflow with copied data
        new_workflow = Workflow(
            user_id=target_user_id,
            name=new_name or f"{source.name} (Copy)",
            description=source.description,
            is_public=False,  # Copies are private by default
            error_workflow=getattr(source, "error_workflow", None),
            flow_data=source.flow_data,
            version=1  # Reset version for the copy
        )
        
        db.add(new_workflow)
        await db.commit()
        await db.refresh(new_workflow)
        
        return new_workflow

    async def update_workflow_visibility(
        self, 
        db: AsyncSession, 
        workflow_id: uuid.UUID, 
        user_id: uuid.UUID, 
        is_public: bool
    ) -> Optional[Workflow]:
        """
        Update the visibility (public/private) of a workflow.
        Only the owner can change visibility.
        """
        workflow = await self.get_by_id(db, workflow_id, user_id)
        if not workflow:
            return None
        
        workflow.is_public = is_public
        await db.commit()
        await db.refresh(workflow)
        
        return workflow


class WorkflowTemplateService(BaseService[WorkflowTemplate]):
    def __init__(self):
        super().__init__(WorkflowTemplate)

    async def get_templates_by_category(
        self, 
        db: AsyncSession, 
        category: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[WorkflowTemplate]:
        """
        Get workflow templates by category.
        """
        query = (
            select(self.model)
            .filter_by(category=category)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(query)
        return result.scalars().all()

    async def search_templates(
        self, 
        db: AsyncSession, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[WorkflowTemplate]:
        """
        Search workflow templates by name or description.
        """
        search_filter = or_(
            self.model.name.icontains(search_term),
            self.model.description.icontains(search_term)
        )
        
        query = (
            select(self.model)
            .filter(search_filter)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(query)
        return result.scalars().all()

    async def get_categories(self, db: AsyncSession) -> List[str]:
        """
        Get all unique template categories.
        """
        query = select(self.model.category).distinct()
        result = await db.execute(query)
        return [category for category in result.scalars().all() if category]

    async def create_from_workflow(
        self, 
        db: AsyncSession, 
        workflow_id: uuid.UUID, 
        template_name: str,
        template_description: Optional[str] = None,
        category: str = 'User Created'
    ) -> Optional[WorkflowTemplate]:
        """
        Create a template from an existing workflow.
        """
        # Get the workflow (must be public or accessible)
        workflow_service = WorkflowService()
        workflow = await workflow_service.get_accessible_workflow(db, workflow_id)
        
        if not workflow:
            return None
        
        # Create template
        template = WorkflowTemplate(
            name=template_name,
            description=template_description or workflow.description,
            category=category,
            flow_data=workflow.flow_data
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        return template 