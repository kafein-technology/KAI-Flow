import uuid
import base64
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import text, bindparam, or_
from app.models.user_credential import UserCredential
from app.models.workflow import Workflow
from app.services.base import BaseService
from app.schemas.user_credential import (
    UserCredentialCreate,
    UserCredentialUpdate,
    CredentialWorkflowUsageResponse,
    CredentialWorkflowUsageItem,
    CredentialWorkflowNodeUsage,
)
from app.core.encryption import encrypt_data, decrypt_data
from app.core.credential_fields import (
    CREDENTIAL_FIELD_NAMES,
    find_credential_usages_in_flow_data,
)


class CredentialService(BaseService[UserCredential]):
    def __init__(self):
        super().__init__(UserCredential)

    async def get_by_user_id(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> List[UserCredential]:
        """
        Get all credentials for a specific user.
        """
        query = select(self.model).filter_by(user_id=user_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_user_id_and_name(
        self, db: AsyncSession, user_id: uuid.UUID, name: str
    ) -> List[UserCredential]:
        """
        Get credentials for a specific user filtered by name.
        """
        query = select(self.model).filter_by(user_id=user_id, name=name)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_user_and_id(
        self, db: AsyncSession, user_id: uuid.UUID, credential_id: uuid.UUID
    ) -> Optional[UserCredential]:
        """
        Get a specific credential by user and credential ID.
        """
        query = select(self.model).filter_by(user_id=user_id, id=credential_id)
        result = await db.execute(query)
        return result.scalars().first()

    async def create_credential(
        self, db: AsyncSession, user_id: uuid.UUID, credential_data: UserCredentialCreate
    ) -> UserCredential:
        """
        Create a new credential for a user.
        """
        # Encrypt the secret data
        encrypted_bytes = encrypt_data(credential_data.secret)
        # Convert bytes to base64 string for database storage
        encrypted_secret = base64.b64encode(encrypted_bytes).decode('utf-8')
        
        # Create the credential object
        credential = UserCredential(
            id=uuid.uuid4(),
            user_id=user_id,
            name=credential_data.name,
            service_type=credential_data.service_type,
            encrypted_secret=encrypted_secret
        )
        
        db.add(credential)
        await db.commit()
        await db.refresh(credential)
        return credential

    async def update_credential(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        credential_id: uuid.UUID,
        update_data: UserCredentialUpdate
    ) -> Optional[UserCredential]:
        """
        Update an existing credential.
        """
        # Get the credential
        credential = await self.get_by_user_and_id(db, user_id, credential_id)
        if not credential:
            return None
        
        # Update fields
        if update_data.name is not None:
            credential.name = update_data.name
        
        await db.commit()
        await db.refresh(credential)
        return credential

    async def delete_credential(
        self, db: AsyncSession, user_id: uuid.UUID, credential_id: uuid.UUID
    ) -> bool:
        """
        Delete a credential.
        """
        credential = await self.get_by_user_and_id(db, user_id, credential_id)
        if not credential:
            return False
        
        await db.delete(credential)
        await db.commit()
        return True

    async def get_decrypted_credential(
        self, db: AsyncSession, user_id: uuid.UUID, credential_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get a credential with decrypted secret data.
        """
        credential = await self.get_by_user_and_id(db, user_id, credential_id)
        if not credential:
            return None
        try:
            # Convert base64 string back to bytes for decryption
            encrypted_bytes = base64.b64decode(credential.encrypted_secret.encode('utf-8'))
            decrypted_secret = decrypt_data(encrypted_bytes)
            return {
                "id": credential.id,
                "name": credential.name,
                "service_type": credential.service_type,
                "secret": decrypted_secret if decrypted_secret is not None else {},
                "created_at": credential.created_at,
                "updated_at": credential.updated_at
            }
        except Exception:
            # Return credential with empty secret if decryption fails
            return {
                "id": credential.id,
                "name": credential.name,
                "service_type": credential.service_type,
                "secret": {},
                "created_at": credential.created_at,
                "updated_at": credential.updated_at
            }

    async def get_workflows_using_credential(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
    ) -> Optional[CredentialWorkflowUsageResponse]:
        """
        Find workflows owned by the user that reference the credential in node data.
        Uses a JSONB filter in PostgreSQL, then scans only matched workflows in Python.
        """
        credential = await self.get_by_user_and_id(db, user_id, credential_id)
        if not credential:
            return None

        cred_id_str = str(credential_id)
        containment_conditions = [
            Workflow.flow_data.contains({"nodes": [{"data": {field: cred_id_str}}]})
            for field in CREDENTIAL_FIELD_NAMES
        ]

        stmt = (
            select(
                Workflow.id,
                Workflow.name,
                Workflow.updated_at,
                Workflow.flow_data,
            )
            .where(
                Workflow.user_id == user_id,
                or_(*containment_conditions),
            )
            .order_by(Workflow.updated_at.desc())
        )

        result = await db.execute(stmt)
        rows = result.all()

        workflows: List[CredentialWorkflowUsageItem] = []
        for row in rows:
            using_nodes_raw = find_credential_usages_in_flow_data(row.flow_data, cred_id_str)
            if not using_nodes_raw:
                continue

            using_nodes = [
                CredentialWorkflowNodeUsage(
                    node_id=usage["node_id"],
                    node_type=usage["node_type"],
                    field=usage["field"],
                )
                for usage in using_nodes_raw
            ]
            workflows.append(
                CredentialWorkflowUsageItem(
                    id=row.id,
                    name=row.name,
                    updated_at=row.updated_at,
                    using_nodes=using_nodes,
                )
            )

        return CredentialWorkflowUsageResponse(
            credential_id=credential_id,
            workflow_count=len(workflows),
            workflows=workflows,
        ) 