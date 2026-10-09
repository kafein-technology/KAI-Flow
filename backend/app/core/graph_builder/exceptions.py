"""
GraphBuilder Exception Classes
=============================

Custom exception hierarchy for the GraphBuilder system providing
detailed error information for workflow orchestration failures.

AUTHORS: KAI-Flow Workflow Orchestration Team
VERSION: 2.1.0
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Flow Platform
"""

from typing import Any, Dict, Optional, List
import traceback
import datetime

from app.core.error_normalization import (
    normalize_execution_error,
    sanitize_error_text,
)


class WorkflowError(Exception):
    """
    Base exception for all workflow-related errors.
    
    Provides common functionality for all workflow exceptions including
    error tracking, context preservation, and detailed error information.
    """
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.datetime.now()
        self.stack_trace = traceback.format_exc()
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace
        }


class NodeExecutionError(WorkflowError):
    """
    Exception raised when node execution fails.
    
    Captures detailed information about the failed node including:
    - Node ID and type
    - Original error that caused the failure  
    - Node configuration and connection information
    - Execution context
    """
    
    def __init__(
        self, 
        node_id: str, 
        node_type: str, 
        original_error: Exception,
        node_config: Optional[Dict[str, Any]] = None,
        input_connections: Optional[Dict[str, Any]] = None,
        output_connections: Optional[Dict[str, Any]] = None
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.original_error = original_error
        self.node_config = node_config or {}
        self.input_connections = input_connections or {}
        self.output_connections = output_connections or {}
        self.error_details = normalize_execution_error(original_error)
        
        # The public message is stable and actionable. The original exception
        # object and its sanitized provider diagnostics remain available below.
        message = (
            f"Node {node_id} ({node_type}) execution failed: "
            f"{self.error_details.display_message}"
        )
        
        # Build enhanced context
        context = {
            "node_id": node_id,
            "node_type": node_type,
            "original_error": self.error_details.raw_message,
            "original_error_type": type(original_error).__name__,
            "error_code": self.error_details.code,
            "error_category": self.error_details.category,
            "http_status": self.error_details.status_code,
            "provider_error_code": self.error_details.provider_code,
            "provider_message": self.error_details.provider_message,
            "retryable": self.error_details.retryable,
            "resolution": self.error_details.resolution,
            "node_config": node_config,
            "input_connections": input_connections,
            "output_connections": output_connections,
        }
        
        super().__init__(message, context)
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get comprehensive debug information for troubleshooting."""
        return {
            **self.to_dict(),
            "node_details": {
                "node_id": self.node_id,
                "node_type": self.node_type,
                "config_keys": list(self.node_config.keys()) if self.node_config else [],
                "input_connection_count": len(self.input_connections),
                "output_connection_count": len(self.output_connections)
            },
            "original_error_details": {
                "type": type(self.original_error).__name__,
                "message": sanitize_error_text(self.original_error),
                "args": sanitize_error_text(getattr(self.original_error, 'args', [])),
            },
            "normalized_error": self.error_details.to_dict(),
        }


def find_deepest_node_execution_error(error: BaseException) -> Optional["NodeExecutionError"]:
    """Return the original failing node error from a wrapped exception chain."""
    deepest: Optional[NodeExecutionError] = None
    pending: List[BaseException] = [error]
    visited: set[int] = set()

    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))

        if isinstance(current, NodeExecutionError):
            deepest = current

        for nested in (
            getattr(current, "__context__", None),
            getattr(current, "__cause__", None),
            getattr(current, "original_error", None),
            getattr(current, "_kai_node_execution_error", None),
        ):
            if isinstance(nested, BaseException) and id(nested) not in visited:
                pending.append(nested)

    return deepest


class ConnectionError(WorkflowError):
    """
    Exception raised when connection mapping or validation fails.
    
    Captures information about connection failures including:
    - Source and target node information
    - Connection handle details
    - Validation errors
    """
    
    def __init__(
        self,
        message: str,
        source_node_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        source_handle: Optional[str] = None,
        target_handle: Optional[str] = None,
        validation_errors: Optional[List[str]] = None
    ):
        self.source_node_id = source_node_id
        self.target_node_id = target_node_id
        self.source_handle = source_handle
        self.target_handle = target_handle
        self.validation_errors = validation_errors or []
        
        # Build enhanced context
        context = {
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "source_handle": source_handle,
            "target_handle": target_handle,
            "validation_errors": validation_errors
        }
        
        super().__init__(message, context)
    
    def get_connection_info(self) -> str:
        """Get formatted connection information string."""
        if self.source_node_id and self.target_node_id:
            source = f"{self.source_node_id}[{self.source_handle or 'output'}]"
            target = f"{self.target_node_id}[{self.target_handle or 'input'}]"
            return f"{source} → {target}"
        return "Unknown connection"


class ValidationError(WorkflowError):
    """
    Exception raised when workflow validation fails.
    
    Captures comprehensive validation failure information including:
    - Validation errors and warnings
    - Node and connection counts
    - Specific validation rule failures
    """
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        validation_warnings: Optional[List[str]] = None,
        node_count: Optional[int] = None,
        connection_count: Optional[int] = None
    ):
        self.validation_errors = validation_errors or []
        self.validation_warnings = validation_warnings or []
        self.node_count = node_count
        self.connection_count = connection_count
        
        # Build enhanced context
        context = {
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
            "node_count": node_count,
            "connection_count": connection_count,
            "error_count": len(validation_errors) if validation_errors else 0,
            "warning_count": len(validation_warnings) if validation_warnings else 0
        }
        
        super().__init__(message, context)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        return {
            "valid": len(self.validation_errors) == 0,
            "error_count": len(self.validation_errors),
            "warning_count": len(self.validation_warnings),
            "node_count": self.node_count,
            "connection_count": self.connection_count,
            "errors": self.validation_errors,
            "warnings": self.validation_warnings
        }


class ControlFlowError(WorkflowError):
    """
    Exception raised when control flow logic fails.
    
    Captures information about control flow failures including:
    - Control flow type (conditional, loop, parallel)
    - Node configuration
    - Condition evaluation errors
    """
    
    def __init__(
        self,
        message: str,
        control_flow_type: Optional[str] = None,
        node_id: Optional[str] = None,
        condition_config: Optional[Dict[str, Any]] = None
    ):
        self.control_flow_type = control_flow_type
        self.node_id = node_id
        self.condition_config = condition_config or {}
        
        # Build enhanced context
        context = {
            "control_flow_type": control_flow_type,
            "node_id": node_id,
            "condition_config": condition_config
        }
        
        super().__init__(message, context)


class GraphCompilationError(WorkflowError):
    """
    Exception raised when LangGraph compilation fails.
    
    Captures information about graph compilation failures including:
    - Node and edge information
    - Compilation stage
    - LangGraph specific errors
    """
    
    def __init__(
        self,
        message: str,
        compilation_stage: Optional[str] = None,
        node_count: Optional[int] = None,
        edge_count: Optional[int] = None,
        langgraph_error: Optional[Exception] = None
    ):
        self.compilation_stage = compilation_stage
        self.node_count = node_count
        self.edge_count = edge_count
        self.langgraph_error = langgraph_error
        
        # Build enhanced context
        context = {
            "compilation_stage": compilation_stage,
            "node_count": node_count,
            "edge_count": edge_count,
            "langgraph_error": str(langgraph_error) if langgraph_error else None,
            "langgraph_error_type": type(langgraph_error).__name__ if langgraph_error else None
        }
        
        super().__init__(message, context)


# Exception type mapping for easy access
EXCEPTION_TYPES = {
    "workflow": WorkflowError,
    "node_execution": NodeExecutionError,
    "connection": ConnectionError,
    "validation": ValidationError,
    "control_flow": ControlFlowError,
    "graph_compilation": GraphCompilationError
}


def create_exception(
    exception_type: str,
    message: str,
    **kwargs
) -> WorkflowError:
    """
    Factory function to create appropriate exception types.
    
    Args:
        exception_type: Type of exception to create
        message: Error message
        **kwargs: Additional arguments for specific exception types
    
    Returns:
        Appropriate WorkflowError subclass instance
    """
    exception_class = EXCEPTION_TYPES.get(exception_type, WorkflowError)
    return exception_class(message, **kwargs)