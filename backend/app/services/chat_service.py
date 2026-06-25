

import uuid
import base64
import logging
from uuid import UUID
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, or_
from app.models.chat import ChatMessage
from app.schemas.chat import ChatMessageCreate, ChatMessageUpdate
from app.core.encryption import encrypt_data, decrypt_data
from app.core.engine import get_engine
from collections import defaultdict

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = get_engine()
        self._workflow_built = False
        self._last_workflow_id = None
    
    async def _execute_workflow(self, user_input: str, chatflow_id: UUID, workflow_id: UUID = None) -> str:

        try:
            logger.info("Starting workflow execution", extra={
                "user_input_length": len(user_input),
                "chatflow_id": str(chatflow_id),
                "workflow_id": str(workflow_id) if workflow_id else None
            })
            
            # Get workflow - either from database or use default
            if workflow_id:
                workflow_data = await self._get_workflow_by_id(workflow_id)
                if not workflow_data:
                    logger.warning(f"Workflow {workflow_id} not found, falling back to default")
                    workflow_data = await self._get_default_workflow()
            else:
                workflow_data = await self._get_default_workflow()
            
            if not workflow_data:
                logger.error("No workflow found")
                return "I apologize, but no workflow is configured for this chat."
            
            # SESSION ID BASED CONTEXT - use chatflow_id as session_id
            # CRITICAL: session_id must always be set
            session_id = str(chatflow_id)
            
            # Ensure session_id is valid
            if not session_id or session_id == 'None' or len(session_id.strip()) == 0:
                session_id = f"chat_session_{uuid.uuid4().hex[:8]}"
                logger.warning(f"Invalid session_id, generated: {session_id}")
            
            user_context = {
                "session_id": session_id,
                "user_id": user_id if user_id else str(chatflow_id),
                "workflow_id": str(workflow_id) if workflow_id else workflow_data.get("id", "default")
            }
            
            # Build workflow only if needed (different workflow or not built yet)
            current_workflow_id = str(workflow_id) if workflow_id else workflow_data.get("id", "default")
            if not self._workflow_built or self._last_workflow_id != current_workflow_id:
                self.engine.build(workflow_data, user_context=user_context)
                self._workflow_built = True
                self._last_workflow_id = current_workflow_id
            
            # Execute workflow using the engine
            execution_result = await self.engine.execute(
                inputs={"input": user_input},
                stream=False,
                user_context=user_context
            )
            
            # Extract the response from execution result
            if execution_result:
                if isinstance(execution_result, dict):
                    # Check for error first
                    if not execution_result.get("success", True):
                        error_msg = execution_result.get("error", "Unknown execution error")
                        logger.error("Workflow execution failed", extra={
                            "error": error_msg,
                            "chatflow_id": str(chatflow_id)
                        })
                        return f"I encountered an error: {error_msg}"
                    
                    # Try to extract meaningful response from various possible locations
                    response = None
                    
                    # 1. Check 'result' field first (most common)
                    if execution_result.get("result"):
                        response = execution_result.get("result")
                    
                    # 2. Check 'output' field
                    if not response and execution_result.get("output"):
                        response = execution_result.get("output")
                    
                    # 3. Check 'state' for last_output
                    if not response and execution_result.get("state"):
                        state = execution_result.get("state", {})
                        response = state.get("last_output")
                        
                        # Also check node_outputs for any output
                        if not response and state.get("node_outputs"):
                            node_outputs = state.get("node_outputs", {})
                            # Get the last node output
                            for node_id, output in node_outputs.items():
                                if output:
                                    if isinstance(output, dict):
                                        response = output.get("output") or output.get("content") or output.get("result") or str(output)
                                    else:
                                        response = str(output)
                    
                    # 4. Check echo or message fields as fallback
                    if not response:
                        response = execution_result.get("echo", {}).get("input", "") or execution_result.get("message", "")
                    
                    # Handle dict response
                    if isinstance(response, dict):
                        response = response.get("content") or response.get("output") or response.get("result") or str(response)
                    
                    response = str(response) if response else "No response generated."
                else:
                    response = str(execution_result)
                
                logger.info("Workflow execution completed successfully", extra={
                    "response_length": len(response),
                    "chatflow_id": str(chatflow_id)
                })
                
                return response
            
            # Fallback if no result
            logger.warning("Workflow execution completed but no result returned", extra={
                "chatflow_id": str(chatflow_id)
            })
            return "I apologize, but I couldn't generate a response at this time."
            
        except Exception as e:
            logger.error("Workflow execution failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "chatflow_id": str(chatflow_id),
                "user_input_length": len(user_input)
            })
            return f"I encountered an error while processing your request: {str(e)}"
    
    async def _get_workflow_by_id(self, workflow_id: UUID) -> Optional[Dict[str, Any]]:

        try:
            from app.models.workflow import Workflow
            
            result = await self.db.execute(
                select(Workflow).filter(Workflow.id == workflow_id)
            )
            workflow = result.scalars().first()
            
            if workflow and workflow.flow_data:
                # Return the flow_data with the workflow ID
                flow_data = workflow.flow_data.copy() if isinstance(workflow.flow_data, dict) else workflow.flow_data
                if isinstance(flow_data, dict):
                    flow_data["id"] = str(workflow.id)
                return flow_data
            
            return None
        except Exception as e:
            logger.error(f"Failed to get workflow by ID {workflow_id}: {e}")
            return None
    
    async def _get_default_workflow(self) -> Optional[Dict[str, Any]]:

        try:
            # For now, return a simple test workflow
            # In production, you'd query the database for available workflows
            return {
                "id": "default-chat-workflow",
                "nodes": [
                    {
                        "id": "start-1",
                        "type": "StartNode",
                        "data": {"name": "Start"}
                    },
                    {
                        "id": "llm-1", 
                        "type": "OpenAIChat",
                        "data": {
                            "name": "Chat LLM",
                            "model_name": "gpt-3.5-turbo",
                            "temperature": 0.7,
                            "max_tokens": 1000
                        }
                    },
                    {
                        "id": "end-1",
                        "type": "EndNode", 
                        "data": {"name": "End"}
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "start-1",
                        "target": "llm-1"
                    },
                    {
                        "id": "edge-2", 
                        "source": "llm-1",
                        "target": "end-1"
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get default workflow: {e}")
            return None
    
    def _encrypt_content(self, content: str) -> str:

        try:
            encrypted_bytes = encrypt_data(content)
            return base64.b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to encrypt content: {e}")
    
    def _decrypt_content(self, encrypted_content: str) -> str:

        try:
            encrypted_bytes = base64.b64decode(encrypted_content.encode('utf-8'))
            decrypted_data = decrypt_data(encrypted_bytes)
            # If decrypted_data is a dict with 'value' key, return that
            if isinstance(decrypted_data, dict) and 'value' in decrypted_data:
                return decrypted_data['value']
            # Otherwise, convert dict to string or return as-is
            return str(decrypted_data) if isinstance(decrypted_data, dict) else decrypted_data
        except Exception:
            # If decryption fails, it might be an unencrypted legacy content
            # Keep as-is for backward compatibility
            return encrypted_content
    
    def _prepare_message_response(self, message: ChatMessage) -> ChatMessage:

        if message and message.content:
            message.content = self._decrypt_content(message.content)
        return message

    async def create_chat_message(self, chat_message: ChatMessageCreate) -> ChatMessage:
        encrypted_content = self._encrypt_content(chat_message.content)
        
        db_chat_message = ChatMessage(
            role=chat_message.role,
            chatflow_id=chat_message.chatflow_id,
            content=encrypted_content,
            source_documents=chat_message.source_documents,
            user_id=chat_message.user_id,
            workflow_id=chat_message.workflow_id,
        )
        self.db.add(db_chat_message)
        await self.db.commit()
        await self.db.refresh(db_chat_message)
        
        # Return with decrypted content for API response
        return self._prepare_message_response(db_chat_message)

    async def get_all_chats_grouped(self) -> dict[UUID, list[ChatMessage]]:

        stmt = select(ChatMessage).order_by(ChatMessage.chatflow_id, ChatMessage.created_at)
        result = await self.db.execute(stmt)
        all_messages = result.scalars().all()
        
        # Group messages by chatflow_id and decrypt content
        grouped_chats = defaultdict(list)
        for message in all_messages:
            decrypted_message = self._prepare_message_response(message)
            grouped_chats[message.chatflow_id].append(decrypted_message)
            
        return grouped_chats

    async def get_all_chats_grouped_by_user(self, user_id: UUID) -> dict[UUID, list[ChatMessage]]:

        stmt = select(ChatMessage).filter(ChatMessage.user_id == user_id).order_by(ChatMessage.chatflow_id, ChatMessage.created_at)
        result = await self.db.execute(stmt)
        all_messages = result.scalars().all()
        
        # Group messages by chatflow_id and decrypt content
        grouped_chats = defaultdict(list)
        for message in all_messages:
            decrypted_message = self._prepare_message_response(message)
            grouped_chats[message.chatflow_id].append(decrypted_message)
            
        return grouped_chats

    async def get_workflow_chats_grouped_by_user(self, workflow_id: UUID, user_id: UUID, is_builder: bool = False) -> dict[UUID, list[ChatMessage]]:

        if is_builder:
            filter_cond = ChatMessage.source_documents == "ai_builder"
        else:
            filter_cond = or_(
                ChatMessage.source_documents != "ai_builder",
                ChatMessage.source_documents.is_(None)
            )

        stmt = select(ChatMessage).filter(
            ChatMessage.workflow_id == workflow_id,
            ChatMessage.user_id == user_id,
            filter_cond
        ).order_by(ChatMessage.chatflow_id, ChatMessage.created_at)
        
        result = await self.db.execute(stmt)
        all_messages = result.scalars().all()
        
        # Group messages by chatflow_id and decrypt content
        grouped_chats = defaultdict(list)
        for message in all_messages:
            decrypted_message = self._prepare_message_response(message)
            grouped_chats[message.chatflow_id].append(decrypted_message)
            
        return grouped_chats

    async def get_chat_messages(self, chatflow_id: UUID, user_id: UUID = None) -> list[ChatMessage]:
        if user_id:
            result = await self.db.execute(
                select(ChatMessage).filter(
                    ChatMessage.chatflow_id == chatflow_id,
                    ChatMessage.user_id == user_id
                )
            )
        else:
            result = await self.db.execute(
                select(ChatMessage).filter(ChatMessage.chatflow_id == chatflow_id)
            )
        messages = result.scalars().all()
        return [self._prepare_message_response(msg) for msg in messages]

    async def update_chat_message(self, chat_message_id: UUID, chat_message_update: ChatMessageUpdate, user_id: UUID = None) -> list[ChatMessage]:
        if user_id:
            result = await self.db.execute(
                select(ChatMessage).filter(
                    ChatMessage.id == chat_message_id,
                    ChatMessage.user_id == user_id
                )
            )
        else:
            result = await self.db.execute(select(ChatMessage).filter(ChatMessage.id == chat_message_id))
        db_chat_message = result.scalars().first()

        if not db_chat_message:
            return None

        # If the message is not from a user, just update it simply and return the full chat.
        if db_chat_message.role != 'user':
            update_data = chat_message_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                if key == 'content' and value is not None:
                    setattr(db_chat_message, key, self._encrypt_content(value))
                else:
                    setattr(db_chat_message, key, value)
                    await self.db.commit()
        return await self.get_chat_messages(db_chat_message.chatflow_id, user_id)

        # --- Logic for cascading update on a user message ---
        chatflow_id = db_chat_message.chatflow_id
        original_timestamp = db_chat_message.created_at

        # 1. Delete all subsequent messages in the same conversation
        delete_stmt = delete(ChatMessage).where(
            ChatMessage.chatflow_id == chatflow_id,
            ChatMessage.created_at > original_timestamp
        )
        await self.db.execute(delete_stmt)

        # 2. Update the user's message content
        new_content = chat_message_update.content
        if new_content is not None:
            db_chat_message.content = self._encrypt_content(new_content)

        # 3. Regenerate a new response from the LLM using actual workflow
        llm_response_content = await self._execute_workflow(new_content, chatflow_id)
        encrypted_llm_content = self._encrypt_content(llm_response_content)
        llm_message = ChatMessage(
            role="assistant",
            content=encrypted_llm_content,
            chatflow_id=chatflow_id
        )
        self.db.add(llm_message)

        await self.db.commit()

        # 4. Return the new state of the conversation
        return await self.get_chat_messages(chatflow_id, user_id)

    async def delete_chat_message(self, chat_message_id: UUID, user_id: UUID = None) -> bool:
        if user_id:
            result = await self.db.execute(
                select(ChatMessage).filter(
                    ChatMessage.id == chat_message_id,
                    ChatMessage.user_id == user_id
                )
            )
        else:
            result = await self.db.execute(select(ChatMessage).filter(ChatMessage.id == chat_message_id))
        db_chat_message = result.scalars().first()

        if not db_chat_message:
            return False

        # If a user's message is deleted, cascade delete all subsequent messages
        if db_chat_message.role == 'user':
            delete_stmt = delete(ChatMessage).where(
                ChatMessage.chatflow_id == db_chat_message.chatflow_id,
                ChatMessage.created_at > db_chat_message.created_at
            )
            await self.db.execute(delete_stmt)

        # Delete the target message itself
        await self.db.delete(db_chat_message)
        await self.db.commit()
        return True

    async def delete_chatflow(self, chatflow_id: UUID, user_id: UUID = None) -> bool:

        try:
            # Delete all messages for the chatflow_id
            delete_stmt = delete(ChatMessage).where(
                ChatMessage.chatflow_id == chatflow_id
            )
            
            # If user_id is provided, also filter by user_id for security
            if user_id:
                delete_stmt = delete_stmt.where(ChatMessage.user_id == user_id)
            
            await self.db.execute(delete_stmt)
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            return False

    async def start_new_chat(self, user_input: str, user_id: UUID = None, workflow_id: UUID = None) -> list[ChatMessage]:
        # 1. Generate a new chatflow_id for the new conversation
        chatflow_id = uuid.uuid4()

        # 2. Save user's message
        user_message = ChatMessageCreate(
            role="user",
            content=user_input,
            chatflow_id=chatflow_id,
            user_id=user_id,
            workflow_id=workflow_id
        )
        await self.create_chat_message(user_message)

        # 3. Execute the actual workflow with the specified workflow_id
        llm_response_content = await self._execute_workflow(user_input, chatflow_id, workflow_id)

        # 4. Save LLM's response (create_chat_message will handle encryption)
        llm_message = ChatMessageCreate(
            role="assistant",
            content=llm_response_content,
            chatflow_id=chatflow_id,
            user_id=user_id,
            workflow_id=workflow_id
        )
        await self.create_chat_message(llm_message)
        
        # 5. Return all messages for the newly created chatflow
        return await self.get_chat_messages(chatflow_id, user_id)

    async def handle_chat_interaction(self, chatflow_id: UUID, user_input: str, user_id: UUID = None, workflow_id: UUID = None) -> list[ChatMessage]:
        # 1. Save user's message
        user_message = ChatMessageCreate(
            role="user",
            content=user_input,
            chatflow_id=chatflow_id,
            user_id=user_id,
            workflow_id=workflow_id
        )
        await self.create_chat_message(user_message)

        # 2. Execute the actual workflow with the specified workflow_id
        llm_response_content = await self._execute_workflow(user_input, chatflow_id, workflow_id)

        # 3. Save LLM's response (create_chat_message will handle encryption)
        llm_message = ChatMessageCreate(
            role="assistant",
            content=llm_response_content,
            chatflow_id=chatflow_id,
            user_id=user_id,
            workflow_id=workflow_id
        )
        await self.create_chat_message(llm_message)
        
        # 4. Return all messages for the chatflow
        return await self.get_chat_messages(chatflow_id, user_id) 