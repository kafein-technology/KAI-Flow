from app.models.user import User
from app.services.base import BaseService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from app.schemas.auth import UserSignUpData, UserUpdateProfile
from app.core.security import get_password_hash, verify_password
from datetime import datetime, timezone


class UserService(BaseService[User]):
    def __init__(self):
        super().__init__(User)

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """
        Get a user by their email address.
        """
        result = await db.execute(select(self.model).filter_by(email=email))
        return result.scalars().first()

    async def authenticate_user(self, db: AsyncSession, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.
        """
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        
        # Update last_login timestamp
        user.last_login = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user

    async def update_user(self, db: AsyncSession, user: User, update_data: UserUpdateProfile) -> User:
        """
        Update user details.
        """
        if update_data.full_name is not None:
            user.full_name = update_data.full_name
        if update_data.password is not None:
            user.password_hash = get_password_hash(update_data.password)
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def create_user(self, db: AsyncSession, user_data: UserSignUpData) -> User:
        """
        Create a new user.
        """
        hashed_password = get_password_hash(user_data.credential)
        db_user = User(
            email=user_data.email,
            full_name=user_data.name,
            password_hash=hashed_password,
            temp_token=user_data.tempToken,
            status="active"  # or whatever default status you want
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user 