from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional

from app.schemas.chat import ChatMessageResponse, ChatMessageUpdate, ChatMessageInput
from app.services.chat_service import ChatService
from app.services.memory.service import memory_service
from app.core.database import get_db_session, get_db
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("", response_model=Dict[UUID, List[ChatMessageResponse]])
async def get_all_chats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all chat conversations for the current user, grouped by their chatflow_id.
    """
    service = ChatService(db)
    return await service.get_all_chats_grouped_by_user(current_user.id)

@router.get("/workflow/{workflow_id}", response_model=Dict[UUID, List[ChatMessageResponse]])
async def get_workflow_chats(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all chat conversations for a specific workflow, grouped by their chatflow_id.
    """
    service = ChatService(db)
    return await service.get_workflow_chats_grouped_by_user(workflow_id, current_user.id)

@router.post("", response_model=List[ChatMessageResponse], status_code=status.HTTP_201_CREATED)
async def start_new_chat(
    user_input: ChatMessageInput,
    workflow_id: UUID = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Starts a new chat conversation for the current user.
    This creates a new chatflow_id, saves the user's first message,
    triggers an LLM response, and returns the initial exchange.
    """
    service = ChatService(db)
    return await service.start_new_chat(user_input=user_input.content, user_id=current_user.id, workflow_id=workflow_id)

@router.get("/{chatflow_id}", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    chatflow_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    service = ChatService(db)
    return await service.get_chat_messages(chatflow_id=chatflow_id, user_id=current_user.id)

@router.post("/{chatflow_id}/interact", response_model=List[ChatMessageResponse])
async def handle_chat_interaction(
    chatflow_id: UUID,
    user_input: ChatMessageInput,
    workflow_id: UUID = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    service = ChatService(db)
    return await service.handle_chat_interaction(chatflow_id=chatflow_id, user_input=user_input.content, user_id=current_user.id, workflow_id=workflow_id)

@router.put("/{chat_message_id}", response_model=List[ChatMessageResponse])
async def update_chat_message(
    chat_message_id: UUID,
    chat_message_update: ChatMessageInput, # Changed to ChatMessageInput for simplicity
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    service = ChatService(db)
    # The service method now handles all logic and returns the full chat history
    updated_chat_history = await service.update_chat_message(
        chat_message_id, 
        ChatMessageUpdate(content=chat_message_update.content),
        user_id=current_user.id
    )
    if updated_chat_history is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    return updated_chat_history

@router.delete("/{chat_message_id}", status_code=status.HTTP_200_OK)
async def delete_chat_message(
    chat_message_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    service = ChatService(db)
    if not await service.delete_chat_message(chat_message_id, user_id=current_user.id):
        raise HTTPException(status_code=404, detail="Chat message not found")
    return {"detail": "Mesaj başarı ile silindi"}

@router.delete("/chatflow/{chatflow_id}", status_code=status.HTTP_200_OK)
async def delete_chatflow(
    chatflow_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes all messages for a specific chatflow_id.
    """
    service = ChatService(db)
    if not await service.delete_chatflow(chatflow_id, user_id=current_user.id):
        raise HTTPException(status_code=404, detail="Chatflow not found")
    return {"detail": "Konuşma geçmişi başarı ile silindi"}

@router.get("/active-session/id", response_model=Dict[str, Optional[str]])
async def get_active_session_id(
    chatflow_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    db = next(get_db())
    session_id = memory_service.get_active_session_id(db, str(current_user.id), chatflow_id=chatflow_id)
    return {"session_id": session_id}