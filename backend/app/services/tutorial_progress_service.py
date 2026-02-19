from app.models.tutorial_progress import TutorialProgress
from app.services.base import BaseService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List


class TutorialProgressService(BaseService[TutorialProgress]):
    def __init__(self):
        super().__init__(TutorialProgress)

    async def get_by_user(self, db: AsyncSession, user_id) -> List[TutorialProgress]:
        result = await db.execute(
            select(self.model).filter_by(user_id=user_id).order_by(self.model.updated_at.desc())
        )
        return result.scalars().all()

    async def get_by_user_and_tutorial(self, db: AsyncSession, user_id, tutorial_id: str) -> Optional[TutorialProgress]:
        result = await db.execute(
            select(self.model).filter_by(user_id=user_id, tutorial_id=tutorial_id)
        )
        return result.scalars().first()

    async def upsert_progress(self, db: AsyncSession, user_id, tutorial_id: str, current_step: int, completed_steps: list) -> TutorialProgress:
        existing = await self.get_by_user_and_tutorial(db, user_id, tutorial_id)

        if existing:
            existing.current_step = current_step
            existing.completed_steps = completed_steps
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

        progress = TutorialProgress(
            user_id=user_id,
            tutorial_id=tutorial_id,
            current_step=current_step,
            completed_steps=completed_steps,
        )
        db.add(progress)
        await db.commit()
        await db.refresh(progress)
        return progress

    async def delete_by_user_and_tutorial(self, db: AsyncSession, user_id, tutorial_id: str) -> Optional[TutorialProgress]:
        progress = await self.get_by_user_and_tutorial(db, user_id, tutorial_id)
        if progress:
            await db.delete(progress)
            await db.commit()
        return progress
