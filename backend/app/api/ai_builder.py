from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import openai
import json
from typing import Optional, Literal, Dict, Any

from app.services.ai_builder import AIBuilderOrchestrator
from app.services.credential_service import CredentialService
from app.services.dependencies import get_db_session, get_credential_service_dep
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.schemas.chat import ChatMessageCreate

router = APIRouter()
ai_builder_service = AIBuilderOrchestrator()


class GenerateRequest(BaseModel):
    question: str
    credential_id: str
    model_name: Optional[str] = "gpt-4o"
    base_url: Optional[str] = None
    mode: Literal["build", "edit"] = "build"
    existing_workflow: Optional[Dict[str, Any]] = None
    verify_ssl: Optional[bool] = None
    extra_body_params: Optional[str] = None
    workflow_id: Optional[str] = None
    chatflow_id: Optional[str] = None


@router.post("/generate")
async def generate_workflow(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep)
):
    try:
        # Resolve credential
        try:
            cred_id_uuid = uuid.UUID(request.credential_id)
        except ValueError:
            raise ValueError("Invalid credential_id format. Must be UUID.")

        decrypted_cred = await credential_service.get_decrypted_credential(
            db, current_user.id, cred_id_uuid
        )
        if not decrypted_cred:
            raise ValueError("Selected credential not found or unauthorized.")

        secret = decrypted_cred.get("secret", {})
        api_key = secret.get("api_key") or secret.get("access_token")

        if not api_key:
            raise ValueError("Selected credential does not contain a valid API key. Click the settings icon in the header to select or update your credential.")

        # Resolve Model Name and Base URL (credential secret has priority)
        model_name = secret.get("model_name") or request.model_name or "gpt-4o"
        base_url = secret.get("base_url") or request.base_url

        # Resolve SSL Verification (request overrides credential, credential skip_ssl_verify overrides default True)
        verify_ssl = True
        if request.verify_ssl is not None:
            verify_ssl = request.verify_ssl
        elif "skip_ssl_verify" in secret:
            skip_ssl = secret.get("skip_ssl_verify", False)
            if isinstance(skip_ssl, str):
                skip_ssl = skip_ssl.lower() in ("true", "1", "yes", "on")
            verify_ssl = not bool(skip_ssl)

        # Resolve Extra Body Parameters (request overrides credential)
        extra_body_params = request.extra_body_params or secret.get("extra_body_params")
        if isinstance(extra_body_params, dict):
            # If extra_body_params is stored as a dict in the secret database, convert it to a JSON string
            extra_body_params = json.dumps(extra_body_params)

        # Load chat history if chatflow_id is provided
        chat_history_list = None
        if request.chatflow_id:
            try:
                cf_id = uuid.UUID(request.chatflow_id)
                chat_service = ChatService(db)
                messages = await chat_service.get_chat_messages(chatflow_id=cf_id, user_id=current_user.id)
                chat_history_list = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages
                ]
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to load chat history for AI Builder: {e}")

        result = await ai_builder_service.generate_workflow(
            question=request.question,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            mode=request.mode,
            existing_workflow=request.existing_workflow,
            verify_ssl=verify_ssl,
            extra_body_params=extra_body_params,
            chat_history=chat_history_list
        )

        # Save user/assistant chat history if chatflow_id is provided
        if request.chatflow_id:
            try:
                cf_id = uuid.UUID(request.chatflow_id)
                w_id = None
                if request.workflow_id:
                    try:
                        w_id = uuid.UUID(request.workflow_id)
                    except (ValueError, TypeError):
                        pass
                chat_service = ChatService(db)

                # Save user message
                await chat_service.create_chat_message(
                    ChatMessageCreate(
                        role="user",
                        content=request.question,
                        chatflow_id=cf_id,
                        user_id=current_user.id,
                        workflow_id=w_id,
                        source_documents="ai_builder"
                    )
                )

                # Save assistant message
                if result.get("invalid_request"):
                    reject_msg = result.get("message") or "Your request does not appear to be a workflow edit. Please describe what you want to change."
                    assistant_content = f"⚠️ {reject_msg}"
                else:
                    assistant_content = (
                        "Workflow updated successfully!"
                        if request.mode == "edit"
                        else "Workflow created successfully! The nodes have been placed on your canvas."
                    )

                await chat_service.create_chat_message(
                    ChatMessageCreate(
                        role="assistant",
                        content=assistant_content,
                        chatflow_id=cf_id,
                        user_id=current_user.id,
                        workflow_id=w_id,
                        source_documents="ai_builder"
                    )
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to save AI Builder chat messages: {e}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except openai.RateLimitError as e:
        raise HTTPException(status_code=429, detail="Insufficient quota or rate limit exceeded. Please check your API balance and limits.")
    except openai.AuthenticationError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired API key. Please check your credentials in Settings → Credentials.")
    except (openai.APIConnectionError, openai.APITimeoutError) as e:
        raise HTTPException(status_code=504, detail="Could not connect to the AI API or the request timed out. Please check your internet connection or the Base URL you entered and try again.")
    except openai.APIError as e:
        # Some generic provider errors (like missing JSON schema support)
        err_msg = e.message if hasattr(e, 'message') else str(e)
        raise HTTPException(status_code=502, detail=f"API provider returned an error: {err_msg}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
