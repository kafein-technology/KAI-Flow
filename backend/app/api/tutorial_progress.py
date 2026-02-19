import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.tutorial_progress_service import TutorialProgressService
from app.services.dependencies import get_tutorial_progress_service_dep

logger = logging.getLogger(__name__)
router = APIRouter()


class TutorialProgressUpdate(BaseModel):
    current_step: int
    completed_steps: list[str]


class TutorialProgressResponse(BaseModel):
    tutorial_id: str
    current_step: int
    completed_steps: list[str]

    class Config:
        from_attributes = True


@router.get("", response_model=List[TutorialProgressResponse])
async def get_all_progress(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    service: TutorialProgressService = Depends(get_tutorial_progress_service_dep),
):
    try:
        results = await service.get_by_user(db, current_user.id)
        return [
            TutorialProgressResponse(
                tutorial_id=r.tutorial_id,
                current_step=r.current_step,
                completed_steps=r.completed_steps or [],
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error fetching tutorial progress: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{tutorial_id}", response_model=TutorialProgressResponse)
async def get_progress(
    tutorial_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    service: TutorialProgressService = Depends(get_tutorial_progress_service_dep),
):
    try:
        progress = await service.get_by_user_and_tutorial(db, current_user.id, tutorial_id)
        if not progress:
            raise HTTPException(status_code=404, detail="Progress not found")
        return TutorialProgressResponse(
            tutorial_id=progress.tutorial_id,
            current_step=progress.current_step,
            completed_steps=progress.completed_steps or [],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tutorial progress for {tutorial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{tutorial_id}", response_model=TutorialProgressResponse)
async def save_progress(
    tutorial_id: str,
    data: TutorialProgressUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    service: TutorialProgressService = Depends(get_tutorial_progress_service_dep),
):
    try:
        progress = await service.upsert_progress(
            db, current_user.id, tutorial_id, data.current_step, data.completed_steps
        )
        return TutorialProgressResponse(
            tutorial_id=progress.tutorial_id,
            current_step=progress.current_step,
            completed_steps=progress.completed_steps or [],
        )
    except Exception as e:
        logger.error(f"Error saving tutorial progress for {tutorial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{tutorial_id}")
async def delete_progress(
    tutorial_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    service: TutorialProgressService = Depends(get_tutorial_progress_service_dep),
):
    try:
        progress = await service.delete_by_user_and_tutorial(db, current_user.id, tutorial_id)
        if not progress:
            raise HTTPException(status_code=404, detail="Progress not found")
        return {"message": "Progress deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tutorial progress for {tutorial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
