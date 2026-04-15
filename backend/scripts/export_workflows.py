#!/usr/bin/env python3
"""
KAI-Flow Workflow Export Script
==================================

Export workflows to distributable YAML bundle.
- Preserves original workflow and credential UUIDs
- Extracts credential structure with empty values

Usage:
    cd backend
    python -m scripts.export_workflows --ids "uuid1,uuid2" --output ./export_bundle
    python -m scripts.export_workflows --user-email "admin@example.com" --output ./export_bundle
"""

import asyncio
import argparse
import json
import yaml
import uuid
import base64
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db_session_context
from app.core.encryption import decrypt_data
from app.models.workflow import Workflow
from app.models.user_credential import UserCredential
from app.models.user import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

def get_empty_secret_from_credential(credential: UserCredential) -> Dict[str, Any]:
    """
    Decrypt credential secret and clear all values.
    Returns the structure with empty strings.
    """
    try:
        encrypted_bytes = base64.b64decode(credential.encrypted_secret)
        actual_secret = decrypt_data(encrypted_bytes)
        
        if not actual_secret or not isinstance(actual_secret, dict):
            return {"api_key": ""}
        
        # Clear all values - keep the keys
        empty_secret = {}
        for key, value in actual_secret.items():
            if isinstance(value, dict):
                empty_secret[key] = {k: "" for k in value.keys()}
            else:
                empty_secret[key] = ""
        
        return empty_secret
        
    except Exception as e:
        logger.exception(f"Warning: Could not decrypt credential: {e}")
        return {"api_key": ""}


async def export_workflows(
    workflow_ids: Optional[List[str]] = None,
    user_email: Optional[str] = None,
    output_dir: str = "./export_bundle",
    export_name: str = "default"
):
    """
    Export workflows preserving original UUIDs.
    Credentials are exported with empty secrets (user fills them).
    """
    output_path = Path(output_dir)
    # Sanitize export name
    safe_export_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in export_name.strip().lower())
    flows_dir = output_path / f"{safe_export_name}_flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    
    config = {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "target_user_email": "admin@yourdomain.com",
        "workflows": [],
        "credentials": []
    }
    
    seen_credentials = {}  # cred_id_str -> credential info
    
    async with get_db_session_context() as db:
        # Get workflows to export
        workflows_to_export = []
        
        if workflow_ids:
            for wf_id in workflow_ids:
                try:
                    result = await db.execute(
                        select(Workflow).where(Workflow.id == uuid.UUID(wf_id))
                    )
                    workflow = result.scalar_one_or_none()
                    if workflow:
                        workflows_to_export.append(workflow)
                    else:
                        logger(f"Warning: Workflow not found: {wf_id}")
                except Exception as e:
                    logger(f"Warning: Invalid workflow ID {wf_id}: {e}")
        
        elif user_email:
            user_result = await db.execute(
                select(User).where(User.email == user_email)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                logger(f"Error: User not found: {user_email}")
                return
            
            wf_result = await db.execute(
                select(Workflow).where(Workflow.user_id == user.id)
            )
            workflows_to_export = wf_result.scalars().all()
            config["target_user_email"] = user_email
            logger(f"Exporting all workflows for: {user_email}")
        
        else:
            logger("Error: Please provide --ids or --user-email")
            return
        
        if not workflows_to_export:
            logger("Error: No workflows to export")
            return
        
        logger(f"\nExporting {len(workflows_to_export)} workflow(s)...\n")
        
        for workflow in workflows_to_export:
            # Keep flow_data as-is (don't modify credential_id)
            flow_data = dict(workflow.flow_data) if workflow.flow_data else {}
            
            # Find all credential fields in nodes
            # Check all known credential field names used by different node types
            CREDENTIAL_FIELD_NAMES = [
                "credential_id", "credential",
                "basic_auth_credential_id", "header_auth_credential_id"
            ]
            
            # Find all credential fields in nodes
            # Check all known credential field names used by different node types
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
                                select(UserCredential).where(UserCredential.id == uuid.UUID(cred_id))
                            )
                            cred = cred_result.scalar_one_or_none()
                            
                            if cred:
                                empty_secret = get_empty_secret_from_credential(cred)
                                seen_credentials[cred_id] = {
                                    "id": str(cred.id),  # Preserve original UUID
                                    "name": cred.name,
                                    "service_type": cred.service_type,
                                    "secret": empty_secret
                                }
                                logger(f"Credential: {cred.name} (ID: {cred_id})")
                        except Exception as e:
                            logger(f"Warning: Could not process credential {cred_id}: {e}")
            
            # Save flow file (unchanged - keeps credential_id as-is)
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in workflow.name.lower())[:50]
            flow_file = f"{safe_export_name}_flows/{safe_name}.json"
            (output_path / flow_file).write_text(
                json.dumps(flow_data, indent=2, default=str, ensure_ascii=False)
            )
            
            config["workflows"].append({
                "id": str(workflow.id),  # Preserve original UUID
                "name": workflow.name,
                "description": workflow.description or "",
                "is_public": workflow.is_public,
                "flow_file": flow_file
            })
            
            logger(f"Exported: {workflow.name} (ID: {workflow.id})")
        
        # Add all found credentials to config
        for cred_info in seen_credentials.values():
            config["credentials"].append(cred_info)
    
    # Write YAML config
    yaml_content = yaml.dump(
        config, 
        default_flow_style=False, 
        sort_keys=False, 
        allow_unicode=True
    )
    (output_path / f"{safe_export_name}_workflows_config.yaml").write_text(yaml_content, encoding="utf-8")
    
    # Write README
    readme = f"""# KAI-Flow Workflow Export Bundle

Generated: {config['generated_at']}

## Contents
- {len(config['workflows'])} workflow(s)
- {len(config['credentials'])} credential(s) (empty - fill before import)

## Import Instructions

### 1. Edit `workflows_config.yaml`

- Set `target_user_email` to the target user's email
- Fill in all credential `secret` values

### 2. Run Import Script

```bash
cd backend
python -m scripts.import_workflows --config /path/to/{safe_export_name}_workflows_config.yaml
```

## Workflows

"""
    for wf in config["workflows"]:
        readme += f"- **{wf['name']}** (ID: `{wf['id']}`)\n"
    
    readme += "\n## Credentials\n\n"
    for cred in config["credentials"]:
        readme += f"- **{cred['name']}** ({cred['service_type']}) - ID: `{cred['id']}`\n"
        readme += f"  Fields: {list(cred['secret'].keys())}\n\n"
    
    (output_path / "README.md").write_text(readme, encoding="utf-8")
    
    logger(f"\n{'='*50}")
    logger(f"Export complete: {output_path.absolute()}")
    logger(f"Workflows: {len(config['workflows'])}")
    logger(f"Credentials: {len(config['credentials'])}")
    logger(f"\nIMPORTANT: Fill credential secrets before import!")


def main():
    parser = argparse.ArgumentParser(
        description="Export KAI-Flow workflows to distributable bundle"
    )
    parser.add_argument("--ids", help="Comma-separated workflow UUIDs to export")
    parser.add_argument("--user-email", help="Export all workflows for this user")
    parser.add_argument("--output", required=True, help="Output directory path")
    parser.add_argument("--name", required=True, help="Export name (used for folder/file naming)")
    
    args = parser.parse_args()
    
    if not args.ids and not args.user_email:
        parser.error("Either --ids or --user-email is required")
    
    workflow_ids = None
    if args.ids:
        workflow_ids = [wid.strip() for wid in args.ids.split(",") if wid.strip()]
    
    asyncio.run(export_workflows(
        workflow_ids=workflow_ids,
        user_email=args.user_email,
        output_dir=args.output,
        export_name=args.name
    ))


if __name__ == "__main__":
    main()