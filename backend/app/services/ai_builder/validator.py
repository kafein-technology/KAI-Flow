import logging
from typing import List, Dict, Any, Optional

from .handle_types import are_handles_compatible, resolve_handle_type

logger = logging.getLogger(__name__)


class ValidationIssue:

    def __init__(self, code: str, path: str, message: str):
        self.code = code
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.path}: {self.message}"

    def __repr__(self) -> str:
        return f"ValidationIssue({self.code!r}, {self.path!r}, {self.message!r})"


# ─── Metadata Cache ───
# This cache stores node metadata to prevent repeated instantiation.
_metadata_cache: Dict[str, Any] = {}


def _get_cached_metadata(registry, node_type: str) -> Optional[Any]:
    if node_type not in _metadata_cache:
        node_class = registry.get_node(node_type)
        if node_class:
            try:
                _metadata_cache[node_type] = node_class().metadata
            except Exception as e:
                logger.debug(f"Could not instantiate metadata for {node_type}: {e}")
                _metadata_cache[node_type] = None
        else:
            _metadata_cache[node_type] = None
    return _metadata_cache[node_type]


def clear_metadata_cache():
    _metadata_cache.clear()


def _find_handle_type(handles, handle_name: str) -> str:
    for h in (handles or []):
        if isinstance(h, str):
            if h == handle_name:
                return "any"
            continue
        if hasattr(h, "name") and h.name == handle_name:
            return h.type if hasattr(h, "type") else "any"
    return "any"


def _is_trigger_node(registry, node_type: str) -> bool:
    meta = _get_cached_metadata(registry, node_type)
    if not meta:
        return False
    node_type_attr = getattr(meta, "node_type", None)
    if node_type_attr:
        nt_str = node_type_attr.value if hasattr(node_type_attr, "value") else str(node_type_attr)
        if "trigger" in nt_str.lower():
            return True
    return "trigger" in node_type.lower()


# ═══════════════════════════════════════════════════════════════
# STRUCTURAL VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_structure(workflow: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    node_ids: set = set()

    for i, node in enumerate(nodes):
        nid = node.get("id", "")
        ntype = node.get("type", "")

        if not nid:
            issues.append(ValidationIssue(
                "missing_id", f"nodes[{i}]", "Node ID is missing"
            ))
        if not ntype:
            issues.append(ValidationIssue(
                "missing_type", f"nodes[{i}]", "Node type is missing"
            ))
        if nid and nid in node_ids:
            issues.append(ValidationIssue(
                "duplicate_id", f"nodes[{i}].id",
                f"Duplicate node ID: '{nid}'"
            ))
        if nid:
            node_ids.add(nid)

    # Edge reference checks
    for i, edge in enumerate(edges):
        src = edge.get("source", "")
        tgt = edge.get("target", "")

        if src and src not in node_ids:
            issues.append(ValidationIssue(
                "unknown_source", f"edges[{i}].source",
                f"Edge source '{src}' references non-existent node"
            ))
        if tgt and tgt not in node_ids:
            issues.append(ValidationIssue(
                "unknown_target", f"edges[{i}].target",
                f"Edge target '{tgt}' references non-existent node"
            ))
        if not edge.get("sourceHandle"):
            issues.append(ValidationIssue(
                "missing_source_handle", f"edges[{i}].sourceHandle",
                "Edge sourceHandle is missing"
            ))
        if not edge.get("targetHandle"):
            issues.append(ValidationIssue(
                "missing_target_handle", f"edges[{i}].targetHandle",
                "Edge targetHandle is missing"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════
# SEMANTIC/TOPOLOGY VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_topology(workflow: Dict[str, Any]) -> List[ValidationIssue]:
    from app.core.node_registry import node_registry

    issues: List[ValidationIssue] = []
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    nodes_by_id = {n.get("id"): n for n in nodes}

    # ── 1. Core ValidationEngine check ──
    try:
        from app.core.graph_builder.validation import ValidationEngine
        val_engine = ValidationEngine(node_registry)
        val_result = val_engine.validate_workflow(workflow)
        if hasattr(val_result, "errors") and val_result.errors:
            for err in val_result.errors:
                issues.append(ValidationIssue(
                    "core_validation", "workflow", str(err)
                ))
    except Exception as e:
        logger.debug(f"Core ValidationEngine check skipped: {e}")

    # ── 2. Handle compatibility check ──
    for edge in edges:
        source_node = nodes_by_id.get(edge.get("source"))
        target_node = nodes_by_id.get(edge.get("target"))
        if not source_node or not target_node:
            continue

        source_meta = _get_cached_metadata(node_registry, source_node.get("type"))
        target_meta = _get_cached_metadata(node_registry, target_node.get("type"))
        if not source_meta or not target_meta:
            continue

        output_type = _find_handle_type(
            getattr(source_meta, "outputs", []), edge.get("sourceHandle")
        )
        input_type = _find_handle_type(
            getattr(target_meta, "inputs", []), edge.get("targetHandle")
        )

        if not are_handles_compatible(output_type, input_type):
            issues.append(ValidationIssue(
                "incompatible_handles",
                f"edge({edge.get('source')}->{edge.get('target')})",
                f"Output '{edge.get('sourceHandle')}' "
                f"(type: {resolve_handle_type(output_type).value}) "
                f"cannot connect to input '{edge.get('targetHandle')}' "
                f"(type: {resolve_handle_type(input_type).value})"
            ))

    # ── 3. Required connections check ──
    for node in nodes:
        meta = _get_cached_metadata(node_registry, node.get("type"))
        if not meta:
            continue
        for inp in (getattr(meta, "inputs", None) or []):
            if not getattr(inp, "is_connection", False):
                continue
            if not getattr(inp, "required", True):
                continue

            has_connection = any(
                e.get("target") == node.get("id")
                and e.get("targetHandle") == inp.name
                for e in edges
            )
            if not has_connection:
                issues.append(ValidationIssue(
                    "missing_required_connection",
                    f"node({node.get('id')}).{inp.name}",
                    f"Node '{node.get('id')}' ({node.get('type')}) "
                    f"is missing required connection to '{inp.name}' input handle"
                ))

    # ── 4. Trigger-terminator rules ──
    webhook_triggers = [
        n for n in nodes
        if "webhook" in n.get("type", "").lower()
        and _is_trigger_node(node_registry, n.get("type"))
    ]
    if webhook_triggers:
        has_respond = any(n.get("type") == "RespondToWebhook" for n in nodes)
        has_end = any(n.get("type") == "EndNode" for n in nodes)
        if has_end and not has_respond:
            issues.append(ValidationIssue(
                "invalid_terminator", "workflow",
                "Webhook workflows MUST use RespondToWebhook, not EndNode. "
                "Replace EndNode with RespondToWebhook."
            ))

    return issues


def validate_workflow(workflow: Dict[str, Any]) -> List[ValidationIssue]:
    return validate_structure(workflow) + validate_topology(workflow)
