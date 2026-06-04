from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ConnectionSuggestion:
    """Represents a suggested connection between nodes"""
    source_id: str
    source_handle: str
    target_id: str
    target_handle: str
    confidence: float
    reason: str

class AutoConnector:
    """Automatically suggests and validates node connections"""
    
    def __init__(self, registry: Dict[str, Any]):
        self.registry = registry
        self.compatibility_map = self._build_compatibility_map()
    
    def _build_compatibility_map(self) -> Dict[Tuple[str, str], float]:
        """Build a map of compatible input/output types with confidence scores"""
        return {
            # Exact matches
            ("llm", "llm"): 1.0,
            ("prompt", "prompt"): 1.0,
            ("tool", "tool"): 1.0,
            ("chain", "chain"): 1.0,
            ("agent", "agent"): 1.0,
            
            # Common patterns
            ("llm", "chain"): 0.9,
            ("llm", "agent"): 0.9,
            ("prompt", "llm"): 0.95,
            ("prompt", "chain"): 0.9,
            ("prompt", "agent"): 0.85,
            ("tool", "agent"): 0.95,
            ("tools", "agent"): 0.95,
            ("memory", "agent"): 0.9,
            ("memory", "chain"): 0.85,
            ("chain", "agent"): 0.8,
            ("text", "prompt"): 0.9,
            ("text", "llm"): 0.7,
            ("document", "vector_store"): 0.95,
            ("vector_store", "retriever"): 0.95,
            ("retriever", "chain"): 0.9,
            ("retriever", "agent"): 0.85,
            
            # Any type can connect with lower confidence
            ("any", "any"): 0.5,
        }
    
    def can_connect(
        self, 
        source_node: Dict[str, Any], 
        target_node: Dict[str, Any], 
        source_handle: str = "output", 
        target_handle: str = "input"
    ) -> Tuple[bool, float, str]:
        """
        Check if two nodes can be connected
        Returns: (can_connect, confidence, reason)
        """
        source_type = self._get_output_type(source_node, source_handle)
        target_type = self._get_input_type(target_node, target_handle)
        
        # Check exact match
        if source_type == target_type:
            return True, 1.0, f"Exact type match: {source_type}"
        
        # Check compatibility map
        confidence = self.compatibility_map.get((source_type, target_type), 0)
        
        # Check reverse compatibility for bidirectional connections
        if confidence == 0:
            confidence = self.compatibility_map.get((target_type, source_type), 0) * 0.8
        
        # Check any type compatibility
        if confidence == 0:
            if source_type == "any" or target_type == "any":
                confidence = 0.5
            else:
                # Check for any-any fallback
                confidence = self.compatibility_map.get(("any", "any"), 0.3)
        
        if confidence > 0:
            reason = f"Compatible types: {source_type} → {target_type} (confidence: {confidence:.0%})"
            return True, confidence, reason
        
        return False, 0, f"Incompatible types: {source_type} → {target_type}"
    
    def suggest_connections(
        self, 
        nodes: List[Dict[str, Any]], 
        existing_edges: Optional[List[Dict[str, Any]]] = None
    ) -> List[ConnectionSuggestion]:
        """Suggest possible connections between nodes"""
        suggestions = []
        existing_edges = existing_edges or []
        
        # Create a set of existing connections for quick lookup
        existing_connections = set()
        for edge in existing_edges:
            key = (
                edge["source"], 
                edge.get("sourceHandle", "output"),
                edge["target"],
                edge.get("targetHandle", "input")
            )
            existing_connections.add(key)
        
        # Check all possible connections
        for source in nodes:
            source_outputs = self._get_node_outputs(source)
            
            for target in nodes:
                if source["id"] == target["id"]:
                    continue  # Can't connect to self
                
                target_inputs = self._get_node_inputs(target)
                
                for output in source_outputs:
                    for input_spec in target_inputs:
                        # Skip if connection already exists
                        connection_key = (
                            source["id"],
                            output["name"],
                            target["id"],
                            input_spec["name"]
                        )
                        if connection_key in existing_connections:
                            continue
                        
                        # Check if connection is possible
                        can_connect, confidence, reason = self.can_connect(
                            source, target, 
                            output["name"], 
                            input_spec["name"]
                        )
                        
                        if can_connect and confidence >= 0.5:
                            suggestions.append(ConnectionSuggestion(
                                source_id=source["id"],
                                source_handle=output["name"],
                                target_id=target["id"],
                                target_handle=input_spec["name"],
                                confidence=confidence,
                                reason=reason
                            ))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggestions
    
    def validate_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all connections in a workflow"""
        nodes = workflow_data.get("nodes", [])
        edges = workflow_data.get("edges", [])
        
        # Create node lookup
        node_map = {node["id"]: node for node in nodes}
        
        errors = []
        warnings = []
        valid_connections = []
        
        for edge in edges:
            source_id = edge.get("source")
            target_id = edge.get("target")
            source_handle = edge.get("sourceHandle", "output")
            target_handle = edge.get("targetHandle", "input")
            
            # Check if nodes exist
            if source_id not in node_map:
                errors.append(f"Source node '{source_id}' not found")
                continue
            
            if target_id not in node_map:
                errors.append(f"Target node '{target_id}' not found")
                continue
            
            # Validate connection
            source_node = node_map[source_id]
            target_node = node_map[target_id]
            
            can_connect, confidence, reason = self.can_connect(
                source_node, target_node,
                source_handle, target_handle
            )
            
            if not can_connect:
                errors.append(f"Invalid connection: {source_id}.{source_handle} → {target_id}.{target_handle} - {reason}")
            elif confidence < 0.7:
                warnings.append(f"Low confidence connection: {source_id}.{source_handle} → {target_id}.{target_handle} - {reason}")
                valid_connections.append(edge)
            else:
                valid_connections.append(edge)
        
        # Check for required inputs
        for node in nodes:
            node_inputs = self._get_node_inputs(node)
            connected_inputs = set()
            
            for edge in edges:
                if edge["target"] == node["id"]:
                    connected_inputs.add(edge.get("targetHandle", "input"))
            
            for input_spec in node_inputs:
                if input_spec.get("required", False) and input_spec["name"] not in connected_inputs:
                    # Check if user provided the input
                    user_data = node.get("data", {})
                    if input_spec["name"] not in user_data:
                        warnings.append(f"Node '{node['id']}' missing required input: {input_spec['name']}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "valid_connections": valid_connections,
            "total_connections": len(edges),
            "suggestions": self.suggest_connections(nodes, edges) if len(errors) == 0 else []
        }
    
    def _get_output_type(self, node: Dict[str, Any], handle: str = "output") -> str:
        """Get the output type of a node"""
        node_type = node.get("type", "")
        node_class = self.registry.get(node_type)
        
        if node_class and (hasattr(node_class, '_metadata') or hasattr(node_class, '_metadatas')):
            metadata = getattr(node_class, '_metadata', None) or getattr(node_class, '_metadatas', {})
            outputs = metadata.get("outputs", [])
            
            for output in outputs:
                if output.get("name") == handle:
                    return output.get("type", "any")
        
        # Default type mappings
        type_map = {
            "OpenAIChat": "llm",
            "AnthropicChat": "llm",
            "PromptTemplate": "prompt",
            "ReactAgentPrompt": "prompt",
            "GoogleSearch": "tool",
            "Wikipedia": "tool",
            "Calculator": "tool",
            "BufferMemory": "memory",
            "ConversationSummaryMemory": "memory",
            "LLMChain": "chain",
            "ReactAgent": "agent",
            "VectorStore": "vector_store",
            "PDFLoader": "document",
        }
        
        for key, value in type_map.items():
            if key in node_type:
                return value
        
        return "any"
    
    def _get_input_type(self, node: Dict[str, Any], handle: str = "input") -> str:
        """Get the input type of a node"""
        node_type = node.get("type", "")
        node_class = self.registry.get(node_type)
        
        if node_class and (hasattr(node_class, '_metadata') or hasattr(node_class, '_metadatas')):
            metadata = getattr(node_class, '_metadata', None) or getattr(node_class, '_metadatas', {})
            inputs = metadata.get("inputs", [])
            
            for input_spec in inputs:
                if input_spec.get("name") == handle:
                    return input_spec.get("type", "any")
        
        # Default handle type mappings
        handle_map = {
            "llm": "llm",
            "prompt": "prompt",
            "tools": "tools",
            "memory": "memory",
            "chain": "chain",
            "agent": "agent",
            "document": "document",
            "vector_store": "vector_store",
        }
        
        return handle_map.get(handle, "any")
    
    def _get_node_outputs(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all outputs of a node"""
        node_type = node.get("type", "")
        node_class = self.registry.get(node_type)
        
        if node_class and (hasattr(node_class, '_metadata') or hasattr(node_class, '_metadatas')):
            metadata = getattr(node_class, '_metadata', None) or getattr(node_class, '_metadatas', {})
            return metadata.get("outputs", [{"name": "output", "type": "any"}])
        
        return [{"name": "output", "type": self._get_output_type(node)}]
    
    def _get_node_inputs(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all inputs of a node"""
        node_type = node.get("type", "")
        node_class = self.registry.get(node_type)
        
        if node_class and (hasattr(node_class, '_metadata') or hasattr(node_class, '_metadatas')):
            metadata = getattr(node_class, '_metadata', None) or getattr(node_class, '_metadatas', {})
            return metadata.get("inputs", [])
        
        # Fallback: assume a generic 'input' handle if the node does not
        # explicitly declare inputs in its metadata. This ensures the auto
        # connector can still suggest reasonable defaults.
        return [{"name": "input", "type": "any", "required": False}]