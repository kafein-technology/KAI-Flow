"""Shared helpers for workflow export/import bundles."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

CREDENTIAL_FIELD_NAMES = [
    "credential_id",
    "credential",
    "basic_auth_credential_id",
    "header_auth_credential_id",
]


def map_credentials_in_flow_data(flow_data: dict, uuid_mapping: Dict[str, str]) -> None:
    """Replace exported credential UUIDs with mapped IDs in flow node data."""
    for node in flow_data.get("nodes", []):
        node_data = node.get("data", {})
        for field_name in CREDENTIAL_FIELD_NAMES:
            cred_val = node_data.get(field_name)
            if cred_val and isinstance(cred_val, str) and cred_val in uuid_mapping:
                node_data[field_name] = uuid_mapping[cred_val]


def resolve_exported_error_workflow_id(
    wf_config: dict,
    flow_data: dict,
) -> Optional[str]:
    """Resolve error workflow ID from YAML config or flow_data settings."""
    error_id = wf_config.get("error_workflow")
    if error_id and str(error_id).strip():
        return str(error_id).strip()

    settings = flow_data.get("settings")
    if isinstance(settings, dict):
        flow_error_id = settings.get("error_workflow_id")
        if flow_error_id and str(flow_error_id).strip():
            return str(flow_error_id).strip()

    return None


def _clear_error_workflow_settings(flow_data: dict) -> None:
    settings = flow_data.get("settings")
    if isinstance(settings, dict) and "error_workflow_id" in settings:
        settings.pop("error_workflow_id", None)


def apply_error_workflow_link(
    workflow: Any,
    flow_data: dict,
    old_error_id: str,
    workflow_uuid_mapping: Dict[str, str],
) -> bool:
    """
    Map and apply error handler workflow link on import.

    Returns True when a valid mapped link was applied, False otherwise.
    """
    old_error_id = str(old_error_id).strip()
    if not old_error_id:
        return False

    mapped_id = workflow_uuid_mapping.get(old_error_id)
    workflow_id = str(workflow.id)

    if not mapped_id or mapped_id == workflow_id:
        workflow.error_workflow = None
        _clear_error_workflow_settings(flow_data)
        workflow.flow_data = flow_data
        return False

    try:
        new_uuid = uuid.UUID(mapped_id)
    except (ValueError, AttributeError):
        workflow.error_workflow = None
        _clear_error_workflow_settings(flow_data)
        workflow.flow_data = flow_data
        return False

    workflow.error_workflow = new_uuid
    settings = flow_data.get("settings")
    if not isinstance(settings, dict):
        settings = {}
        flow_data["settings"] = settings
    settings["error_workflow_id"] = mapped_id
    workflow.flow_data = flow_data
    return True


def collect_missing_error_workflow_warnings(workflows: List[dict]) -> List[str]:
    """Return warning messages for error handlers not included in the export bundle."""
    exported_ids = {str(wf["id"]) for wf in workflows if wf.get("id")}
    warnings: List[str] = []

    for wf in workflows:
        error_workflow_id = wf.get("error_workflow")
        if not error_workflow_id:
            continue
        error_workflow_id = str(error_workflow_id)
        if error_workflow_id not in exported_ids:
            warnings.append(
                f"WARN: error handler workflow not included in export for "
                f"'{wf.get('name', 'unknown')}' (ref: {error_workflow_id})"
            )

    return warnings
