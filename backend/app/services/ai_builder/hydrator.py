import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def hydrate_with_defaults(skeleton: Dict[str, Any]) -> Dict[str, Any]:
    from app.core.node_registry import node_registry
    hydrated_nodes = []
    
    for node in skeleton.get("nodes", []):
        node_id = node.get("id")
        node_type = node.get("type")
        node_data = node.get("data", {})
        node_name = node_data.get("name", node_id)
        
        # Get defaults from registry
        properties = {}
        node_class = node_registry.get_node(node_type)
        if node_class:
            try:
                metadata = node_class().metadata
                for prop in (metadata.properties or []):
                    properties[prop.name] = prop.default if prop.default is not None else ""
            except Exception as e:
                logger.error(f"Failed to read metadata for {node_type}: {e}")
                
        # Keep name and override default values with whatever the skeleton returned
        properties["name"] = node_name
        for k, v in node_data.items():
            if k != "name":
                properties[k] = v
                
        hydrated_nodes.append({
            "id": node_id,
            "type": node_type,
            "data": properties
        })
        
    return {
        "nodes": hydrated_nodes,
        "edges": skeleton.get("edges", [])
    }
