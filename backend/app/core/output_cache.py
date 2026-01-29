"""
KAI-Fusion Node Output Cache Management - Intelligent State Caching System
==========================================================================

This module implements sophisticated caching and retrieval mechanisms for
node outputs in the KAI-Fusion Graph Builder system. It provides intelligent
output management with multiple fallback strategies and performance optimization.

This replaces the ad-hoc caching logic scattered throughout the graph builder
with a centralized, maintainable cache management system.

Features:
- Intelligent cache retrieval with multiple fallback strategies
- Type-aware output extraction
- Performance optimization for large workflows
- Consistent data access patterns
- Comprehensive error handling

Authors: KAI-Fusion Development Team
Version: 3.0.0 - Clean Architecture Refactor
Last Updated: 2025-01-13
"""

from typing import Dict, Any, Optional, List, Union
import logging
from datetime import datetime

from app.core.state import FlowState

logger = logging.getLogger(__name__)


class NodeOutputCache:
    """
    Intelligent node output cache with advanced retrieval strategies.

    This class provides centralized management of node outputs with
    smart fallback mechanisms and performance optimization. It handles
    the complexity of retrieving cached data from various storage locations.
    """

    def __init__(self):
        """Initialize the output cache manager."""
        self.access_stats = {}  # Track cache access patterns for optimization

    def get_cached_output(
        self, node_id: str, input_name: str, state: FlowState
    ) -> Optional[Any]:
        """
        Retrieve cached output with intelligent fallback strategies.

        Priority order:
        1. Direct input_name match in stored result
        2. Common fallback keys (documents, output, content)
        3. Full stored result as last resort

        Args:
            node_id: ID of the source node to get output from
            input_name: Name of the specific input/output we need
            state: Current workflow state containing cached outputs

        Returns:
            Cached output if found, None if not available
        """
        start_time = datetime.now()

        try:
            # Check if node has any stored output
            if not self._has_cached_output(node_id, state):
                self._record_cache_miss(node_id, input_name)
                return None

            stored_result = state.node_outputs[node_id]
            logger.debug(
                f"[CACHE] Found stored result for {node_id}: {type(stored_result)}"
            )

            # Strategy 1: Direct input name match
            result = self._try_direct_match(stored_result, input_name)
            if result is not None:
                self._record_cache_hit(node_id, input_name, "direct_match")
                return result

            # Strategy 2: Common fallback keys
            result = self._try_fallback_keys(stored_result, input_name)
            if result is not None:
                self._record_cache_hit(node_id, input_name, "fallback_key")
                return result

            # Strategy 3: Full result fallback
            logger.debug(
                f"[CACHE] Using full stored result as fallback for {input_name}"
            )
            self._record_cache_hit(node_id, input_name, "full_result")
            return stored_result

        except Exception as e:
            logger.error(
                f"[CACHE ERROR] Failed to retrieve cached output for {node_id}: {e}"
            )
            self._record_cache_error(node_id, input_name, str(e))
            return None
        finally:
            # Track access time for performance monitoring
            access_duration = (datetime.now() - start_time).total_seconds() * 1000
            self._record_access_time(node_id, access_duration)

    def _has_cached_output(self, node_id: str, state: FlowState) -> bool:
        """Check if node has any cached output available."""
        return (
            hasattr(state, "node_outputs")
            and isinstance(state.node_outputs, dict)
            and node_id in state.node_outputs
        )

    def _try_direct_match(self, stored_result: Any, input_name: str) -> Optional[Any]:
        """Try to find direct match for input_name in stored result."""
        if isinstance(stored_result, dict) and input_name in stored_result:
            result = stored_result[input_name]
            logger.debug(
                f"[CACHE] Direct match found for '{input_name}': {type(result)}"
            )
            if input_name == "documents" and isinstance(result, list):
                logger.debug(f"[CACHE] Documents list length: {len(result)}")
            return result
        return None

    def _try_fallback_keys(self, stored_result: Any, input_name: str) -> Optional[Any]:
        """Try common fallback keys when direct match fails."""
        if not isinstance(stored_result, dict):
            return None

        # Common fallback mappings
        fallback_keys = {
            "documents": ["documents", "document", "content", "output"],
            "content": ["content", "output", "text", "documents"],
            "output": ["output", "result", "content"],
            "input": ["input", "content", "text", "output"],
        }

        # Try fallbacks for this input_name
        for fallback_key in fallback_keys.get(input_name, ["documents", "output"]):
            if fallback_key in stored_result:
                result = stored_result[fallback_key]
                logger.debug(
                    f"[CACHE] Fallback match '{fallback_key}' for '{input_name}': {type(result)}"
                )
                return result

        return None

    def store_output(
        self,
        node_id: str,
        output: Any,
        state: FlowState,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Store node output in cache with metadata.

        Args:
            node_id: ID of the node producing the output
            output: The output data to cache
            state: Current workflow state
            metadata: Optional metadata about the output
        """
        try:
            if not hasattr(state, "node_outputs"):
                state.node_outputs = {}

            state.node_outputs[node_id] = output  # Keep simple for compatibility
            logger.debug(f"[CACHE] Stored output for {node_id}: {type(output)}")

        except Exception as e:
            logger.error(f"[CACHE ERROR] Failed to store output for {node_id}: {e}")

    def clear_cache_for_node(self, node_id: str, state: FlowState):
        """Clear cached output for a specific node."""
        if hasattr(state, "node_outputs") and node_id in state.node_outputs:
            del state.node_outputs[node_id]
            logger.debug(f"[CACHE] Cleared cache for {node_id}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        return {
            "access_patterns": self.access_stats,
            "total_accesses": sum(
                stats["accesses"] for stats in self.access_stats.values()
            ),
            "cache_hit_rate": self._calculate_hit_rate(),
            "average_access_time": self._calculate_average_access_time(),
        }

    # Performance monitoring methods
    def _record_cache_hit(self, node_id: str, input_name: str, strategy: str):
        """Record successful cache retrieval."""
        key = f"{node_id}:{input_name}"
        if key not in self.access_stats:
            self.access_stats[key] = {
                "hits": 0,
                "misses": 0,
                "errors": 0,
                "accesses": 0,
            }

        self.access_stats[key]["hits"] += 1
        self.access_stats[key]["accesses"] += 1
        logger.debug(f"Cache hit for {key} using {strategy}")

    def _record_cache_miss(self, node_id: str, input_name: str):
        """Record cache miss."""
        key = f"{node_id}:{input_name}"
        if key not in self.access_stats:
            self.access_stats[key] = {
                "hits": 0,
                "misses": 0,
                "errors": 0,
                "accesses": 0,
            }

        self.access_stats[key]["misses"] += 1
        self.access_stats[key]["accesses"] += 1
        logger.debug(f"Cache miss for {key}")

    def _record_cache_error(self, node_id: str, input_name: str, error: str):
        """Record cache access error."""
        key = f"{node_id}:{input_name}"
        if key not in self.access_stats:
            self.access_stats[key] = {
                "hits": 0,
                "misses": 0,
                "errors": 0,
                "accesses": 0,
            }

        self.access_stats[key]["errors"] += 1
        self.access_stats[key]["accesses"] += 1
        logger.warning(f"Cache error for {key}: {error}")

    def _record_access_time(self, node_id: str, duration_ms: float):
        """Record cache access time for performance monitoring."""
        if node_id not in self.access_stats:
            self.access_stats[node_id] = {"access_times": []}
        elif "access_times" not in self.access_stats[node_id]:
            self.access_stats[node_id]["access_times"] = []

        # Keep only last 100 access times to prevent memory bloat
        access_times = self.access_stats[node_id]["access_times"]
        access_times.append(duration_ms)
        if len(access_times) > 100:
            access_times.pop(0)

    def _calculate_hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        total_hits = sum(stats.get("hits", 0) for stats in self.access_stats.values())
        total_accesses = sum(
            stats.get("accesses", 0) for stats in self.access_stats.values()
        )

        if total_accesses == 0:
            return 0.0

        return (total_hits / total_accesses) * 100

    def _calculate_average_access_time(self) -> float:
        """Calculate average cache access time."""
        all_times = []
        for stats in self.access_stats.values():
            all_times.extend(stats.get("access_times", []))

        if not all_times:
            return 0.0

        return sum(all_times) / len(all_times)


class NodeConnectionExtractor:
    """
    High-level extractor that coordinates node handlers and cache management.

    This replaces the monolithic _extract_connected_node_instances function
    with a clean, maintainable implementation using Strategy Pattern.
    """

    def __init__(self, handler_registry=None):
        """Initialize with handler registry and cache manager."""
        # Import here to avoid circular imports
        from app.core.node_handlers import node_handler_registry

        self.handler_registry = handler_registry or node_handler_registry
        self.output_cache = NodeOutputCache()
        self.nodes_registry = {}  # Will be injected by GraphBuilder

    def extract_connected_instances(
        self, gnode: Any, state: FlowState, nodes_registry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main extraction method replacing the monolithic function.

        This is the clean, maintainable replacement for
        _extract_connected_node_instances that uses Strategy Pattern.
        """
        self.nodes_registry = nodes_registry
        connected = {}

        # Validate input connections exist
        if not hasattr(gnode.node_instance, "_input_connections"):
            logger.debug(f"[DEBUG] No input connections found for {gnode.id}")
            return connected

        logger.debug(
            f"[DEBUG] Extracting {len(gnode.node_instance._input_connections)} connections for {gnode.id}"
        )

        # Process each input connection
        for (
            input_name,
            connection_info,
        ) in gnode.node_instance._input_connections.items():
            try:
                result = self._process_connection(input_name, connection_info, state)

                if result is not None:
                    connected[input_name] = result
                    connection_count = (
                        len(connection_info) if isinstance(connection_info, list) else 1
                    )
                    logger.debug(
                        f"[DEBUG] Successfully connected {input_name} with {connection_count} connection(s)"
                    )
                else:
                    logger.debug(f"[DEBUG] No result for connection {input_name}")

            except Exception as e:
                logger.error(f"[ERROR] Failed to extract connection {input_name}: {e}")
                import traceback

                logger.error(f"[ERROR] Stack trace: {traceback.format_exc()}")
                continue

        logger.debug(
            f"[DEBUG] Extraction completed: {len(connected)} connections established"
        )
        return connected

    def _process_connection(
        self,
        input_name: str,
        connection_info: Union[Dict[str, str], List[Dict[str, str]]],
        state: FlowState,
    ) -> Optional[Any]:
        """
        Unified connection processing that handles both single and multiple connections.

        Args:
            input_name: Name of the input handle
            connection_info: Single connection dict or list of connection dicts
            state: Current flow state

        Returns:
            Processed connection result (single value or aggregated for multiple)
        """
        if isinstance(connection_info, list):
            logger.debug(
                f"[DEBUG] Processing {len(connection_info)} multiple connections for {input_name}"
            )
            return self._extract_many_connections(input_name, connection_info, state)
        else:
            logger.debug(f"[DEBUG] Processing single connection for {input_name}")
            return self._extract_single_connection(input_name, connection_info, state)

    def _extract_single_connection(
        self, input_name: str, connection_info: Dict[str, str], state: FlowState
    ) -> Optional[Any]:
        """Extract a single connection using appropriate handler."""
        source_node_id = connection_info["source_node_id"]

        # Get source node instance
        if source_node_id not in self.nodes_registry:
            logger.error(f"[ERROR] Source node {source_node_id} not found in registry")
            return None

        gnode_instance = self.nodes_registry[source_node_id]
        source_node_instance = gnode_instance.node_instance
        node_type = source_node_instance.metadata.node_type

        # Get appropriate handler
        handler = self.handler_registry.get_handler(node_type)
        if not handler:
            logger.error(f"[ERROR] No handler found for node type: {node_type}")
            return None

        # Pass nodes_registry to handler for connected input resolution
        if hasattr(handler, "nodes_registry"):
            handler.nodes_registry = self.nodes_registry

        # Use handler to extract connection
        result = handler.extract_connected_instance(
            connection_info, source_node_instance, gnode_instance, state
        )

        logger.debug(
            f"[DEBUG] Single connection result for {input_name} from {source_node_id}: {type(result)}"
        )
        return result

    def _extract_many_connections(
        self, input_name: str, connection_list: List[Dict[str, str]], state: FlowState
    ) -> Optional[Any]:
        """
        REDESIGNED: Extract and aggregate multiple connections for a single input.

        This method properly handles lists of connection dictionaries and aggregates
        the results using intelligent strategies.

        Args:
            input_name: Name of the input handle
            connection_list: List of connection dictionaries
            state: Current flow state

        Returns:
            Aggregated result from multiple connections
        """
        if not connection_list:
            logger.debug(f"[DEBUG] Empty connection list for {input_name}")
            return None

        logger.debug(
            f"[DEBUG] Processing {len(connection_list)} connections for {input_name}"
        )

        # Extract results from each connection
        results = []
        for i, connection_info in enumerate(connection_list):
            try:
                if not isinstance(connection_info, dict):
                    logger.error(
                        f"[ERROR] Invalid connection format at index {i}: {type(connection_info)}"
                    )
                    continue

                source_node_id = connection_info.get("source_node_id")
                if not source_node_id:
                    logger.error(f"[ERROR] Missing source_node_id in connection {i}")
                    continue

                logger.debug(
                    f"[DEBUG] Processing connection {i + 1}/{len(connection_list)}: {source_node_id}"
                )

                # Extract single connection result
                result = self._extract_single_connection(
                    input_name, connection_info, state
                )
                if result is not None:
                    results.append(
                        {
                            "source": source_node_id,
                            "handle": connection_info.get("source_handle", "output"),
                            "data": result,
                        }
                    )
                    logger.debug(f"✓ Connection {i + 1} successful: {source_node_id}")
                else:
                    logger.debug(
                        f"✗ Connection {i + 1} returned None: {source_node_id}"
                    )

            except Exception as e:
                logger.error(f"Failed to process connection {i}: {e}")
                continue

        if not results:
            logger.debug(f"No successful connections for {input_name}")
            return None

        # Aggregate the results using intelligent strategies
        aggregated = self._aggregate_multiple_results(
            input_name, results, connection_list
        )
        logger.debug(
            f"[DEBUG] Aggregated {len(results)} results for {input_name}: {type(aggregated)}"
        )

        return aggregated

    def _aggregate_multiple_results(
        self,
        input_name: str,
        results: List[Dict[str, Any]],
        connection_info: List[Dict[str, str]],
    ) -> Any:
        """
        Aggregate multiple connection results using intelligent strategies.

        Args:
            input_name: Name of the input being processed
            results: List of successful connection results
            connection_info: Original connection info for priority/metadata

        Returns:
            Intelligently aggregated result
        """
        if not results:
            return None

        if len(results) == 1:
            return results[0]["data"]

        # Extract just the data values for processing
        data_values = [result["data"] for result in results]

        logger.debug(f"Aggregating {len(data_values)} results for {input_name}")

        # Strategy 1: Tool aggregation (for tools input)
        if input_name.lower() in ["tools", "tool", "tool_list"]:
            return self._aggregate_tools(data_values, results)

        # Strategy 2: Document aggregation (for documents, content)
        elif input_name.lower() in ["documents", "document", "content", "data"]:
            return self._aggregate_documents(data_values)

        # Strategy 3: List aggregation (default for most cases)
        elif all(isinstance(val, list) for val in data_values):
            return self._aggregate_lists(data_values)

        # Strategy 4: String concatenation
        elif all(isinstance(val, str) for val in data_values):
            logger.debug(f"Using string concatenation for {input_name}")
            return self._aggregate_strings(data_values)

        # Strategy 5: Dictionary merging
        elif all(isinstance(val, dict) for val in data_values):
            logger.debug(f"Using dictionary merging for {input_name}")
            return self._aggregate_dicts(data_values)

        # Fallback: Return as list for further processing
        else:
            logger.debug(
                f"[DEBUG] Fallback aggregation: returning list of {len(data_values)} items"
            )
            logger.debug(
                f"[DEBUG] Data types: {[type(val).__name__ for val in data_values]}"
            )
            return data_values

    def _aggregate_tools(
        self, data_values: List[Any], results: List[Dict[str, Any]]
    ) -> List[Any]:
        """Aggregate tool connections into a unified tool list."""
        tools = []
        for i, data in enumerate(data_values):
            source = results[i]["source"]

            if isinstance(data, list):
                tools.extend(data)
                logger.debug(f"[DEBUG] Added {len(data)} tools from list in {source}")
            elif isinstance(data, dict):
                # Handle dict responses from providers (CRITICAL FIX for "string indices" error)
                if "tools" in data:
                    tool_data = data["tools"]
                    if isinstance(tool_data, list):
                        tools.extend(tool_data)
                        logger.debug(
                            f"[DEBUG] Added {len(tool_data)} tools from dict.tools in {source}"
                        )
                    else:
                        tools.append(tool_data)
                        logger.debug(
                            f"[DEBUG] Added single tool from dict.tools in {source}"
                        )
                elif "tool" in data:
                    # Alternative key for single tools
                    tools.append(data["tool"])
                    logger.debug(
                        f"[DEBUG] Added single tool from dict.tool in {source}"
                    )
                else:
                    # Dict might be the tool itself (for some tool types)
                    logger.warning(
                        f"[WARNING] Dict without 'tools' key from {source}, treating as tool object"
                    )
                    tools.append(data)
            else:
                tools.append(data)
                logger.debug(
                    f"[DEBUG] Added single tool ({type(data).__name__}) from {source}"
                )

        logger.debug(f"[DEBUG] Tool aggregation complete: {len(tools)} total tools")
        return tools

    def _aggregate_documents(self, data_values: List[Any]) -> List[Any]:
        """Aggregate document connections."""
        documents = []
        for data in data_values:
            if isinstance(data, list):
                documents.extend(data)
            else:
                documents.append(data)
        return documents

    def _aggregate_lists(self, data_values: List[List[Any]]) -> List[Any]:
        """Flatten and aggregate list values."""
        aggregated = []
        for data_list in data_values:
            aggregated.extend(data_list)
        return aggregated

    def _aggregate_strings(self, data_values: List[str]) -> str:
        """Concatenate string values with separator."""
        return " | ".join(data_values)

    def _aggregate_dicts(self, data_values: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge dictionary values."""
        merged = {}
        for data_dict in data_values:
            merged.update(data_dict)
        return merged

    def set_nodes_registry(self, nodes_registry: Dict[str, Any]):
        """
         FIX: Set the nodes registry for connection extraction.

        This method is called by GraphBuilder to inject the nodes registry
        so that connection extraction can find source nodes.
        """
        self.nodes_registry = nodes_registry

        # Also update handlers with the registry
        for handler in self.handler_registry._handlers.values():
            if hasattr(handler, "nodes_registry"):
                handler.nodes_registry = nodes_registry

        logger.info(
            f"Nodes registry set: {len(nodes_registry)} nodes available for connection extraction"
        )


# Global instance for use in GraphBuilder
default_connection_extractor = NodeConnectionExtractor()
