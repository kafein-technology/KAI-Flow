"""
Minimal Integration Enhancement for execute_adhoc_workflow
=========================================================

This module provides a drop-in enhancement for the existing execute_adhoc_workflow
function with minimal code changes required.
"""

import logging
from typing import Any, Dict, Optional, Union, AsyncGenerator
from .dynamic_workflow_engine import DynamicWorkflowEngine, DynamicWorkflowContext

logger = logging.getLogger(__name__)

class WorkflowExecutionEnhancer:
    """
    Minimal enhancement wrapper for execute_adhoc_workflow
    
    Usage:
    1. Create instance: enhancer = WorkflowExecutionEnhancer()
    2. Replace engine.build() with: enhancer.enhanced_build()
    3. Replace engine.execute() with: enhancer.enhanced_execute()
    
    This provides full dynamic capabilities with minimal code changes.
    """
    
    def __init__(self):
        # We don't initialize a global engine anymore to prevent state sharing
        pass
    
    def create_context_from_request(self, req: Any, current_user: Any = None,
                                   is_webhook: bool = False, owner_id: str = None) -> DynamicWorkflowContext:
        """Create dynamic context from request parameters"""
        
        # We need a temporary engine just to create context helper
        # Or we can just import the context class directly?
        # DynamicWorkflowContext is imported at top level, so we can use it directly
        # But we need create_dynamic_context method logic
        
        # Instantiate a temporary engine for this helper method
        temp_engine = DynamicWorkflowEngine()
        
        # Generate session_id with safe fallback logic
        session_id = getattr(req, 'session_id', None) or getattr(req, 'chatflow_id', None)
        
        if not session_id:
            # Safe fallback using object id
            logger.warning(f"No session_id or chatflow_id provided, using object id fallback")
            session_id = f"session_{id(req)}"
            
        if isinstance(session_id, int):
            session_id = str(session_id)
        
        # Handle user context
        user_id = None
        if not is_webhook and current_user:
            user_id = str(current_user.id)
        elif is_webhook:
            user_id = "webhook_system"
        
        context = temp_engine.create_dynamic_context(
            session_id=session_id,
            user_id=user_id,
            owner_id=owner_id or user_id,  # Use provided owner_id or fallback to user_id
            workflow_id=req.workflow_id,
            metadata={
                "chatflow_id": getattr(req, 'chatflow_id', None),
                "input_text": getattr(req, 'input_text', ''),
                "is_webhook": is_webhook,
                "request_timestamp": str(__import__('datetime').datetime.utcnow())
            }
        )
        
        return context
    
    def enhanced_build(self, flow_data: Dict[str, Any], user_context: Dict[str, Any] = None):
        """
        Enhanced build with dynamic capabilities.
        Returns: (DynamicWorkflowContext, CompiledGraph, DynamicWorkflowEngine)
        """
        
        # Create a FRESH engine for this request
        engine = DynamicWorkflowEngine()
        
        # Create context locally
        session_id = user_context.get('session_id') if user_context else f"build_{id(flow_data)}"
        context = engine.create_dynamic_context(
            session_id=session_id,
            user_id=user_context.get('user_id') if user_context else None,
            owner_id=user_context.get('owner_id') if user_context else None,
            workflow_id=user_context.get('workflow_id') if user_context else None
        )
        
        try:
            logger.info(f"Enhanced build starting (session: {context.session_id})")
            
            # Use dynamic engine to build workflow
            compiled_graph = engine.build_dynamic_workflow(
                flow_data, context
            )
            
            logger.info(f"Enhanced build completed successfully")
            return context, compiled_graph, engine
            
        except Exception as e:
            logger.error(f"Enhanced build failed: {e}")
            raise
    
    async def enhanced_execute(self, inputs: Dict[str, Any] = None, *, stream: bool = False, 
                             user_context: Dict[str, Any] = None, 
                             build_result=None) -> Union[Dict[str, Any], AsyncGenerator]:
        """
        Enhanced execute with dynamic capabilities.
        Args:
            build_result: Tuple returned by enhanced_build
        """
        
        # Check if build_result is provided (stateless mode)
        if build_result:
            context, compiled_graph, engine = build_result
        else:
            raise RuntimeError("Must provide build_result (context, compiled_graph, engine) to enhanced_execute()")
        
        try:
            logger.info(f"Enhanced execute starting (session: {context.session_id})")
            
            # Ensure the graph is set on the builder instance associated with this engine
            engine.base_builder.graph = compiled_graph
            
            result = await engine.execute_dynamic_workflow(
                inputs or {}, context, stream
            )
            
            logger.info(f"Enhanced execute completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Enhanced execute failed: {e}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics"""
        return {"error": "Metrics not available in stateless mode"}
    
    def cleanup(self):
        """Cleanup resources"""
        pass


# Global instance for easy use
_workflow_enhancer = WorkflowExecutionEnhancer()

def get_workflow_enhancer() -> WorkflowExecutionEnhancer:
    """Get the global workflow enhancer instance"""
    return _workflow_enhancer

def create_workflow_enhancer() -> WorkflowExecutionEnhancer:
    """Create a new workflow enhancer instance"""
    return WorkflowExecutionEnhancer()