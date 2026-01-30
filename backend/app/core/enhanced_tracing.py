"""
KAI-Fusion Enhanced Tracing System - Performance-Integrated Monitoring
=====================================================================

Enhanced tracing system with performance monitoring integration.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from functools import wraps
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import CallbackManager

from .constants import ENABLE_WORKFLOW_TRACING, TRACE_MEMORY_OPERATIONS, LANGCHAIN_TRACING_V2
from .performance_monitor import get_performance_monitor

logger = logging.getLogger(__name__)


class EnhancedWorkflowTracer:
    """Enhanced tracer with performance monitoring integration."""
    
    def __init__(self, session_id: Optional[str] = None, user_id: Optional[str] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.workflow_start_time: Optional[float] = None
        self.node_executions: Dict[str, str] = {}  # node_id -> execution_id
        self.performance_monitor = get_performance_monitor()
        
    def start_workflow(self, workflow_id: Optional[str] = None, flow_data: Optional[Dict[str, Any]] = None):
        """Start tracking a workflow execution with performance monitoring."""
        self.workflow_start_time = time.time()
        
        # Extract workflow metrics
        node_count = len(flow_data.get("nodes", [])) if flow_data else 0
        connection_count = len(flow_data.get("edges", [])) if flow_data else 0
        
        # Start performance monitoring
        if self.session_id:
            self.performance_monitor.start_workflow_monitoring(
                workflow_id or "unknown",
                self.session_id,
                node_count,
                connection_count
            )
        
        if LANGCHAIN_TRACING_V2:
            metadata = {
                "workflow_id": workflow_id,
                "session_id": self.session_id,
                "user_id": self.user_id,
                "node_count": node_count,
                "edge_count": connection_count,
                "platform": "kai-fusion",
                "version": "2.1.0"
            }
            
            logger.info(f"Enhanced workflow trace started: {workflow_id}")
            logger.info(f"Metadata: {metadata}")
            
    def start_node_execution(self, node_id: str, node_type: str, inputs: Dict[str, Any]):
        """Start tracking a node execution with performance monitoring."""
        # Start performance monitoring
        execution_id = self.performance_monitor.start_node_execution(
            node_id, node_type, self.session_id
        )
        self.node_executions[node_id] = execution_id
        
        if ENABLE_WORKFLOW_TRACING:
            logger.info(f"Node execution started: {node_id} ({node_type})")
            logger.info(f"Inputs: {list(inputs.keys())}")
    
    def end_node_execution(self, node_id: str, node_type: str, outputs: Dict[str, Any], 
                          success: bool = True, error_message: Optional[str] = None):
        """End tracking a node execution with performance monitoring."""
        # End performance monitoring
        if node_id in self.node_executions:
            execution_id = self.node_executions[node_id]
            
            # Calculate output size if possible
            output_size = None
            try:
                if isinstance(outputs, dict) and "output" in outputs:
                    output_size = len(str(outputs["output"]))
                elif isinstance(outputs, str):
                    output_size = len(outputs)
            except Exception:
                pass
            
            self.performance_monitor.end_node_execution(
                execution_id, success, error_message, output_size
            )
            del self.node_executions[node_id]
        
        if ENABLE_WORKFLOW_TRACING:
            status = "SUCCESS" if success else "FAILED"
            logger.info(f"Node execution completed: {node_id} ({node_type}) - {status}")
            if error_message:
                logger.error(f"Error: {error_message}")
    
    def track_memory_operation(self, operation: str, node_id: str, content: str, session_id: str):
        """Track memory operations with enhanced monitoring."""
        if TRACE_MEMORY_OPERATIONS:
            # Record memory usage
            try:
                import sys
                memory_usage = sys.getsizeof(content) / (1024 * 1024)  # MB
                self.performance_monitor.record_memory_usage(
                    memory_usage, session_id, f"memory_{operation}"
                )
            except Exception:
                pass
            logger.info(f"Memory {operation}: {node_id} ({len(content)} chars)")
    
    def track_connection_resolution(self, node_count: int, connection_count: int, resolution_time: float):
        """Track connection resolution performance."""
        self.performance_monitor.record_connection_resolution_time(
            node_count, connection_count, resolution_time, self.session_id
        )
    
    def end_workflow(self, success: bool, error: Optional[str] = None):
        """End workflow tracking with performance monitoring."""
        # End performance monitoring
        if self.session_id:
            self.performance_monitor.end_workflow_monitoring(
                self.session_id, success, error
            )
        
        if self.workflow_start_time:
            total_duration = time.time() - self.workflow_start_time
            
            status = "SUCCESS" if success else "FAILED"
            logger.info(f"Enhanced workflow completed in {total_duration:.2f}s - {status}")
            
            if error:
                logger.error(f"Workflow error: {error}")

    def get_callback_manager(self) -> Optional[CallbackManager]:
        """Get callback manager for LangSmith integration."""
        if LANGCHAIN_TRACING_V2:
            try:
                from app.core.constants import LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
                if LANGCHAIN_API_KEY:
                    tracer = LangChainTracer(
                        project_name=LANGCHAIN_PROJECT or "kai-fusion",
                        session_id=self.session_id
                    )
                    return CallbackManager([tracer])
            except Exception as e:
                logger.warning(f"Failed to create LangSmith callback manager: {e}")
        return None


def enhanced_trace_workflow(func):
    """Enhanced decorator to trace workflow execution with performance monitoring."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not ENABLE_WORKFLOW_TRACING:
            return await func(*args, **kwargs)
        
        # Extract session and user info from kwargs
        session_id = kwargs.get('session_id')
        user_id = kwargs.get('user_id')
        workflow_id = kwargs.get('workflow_id')
        
        tracer = EnhancedWorkflowTracer(session_id=session_id, user_id=user_id)
        
        try:
            # Start workflow tracing
            flow_data = kwargs.get('flow_data') or (args[0] if args else {})
            tracer.start_workflow(workflow_id=workflow_id, flow_data=flow_data)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # End workflow tracing
            tracer.end_workflow(success=True)
            
            return result
            
        except Exception as e:
            tracer.end_workflow(success=False, error=str(e))
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not ENABLE_WORKFLOW_TRACING:
            return func(*args, **kwargs)
        
        # Extract session and user info from kwargs
        session_id = kwargs.get('session_id')
        user_id = kwargs.get('user_id')
        workflow_id = kwargs.get('workflow_id')
        
        tracer = EnhancedWorkflowTracer(session_id=session_id, user_id=user_id)
        
        try:
            # Start workflow tracing
            flow_data = kwargs.get('flow_data') or (args[0] if args else {})
            tracer.start_workflow(workflow_id=workflow_id, flow_data=flow_data)
            
            # Execute function
            result = func(*args, **kwargs)
            
            # End workflow tracing
            tracer.end_workflow(success=True)
            
            return result
            
        except Exception as e:
            tracer.end_workflow(success=False, error=str(e))
            raise
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def enhanced_trace_node_execution(func):
    """Enhanced decorator to trace individual node execution with performance monitoring."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not ENABLE_WORKFLOW_TRACING:
            return func(self, *args, **kwargs)
        
        node_id = getattr(self, 'node_id', 'unknown')
        node_type = getattr(self, 'metadata', {}).get('name', 'unknown')
        session_id = getattr(self, 'session_id', None)
        
        tracer = EnhancedWorkflowTracer(session_id=session_id)
        
        try:
            # Start node tracing
            inputs = kwargs.get('inputs', {})
            tracer.start_node_execution(node_id, node_type, inputs)
            
            # Execute function
            result = func(self, *args, **kwargs)
            
            # End node tracing
            outputs = {'output': result} if result else {}
            tracer.end_node_execution(node_id, node_type, outputs, success=True)
            
            return result
            
        except Exception as e:
            tracer.end_node_execution(node_id, node_type, {}, success=False, error_message=str(e))
            logger.error(f"Enhanced node {node_id} failed: {str(e)}")
            raise
    
    return wrapper


def enhanced_trace_memory_operation(operation: str):
    """Enhanced decorator to trace memory operations with performance monitoring."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not TRACE_MEMORY_OPERATIONS:
                return func(self, *args, **kwargs)
            
            node_id = getattr(self, 'node_id', 'unknown')
            session_id = getattr(self, 'session_id', 'unknown')
            
            tracer = EnhancedWorkflowTracer(session_id=session_id)
            
            try:
                # Execute function
                result = func(self, *args, **kwargs)
                
                # Track memory operation
                content = str(result) if result else ""
                tracer.track_memory_operation(operation, node_id, content, session_id)
                
                return result
                
            except Exception as e:
                logger.error(f"Enhanced memory operation {operation} failed: {str(e)}")
                raise
        
        return wrapper
    return decorator


def get_enhanced_workflow_tracer(session_id: Optional[str] = None, user_id: Optional[str] = None) -> EnhancedWorkflowTracer:
    """Get an enhanced workflow tracer instance."""
    return EnhancedWorkflowTracer(session_id=session_id, user_id=user_id)


def setup_enhanced_tracing():
    """Initialize enhanced tracing configuration."""
    if LANGCHAIN_TRACING_V2:
        try:
            from app.core.config import setup_langsmith
            setup_langsmith()
            logger.info("Enhanced workflow tracing initialized with LangSmith")
        except Exception as e:
            logger.warning(f"LangSmith setup failed: {e}")
            logger.info("Enhanced workflow tracing initialized (local only)")
    else:
        logger.info("Enhanced workflow tracing initialized (local only)")


# Backward compatibility aliases
trace_workflow = enhanced_trace_workflow
trace_node_execution = enhanced_trace_node_execution
trace_memory_operation = enhanced_trace_memory_operation
get_workflow_tracer = get_enhanced_workflow_tracer