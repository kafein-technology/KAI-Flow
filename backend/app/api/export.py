"""
Workflow Export API Endpoint
============================

Provides REST API for exporting workflows as ZIP bundle.
"""

import json
import yaml
import uuid
import base64
import zipfile
import io
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db_session
from app.core.encryption import decrypt_data
from app.models.workflow import Workflow
from app.models.user_credential import UserCredential
from app.models.user import User
from app.auth.dependencies import get_current_user


router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    workflow_ids: List[str]


def get_empty_secret_from_credential(encrypted_secret: str) -> dict:
    """Decrypt credential and return structure with processed values.
    
    Rules:
    1. Keep 'id', 'name', 'service_type' WITH their values
    2. Filter out 'created_at', 'updated_at' entirely
    3. Keep all other keys but clear their values to ""
    """
    # Keys to keep with their values
    KEEP_WITH_VALUE = {'id', 'name', 'service_type'}
    # Keys to filter out entirely
    FILTER_OUT = {'created_at', 'updated_at'}
    
    try:
        encrypted_bytes = base64.b64decode(encrypted_secret)
        actual_secret = decrypt_data(encrypted_bytes)
        
        if not actual_secret or not isinstance(actual_secret, dict):
            return {"api_key": ""}
        
        processed_secret = {}
        for key, value in actual_secret.items():
            # Rule 1: Keep these keys with their values
            if key in KEEP_WITH_VALUE:
                processed_secret[key] = value
            # Rule 2: Skip these keys entirely
            elif key in FILTER_OUT:
                continue
            # Rule 3: Keep key but clear value
            elif isinstance(value, dict):
                # For nested dicts, apply same rules
                processed_secret[key] = {
                    k: v if k in KEEP_WITH_VALUE else "" 
                    for k, v in value.items() 
                    if k not in FILTER_OUT
                }
            else:
                processed_secret[key] = ""
        
        return processed_secret if processed_secret else {"api_key": ""}
    except Exception:
        return {"api_key": ""}


import logging
logger = logging.getLogger(__name__)


@router.post("/workflows")
async def export_workflows(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export selected workflows as ZIP bundle.
    
    Returns a ZIP file containing:
    - workflows_config.yaml (main config with credentials placeholders)
    - flows/*.json (individual workflow flow data)
    - README.md (import instructions)
    """
    logger.info(f"Export request from user: {current_user.email}")
    logger.info(f"Workflow IDs: {request.workflow_ids}")

    if not request.workflow_ids:
        raise HTTPException(status_code=400, detail="No workflow IDs provided")
    
    config = {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "target_user_email": current_user.email,
        "user_password": "",  # Fill this to auto-create user on import
        "user_name": current_user.full_name or "",  # Optional user display name
        "workflows": [],
        "credentials": []
    }
    
    seen_credentials = {}
    flow_files = {}  # filename -> content
    
    for wf_id_str in request.workflow_ids:
        try:
            wf_id = uuid.UUID(wf_id_str)
        except ValueError:
            continue
        
        result = await db.execute(
            select(Workflow).where(
                Workflow.id == wf_id,
                Workflow.user_id == current_user.id
            )
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            continue
        
        flow_data = dict(workflow.flow_data) if workflow.flow_data else {}
        
        # Find credentials in nodes
        # Check all known credential field names used by different node types:
        # - "credential_id": OpenAI, Cohere, Tavily, Retriever, Vector Store, etc.
        # - "credential": Kafka Producer, Kafka Trigger, Web Scraper
        # - "basic_auth_credential_id": Webhook Trigger (Basic Auth)
        # - "header_auth_credential_id": Webhook Trigger (Header Auth)
        CREDENTIAL_FIELD_NAMES = [
            "credential_id", "credential",
            "basic_auth_credential_id", "header_auth_credential_id"
        ]
        
        # Check all known credential field names used by different node types:
        # - "credential_id": OpenAI, Cohere, Tavily, Retriever, Vector Store, etc.
        # - "credential": Kafka Producer, Kafka Trigger, Web Scraper
        # - "basic_auth_credential_id": Webhook Trigger (Basic Auth)
        # - "header_auth_credential_id": Webhook Trigger (Header Auth)
        CREDENTIAL_FIELD_NAMES = [
            "credential_id", "credential",
            "basic_auth_credential_id", "header_auth_credential_id"
        ]
        
        for node in flow_data.get("nodes", []):
            node_data = node.get("data", {})
            
            for field_name in CREDENTIAL_FIELD_NAMES:
                cred_id = node_data.get(field_name)
                
                if cred_id and isinstance(cred_id, str) and cred_id not in seen_credentials:
                    try:
                        cred_result = await db.execute(
                            select(UserCredential).where(
                                UserCredential.id == uuid.UUID(cred_id)
                            )
                        )
                        cred = cred_result.scalar_one_or_none()
                        
                        if cred:
                            empty_secret = get_empty_secret_from_credential(cred.encrypted_secret)
                            seen_credentials[cred_id] = {
                                "id": str(cred.id),
                                "name": cred.name,
                                "service_type": cred.service_type,
                                "secret": empty_secret
                            }
                    except Exception:
                        pass
            for field_name in CREDENTIAL_FIELD_NAMES:
                cred_id = node_data.get(field_name)
                
                if cred_id and isinstance(cred_id, str) and cred_id not in seen_credentials:
                    try:
                        cred_result = await db.execute(
                            select(UserCredential).where(
                                UserCredential.id == uuid.UUID(cred_id)
                            )
                        )
                        cred = cred_result.scalar_one_or_none()
                        
                        if cred:
                            empty_secret = get_empty_secret_from_credential(cred.encrypted_secret)
                            seen_credentials[cred_id] = {
                                "id": str(cred.id),
                                "name": cred.name,
                                "service_type": cred.service_type,
                                "secret": empty_secret
                            }
                    except Exception:
                        pass
        
        # Create flow file
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in workflow.name.lower())[:50]
        flow_filename = f"flows/{safe_name}.json"
        flow_files[flow_filename] = json.dumps(flow_data, indent=2, default=str, ensure_ascii=False)
        
        config["workflows"].append({
            "id": str(workflow.id),
            "name": workflow.name,
            "description": workflow.description or "",
            "is_public": workflow.is_public,
            "flow_file": flow_filename
        })
    
    if not config["workflows"]:
        raise HTTPException(status_code=404, detail="No workflows found to export")
    
    # Add credentials to config
    for cred_info in seen_credentials.values():
        config["credentials"].append(cred_info)
    
    # Create README
    readme = f"""# KAI-Fusion Workflow Export Bundle

Generated: {config['generated_at']}
Exported by: {current_user.email}

## Contents
- {len(config['workflows'])} workflow(s)
- {len(config['credentials'])} credential(s) (empty - fill before import)

## Import Instructions

### 1. Edit `workflows_config.yaml`

- Set `target_user_email` to the target user's email
- Fill in all credential `secret` values with actual API keys

### 2. Run Import Script

```bash
cd backend
python -m scripts.import_workflows --config /path/to/workflows_config.yaml
```

## Workflows

"""
    for wf in config["workflows"]:
        readme += f"- **{wf['name']}** (ID: `{wf['id']}`)\n"
    
    if config["credentials"]:
        readme += "\n## Credentials (fill these before import)\n\n"
        for cred in config["credentials"]:
            readme += f"- **{cred['name']}** ({cred['service_type']})\n"
            readme += f"  - ID: `{cred['id']}`\n"
            readme += f"  - Fields: {list(cred['secret'].keys())}\n\n"
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add YAML config
        yaml_content = yaml.dump(
            config,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )
        zf.writestr("workflows_config.yaml", yaml_content)
        
        # Add flow files
        for filename, content in flow_files.items():
            zf.writestr(filename, content)
        
        # Add README
        zf.writestr("README.md", readme)
    
    zip_buffer.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"workflows_export_{timestamp}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={zip_filename}"
        }
    )