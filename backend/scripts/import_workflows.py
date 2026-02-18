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
from typing import Dict, Any

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

            # 2. Create credentials with ORIGINAL UUIDs
            created_credentials = 0
            skipped_credentials = 0

            log(f"\nProcessing credentials...")

            for cred_config in config.get("credentials", []):
                cred_id = cred_config.get("id")
                name = cred_config.get("name")
                service_type = cred_config.get("service_type")
                secret = cred_config.get("secret", {})

                if not cred_id or not name or not service_type:
                    log(f"  SKIP: Invalid credential config: {cred_config}")
                    skipped_credentials += 1
                    continue

                # Check if credential values are filled
                has_values = any(v for v in secret.values() if v)
                if not has_values:
                    log(f"  SKIP: Empty credential: {name} (fill secrets first)")
                    skipped_credentials += 1
                    continue

                # Check if credential already exists (by ID)
                try:
                    existing = await db.execute(
                        select(UserCredential).where(UserCredential.id == uuid.UUID(cred_id))
                    )
                    if existing.scalar_one_or_none():
                        log(f"  SKIP: Credential already exists: {name} (ID: {cred_id})")
                        skipped_credentials += 1
                        continue
                except Exception as e:
                    log(f"  WARN: Error checking credential {cred_id}: {e}")

                if dry_run:
                    log(f"  Would create: {name} (ID: {cred_id})")
                    continue

                # Create credential with ORIGINAL UUID
                try:
                    encrypted_bytes = encrypt_data(secret)
                    encrypted_secret = base64.b64encode(encrypted_bytes).decode('utf-8')

                    credential = UserCredential(
                        id=uuid.UUID(cred_id),  # Use ORIGINAL UUID
                        user_id=user.id,
                        name=name,
                        service_type=service_type,
                        encrypted_secret=encrypted_secret
                    )
                    db.add(credential)
                    await db.flush()

                    created_credentials += 1
                    log(f"  Created: {name} (ID: {cred_id})")

                except Exception as e:
                    log(f"  ERROR creating {name}: {e}")
                    skipped_credentials += 1

            # 3. Import workflows with ORIGINAL UUIDs
            created_workflows = 0
            skipped_workflows = 0

            log(f"\nProcessing workflows...")

            for wf_config in config.get("workflows", []):
                wf_id = wf_config.get("id")
                wf_name = wf_config.get("name")
                flow_file_rel = wf_config.get("flow_file")

                if not wf_id or not wf_name or not flow_file_rel:
                    log(f"  SKIP: Invalid workflow config: {wf_config}")
                    skipped_workflows += 1
                    continue

                flow_file = base_dir / flow_file_rel

                if not flow_file.exists():
                    log(f"  ERROR: Flow file not found: {flow_file}")
                    skipped_workflows += 1
                    continue

                # Check if workflow already exists (by ID)
                try:
                    existing = await db.execute(
                        select(Workflow).where(Workflow.id == uuid.UUID(wf_id))
                    )
                    if existing.scalar_one_or_none():
                        log(f"  SKIP: Workflow already exists: {wf_name} (ID: {wf_id})")
                        skipped_workflows += 1
                        continue
                except Exception as e:
                    log(f"  WARN: Error checking workflow {wf_id}: {e}")

                # Read flow data
                try:
                    flow_data = json.loads(flow_file.read_text(encoding="utf-8"))
                except Exception as e:
                    log(f"  ERROR reading {flow_file}: {e}")
                    skipped_workflows += 1
                    continue

                if dry_run:
                    log(f"  Would import: {wf_name} (ID: {wf_id})")
                    continue

                # Create workflow with ORIGINAL UUID
                try:
                    workflow = Workflow(
                        id=uuid.UUID(wf_id),  # Use ORIGINAL UUID
                        user_id=user.id,
                        name=wf_name,
                        description=wf_config.get("description", ""),
                        is_public=wf_config.get("is_public", False),
                        flow_data=flow_data
                    )
                    db.add(workflow)
                    created_workflows += 1
                    log(f"  Imported: {wf_name} (ID: {wf_id})")

                except Exception as e:
                    log(f"  ERROR importing {wf_name}: {e}")
                    skipped_workflows += 1

            # Commit all changes
            if not dry_run:
                await db.commit()

            # Summary
            log(f"\n{'=' * 50}")
            log(f"Import Summary")
            log(f"  Credentials: {created_credentials} created, {skipped_credentials} skipped")
            log(f"  Workflows: {created_workflows} imported, {skipped_workflows} skipped")

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

