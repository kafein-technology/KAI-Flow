import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.node_registry import node_registry
from app.auth.dependencies import get_current_user
from app.core.credential_provider import credential_provider

logger = logging.getLogger(__name__)
router = APIRouter()

class NodeOptionsRequest(BaseModel):
    property_name: str
    values: Dict[str, Any] = {}

@router.get("")
async def get_all_nodes():
    """
    Retrieve the metadata for all registered nodes.
    This endpoint provides the frontend with all necessary information
    to render nodes and their configuration modals dynamically.
    """
    # Ensure nodes are discovered
    if not node_registry.nodes:
        node_registry.discover_nodes()
    
    nodes_list = []
    for name, node_class in node_registry.nodes.items():
        # Skip hidden aliases (like ReactAgent)
        if name in node_registry.hidden_aliases:
            continue
            
        try:
            instance = node_class()
            # Use model_dump instead of deprecated dict() and drop None fields
            metadata = (
                instance.metadata.model_dump(exclude_none=True)
                if hasattr(instance.metadata, "model_dump")
                else instance.metadata.dict(exclude_none=True)
            )
            # Add the node name to the metadata and ensure each node has an ID
            metadata["name"] = name
            metadata['id'] = name
            nodes_list.append(metadata)
        except Exception as e:
            logger.error(f"Failed to get metadata for node {name}: {e}", exc_info=True)
            # Skip failing nodes in production
            continue
    return nodes_list

@router.get("/categories")
async def get_node_categories():
    """
    Retrieve all available node categories.
    """
    categories = set()
    for name, node_class in node_registry.nodes.items():
        # Skip hidden aliases (like ReactAgent)
        if name in node_registry.hidden_aliases:
            continue
            
        try:
            instance = node_class()
            # Use model_dump instead of deprecated dict() and drop None fields
            metadata_dict = (
                instance.metadata.model_dump(exclude_none=True)
                if hasattr(instance.metadata, "model_dump")
                else instance.metadata.dict(exclude_none=True)
            )
            category = metadata_dict.get("category", "Other")
            categories.add(category)
        except Exception as e:
            logger.error(f"Failed to get category for node {name}: {e}", exc_info=True)
    
    # Convert to list of category objects
    categories_list = [
        {
            "name": category,
            "display_name": category.replace("_", " ").title(),
            "description": f"Nodes in the {category} category"
        }
        for category in sorted(categories)
    ]
    
    return categories_list

@router.get("/{node_type}")
async def get_node_details(node_type: str):
    """
    Get detailed information about a specific node type including
    configuration schema, examples, and usage instructions.
    """
    node_class = node_registry.get_node(node_type)
    if not node_class:
        raise HTTPException(status_code=404, detail=f"Node type '{node_type}' not found")
    
    try:
        instance = node_class()
        # Use model_dump instead of deprecated dict() and drop None fields
        metadata = (
            instance.metadata.model_dump(exclude_none=True)
            if hasattr(instance.metadata, "model_dump")
            else instance.metadata.dict(exclude_none=True)
        )
        
        # Add detailed configuration schema
        detailed_info = {
            **metadata,
            "configuration_schema": {
                "properties": {},
                "required": []
            },
            "examples": [],
            "usage_tips": [],
            "compatible_nodes": []
        }
        
        # Add configuration schema based on inputs
        for input_config in metadata.get("inputs", []):
            detailed_info["configuration_schema"]["properties"][input_config.get("name", "")] = {
                "type": input_config.get("type", "string"),
                "description": input_config.get("description", ""),
                "required": input_config.get("required", False),
                "default": input_config.get("default_value")
            }
            
            if input_config.get("required", False):
                detailed_info["configuration_schema"]["required"].append(input_config.get("name", ""))
        
        # Add usage examples based on node type
        if node_type == "OpenAIChat":
            detailed_info["examples"] = [
                {
                    "name": "Basic Chat",
                    "config": {
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.7,
                        "max_tokens": 150
                    }
                },
                {
                    "name": "Creative Writing",
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.9,
                        "max_tokens": 500
                    }
                }
            ]
            detailed_info["usage_tips"] = [
                "Lower temperature (0.1-0.3) for factual responses",
                "Higher temperature (0.7-0.9) for creative content",
                "Use system prompts to set behavior"
            ]
        
        return detailed_info
        
    except Exception as e:
        logger.error(f"Failed to get details for node {node_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve node details: {str(e)}")

@router.post("/validate-config")
async def validate_node_config(node_type: str, config: Dict[str, Any]):
    """
    Validate a node configuration without executing it.
    Useful for real-time validation in the canvas editor.
    """
    node_class = node_registry.get_node(node_type)
    if not node_class:
        raise HTTPException(status_code=404, detail=f"Node type '{node_type}' not found")
    
    try:
        # Try to create instance with config
        instance = node_class()
        instance.user_data = config
        
        # Basic validation
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required fields
        metadata = instance.metadata
        for input_config in metadata.inputs:
            if input_config.required and input_config.name not in config:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Required field '{input_config.name}' is missing")
        
        # Add warnings for recommended fields
        if node_type == "OpenAIChat" and "model" not in config:
            validation_result["warnings"].append("Model not specified, will use default")
        
        return validation_result
        
    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": []
        }

@router.get("/registry/stats")
async def get_registry_statistics():
    """
    Get statistics about the node registry.
    """
    nodes_by_category = {}
    total_nodes = len(node_registry.nodes)
    
    for name, node_class in node_registry.nodes.items():
        # Skip hidden aliases (like ReactAgent)
        if name in node_registry.hidden_aliases:
            continue
            
        try:
            instance = node_class()
            category = instance.metadata.category
            if category not in nodes_by_category:
                nodes_by_category[category] = 0
            nodes_by_category[category] += 1
        except Exception:
            continue
    
    return {
        "total_nodes": total_nodes,
        "categories": len(nodes_by_category),
        "nodes_by_category": nodes_by_category,
        "most_popular_category": max(nodes_by_category, key=nodes_by_category.get) if nodes_by_category else None
    }

@router.get("/search/{query}")
async def search_nodes(query: str):
    """
    Search nodes by name, description, or category.
    """
    results = []
    query_lower = query.lower()
    
    for name, node_class in node_registry.nodes.items():
        # Skip hidden aliases (like ReactAgent)
        if name in node_registry.hidden_aliases:
            continue
            
        try:
            instance = node_class()
            metadata = instance.metadata.dict()
            
            # Search in name, description, category
            searchable_text = f"{metadata.get('name', '')} {metadata.get('description', '')} {metadata.get('category', '')}".lower()
            
            if query_lower in searchable_text:
                results.append({
                    "node_type": name,
                    "name": metadata.get("name", ""),
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", ""),
                    "relevance_score": searchable_text.count(query_lower)
                })
        except Exception:
            continue
    
    # Sort by relevance
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:10]  # Return top 10 results

@router.post("/{node_type}/options")
async def get_node_property_options(
    node_type: str,
    request: NodeOptionsRequest,
    current_user=Depends(get_current_user),
):
    """
    Fill a dynamic field.

    The node declares `optionsMethod` on the property; this endpoint calls that
    method with the values currently entered in the panel and returns the list.
    """
    node_class = node_registry.get_node(node_type)
    if not node_class:
        raise HTTPException(status_code=404, detail=f"Node type '{node_type}' not found")

    try:
        instance = node_class()
    except Exception as e:
        logger.error(f"Could not create node {node_type}: {e}")
        raise HTTPException(status_code=500, detail="Node could not be created")

    prop = next(
        (p for p in instance._metadata.get("properties", []) if p.name == request.property_name),
        None,
    )
    if prop is None:
        raise HTTPException(
            status_code=404,
            detail=f"Property '{request.property_name}' not found on {node_type}",
        )

    method_name = getattr(prop, "optionsMethod", None)
    if not method_name:
        raise HTTPException(
            status_code=400,
            detail=f"Property '{request.property_name}' does not load options dynamically",
        )

    loader = getattr(instance, method_name, None)
    if not callable(loader):
        raise HTTPException(
            status_code=500,
            detail=f"Node {node_type} has no method named '{method_name}'",
        )

    try:
        instance.credentials = credential_provider.get_credentials_sync(current_user.id)
    except Exception as e:
        logger.warning(f"Could not load credentials for options request: {e}")
        instance.credentials = []

    try:
        return {"options": loader(request.values)}
    except Exception as e:
        logger.error(f"Loading options for {node_type}.{request.property_name} failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))