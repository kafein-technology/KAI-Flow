"""
KAI-Flow Centralized Templating Engine
======================================

Provides unified, recursive, and Unicode-safe Jinja2 rendering utilities
for resolving templates in user inputs, nested configurations (dicts, lists),
and connection contexts across all node types.

AUTHORS: KAI-Flow Workflow Orchestration Team
VERSION: 1.0.0
LICENSE: Proprietary - KAI-Flow Platform
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List, Union

from jinja2 import Environment
from app.core.state import FlowState

logger = logging.getLogger(__name__)

# Custom Jinja2 environment with Unicode-safe tojson filter
# This prevents Turkish/Unicode characters from being escaped to \uXXXX format
def _tojson_unicode(value):
    """JSON encode preserving Unicode characters (no ASCII escaping)"""
    return json.dumps(value, ensure_ascii=False, default=str)

_jinja_env = Environment()
_jinja_env.filters['tojson'] = _tojson_unicode


def normalize_display_name(name: str) -> str:
    """Normalize a display name to a Jinja-safe identifier.
    
    Example:
        "OpenAI GPT" -> "openai_gpt"
    """
    if not name:
        return ""
    
    normalized = re.sub(r"[^0-9a-zA-Z_]+", "_", name).strip("_")
    if not normalized:
        return ""
    
    # Jinja identifiers should not start with a digit
    if normalized[0].isdigit():
        normalized = f"n_{normalized}"
    
    return normalized


def get_primary_output(node_id: str, state: FlowState) -> Any:
    """Determine the primary output value for a given node from FlowState.

    Heuristic:
    - If node_outputs[node_id] is a dict:
      - Prefer 'output'
      - Then 'content'
      - If only one key, return that single value
      - Otherwise return the entire dict
    - Otherwise, return the stored value directly.
    """
    if not hasattr(state, "node_outputs"):
        return None
    
    node_output = state.node_outputs.get(node_id)
    if node_output is None:
        return None
    
    if isinstance(node_output, dict):
        if "output" in node_output:
            return node_output["output"]
        if "content" in node_output:
            return node_output["content"]
        if len(node_output) == 1:
            return next(iter(node_output.values()))
        return node_output
    
    return node_output


def build_template_context(state: FlowState, nodes_registry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the templating context from state, inputs, webhook data, and node outputs."""
    context: Dict[str, Any] = {}
    
    # 1. Add current_input as 'input' (allows {{input}} to work like a chat system)
    if hasattr(state, 'current_input') and state.current_input is not None:
        context['input'] = state.current_input
        
    # 2. Add webhook data for webhook-triggered workflows
    if hasattr(state, 'webhook_data') and state.webhook_data:
        context['webhook_data'] = state.webhook_data
        webhook_payload = state.webhook_data.get('data', state.webhook_data)
        context['webhook_trigger'] = webhook_payload
        logger.debug(f"[TEMPLATE] Added webhook_trigger to context keys: {list(webhook_payload.keys()) if isinstance(webhook_payload, dict) else type(webhook_payload)}")

    # 3. Add executed node outputs with friendly aliases
    has_node_outputs = hasattr(state, "node_outputs") and bool(state.node_outputs)
    
    if has_node_outputs:
        for other_node_id in state.node_outputs.keys():
            alias_candidates: List[tuple[str, str]] = []
            
            # Lookup node definition from registry if available
            graph_node = None
            if nodes_registry:
                graph_node = nodes_registry.get(other_node_id)
                
            if graph_node:
                # UI Name (user_data["name"]) - highest priority
                ui_name = None
                try:
                    user_data = getattr(graph_node, "user_data", {}) or {}
                    if isinstance(user_data, dict):
                        ui_name = user_data.get("name")
                except Exception:
                    pass
                if ui_name:
                    alias_candidates.append(("ui_name", str(ui_name)))
                
                # Pydantic NodeMetadata from node instance
                node_meta_model = None
                try:
                    node_meta_model = getattr(graph_node.node_instance, "metadata", None)
                except Exception:
                    pass
                if node_meta_model is not None:
                    display_name = getattr(node_meta_model, "display_name", None)
                    meta_name = getattr(node_meta_model, "name", None)
                    if display_name:
                        alias_candidates.append(("display_name", str(display_name)))
                    if meta_name and meta_name != display_name:
                        alias_candidates.append(("meta_name", str(meta_name)))
                        
                # GraphNodeInstance metadata dict fallback
                metadata_dict = getattr(graph_node, "metadata", {}) or {}
                if isinstance(metadata_dict, dict):
                    md_display = metadata_dict.get("display_name")
                    md_name = metadata_dict.get("name")
                    if md_display:
                        alias_candidates.append(("graph_display_name", str(md_display)))
                    if md_name and md_name != md_display:
                        alias_candidates.append(("graph_name", str(md_name)))
            
            # Final fallback: node_id
            alias_candidates.append(("node_id", str(other_node_id)))
            
            primary_value = get_primary_output(other_node_id, state)
            if primary_value is None:
                continue
                
            # If the node is a StartNode, also allow {{input}} fallback mapping
            try:
                node_type = getattr(graph_node, 'type', None)
                if node_type == 'StartNode' and 'input' not in context:
                    context['input'] = primary_value
            except Exception:
                pass
                
            # Normalize and assign aliases without overwriting existing keys
            for source_type, raw_name in alias_candidates:
                normalized = normalize_display_name(raw_name)
                if not normalized:
                    continue
                if normalized in context:
                    continue
                context[normalized] = primary_value
                logger.debug(f"[TEMPLATE] Added alias '{normalized}' ({source_type}) into context")
                
    return context


def render_template_string(template_str: str, context: Dict[str, Any], node_id: str) -> str:
    """Render a single template string using context. Supports both ${{var}} and {{var}}."""
    if "{{" not in template_str or "}}" not in template_str:
        return template_str

    try:
        # Convert ${{var}} to {{var}} syntax for standard Jinja rendering
        processed_template = template_str.replace("${" + "{", "{{").replace("}}", "}}")
        template = _jinja_env.from_string(processed_template)
        return template.render(**context)
    except Exception as e:
        logger.warning(f"Jinja rendering failed for node {node_id}: {e}")
        return template_str


def render_value_recursively(value: Any, context: Dict[str, Any], node_id: str) -> Any:
    """Walk value and render any strings recursively (dicts, lists, tuples)."""
    if isinstance(value, str):
        return render_template_string(value, context, node_id)
    elif isinstance(value, dict):
        return {k: render_value_recursively(v, context, node_id) for k, v in value.items()}
    elif isinstance(value, list):
        return [render_value_recursively(v, context, node_id) for v in value]
    elif isinstance(value, tuple):
        return tuple(render_value_recursively(v, context, node_id) for v in value)
    return value


def apply_jinja_to_inputs(
    inputs: Dict[str, Any],
    state: FlowState,
    node_id: str,
    nodes_registry: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Resolve Jinja templates dynamically on all input fields, including nested dictionaries/lists.
    
    If state has variables, those are also merged into context.
    """
    if not inputs:
        return inputs
        
    try:
        context = build_template_context(state, nodes_registry)
        
        # Merge state variables into context (do not overwrite primary context values)
        if hasattr(state, 'variables') and isinstance(state.variables, dict):
            for k, v in state.variables.items():
                if k not in context:
                    context[k] = v
                    
        if not context:
            logger.debug(f"[TEMPLATE] No context built for node {node_id}; skipping templating")
            return inputs
            
        logger.debug(f"[TEMPLATE] Applying dynamic templating to inputs of node {node_id}")
        rendered_inputs = render_value_recursively(inputs, context, node_id)
        
        # Check if the inputs contain Jinja templates
        has_jinja = False
        try:
            has_jinja = "{{" in str(inputs)
        except Exception:
            pass

        # Print before and after for terminal visualization if there's any Jinja template in inputs
        if has_jinja:
            print(f"\n[JINJA TEMPLATING] Node: {node_id}")
            print(f"   BEFORE: {inputs}")
            print(f"   AFTER : {rendered_inputs}\n")
            
        return rendered_inputs
        
    except Exception as e:
        logger.error(f"Failed to apply dynamic templating for node {node_id}: {e}")
        return inputs
