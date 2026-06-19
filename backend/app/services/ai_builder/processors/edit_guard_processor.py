import logging
import re
from typing import Dict, Any
from app.services.ai_builder.state import AIBuilderState

logger = logging.getLogger(__name__)


class EditGuardProcessor:
    def process(self, state: AIBuilderState) -> Dict[str, Any]:
        mode = state.get("mode", "build")
        original = state.get("original_workflow", {})
        validation_errors = state.get("validation_errors", [])

        if mode != "edit" or not original or validation_errors:
            return {}  # Skip guard if not editing or already has errors

        modified = state.get("current_workflow", {})
        question = state.get("question", "").lower()
        # Normalize: remove extra spaces, replace Turkish dotless-i with regular i for matching
        q_normalized = re.sub(r'\s+', ' ', question).strip()

        def type_matches_question(node_type: str, q: str) -> bool:
            """Check if any significant word from the CamelCase type name appears in the question."""
            words = re.findall(r'[A-Za-z][a-z]*|[A-Z]+', node_type)
            for w in words:
                w_lower = w.lower()
                if len(w_lower) > 2 and w_lower in q:
                    return True
            # Also check the full type without case (e.g. "openaichat" vs "openai" in question)
            type_lower = node_type.lower()
            # Check if question contains any contiguous substring of the type (min 4 chars)
            for i in range(len(type_lower)):
                for j in range(i + 4, len(type_lower) + 1):
                    substr = type_lower[i:j]
                    if substr in q:
                        return True
            return False

        def name_matches_question(node_name: str, node_type: str, q: str) -> bool:
            """Flexible name matching that handles spaces, underscores, and partial matches."""
            if not node_name:
                return False
            # Direct match
            if node_name in q:
                return True
            # Match with spaces instead of underscores (e.g. "openai_chat" matches "openai chat" or "open ai")
            name_spaced = node_name.replace("_", " ")
            if name_spaced in q:
                return True
            # Match individual significant parts (e.g. "openai" from "openai_chat")
            parts = node_name.split("_")
            significant_parts = [p for p in parts if len(p) > 2]
            if significant_parts and any(p in q for p in significant_parts):
                return True
            return False

        def data_field_matches_question(orig_data: dict, mod_data: dict, q: str) -> bool:
            """Check if any changed field's name appears in the question."""
            for k, v in mod_data.items():
                if k not in orig_data or orig_data[k] != v:
                    parts = k.lower().replace('-', '_').split('_')
                    if any(p in q for p in parts if len(p) > 2):
                        return True
            return False

        # If the LLM determines the user wants a paradigm shift (e.g. manual vs automatic), it sets this flag
        llm_declared_structural_change = modified.get("structural_change_made", False)

        orig_nodes = {n.get("id"): n for n in original.get("nodes", [])}
        mod_nodes = {n.get("id"): n for n in modified.get("nodes", [])}

        safe_nodes = []
        for node_id, orig_node in orig_nodes.items():
            if node_id in mod_nodes:
                mod_node = mod_nodes[node_id]
                node_name = orig_node.get("data", {}).get("name", "").lower()
                node_type = orig_node.get("type", "")

                if mod_node != orig_node:
                    is_authorized = False

                    # Smart bypass: Jeśli sztuczna inteligencja zdecydowała, że intencją jest zmiana strukturalna
                    if llm_declared_structural_change:
                        is_authorized = True
                    # Global edit keywords
                    elif any(w in q_normalized for w in ["all", "her", "bütün", "tüm", "hepsini", "tamamını"]):
                        is_authorized = True
                    # Flexible name matching
                    elif name_matches_question(node_name, node_type, q_normalized):
                        is_authorized = True
                    # Full type name check
                    elif node_type.lower() in q_normalized:
                        is_authorized = True
                    # CamelCase word splitting check
                    elif type_matches_question(node_type, q_normalized):
                        is_authorized = True
                    # Changed data field name check
                    elif data_field_matches_question(orig_node.get("data", {}), mod_node.get("data", {}), q_normalized):
                        is_authorized = True

                    if not is_authorized:
                        logger.warning(f"❌ [EDIT GUARD] Halting unauthorized change to node {node_id} ({node_name})")
                        safe_nodes.append(orig_node)
                    else:
                        logger.info(f"✅ [EDIT GUARD] Authorized change to node {node_id} ({node_name})")
                        safe_nodes.append(mod_node)
                else:
                    safe_nodes.append(mod_node)
            else:
                if not llm_declared_structural_change and not any(word in q_normalized for word in ["remove", "delete", "sil", "kaldır", "kaldırıldı"]):
                    logger.warning(f"❌ [EDIT GUARD] Halting unauthorized deletion of node {node_id}")
                    safe_nodes.append(orig_node)
                else:
                    logger.info(f"🗑️ [EDIT GUARD] Authorized deletion of node {node_id}")

        for node_id, mod_node in mod_nodes.items():
            if node_id not in orig_nodes:
                logger.info(f"➕ [EDIT GUARD] Authorized addition of new node {node_id} ({mod_node.get('type')})")
                safe_nodes.append(mod_node)

        # Safely preserve edges: if the LLM didn't return any edges, use the original ones to prevent disconnections.
        final_edges = modified.get("edges", [])
        if not final_edges:
            final_edges = original.get("edges", [])

        return {"current_workflow": {"nodes": safe_nodes, "edges": final_edges}}
