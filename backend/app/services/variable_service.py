import base64
from app.models.variable import Variable
from app.services.base import BaseService
from app.core.encryption import encrypt_data, decrypt_data
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import Optional, List
from app.schemas.variable import VariableCreate, VariableUpdate, VariableResponse


class VariableService(BaseService[Variable]):
    def __init__(self):
        super().__init__(Variable)
    
    def _encrypt_value(self, value: str) -> str:
        """
        Encrypt a variable value and return as base64 string for database storage. 
        """
        try:
            encrypted_bytes = encrypt_data(value)
            return base64.b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to encrypt value: {e}")
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """
        Decrypt a base64 encoded encrypted value from database.
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
            decrypted_data = decrypt_data(encrypted_bytes)
            # If decrypted_data is a dict with 'value' key, return that
            if isinstance(decrypted_data, dict) and 'value' in decrypted_data:
                return decrypted_data['value']
            # Otherwise, convert dict to string or return as-is
            return str(decrypted_data) if isinstance(decrypted_data, dict) else decrypted_data
        except Exception as e:
            raise ValueError(f"Failed to decrypt value: {e}")
    
    def _read_value(self, variable: Variable) -> str:
        try:
            return self._decrypt_value(variable.value)
        except ValueError:
            # Older installations may contain values written before encryption.
            return variable.value

    def to_response(self, variable: Variable) -> VariableResponse:
        # Keep the mapped ORM object encrypted; mutating it can flush plaintext.
        return VariableResponse.model_validate(variable).model_copy(
            update={"value": self._read_value(variable)}
        )

    async def get_for_user(self, db: AsyncSession, id, user_id) -> Optional[Variable]:
        result = await db.execute(
            select(self.model).filter_by(id=id, user_id=user_id)
        )
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, *, user_id, skip: int = 0, limit: int = 100) -> List[Variable]:
        result = await db.execute(
            select(self.model)
            .filter_by(user_id=user_id)
            .order_by(self.model.name, self.model.workflow_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_name_and_user(self, db: AsyncSession, name: str, user_id, workflow_id=None) -> Optional[Variable]:
        """
        Get a variable by its name and user ID.
        """
        result = await db.execute(
            select(self.model).filter_by(name=name, user_id=user_id, workflow_id=workflow_id)
        )
        variable = result.scalars().first()
        return variable

    async def get_by_type(self, db: AsyncSession, type: str, user_id) -> List[Variable]:
        """
        Get all variables by their type.
        """
        result = await db.execute(
            select(self.model).filter_by(type=type, user_id=user_id)
        )
        variables = result.scalars().all()
        return variables

    async def get_runtime_values(self, db: AsyncSession, user_id, workflow_id=None) -> dict[str, str]:
        """Snapshot globals and workflow variables; workflow values override globals."""
        scope_filter = (
            or_(self.model.workflow_id.is_(None), self.model.workflow_id == workflow_id)
            if workflow_id is not None else self.model.workflow_id.is_(None)
        )
        result = await db.execute(
            select(self.model).where(self.model.user_id == user_id, scope_filter)
        )
        variables = list(result.scalars())
        return {
            variable.name: self._read_value(variable)
            for variable in sorted(variables, key=lambda item: item.workflow_id is not None)
        }

    async def create_variable(self, db: AsyncSession, variable_data: VariableCreate, user_id) -> Variable:
        """
        Create a new variable with encrypted value.
        """
        encrypted_value = self._encrypt_value(variable_data.value)
        
        db_variable = Variable(
            name=variable_data.name,
            value=encrypted_value,
            type=variable_data.type,
            user_id=user_id,
            workflow_id=variable_data.workflow_id,
        )
        db.add(db_variable)
        await db.commit()
        await db.refresh(db_variable)
        
        return db_variable

    async def update_variable(self, db: AsyncSession, variable: Variable, update_data: VariableUpdate) -> Variable:
        """
        Update variable details with encryption for value updates.
        """
        if update_data.name is not None:
            variable.name = update_data.name
        if update_data.value is not None:
            variable.value = self._encrypt_value(update_data.value)
        if update_data.type is not None:
            variable.type = update_data.type
        if "workflow_id" in update_data.model_fields_set:
            variable.workflow_id = update_data.workflow_id
        
        db.add(variable)
        await db.commit()
        await db.refresh(variable)
        
        return variable

    async def delete_by_name(self, db: AsyncSession, name: str, user_id, workflow_id=None) -> Optional[Variable]:
        """
        Delete a variable by name.
        """
        variable = await self.get_by_name_and_user(db, name, user_id, workflow_id)
        if variable:
            await db.delete(variable)
            await db.commit()
        return variable
