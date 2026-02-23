"""Dependency Injection for Service Layer.

Provides service factory functions and dependency injection patterns
for the Agent-Flow V2 service layer.
"""

from functools import lru_cache
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session, get_db
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService, WorkflowTemplateService
from app.services.execution_service import ExecutionService
from app.services.credential_service import CredentialService
from app.services.api_key_service import APIKeyService
from app.services.variable_service import VariableService
from app.services.chat_service import ChatService
from app.services.scheduled_job_service import ScheduledJobService
from app.services.webhook_service import WebhookService


@lru_cache
def get_user_service_dep() -> UserService:
    return UserService()

@lru_cache
def get_workflow_service_dep() -> WorkflowService:
    return WorkflowService()

@lru_cache
def get_workflow_template_service_dep() -> WorkflowTemplateService:
    return WorkflowTemplateService()

@lru_cache
def get_execution_service_dep() -> ExecutionService:
    return ExecutionService()

@lru_cache
def get_credential_service_dep() -> CredentialService:
    return CredentialService()


@lru_cache
def get_api_key_service() -> APIKeyService:
    return APIKeyService()

@lru_cache
def get_variable_service_dep() -> VariableService:
    return VariableService()

async def get_scheduled_job_service_dep(db: AsyncSession = Depends(get_db_session)) -> ScheduledJobService:
    return ScheduledJobService(db)
@lru_cache
def get_webhook_service_dep() -> WebhookService:
    return WebhookService()

# ChatService requires db at initialization, so we create it inline in the endpoint 