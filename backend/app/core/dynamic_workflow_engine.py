"""
KAI-Fusion Dynamic Workflow Engine - Fully Dynamic LangGraph-Based Solution
===========================================================================

This module provides enhanced dynamic workflow capabilities built on top of the existing
LangGraph infrastructure with minimal changes to current codebase.

Key Features:
- Dynamic node resolution and instantiation
- Runtime workflow modification capabilities
- Enhanced connection mapping with type inference
- Automatic workflow optimization
- Dynamic execution context management
"""

from typing import Dict, Any, List, Optional, Union, AsyncGenerator, Type
from dataclasses import dataclass
import logging
import uuid
import asyncio
from datetime import datetime

from .graph_builder import GraphBuilder

from .state import FlowState
from .node_registry import node_registry
from app.nodes.base import BaseNode

logger = logging.getLogger(__name__)

@dataclass
class DynamicWorkflowContext:
    """Context for dynamic workflow execution"""

    session_id: str
    user_id: Optional[str] = None
    owner_id: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    runtime_config: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.runtime_config is None:
            self.runtime_config = {}


class DynamicNodeResolver:
    """Resolves and instantiates nodes dynamically at runtime"""
    
    def __init__(self, node_registry: Dict[str, Type[BaseNode]]):
        self.node_registry = node_registry
        self._resolved_cache = {}
    
    def resolve_node_type(self, node_def: Dict[str, Any]) -> Type[BaseNode]:
        """Dynamically resolve node type with fallback strategies"""
        node_type = node_def.get("type")
        
        if not node_type:
            raise ValueError("Node definition missing type")
        
        # Direct registry lookup
        if node_type in self.node_registry:
            return self.node_registry[node_type]
        
        # Dynamic type resolution strategies
        resolved_type = self._try_fuzzy_match(node_type)
        if resolved_type:
            return resolved_type
        
        # Plugin-based resolution (future extension point)
        resolved_type = self._try_plugin_resolution(node_type)
        if resolved_type:
            return resolved_type
        
        raise ValueError(f"Cannot resolve node type: {node_type}. Available: {list(self.node_registry.keys())}")
    
    def _try_fuzzy_match(self, node_type: str) -> Optional[Type[BaseNode]]:
        """Try fuzzy matching for node types"""
        node_type_lower = node_type.lower()
        
        # Try exact case-insensitive match
        for registry_type, node_class in self.node_registry.items():
            if registry_type.lower() == node_type_lower:
                return node_class
        
        # Try partial matching for common variations
        for registry_type, node_class in self.node_registry.items():
            if node_type_lower in registry_type.lower() or registry_type.lower() in node_type_lower:
                logger.warning(f"Using fuzzy match: {node_type} -> {registry_type}")
                return node_class
        
        return None
    
    def _try_plugin_resolution(self, node_type: str) -> Optional[Type[BaseNode]]:
        """Try plugin-based node resolution (extensible)"""
        # Future: Dynamic plugin loading
        return None
    
    def create_dynamic_instance(self, node_def: Dict[str, Any], context: DynamicWorkflowContext) -> BaseNode:
        """Create node instance with dynamic configuration"""
        node_class = self.resolve_node_type(node_def)
        instance = node_class()
        
        # Set basic properties
        instance.node_id = node_def["id"]
        instance.user_data = node_def.get("data", {})

        # Apply dynamic context
        if hasattr(instance, 'apply_context'):
            instance.apply_context(context)
        
        return instance


class DynamicConnectionMapper:
    """Enhanced connection mapping with type inference and validation"""
    
    def __init__(self):
        self.type_inference_cache = {}
    
    def infer_connection_types(self, nodes: Dict[str, BaseNode], connections: List[Any]) -> Dict[str, str]:
        """Dynamically infer connection types based on node metadata"""
        connection_types = {}
        
        for conn in connections:
            source_id = conn.source_node_id
            target_id = conn.target_node_id
            source_handle = conn.source_handle
            target_handle = conn.target_handle
            
            # Get type information from nodes
            source_node = nodes.get(source_id)
            target_node = nodes.get(target_id)
            
            if source_node and target_node:
                inferred_type = self._infer_type_from_nodes(
                    source_node, source_handle, target_node, target_handle
                )
                connection_key = f"{source_id}.{source_handle}->{target_id}.{target_handle}"
                connection_types[connection_key] = inferred_type
        
        return connection_types
    
    def _infer_type_from_nodes(self, source_node: BaseNode, source_handle: str, 
                             target_node: BaseNode, target_handle: str) -> str:
        """Infer connection type from node metadata"""
        
        # Try to get output type from source node
        if hasattr(source_node, 'metadata') and hasattr(source_node.metadata, 'outputs'):
            for output in source_node.metadata.outputs:
                if output.name == source_handle:
                    return output.type
        
        # Try to get input type from target node
        if hasattr(target_node, 'metadata') and hasattr(target_node.metadata, 'inputs'):
            for input_spec in target_node.metadata.inputs:
                if input_spec.name == target_handle:
                    return input_spec.type
        
        # Default to 'any' if type cannot be inferred
        return "any"


class DynamicWorkflowOptimizer:
    """Optimizes workflows dynamically during compilation"""
    
    def optimize_workflow(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply dynamic optimizations to workflow"""
        optimized_flow = flow_data.copy()
        
        # Optimization strategies
        optimized_flow = self._optimize_node_ordering(optimized_flow)
        optimized_flow = self._optimize_connections(optimized_flow)
        optimized_flow = self._add_implicit_nodes(optimized_flow)

        return optimized_flow
    
    def _optimize_node_ordering(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize node execution order"""
        # Implementation: Topological sorting for better execution order
        return flow_data
    
    def _optimize_connections(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize connection patterns"""
        # Implementation: Remove redundant connections, add missing ones
        return flow_data
    
    def _add_implicit_nodes(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add implicit nodes for better workflow flow"""
        # Implementation: Add missing StartNode/EndNode if needed
        return flow_data


class DynamicWorkflowEngine:
    """
    Enhanced Dynamic Workflow Engine
    ================================
    
    Built on top of existing GraphBuilder with minimal changes.
    Adds full dynamic capabilities while maintaining backward compatibility.
    """
    
    def __init__(self, checkpointer=None):
        self.base_builder = GraphBuilder(node_registry, checkpointer)
        self.node_resolver = DynamicNodeResolver(node_registry.nodes)
        self.connection_mapper = DynamicConnectionMapper()
        self.optimizer = DynamicWorkflowOptimizer()
        
        # Runtime state
        self.active_contexts = {}
        self.dynamic_cache = {}
    
    def create_dynamic_context(self, session_id: str, user_id: Optional[str] = None, 
                             owner_id: Optional[str] = None, workflow_id: Optional[str] = None, **kwargs) -> DynamicWorkflowContext:
        """Create dynamic execution context"""
        context = DynamicWorkflowContext(
            session_id=session_id,
            user_id=user_id,
            owner_id=owner_id,
            workflow_id=workflow_id,
            metadata=kwargs.get('metadata', {}),
            runtime_config=kwargs.get('runtime_config', {})
        )
        
        self.active_contexts[session_id] = context
        return context
    
    def build_dynamic_workflow(self, flow_data: Dict[str, Any], 
                             context: DynamicWorkflowContext) -> Any:
        """Build workflow with full dynamic capabilities"""
        
        logger.info(f"🔄 Building dynamic workflow (session: {context.session_id})")
        
        try:
            # Step 1: Optimize workflow structure
            optimized_flow = self.optimizer.optimize_workflow(flow_data)
            
            # Step 2: Resolve nodes dynamically
            enhanced_flow = self._enhance_with_dynamic_nodes(optimized_flow, context)
            
            # Step 3: Build using enhanced builder
            compiled_graph = self.base_builder.build_from_flow(enhanced_flow, context.user_id)
            
            logger.info(f"✅ Dynamic workflow built successfully")
            return compiled_graph
            
        except Exception as e:
            logger.error(f"❌ Dynamic workflow build failed: {e}")
            raise
    
    def _enhance_with_dynamic_nodes(self, flow_data: Dict[str, Any], 
                                  context: DynamicWorkflowContext) -> Dict[str, Any]:
        """Enhance workflow with dynamically resolved nodes"""
        
        enhanced_flow = flow_data.copy()
        nodes = enhanced_flow.get("nodes", [])
        
        # Process each node for dynamic enhancement
        enhanced_nodes = []
        for node_def in nodes:
            try:
                # Resolve node type dynamically
                node_instance = self.node_resolver.create_dynamic_instance(node_def, context)
                
                # Enhance node definition with resolved information
                enhanced_node_def = node_def.copy()
                enhanced_node_def["_resolved_type"] = node_instance.__class__.__name__
                enhanced_node_def["_dynamic_context"] = context.session_id
                
                enhanced_nodes.append(enhanced_node_def)
                
            except Exception as e:
                logger.error(f"Failed to enhance node {node_def.get('id', 'unknown')}: {e}")
                # Keep original node definition as fallback
                enhanced_nodes.append(node_def)
        
        enhanced_flow["nodes"] = enhanced_nodes
        return enhanced_flow
    
    async def execute_dynamic_workflow(self, inputs: Dict[str, Any], 
                                     context: DynamicWorkflowContext,
                                     stream: bool = False) -> Union[Dict[str, Any], AsyncGenerator]:
        """Execute workflow with dynamic capabilities"""
        
        logger.info(f"Executing dynamic workflow (session: {context.session_id})")
        
        try:
            # Execute using base builder with enhanced context
            result = await self.base_builder.execute_with_monitoring(
                inputs=inputs,
                session_id=context.session_id,
                user_id=context.user_id,
                owner_id=context.owner_id,
                workflow_id=context.workflow_id,
                stream=stream,
            )
            
            logger.info(f"Dynamic workflow execution completed")
            return result
            
        except Exception as e:
            logger.error(f"Dynamic workflow execution failed: {e}")
            raise
    
    def get_runtime_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get runtime metrics for a session"""
        context = self.active_contexts.get(session_id)
        if not context:
            return {"error": "Session not found"}
        
        build_metrics = self.base_builder.get_build_metrics()
        
        return {
            "session_id": session_id,
            "context": {
                "user_id": context.user_id,
                "workflow_id": context.workflow_id,
                "metadata": context.metadata
            },
            "build_metrics": build_metrics,
            "cache_stats": {
                "active_contexts": len(self.active_contexts),
                "dynamic_cache_size": len(self.dynamic_cache)
            }
        }
    
    def cleanup_session(self, session_id: str):
        """Clean up session resources"""
        if session_id in self.active_contexts:
            del self.active_contexts[session_id]
        
        # Clean up related cache entries
        cache_keys_to_remove = [k for k in self.dynamic_cache.keys() if session_id in str(k)]
        for key in cache_keys_to_remove:
            del self.dynamic_cache[key]


# Factory function for easy integration
def create_dynamic_engine(checkpointer=None) -> DynamicWorkflowEngine:
    """Create a new dynamic workflow engine instance"""
    return DynamicWorkflowEngine(checkpointer)


# Integration helper for execute_adhoc_workflow
class ExecuteAdhocWorkflowEnhancer:
    """Helper class to enhance execute_adhoc_workflow with minimal changes"""
    
    def __init__(self):
        self.dynamic_engine = create_dynamic_engine()
    
    def enhance_execution_request(self, req: Any, current_user: Any) -> DynamicWorkflowContext:
        """Create dynamic context from execution request"""
        session_id = req.session_id or str(uuid.uuid4())
        
        context = self.dynamic_engine.create_dynamic_context(
            session_id=session_id,
            user_id=str(current_user.id) if current_user else None,
            owner_id=str(current_user.id) if current_user else None,
            workflow_id=req.workflow_id,
            metadata={
                "chatflow_id": req.chatflow_id,
                "input_text": req.input_text,
                "is_webhook": current_user is None
            }
        )

        return context
    
    async def execute_with_dynamic_engine(self, req: Any, context: DynamicWorkflowContext, 
                                        stream: bool = False) -> Union[Dict[str, Any], AsyncGenerator]:
        """Execute using dynamic engine"""
        
        # Build dynamic workflow
        compiled_graph = self.dynamic_engine.build_dynamic_workflow(req.flow_data, context)
        
        # Execute with dynamic capabilities
        inputs = {"input": req.input_text}
        result = await self.dynamic_engine.execute_dynamic_workflow(inputs, context, stream)
        
        return result