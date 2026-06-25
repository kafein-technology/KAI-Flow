import logging
from typing import List, Dict, Any

from .handle_types import resolve_handle_type, COMPATIBILITY_MATRIX, HandleType

logger = logging.getLogger(__name__)


def compile_node_catalog() -> str:
    from app.core.node_registry import node_registry

    lines = ["=== AVAILABLE NODES ===\n"]

    for meta in node_registry.get_all_nodes():
        display_name = getattr(meta, "display_name", None) or meta.name

        # Connection input handles (with type info)
        conn_inputs = []
        for inp in (meta.inputs or []):
            if getattr(inp, "is_connection", False):
                ht = resolve_handle_type(inp.type)
                req = "*" if getattr(inp, "required", True) else ""
                conn_inputs.append(f"{inp.name}({ht.value}){req}")

        # Connection output handles
        conn_outputs = []
        for out in (meta.outputs or []):
            if isinstance(out, str):
                conn_outputs.append(out)
            else:
                ht = resolve_handle_type(out.type) if hasattr(out, "type") else HandleType.DATA
                conn_outputs.append(f"{out.name}({ht.value})")

        # Configurable properties
        props = [p.name for p in (meta.properties or [])]

        # Shorten description
        desc = (meta.description or "")[:100]

        lines.append(
            f"• {meta.name} ({display_name}) [{meta.category}]\n"
            f"  {desc}\n"
            f"  INPUTS: {', '.join(conn_inputs) if conn_inputs else 'none'}\n"
            f"  OUTPUTS: {', '.join(conn_outputs) if conn_outputs else 'none'}\n"
            f"  PROPS: {', '.join(props) if props else 'none'}"
        )

    return "\n\n".join(lines)


def compile_connection_rules() -> str:
    from app.core.node_registry import node_registry

    lines = ["=== CONNECTION RULES ===\n"]

    # Type compatibility rules — compiled from matrix
    lines.append("HANDLE TYPE COMPATIBILITY:")
    for handle_type, compatible_with in COMPATIBILITY_MATRIX.items():
        if handle_type == HandleType.ANY:
            continue
        compat_names = sorted(h.value for h in compatible_with if h != HandleType.ANY)
        lines.append(f"  • {handle_type.value} can connect to: {', '.join(compat_names)}")
    lines.append("  • 'any' can connect to/from any handle type\n")

    # Required connections — compiled from node metadata
    lines.append("REQUIRED CONNECTIONS (marked with * above):")
    for meta in node_registry.get_all_nodes():
        required_handles = []
        for inp in (meta.inputs or []):
            if getattr(inp, "is_connection", False) and getattr(inp, "required", True):
                ht = resolve_handle_type(inp.type)
                required_handles.append(f"'{inp.name}' ({ht.value})")
        if required_handles:
            lines.append(f"  • {meta.name} requires: {', '.join(required_handles)}")

    # Trigger/terminator rules
    lines.append("\nWORKFLOW RULES:")
    lines.append("  • Webhook-triggered workflows MUST end with 'RespondToWebhook', never 'EndNode'.")
    lines.append("  • Regular workflows should end with 'EndNode'.")
    lines.append("  • Provider nodes (LLM, Embeddings, Tools) connect via side handles (bottom→top), not main flow (left→right).")

    return "\n".join(lines)


def compile_parameterization_schema(node_types: List[str]) -> str:
    from app.core.node_registry import node_registry

    lines = ["=== PROPERTY SCHEMA FOR SELECTED NODES ===\n"]

    for nt in node_types:
        node_class = node_registry.get_node(nt)
        if not node_class:
            continue
        try:
            meta = node_class().metadata
            display_name = getattr(meta, "display_name", None) or meta.name

            prop_lines = []
            for prop in (meta.properties or []):
                req_str = "REQUIRED" if getattr(prop, "required", True) else "optional"
                prop_type = prop.type.value if hasattr(prop.type, "value") else str(prop.type)
                default_str = f", default={prop.default!r}" if prop.default is not None else ""
                desc_str = f" — {prop.description}" if prop.description else ""

                prop_lines.append(
                    f"  • data.{prop.name}: type={prop_type}, {req_str}{default_str}{desc_str}"
                )

            lines.append(
                f"NODE: {meta.name} ({display_name})\n"
                f"  Description: {meta.description or ''}\n"
                f"  Editable Properties:\n"
                + ("\n".join(prop_lines) if prop_lines else "  (none)")
            )
        except Exception as e:
            logger.debug(f"Could not extract schema for {nt}: {e}")

    return "\n\n".join(lines)
