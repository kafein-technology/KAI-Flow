"""
KAI-Flow Node Execution Handlers - Clean Architecture Implementation
====================================================================

This module implements the Strategy Pattern for handling different node types
in the KAI-Flow Graph Builder system. This replaces the monolithic
_extract_connected_node_instances function with clean, maintainable handlers.

Each handler is responsible for a specific node type execution pattern,
following Single Responsibility Principle and making the system extensible.

Authors: KAI-Flow Development Team
Version: 3.0.0 - Clean Architecture Refactor
Last Updated: 2025-01-13
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import re
import json
import uuid

from app.core.state import (
    FlowState,
    attach_runtime_execution_context,
    set_runtime_node_status,
)
from app.nodes.base import NodeType
from app.core.credential_provider import credential_provider
from app.core.templating import apply_jinja_to_inputs
from app.core.runtime_execution import instrument_runtime_artifact

logger = logging.getLogger(__name__)


class NodeExecutionHandler(ABC):
    """
    Abstract base class for node execution strategies.
    
    This implements the Strategy Pattern for handling different node types
    in a clean, maintainable way. Each concrete handler focuses on one
    specific node type execution pattern.
    """
    
    def __init__(self):
        """Initialize handler with optional nodes registry for cross-node communication."""
        self.nodes_registry = {}  # Will be injected by NodeConnectionExtractor
    
    @abstractmethod
    def extract_connected_instance(self,
                                 connection_info: Dict[str, str],
                                 source_node_instance: Any,
                                 gnode_instance: Any,
                                 state: FlowState) -> Any:
        """
        Extract connected node instance based on node type.
        
        Args:
            connection_info: Connection metadata (source_node_id, etc.)
            source_node_instance: The source node instance to execute
            gnode_instance: The original GraphNodeInstance for context
            state: Current workflow state
            
        Returns:
            The extracted/executed result from the connected node
        """
        pass
    
    def _log_execution(self, node_id: str, node_type: str, action: str):
        """Centralized logging for node execution."""
        logger.debug(f"[{node_type.upper()}] {action}: {node_id}")

    def _inject_user_context(self, node_instance: Any, state: FlowState, node_id: str):
        """Inject user context (user_id and credentials) into node instance if supported."""
        # Use owner_id if available (workflow owner), otherwise user_id (executor)
        context_user_id = state.owner_id or state.user_id
        
        # Explicitly set user_id on the node instance to allow nodes to access execution context
        if context_user_id:
            node_instance.user_id = context_user_id
        if node_instance.user_data.get('credential_id') and context_user_id:
            node_instance.credentials = credential_provider.get_credentials_sync(user_id=context_user_id)

class MemoryNodeHandler(NodeExecutionHandler):
    """
    Handler for Memory node types.
    
    Memory nodes provide conversation state and context persistence.
    They need session_id setup and user input context.
    """
    
    def __init__(self):
        """Initialize memory node handler."""
        super().__init__()
    
    def extract_connected_instance(self, 
                                 connection_info: Dict[str, str],
                                 source_node_instance: Any,
                                 gnode_instance: Any,
                                 state: FlowState) -> Any:
        """Extract memory node instance with session context."""
        node_id = connection_info["source_node_id"]
        self._log_execution(node_id, "memory", "extracting")
        set_runtime_node_status(state, node_id, "pending")
        
        try:
            # Set session_id on memory nodes before execution
            source_node_instance.session_id = state.session_id
            print(f"[DEBUG] Set session_id on memory node {node_id}: {state.session_id}")
            
            # Inject user_id if supported
            self._inject_user_context(source_node_instance, state, node_id)
            
            # Extract memory-specific inputs
            memory_inputs = self._extract_memory_inputs(source_node_instance, state)
            
            # Execute memory node to get instance
            node_instance = source_node_instance.execute(**memory_inputs)
            set_runtime_node_status(state, node_id, "success")
            logger.debug(f"[DEBUG] Memory node {node_id} executed successfully: {type(node_instance).__name__}")
            
            return node_instance
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to extract memory node {node_id}: {e}")
            set_runtime_node_status(state, node_id, "failed")
            from app.core.graph_builder.exceptions import NodeExecutionError

            node_error = NodeExecutionError(
                node_id=node_id,
                node_type=getattr(gnode_instance, "type", source_node_instance.__class__.__name__),
                original_error=e,
                node_config=getattr(source_node_instance, "user_data", {}) or {},
            )
            attach_runtime_execution_context(node_error, state)
            raise node_error from e
    
    def _extract_memory_inputs(self, source_node_instance: Any, state: FlowState) -> Dict[str, Any]:
        """Extract inputs needed for memory node execution."""
        memory_inputs = {}

        # Frontend commonly stores form values under user_data["inputs"].
        # Previously we only read top-level user_data, which caused memory nodes
        # to ignore updated UI values (e.g. BufferMemoryNode.limit).
        user_data: Dict[str, Any] = getattr(source_node_instance, "user_data", {}) or {}
        inputs_group: Dict[str, Any] = {}
        try:
            if isinstance(user_data, dict):
                inputs_group = user_data.get("inputs", {}) or {}
        except Exception:
            inputs_group = {}

        # Get memory node input specifications
        for input_spec in source_node_instance.metadata.inputs:
            name = input_spec.name

            # 1) Priority: user_data["inputs"][name]
            if isinstance(inputs_group, dict) and name in inputs_group:
                memory_inputs[name] = inputs_group[name]
            # 2) Fallback: top-level user_data[name]
            elif isinstance(user_data, dict) and name in user_data:
                memory_inputs[name] = user_data[name]
            # 3) Default value
            elif input_spec.default is not None:
                memory_inputs[name] = input_spec.default

        # Pass current state variables to memory node (allows templated/variable-driven config)
        memory_inputs.update(state.variables)

        # Apply Jinja templating to memory inputs so they can reference upstream node outputs
        node_id = getattr(source_node_instance, "node_id", "MemoryNode")
        memory_inputs = apply_jinja_to_inputs(memory_inputs, state, node_id, self.nodes_registry)

        return memory_inputs



class ProviderNodeHandler(NodeExecutionHandler):
    """
    Handler for Provider node types.
    
    Provider nodes create LangChain objects (LLMs, Tools, etc.) from configuration.
    Some provider nodes (like RetrieverProvider) also depend on connections from other nodes.
    """
    
    def __init__(self):
        """Initialize provider node handler."""
        super().__init__()
    
    def extract_connected_instance(
        self,
        connection_info: Dict[str, str],
        source_node_instance: Any,
        gnode_instance: Any,
        state: FlowState,
    ) -> Any:
        """Resolve one provider while preserving the real failure owner."""
        from app.core.graph_builder.exceptions import (
            NodeExecutionError,
            find_deepest_node_execution_error,
        )

        node_id = connection_info["source_node_id"]
        self._log_execution(node_id, "provider", "extracting")
        set_runtime_node_status(state, node_id, "pending")

        try:
            provider_inputs = self._extract_provider_inputs(source_node_instance, state)
            provider_inputs = apply_jinja_to_inputs(
                provider_inputs, state, node_id, self.nodes_registry
            )

            # Validate this provider before touching its child dependencies.
            self._inject_user_context(source_node_instance, state, node_id)
            self._validate_required_credentials(source_node_instance, provider_inputs)
            source_node_instance.validate_configuration(**provider_inputs)

            connected_inputs = self._extract_connected_inputs(
                source_node_instance, gnode_instance, state
            )
            all_inputs = {**provider_inputs, **connected_inputs}
            logger.debug(
                "[DEBUG] Provider node %s inputs: user=%s, connected=%s",
                node_id,
                list(provider_inputs.keys()),
                list(connected_inputs.keys()),
            )

            node_instance = source_node_instance.execute(**all_inputs)
            node_instance = instrument_runtime_artifact(
                node_instance,
                node_id=node_id,
                node_type=getattr(gnode_instance, "type", type(source_node_instance).__name__),
                state=state,
                node_config=getattr(source_node_instance, "user_data", {}) or {},
                input_connections=getattr(source_node_instance, "_input_connections", {}) or {},
                output_connections=getattr(source_node_instance, "_output_connections", {}) or {},
            )

            set_runtime_node_status(state, node_id, "success")
            logger.debug(
                f"[DEBUG] Provider node {node_id} executed successfully: "
                f"{type(node_instance).__name__}"
            )
            return node_instance

        except Exception as error:
            logger.error(f"[ERROR] Failed to extract provider node {node_id}: {error}")
            deepest_error = find_deepest_node_execution_error(error)

            if deepest_error is not None and deepest_error.node_id != node_id:
                # The provider's child failed; this provider is not the error source.
                set_runtime_node_status(state, node_id, "success")
                attach_runtime_execution_context(deepest_error, state)
                raise deepest_error from error

            set_runtime_node_status(state, node_id, "failed")
            if isinstance(error, NodeExecutionError) and error.node_id == node_id:
                attach_runtime_execution_context(error, state)
                raise

            node_error = NodeExecutionError(
                node_id=node_id,
                node_type=getattr(
                    gnode_instance, "type", source_node_instance.__class__.__name__
                ),
                original_error=error,
                node_config=getattr(source_node_instance, "user_data", {}) or {},
                input_connections=getattr(
                    source_node_instance, "_input_connections", {}
                )
                or {},
                output_connections=getattr(
                    source_node_instance, "_output_connections", {}
                )
                or {},
            )
            attach_runtime_execution_context(node_error, state)
            raise node_error from error

    def _validate_required_credentials(
        self, source_node_instance: Any, provider_inputs: Dict[str, Any]
    ) -> None:
        """Fail local credential configuration before resolving child nodes."""
        properties = getattr(source_node_instance.metadata, "properties", None) or []
        user_data = getattr(source_node_instance, "user_data", {}) or {}

        for prop in properties:
            raw_type = getattr(prop, "type", "")
            prop_type = getattr(raw_type, "value", raw_type)
            if str(prop_type).lower() != "credential-select":
                continue

            value = provider_inputs.get(prop.name) or user_data.get(prop.name)
            if getattr(prop, "required", False) and not value:
                label = getattr(prop, "displayName", None) or prop.name
                raise ValueError(f"{label} credential selection is required.")

            if value and source_node_instance.get_credential(value) is None:
                raise ValueError(
                    f"Selected credential with ID '{value}' could not be found."
                )
    def _extract_provider_inputs(self, source_node_instance: Any, state: FlowState) -> Dict[str, Any]:
        """Extract inputs needed for provider node execution."""
        provider_inputs = {}
        
        # Provider nodes work with user configuration inputs (non-connection inputs)
        for input_spec in source_node_instance.metadata.inputs:
            if not input_spec.is_connection:  # Only non-connection inputs
                input_name = input_spec.name
                # Handle both string names and Mock objects in tests
                if hasattr(input_name, '__call__'):
                    continue  # Skip Mock objects that aren't properly configured
                    
                if input_name in source_node_instance.user_data:
                    provider_inputs[input_name] = source_node_instance.user_data[input_name]
                elif input_name in state.variables:
                    provider_inputs[input_name] = state.get_variable(input_name)
                elif input_spec.default is not None:
                    provider_inputs[input_name] = input_spec.default
        
        return provider_inputs
    
    def _extract_connected_inputs(
        self, source_node_instance: Any, gnode_instance: Any, state: FlowState
    ) -> Dict[str, Any]:
        """Resolve every attached dependency and collect all real failures."""
        from app.core.graph_builder.exceptions import (
            NodeExecutionError,
            find_deepest_node_execution_error,
        )
        from app.core.output_cache import NodeConnectionExtractor

        connected_inputs: Dict[str, Any] = {}
        input_connections = getattr(
            source_node_instance, "_input_connections", {}
        ) or {}
        if not input_connections:
            return connected_inputs

        extractor = NodeConnectionExtractor()
        extractor.nodes_registry = self.nodes_registry
        connection_errors = []

        for input_name, connection_info in input_connections.items():
            try:
                result = extractor._process_connection(
                    input_name, connection_info, state
                )
                if result is not None:
                    connected_inputs[input_name] = result
            except Exception as error:
                logger.error(
                    f"[ERROR] Failed to extract connected input '{input_name}': "
                    f"{error}"
                )
                node_error = find_deepest_node_execution_error(error)
                if node_error is None:
                    source_info = (
                        connection_info[0]
                        if isinstance(connection_info, list) and connection_info
                        else connection_info
                    )
                    source_node_id = (
                        source_info.get("source_node_id", "unknown")
                        if isinstance(source_info, dict)
                        else "unknown"
                    )
                    failed_node = self.nodes_registry.get(source_node_id)
                    node_error = NodeExecutionError(
                        node_id=source_node_id,
                        node_type=getattr(failed_node, "type", "Provider"),
                        original_error=error,
                    )
                connection_errors.append(node_error)

        if connection_errors:
            primary_error = connection_errors[0]
            attach_runtime_execution_context(primary_error, state)
            primary_error.context["node_errors"] = [
                error.to_dict() for error in connection_errors
            ]
            raise primary_error

        return connected_inputs

class ProcessorNodeHandler(NodeExecutionHandler):
    """
    Handler for Processor node types.
    
    Processor nodes are the most complex - they combine multiple inputs
    and may need re-execution. This handler implements intelligent caching
    and fallback strategies.
    """
    
    def __init__(self):
        """Initialize processor node handler."""
        super().__init__()
    
    def extract_connected_instance(self,
                                 connection_info: Dict[str, str],
                                 source_node_instance: Any,
                                 gnode_instance: Any,
                                 state: FlowState) -> Any:
        """Extract processor node output with intelligent caching."""
        node_id = connection_info["source_node_id"]
        input_name = connection_info.get("target_handle", "input")
        
        self._log_execution(node_id, "processor", "extracting")
        
        try:
            # 1. Try to get cached output first (most common case)
            cached_result = self._get_cached_output(node_id, input_name, state)
            if cached_result is not None:
                logger.debug(f"[DEBUG] Using cached output for processor {node_id}")
                return cached_result
            
            # 2. If no cache, need to re-execute processor node
            logger.debug(f"[DEBUG] No cached output found for {node_id}, performing re-execution")
            
            # Inject user_id if supported
            self._inject_user_context(source_node_instance, state, node_id)
            
            return self._re_execute_processor(source_node_instance, gnode_instance, state, node_id)
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to extract processor node {node_id}: {e}")
            raise RuntimeError(f"Processor node extraction failed for {node_id}: {str(e)}")
    
    def _get_cached_output(self, node_id: str, input_name: str, state: FlowState) -> Optional[Any]:
        """
        Intelligent cached output retrieval with multiple fallback strategies.
        
        Priority order:
        1. Direct input_name match in stored result
        2. Common fallbacks (documents, output)
        3. Full stored result
        """
        if not (hasattr(state, 'node_outputs') and node_id in state.node_outputs):
            return None
        
        stored_result = state.node_outputs[node_id]
        logger.debug(f"[DEBUG] Found stored result for {node_id}: {type(stored_result)}")
        
        # Try specific input_name first
        if isinstance(stored_result, dict):
            if input_name in stored_result:
                logger.debug(f"[DEBUG] Found specific output '{input_name}' in stored result")
                return stored_result[input_name]
            
            # Common fallbacks
            if "documents" in stored_result:
                logger.debug(f"[DEBUG] Using 'documents' fallback for {input_name}")
                return stored_result["documents"]
            
            if "output" in stored_result:
                logger.debug(f"[DEBUG] Using 'output' fallback for {input_name}")
                return stored_result["output"]
        
        # Return full result as last fallback
        logger.debug("[DEBUG] Using full stored result as fallback")
        return stored_result
    
    def _re_execute_processor(self, source_node_instance: Any, gnode_instance: Any, state: FlowState, node_id: str) -> Any:
        """
        Re-execute a processor node when cached output is not available.
        
        This builds the proper input context and connected_nodes for execution.
        """
        logger.debug(f"[DEBUG] Re-executing processor node {source_node_instance.__class__.__name__}")
        
        # Extract user inputs for processor
        processor_inputs = self._extract_processor_inputs(source_node_instance, state)
        processor_inputs = apply_jinja_to_inputs(processor_inputs, state, node_id, self.nodes_registry)
        
        # Build connected nodes for processor (recursive but controlled)
        processor_connected_nodes = self._build_connected_nodes_for_processor(
            source_node_instance, gnode_instance, state
        )
        
        logger.debug(f"[DEBUG] Processor inputs: {list(processor_inputs.keys())}")
        logger.debug(f"[DEBUG] Processor connected nodes: {list(processor_connected_nodes.keys())}")
        
        # Execute processor with proper context
        result = source_node_instance.execute(processor_inputs, processor_connected_nodes)
        logger.debug(f"[DEBUG] Processor re-execution completed: {type(result)}")
        
        return self._extract_result_output(result)
    
    def _extract_processor_inputs(self, source_node_instance: Any, state: FlowState) -> Dict[str, Any]:
        """Extract user inputs for processor node execution."""
        processor_inputs = {}
        
        for input_spec in source_node_instance.metadata.inputs:
            if not input_spec.is_connection:  # Only non-connection inputs
                # Check user_data first
                if input_spec.name in source_node_instance.user_data:
                    processor_inputs[input_spec.name] = source_node_instance.user_data[input_spec.name]
                # Then check state variables
                elif input_spec.name in state.variables:
                    processor_inputs[input_spec.name] = state.get_variable(input_spec.name)
                # Finally use default
                elif input_spec.default is not None:
                    processor_inputs[input_spec.name] = input_spec.default
        
        # Add current state variables as additional context
        processor_inputs.update(state.variables)
        
        return processor_inputs
    
    def _build_connected_nodes_for_processor(self, 
                                           source_node_instance: Any, 
                                           gnode_instance: Any,
                                           state: FlowState) -> Dict[str, Any]:
        """
        Build connected_nodes dictionary for processor re-execution.
        
        This is controlled recursion - we only go one level deep to avoid
        infinite recursion issues.
        """
        connected_nodes = {}
        
        if not hasattr(source_node_instance, '_input_connections'):
            return connected_nodes
        
        # This is a simplified version - in full implementation,
        # we might need to inject the main handler registry here
        # For now, we skip deep recursion to avoid complexity
        logger.debug(f"[DEBUG] Processor connected nodes building skipped for safety")
        
        return connected_nodes
    
    def _extract_result_output(self, result: Any) -> Any:
        """Extract the specific output from processor result."""
        if isinstance(result, dict):
            # Try common output keys
            for key in ["documents", "output", "content"]:
                if key in result:
                    return result[key]
        
        # Return full result if no specific key found
        logger.debug("[DEBUG] Using full stored result as fallback")
        return result


class TerminatorNodeHandler(NodeExecutionHandler):
    """
    Handler for Terminator node types.
    
    Terminator nodes usually finalize workflows or format outputs.
    They behave similarly to Processor nodes when being extracted as a connection.
    """
    
    def __init__(self):
        """Initialize terminator node handler."""
        super().__init__()
    
    def extract_connected_instance(self,
                                 connection_info: Dict[str, str],
                                 source_node_instance: Any,
                                 gnode_instance: Any,
                                 state: FlowState) -> Any:
        """Extract terminator node output."""
        node_id = connection_info["source_node_id"]
        input_name = connection_info.get("target_handle", "output")
        
        self._log_execution(node_id, "terminator", "extracting")
        
        # 1. Try to get cached output first
        if hasattr(state, 'node_outputs') and node_id in state.node_outputs:
            stored_result = state.node_outputs[node_id]
            if isinstance(stored_result, dict) and input_name in stored_result:
                return stored_result[input_name]
            return stored_result
        
        # 2. If no cache, try to execute it as a simple processor
        try:
            # Inject user_id
            self._inject_user_context(source_node_instance, state, node_id)
            
            # Simple execution for terminator (passing current state as inputs, templated dynamically)
            templated_inputs = apply_jinja_to_inputs(state.variables, state, node_id, self.nodes_registry)
            result = source_node_instance.execute(templated_inputs, {})
            return result
        except Exception as e:
            logger.warning(f"[TERMINATOR] Re-execution failed for {node_id}: {e}")
            return None


class NodeHandlerRegistry:
    """
    Registry for managing node execution handlers.
    
    This provides a clean interface for getting the appropriate handler
    based on node type, following the Factory Pattern.
    """
    
    def __init__(self):
        """Initialize the handler registry with default handlers."""
        self._handlers = {
            NodeType.MEMORY: MemoryNodeHandler(),
            NodeType.PROVIDER: ProviderNodeHandler(),
            NodeType.PROCESSOR: ProcessorNodeHandler(),
            NodeType.TERMINATOR: TerminatorNodeHandler()
        }
    
    def get_handler(self, node_type: NodeType) -> Optional[NodeExecutionHandler]:
        """Get the appropriate handler for a node type."""
        return self._handlers.get(node_type)
    
    def register_handler(self, node_type: NodeType, handler: NodeExecutionHandler):
        """Register a custom handler for a node type."""
        self._handlers[node_type] = handler
    
    def get_supported_types(self) -> List[NodeType]:
        """Get all supported node types."""
        return list(self._handlers.keys())


# Global registry instance
node_handler_registry = NodeHandlerRegistry()