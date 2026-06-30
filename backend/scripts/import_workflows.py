#!/usr/bin/env python3
"""
KAI-Flow Workflow Import Script
==================================

Import workflows from YAML bundle.
- Uses original workflow and credential UUIDs from export
- Credentials are created with filled secrets (encrypted)

Usage:
    cd backend
    python -m scripts.import_workflows --config ./export_bundle/workflows_config.yaml
    python -m scripts.import_workflows --config ./export_bundle/workflows_config.yaml --dry-run
"""

import asyncio
import argparse
import json
import yaml
import uuid
import base64
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# NOTE: logging.basicConfig must be called BEFORE any app imports,
# because app modules trigger logging calls during import which
# auto-configure the root logger and make later basicConfig a no-op.
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)

from app.core.database import get_db_session_context
from app.core.encryption import encrypt_data
from app.models.user import User
from app.models.user_credential import UserCredential
from app.models.workflow import Workflow
from sqlalchemy import select
from scripts.workflow_bundle_utils import (
    apply_error_workflow_link,
    map_credentials_in_flow_data,
    resolve_exported_error_workflow_id,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def log(msg: str):
    """Print and log - ensures output is always visible in CLI/Docker."""
    print(msg, flush=True)


async def import_from_config(config_path: str, dry_run: bool = False):
    """
    Import workflows using original UUIDs from export.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        log(f"ERROR: Config file not found: {config_file}")
        return

    base_dir = config_file.parent

    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))

    log(f"Import Configuration")
    log(f"  Source: {config_file}")
    log(f"  Version: {config.get('version', 'unknown')}")
    log(f"  Workflows: {len(config.get('workflows', []))}")
    log(f"  Credentials: {len(config.get('credentials', []))}")

    if dry_run:
        log(f"\n** DRY RUN MODE - No changes will be made **\n")

    try:
        async with get_db_session_context() as db:
            # 1. Find or create target user
            target_email = config.get("target_user_email", "")
            if not target_email:
                log("ERROR: target_user_email is not set in config")
                return

            result = await db.execute(select(User).where(User.email == target_email))
            user = result.scalar_one_or_none()

            if not user:
                # User doesn't exist - create if password provided
                user_password = config.get("user_password", "")
                user_name = config.get("user_name", target_email.split("@")[0])

                if not user_password:
                    log(f"ERROR: User not found: {target_email}")
                    log("   Add 'user_password: your_password' to config to auto-create user")
                    return

                if dry_run:
                    log(f"\nWould create user: {target_email}")
                else:
                    # Import password hashing
                    from app.core.security import get_password_hash

                    # Create new user
                    new_user = User(
                        email=target_email,
                        full_name=user_name,
                        password_hash=get_password_hash(user_password),
                        status="active"
                    )
                    db.add(new_user)
                    await db.flush()
                    user = new_user
                    log(f"  Created user: {target_email}")

            log(f"\nTarget user: {user.email} (id: {user.id})")

            # 2. Map or Create/Update credentials
            uuid_mapping = {}
            created_credentials = 0
            updated_credentials = 0
            skipped_credentials = 0

            log(f"\nProcessing credentials...")

            for cred_config in config.get("credentials", []):
                old_cred_id = cred_config.get("id")
                name = cred_config.get("name")
                service_type = cred_config.get("service_type")
                secret = cred_config.get("secret", {})

                if not old_cred_id or not name or not service_type:
                    log(f"  SKIP: Invalid credential config: {cred_config}")
                    skipped_credentials += 1
                    continue

                # Check if a credential with same name and service_type exists for TARGET USER
                existing_cred = None
                try:
                    existing = await db.execute(
                        select(UserCredential).where(
                            UserCredential.user_id == user.id,
                            UserCredential.name == name,
                            UserCredential.service_type == service_type
                        )
                    )
                    existing_cred = existing.scalar_one_or_none()
                except Exception as e:
                    log(f"  WARN: Error checking credential {name}: {e}")

                # Check if credential values are filled
                has_values = any(v for v in secret.values() if v)

                if existing_cred:
                    uuid_mapping[old_cred_id] = str(existing_cred.id)
                    if dry_run:
                        log(f"  Would UPDATE (or skip secret update): {name}")
                        continue
                    
                    # Update secret ONLY if new secrets are provided in YAML
                    if has_values:
                        try:
                            encrypted_bytes = encrypt_data(secret)
                            encrypted_secret = base64.b64encode(encrypted_bytes).decode('utf-8')
                            existing_cred.encrypted_secret = encrypted_secret
                            updated_credentials += 1
                            log(f"  Updated: {name}")
                        except Exception as e:
                            log(f"  ERROR updating {name}: {e}")
                            skipped_credentials += 1
                    else:
                        log(f"  Skipped secret update (YAML is empty) but kept mapping for: {name}")
                        skipped_credentials += 1
                else:
                    if dry_run:
                        log(f"  Would CREATE: {name}")
                        continue

                    # Generate NEW UUID for credential
                    new_cred_id = uuid.uuid4()
                    uuid_mapping[old_cred_id] = str(new_cred_id)

                    # Create credential with NEW UUID (even if secrets are empty, allowing user to fill them in UI)
                    try:
                        encrypted_bytes = encrypt_data(secret)
                        encrypted_secret = base64.b64encode(encrypted_bytes).decode('utf-8')

                        credential = UserCredential(
                            id=new_cred_id,
                            user_id=user.id,
                            name=name,
                            service_type=service_type,
                            encrypted_secret=encrypted_secret
                        )
                        db.add(credential)
                        await db.flush()

                        created_credentials += 1
                        log(f"  Created (empty/filled): {name}")

                    except Exception as e:
                        log(f"  ERROR creating {name}: {e}")
                        skipped_credentials += 1

            # 3. Prepare workflow payloads
            created_workflows = 0
            skipped_workflows = 0
            updated_workflows = 0
            error_handlers_linked = 0
            error_handlers_skipped = 0

            log(f"\nProcessing workflows...")

            workflow_payloads: List[Dict[str, Any]] = []

            for wf_config in config.get("workflows", []):
                old_wf_id = wf_config.get("id")
                wf_name = wf_config.get("name")
                flow_file_rel = wf_config.get("flow_file")

                if not old_wf_id or not wf_name or not flow_file_rel:
                    log(f"  SKIP: Invalid workflow config: {wf_config}")
                    skipped_workflows += 1
                    continue

                flow_file = base_dir / flow_file_rel

                if not flow_file.exists():
                    log(f"  ERROR: Flow file not found: {flow_file}")
                    skipped_workflows += 1
                    continue

                existing_wf = None
                try:
                    existing = await db.execute(
                        select(Workflow).where(
                            Workflow.user_id == user.id,
                            Workflow.name == wf_name
                        )
                    )
                    existing_wf = existing.scalar_one_or_none()
                except Exception as e:
                    log(f"  WARN: Error checking workflow {wf_name}: {e}")

                try:
                    flow_data = json.loads(flow_file.read_text(encoding="utf-8"))
                    map_credentials_in_flow_data(flow_data, uuid_mapping)
                except Exception as e:
                    log(f"  ERROR reading or parsing {flow_file}: {e}")
                    skipped_workflows += 1
                    continue

                workflow_payloads.append({
                    "wf_config": wf_config,
                    "flow_data": flow_data,
                    "wf_name": wf_name,
                    "old_wf_id": old_wf_id,
                    "existing_wf": existing_wf,
                })

            workflow_uuid_mapping: Dict[str, str] = {}
            workflow_records: List[Dict[str, Any]] = []

            if dry_run:
                for payload in workflow_payloads:
                    old_wf_id = payload["old_wf_id"]
                    wf_name = payload["wf_name"]
                    existing_wf = payload["existing_wf"]

                    if existing_wf:
                        workflow_uuid_mapping[old_wf_id] = str(existing_wf.id)
                        log(f"  Would UPDATE: {wf_name}")
                    else:
                        workflow_uuid_mapping[old_wf_id] = f"<new:{wf_name}>"
                        log(f"  Would import: {wf_name}")

                log(f"\nProcessing error handler links...")
                for payload in workflow_payloads:
                    wf_name = payload["wf_name"]
                    old_error_id = resolve_exported_error_workflow_id(
                        payload["wf_config"],
                        payload["flow_data"],
                    )
                    if not old_error_id:
                        continue

                    mapped_id = workflow_uuid_mapping.get(old_error_id)
                    if mapped_id and not mapped_id.startswith("<new:"):
                        log(f"  Would link error handler: {wf_name} -> {mapped_id}")
                        error_handlers_linked += 1
                    else:
                        log(f"  WARN: Error handler not in bundle for {wf_name} (ref: {old_error_id})")
                        error_handlers_skipped += 1
            else:
                # Pass 1: import workflows and build UUID mapping
                for payload in workflow_payloads:
                    wf_config = payload["wf_config"]
                    flow_data = payload["flow_data"]
                    wf_name = payload["wf_name"]
                    old_wf_id = payload["old_wf_id"]
                    existing_wf = payload["existing_wf"]

                    try:
                        if existing_wf:
                            existing_wf.description = wf_config.get("description", "")
                            existing_wf.is_public = wf_config.get("is_public", False)
                            existing_wf.flow_data = flow_data
                            workflow_uuid_mapping[old_wf_id] = str(existing_wf.id)
                            workflow_records.append({
                                "workflow": existing_wf,
                                "flow_data": flow_data,
                                "wf_config": wf_config,
                                "wf_name": wf_name,
                            })
                            updated_workflows += 1
                            log(f"  Updated: {wf_name}")
                        else:
                            new_wf_id = uuid.uuid4()
                            workflow = Workflow(
                                id=new_wf_id,
                                user_id=user.id,
                                name=wf_name,
                                description=wf_config.get("description", ""),
                                is_public=wf_config.get("is_public", False),
                                flow_data=flow_data,
                            )
                            db.add(workflow)
                            workflow_uuid_mapping[old_wf_id] = str(new_wf_id)
                            workflow_records.append({
                                "workflow": workflow,
                                "flow_data": flow_data,
                                "wf_config": wf_config,
                                "wf_name": wf_name,
                            })
                            created_workflows += 1
                            log(f"  Imported: {wf_name}")
                    except Exception as e:
                        log(f"  ERROR importing/updating {wf_name}: {e}")
                        skipped_workflows += 1

                await db.flush()

                # Pass 2: restore error handler links
                log(f"\nProcessing error handler links...")
                for record in workflow_records:
                    workflow = record["workflow"]
                    flow_data = record["flow_data"]
                    wf_config = record["wf_config"]
                    wf_name = record["wf_name"]

                    old_error_id = resolve_exported_error_workflow_id(wf_config, flow_data)
                    if not old_error_id:
                        continue

                    linked = apply_error_workflow_link(
                        workflow,
                        flow_data,
                        old_error_id,
                        workflow_uuid_mapping,
                    )
                    if linked:
                        mapped_id = str(workflow.error_workflow)
                        log(f"  Linked error handler: {wf_name} -> {mapped_id}")
                        error_handlers_linked += 1
                    else:
                        log(f"  WARN: Error handler not in bundle for {wf_name} (ref: {old_error_id})")
                        error_handlers_skipped += 1

            # Commit all changes
            if not dry_run:
                await db.commit()

            # Summary
            log(f"\n{'=' * 50}")
            log(f"Import Summary")
            log(f"  Credentials: {created_credentials} created, {updated_credentials} updated, {skipped_credentials} skipped")
            log(f"  Workflows: {created_workflows} imported, {updated_workflows} updated, {skipped_workflows} skipped")
            log(f"  Error handlers: {error_handlers_linked} linked, {error_handlers_skipped} skipped")

            if dry_run:
                log(f"\n** DRY RUN - No changes were made **")
            else:
                log(f"\nImport complete!")

    except Exception as e:
        log(f"\nFATAL ERROR during import: {e}")
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Import KAI-Flow workflows from YAML bundle"
    )
    parser.add_argument("--config", required=True, help="Path to workflows_config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Validate without changes")

    args = parser.parse_args()

    asyncio.run(import_from_config(
        config_path=args.config,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
