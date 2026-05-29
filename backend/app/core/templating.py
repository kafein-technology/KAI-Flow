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


class TemplateValue:
    """A custom value wrapper that behaves like the primary resolved output value (which can be a string,
    list, or dict) but also delegates attribute and item lookups to the full node output dictionary 
    or nested collections to allow path-based access (like node.property or node.0.property).
    """
    def __init__(self, value, dict_data=None):
        self.raw_value = value
        self.dict_data = dict_data or {}

    def __getattr__(self, name):
        # 1. Try to find the attribute in self.dict_data (wrapper envelope)
        if name in self.dict_data:
            return wrap_template_value(self.dict_data[name])
        
        # 2. Try to find the attribute on raw_value if it's a dictionary
        if isinstance(self.raw_value, dict) and name in self.raw_value:
            return wrap_template_value(self.raw_value[name])

        # 3. If raw_value is a list/tuple, check if name is a digit/index
        if isinstance(self.raw_value, (list, tuple)) and name.isdigit():
            idx = int(name)
            if 0 <= idx < len(self.raw_value):
                return wrap_template_value(self.raw_value[idx])

        # 4. If name is a common document content property and raw_value is a string, return the string itself.
        if name in ("page_content", "text", "content", "output") and isinstance(self.raw_value, str):
            return self.raw_value

        # 5. If self.dict_data contains a "documents" or "chunks" list, and the attribute is page_content or metadata
        for list_key in ("documents", "chunks"):
            if list_key in self.dict_data and isinstance(self.dict_data[list_key], list) and self.dict_data[list_key]:
                first_item = self.dict_data[list_key][0]
                if isinstance(first_item, dict) and name in first_item:
                    return wrap_template_value(first_item[name])
                elif hasattr(first_item, name):
                    return wrap_template_value(getattr(first_item, name))

        # 6. Delegate to raw_value's attributes if it has them
        if hasattr(self.raw_value, name):
            return wrap_template_value(getattr(self.raw_value, name))
            
        raise AttributeError(f"'TemplateValue' object has no attribute '{name}'")

    def __getitem__(self, key):
        # 1. Try to look up in self.dict_data
        if isinstance(key, str) and key in self.dict_data:
            return wrap_template_value(self.dict_data[key])
            
        # 2. Try to look up in raw_value if it's a dict or list
        try:
            if isinstance(self.raw_value, (dict, list, tuple)):
                lookup_key = int(key) if (isinstance(key, str) and key.isdigit() and isinstance(self.raw_value, (list, tuple))) else key
                return wrap_template_value(self.raw_value[lookup_key])
        except (KeyError, IndexError, TypeError, ValueError):
            pass

        # 3. If key is a digit/index string (like "0"), and self.dict_data has a "documents" or "chunks" list:
        if isinstance(key, (int, str)):
            try:
                idx = int(key)
                for list_key in ("documents", "chunks"):
                    if list_key in self.dict_data and isinstance(self.dict_data[list_key], list):
                        list_val = self.dict_data[list_key]
                        if 0 <= idx < len(list_val):
                            return wrap_template_value(list_val[idx])
            except (ValueError, TypeError):
                pass

        # 4. Fallback to dictionary key lookups in self.dict_data if key is string
        if isinstance(key, str):
            if isinstance(self.raw_value, dict) and key in self.raw_value:
                return wrap_template_value(self.raw_value[key])

        raise KeyError(f"'TemplateValue' object has no key/index '{key}'")

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __str__(self):
        return str(self.raw_value)

    def __repr__(self):
        return repr(self.raw_value)

    def __eq__(self, other):
        if isinstance(other, TemplateValue):
            return self.raw_value == other.raw_value
        return self.raw_value == other

    def __len__(self):
        try:
            return len(self.raw_value)
        except TypeError:
            return 0

    def __iter__(self):
        if isinstance(self.raw_value, (list, tuple, dict)):
            for item in self.raw_value:
                yield wrap_template_value(item)
        else:
            yield self

    def __add__(self, other):
        return str(self) + str(other)

    def __radd__(self, other):
        return str(other) + str(self)


def wrap_template_value(val):
    if isinstance(val, TemplateValue):
        return val
    if isinstance(val, dict):
        return TemplateValue(val.get("output", val), val)
    if isinstance(val, (list, tuple)):
        return TemplateValue(val, None)
    return val


def normalize_display_name(name: str) -> str:
    """Normalize a display name to a Jinja-safe identifier.
    
    Example:
        "OpenAI GPT" -> "openai_gpt"
    """
    if not name:
        return ""
    
    normalized = re.sub(r"[^0-9a-zA-Z_]+", "_", name.lower()).strip("_")
    if not normalized:
        return ""
    
    # Jinja identifiers should not start with a digit
    if normalized[0].isdigit():
        normalized = f"n_{normalized}"
    
    return normalized


_global_registries = {}


def register_global_registry(key: str, registry: Dict[str, Any]) -> None:
    """Register a workflow's nodes registry globally so it is accessible as fallback during execution."""
    if key and registry:
        _global_registries[str(key)] = registry


def get_primary_output(node_id: str, state: FlowState) -> Any:
    """Determine the primary output value for a given node from FlowState.

    Heuristic:
    - If node_outputs[node_id] is a dict:
      - Peel off the standardized wrapper (which has success, nodeId, output, etc.)
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
        
    # Check if this is the standardized node output wrapper and unwrap it
    if isinstance(node_output, dict) and "success" in node_output and "output" in node_output and "nodeId" in node_output:
        node_output = node_output["output"]
    
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
    # Fallback to globally registered registries if none provided
    if not nodes_registry:
        session_id = getattr(state, "session_id", None)
        workflow_id = getattr(state, "workflow_id", None)
        if session_id:
            nodes_registry = _global_registries.get(str(session_id))
        if not nodes_registry and workflow_id:
            nodes_registry = _global_registries.get(str(workflow_id))
            
    context: Dict[str, Any] = {}
    
    # 1. Add current_input as 'input' (allows {{input}} to work like a chat system)
    if hasattr(state, 'current_input') and state.current_input is not None:
        context['input'] = state.current_input
        
    # 2. Add webhook data for webhook-triggered workflows as fallback (only if not already in node_outputs to avoid collisions)
    if hasattr(state, 'webhook_data') and state.webhook_data:
        context['webhook_data'] = state.webhook_data
        
        # Only add webhook_trigger fallback if it won't be added in step 3 from node_outputs
        has_webhook_output = any("webhook" in nid.lower() for nid in getattr(state, "node_outputs", {}).keys())
        if not has_webhook_output:
            webhook_payload = state.webhook_data.get('data', state.webhook_data)
            primary_val = webhook_payload
            if isinstance(webhook_payload, dict):
                primary_val = webhook_payload.get('input', webhook_payload.get('message', webhook_payload))
            
            # Wrap in TemplateValue so it supports both simple values and nested path lookups
            dict_data = {
                "webhook_data": state.webhook_data,
                "output": state.webhook_data,
            }
            if isinstance(state.webhook_data, dict):
                dict_data.update(state.webhook_data)
                
            context['webhook_trigger'] = TemplateValue(primary_val, dict_data)
            logger.debug("[TEMPLATE] Added fallback webhook_trigger TemplateValue to context")

    # 3. Add executed node outputs with friendly aliases
    has_node_outputs = hasattr(state, "node_outputs") and bool(state.node_outputs)
    
    if has_node_outputs:
        for other_node_id in state.node_outputs.keys():
            alias_candidates: List[tuple[str, str]] = []
            
            # Lookup node definition from registry if available
            graph_node = None
            if nodes_registry:
                graph_node = nodes_registry.get(other_node_id)
                
            # Safe fallback: parse type from node_id (e.g. "WebhookTrigger__uuid" -> "webhook_trigger")
            if "__" in other_node_id:
                parts = other_node_id.split("__")
                type_part = parts[0]
                # Split CamelCase to snake_case (e.g. WebhookTrigger -> webhook_trigger)
                snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', type_part).lower()
                alias_candidates.append(("parsed_type_snake", snake_name))
                alias_candidates.append(("parsed_type_raw", type_part))
                
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
            node_output = state.node_outputs.get(other_node_id)
            for source_type, raw_name in alias_candidates:
                normalized = normalize_display_name(raw_name)
                if not normalized:
                    continue
                if normalized in context:
                    continue
                
                # Wrap primary value with full output dictionary for nested property access (e.g. ${{node.property}})
                context[normalized] = TemplateValue(primary_value, node_output if isinstance(node_output, dict) else {})
                
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
