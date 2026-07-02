"""Shared credential field names used in workflow node data."""

from typing import Any, Dict, List, Optional

# Field names in flow_data.nodes[].data that may hold a credential UUID.
CREDENTIAL_FIELD_NAMES: tuple[str, ...] = (
    "credential_id",
    "credential",
    "basic_auth_credential_id",
    "header_auth_credential_id",
    "minio_credential",
    "llm_credential_id",
)


def find_credential_usages_in_flow_data(
    flow_data: Optional[Dict[str, Any]],
    credential_id: str,
) -> List[Dict[str, str]]:
    """
    Return node usage entries where node data references the given credential ID.
    """
    if not flow_data or not isinstance(flow_data, dict):
        return []

    usages: List[Dict[str, str]] = []
    nodes = flow_data.get("nodes") or []
    if not isinstance(nodes, list):
        return usages

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data") or {}
        if not isinstance(node_data, dict):
            continue

        for field_name in CREDENTIAL_FIELD_NAMES:
            value = node_data.get(field_name)
            if value is not None and str(value) == credential_id:
                usages.append(
                    {
                        "node_id": str(node.get("id") or ""),
                        "node_type": str(node.get("type") or ""),
                        "field": field_name,
                    }
                )

    return usages
