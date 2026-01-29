"""
KAI-Fusion Node Execution Handlers - Clean Architecture Implementation
====================================================================

This module implements the Strategy Pattern for handling different node types
in the KAI-Fusion Graph Builder system. This replaces the monolithic
_extract_connected_node_instances function with clean, maintainable handlers.

Each handler is responsible for a specific node type execution pattern,
following Single Responsibility Principle and making the system extensible.

Authors: KAI-Fusion Development Team
Version: 3.0.0 - Clean Architecture Refactor
Last Updated: 2025-01-13
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import uuid

from app.core.state import FlowState
from app.nodes.base import NodeType
from app.core.credential_provider import credential_provider

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
        
        try:
            # Set session_id on memory nodes before execution
            source_node_instance.session_id = state.session_id
            logger.debug(
                f"[DEBUG] Set session_id on memory node {node_id}: {state.session_id}"
            )
            # Inject user_id if supported
            self._inject_user_context(source_node_instance, state, node_id)
            
            # Extract memory-specific inputs
            memory_inputs = self._extract_memory_inputs(source_node_instance, state)
            
            # Execute memory node to get instance
            node_instance = source_node_instance.execute(**memory_inputs)
            logger.debug(
                f"[DEBUG] Memory node {node_id} executed successfully: {type(node_instance).__name__}"
            )

            return node_instance
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to extract memory node {node_id}: {e}")
            raise RuntimeError(f"Memory node extraction failed for {node_id}: {str(e)}")
    
    def _extract_memory_inputs(self, source_node_instance: Any, state: FlowState) -> Dict[str, Any]:
        """Extract inputs needed for memory node execution."""
        memory_inputs = {}
        
        # Get memory node input specifications
        for input_spec in source_node_instance.metadata.inputs:
            if input_spec.name in source_node_instance.user_data:
                memory_inputs[input_spec.name] = source_node_instance.user_data[
                    input_spec.name
                ]
            elif input_spec.default is not None:
                memory_inputs[input_spec.name] = input_spec.default
        
        # Pass current state variables to memory node
        memory_inputs.update(state.variables)
        
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
    
    def extract_connected_instance(self,
                                 connection_info: Dict[str, str],
                                 source_node_instance: Any,
                                 gnode_instance: Any,
                                 state: FlowState) -> Any:
        """Extract provider node instance from user configuration and connections."""
        node_id = connection_info["source_node_id"]
        self._log_execution(node_id, "provider", "extracting")
        
        try:
            # Extract provider-specific inputs from user configuration
            provider_inputs = self._extract_provider_inputs(source_node_instance, state)
            
            # NEW: Extract connected inputs for provider nodes that need them
            connected_inputs = self._extract_connected_inputs(source_node_instance, gnode_instance, state)
            
            # Merge both input types
            all_inputs = {**provider_inputs, **connected_inputs}

            logger.debug(
                f"[DEBUG] Provider node {node_id} inputs: user={list(provider_inputs.keys())}, connected={list(connected_inputs.keys())}"
            )

            # Inject user_id from state into node instance before execution
            self._inject_user_context(source_node_instance, state, node_id)
            
            # Execute provider node to get LangChain object
            node_instance = source_node_instance.execute(**all_inputs)
            logger.debug(
                f"[DEBUG] Provider node {node_id} executed successfully: {type(node_instance).__name__}"
            )

            return node_instance
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to extract provider node {node_id}: {e}")
            raise RuntimeError(
                f"Provider node extraction failed for {node_id}: {str(e)}"
            )

    def _extract_provider_inputs(
        self, source_node_instance: Any, state: FlowState
    ) -> Dict[str, Any]:
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
    
    def _extract_connected_inputs(self, source_node_instance: Any, gnode_instance: Any, state: FlowState) -> Dict[str, Any]:
        """
        NEW: Extract connected inputs for provider nodes.
        
        This handles provider nodes like RetrieverProvider that need connections
        from other nodes (e.g., embedder from OpenAIEmbeddingsProvider).
        """
        connected_inputs = {}
        
        # Check if this provider node has any connected inputs
        if not hasattr(source_node_instance, '_input_connections'):
            return connected_inputs
        
        # Import here to avoid circular imports
        from app.core.output_cache import NodeConnectionExtractor
        
        # Create a temporary extractor to handle connections
        temp_extractor = NodeConnectionExtractor()
        
        # Process each connected input
        for input_name, connection_info in source_node_instance._input_connections.items():
            try:
                source_node_id = connection_info["source_node_id"]
                logger.debug(
                    f"[DEBUG] Provider extracting connected input '{input_name}' from {source_node_id}"
                )

                # Get source node instance from global registry (injected by GraphBuilder)
                if hasattr(self, 'nodes_registry') and source_node_id in self.nodes_registry:
                    source_gnode = self.nodes_registry[source_node_id]
                    source_instance = source_gnode.node_instance
                    source_node_type = source_instance.metadata.node_type
                    
                    # Handle different source node types
                    if source_node_type.value == "provider":
                        # Execute source provider to get its instance
                        provider_inputs = self._extract_provider_inputs(source_instance, state)
                        
                        # Inject user_id if supported
                        self._inject_user_context(source_instance, state, source_node_id)
                        
                        connected_result = source_instance.execute(**provider_inputs)
                        connected_inputs[input_name] = connected_result
                        logger.debug(
                            f"[DEBUG] Successfully extracted provider connection: {input_name} -> {type(connected_result).__name__}"
                        )

                    elif source_node_type.value == "processor":
                        # Try to get cached output from processor
                        if hasattr(state, 'node_outputs') and source_node_id in state.node_outputs:
                            cached_result = state.node_outputs[source_node_id]
                            connected_inputs[input_name] = cached_result
                            logger.debug(
                                f"[DEBUG] Successfully extracted processor connection: {input_name} -> {type(cached_result)}"
                            )
                        else:
                            logger.warning(
                                f"[WARNING] No cached output for processor {source_node_id}"
                            )

                    else:
                        logger.warning(
                            f"[WARNING] Unsupported connected node type for provider: {source_node_type}"
                        )

                else:
                    logger.error(
                        f"[ERROR] Source node {source_node_id} not found in registry"
                    )

            except Exception as e:
                logger.error(
                    f"[ERROR] Failed to extract connected input '{input_name}': {e}"
                )
                # Continue with other connections rather than failing completely
                continue
        
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
            logger.debug(
                f"[DEBUG] No cached output found for {node_id}, performing re-execution"
            )

            # Inject user_id if supported
            self._inject_user_context(source_node_instance, state, node_id)
            
            return self._re_execute_processor(source_node_instance, gnode_instance, state)
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to extract processor node {node_id}: {e}")
            raise RuntimeError(
                f"Processor node extraction failed for {node_id}: {str(e)}"
            )

    def _get_cached_output(
        self, node_id: str, input_name: str, state: FlowState
    ) -> Optional[Any]:
        """
        Intelligent cached output retrieval with multiple fallback strategies.
        
        Priority order:
        1. Direct input_name match in stored result
        2. Common fallbacks (documents, output)
        3. Full stored result
        """
        if not (hasattr(state, "node_outputs") and node_id in state.node_outputs):
            return None
        
        stored_result = state.node_outputs[node_id]
        logger.debug(
            f"[DEBUG] Found stored result for {node_id}: {type(stored_result)}"
        )

        # Try specific input_name first
        if isinstance(stored_result, dict):
            if input_name in stored_result:
                logger.debug(
                    f"[DEBUG] Found specific output '{input_name}' in stored result"
                )
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
    
    def _re_execute_processor(self, source_node_instance: Any, gnode_instance: Any, state: FlowState) -> Any:
        """
        Re-execute a processor node when cached output is not available.
        
        This builds the proper input context and connected_nodes for execution.
        """
        logger.debug(
            f"[DEBUG] Re-executing processor node {source_node_instance.__class__.__name__}"
        )
        # Extract user inputs for processor
        processor_inputs = self._extract_processor_inputs(source_node_instance, state)
        
        # Build connected nodes for processor (recursive but controlled)
        processor_connected_nodes = self._build_connected_nodes_for_processor(
            source_node_instance, gnode_instance, state
        )

        logger.debug(f"[DEBUG] Processor inputs: {list(processor_inputs.keys())}")
        logger.debug(
            f"[DEBUG] Processor connected nodes: {list(processor_connected_nodes.keys())}"
        )

        # Execute processor with proper context
        result = source_node_instance.execute(processor_inputs, processor_connected_nodes)
        print(f"[DEBUG] Processor re-execution completed: {type(result)}")
        
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
        logger.debug("[DEBUG] Processor connected nodes building skipped for safety")
        return connected_nodes
    
    def _extract_result_output(self, result: Any) -> Any:
        """Extract the specific output from processor result."""
        if isinstance(result, dict):
            # Try common output keys
            for key in ["documents", "output", "content"]:
                if key in result:
                    return result[key]
        
        # Return full result if no specific key found
        return result


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
            NodeType.PROCESSOR: ProcessorNodeHandler()
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