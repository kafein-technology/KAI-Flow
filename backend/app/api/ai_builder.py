from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import openai
from typing import Optional, Literal, Dict, Any

from app.services.ai_builder_service import AIBuilderService
from app.services.credential_service import CredentialService
from app.services.dependencies import get_db_session, get_credential_service_dep
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter()
ai_builder_service = AIBuilderService()


class GenerateRequest(BaseModel):
    question: str
    credential_id: str
    model_name: str = "gpt-4o"
    base_url: Optional[str] = None
    mode: Literal["build", "edit"] = "build"
    existing_workflow: Optional[Dict[str, Any]] = None


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

        # Determine Base URL
        base_url = request.base_url or secret.get("base_url")

        if not api_key:
            raise ValueError("Selected credential does not contain a valid API key. Click the settings icon in the header to select or update your credential.")

        result = await ai_builder_service.generate_workflow(
            question=request.question,
            api_key=api_key,
            model_name=request.model_name,
            base_url=base_url,
            mode=request.mode,
            existing_workflow=request.existing_workflow
        )
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
