"""
GraphBuilder Connection Mapper
=============================

Handles all connection parsing, mapping, and validation for the GraphBuilder system.
Provides clean separation of connection management logic from the main orchestrator.

AUTHORS: KAI-Fusion Workflow Orchestration Team
VERSION: 2.1.0
LAST_UPDATED: 2025-09-16  
LICENSE: Proprietary - KAI-Fusion Platform
"""

from typing import Dict, Any, List, Optional
import logging

from .types import (
    NodeConnection, GraphNodeInstance, NodeConnectionMap,
    ConnectionInfo, ConnectionStatus, NodeInstanceRegistry
)
from .exceptions import ConnectionError
from app.core.connection_manager import ConnectionManager, NodeConnectionMap as CoreNodeConnectionMap
from app.core.connection_pool import ConnectionPool, PooledConnection
from app.nodes import BaseNode


logger = logging.getLogger(__name__)


class ConnectionMapper:
    """
    Handles all connection parsing, mapping, and validation.
    
    Provides clean separation of connection management logic including:
    - Parsing UI edges into internal connection format
    - Building enhanced connection mappings using ConnectionManager
    - Fallback basic connection mapping for compatibility
    - Connection validation and error handling
    """
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        self.connection_manager = connection_manager or ConnectionManager()
        self.connections: List[NodeConnection] = []
        self._connection_stats: Dict[str, Any] = {}
    
    def parse_connections(self, edges: List[Dict[str, Any]]) -> List[NodeConnection]:
        """
        Parse edges into internal connection format with handle support.
        
        Args:
            edges: List of edge dictionaries from the UI
            
        Returns:
            List of parsed NodeConnection objects
            
        Raises:
            ConnectionError: If connection parsing fails
        """
        try:
            connections = []
            
            if edges:
                logger.info(f" PARSING CONNECTIONS ({len(edges)} edges)")

            for edge in edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                source_handle = edge.get("sourceHandle", "output")
                target_handle = edge.get("targetHandle", "input")
                data_type = edge.get("type", "any")

                # Validate required fields
                if not source or not target:
                    logger.warning(f"Skipping invalid edge: missing source or target")
                    continue

                # Create connection object
                conn = NodeConnection(
                    source_node_id=source,
                    source_handle=source_handle,
                    target_node_id=target,
                    target_handle=target_handle,
                    data_type=data_type,
                )
                
                connections.append(conn)
                logger.debug(
                    f"{source}[{source_handle}] ➜ {target}[{target_handle}]"
                )

            # Store connections for later use
            self.connections = connections

            logger.info(f" Parsed {len(connections)} connections successfully")
            return connections
            
        except Exception as e:
            raise ConnectionError(
                f"Failed to parse connections: {str(e)}",
                validation_errors=[str(e)]
            ) from e
    
    def build_enhanced_connection_mappings(
        self, 
        connections: List[NodeConnection], 
        nodes: Dict[str, BaseNode]
    ) -> Dict[str, NodeConnectionMap]:
        """
        Build enhanced connection mappings using ConnectionManager.
        
        Args:
            connections: List of NodeConnection objects
            nodes: Dictionary of node instances by ID
            
        Returns:
            Dictionary of NodeConnectionMap objects by node ID
            
        Raises:
            ConnectionError: If enhanced mapping fails
        """
        try:
            logger.info(" Building enhanced connection mappings")

            # Use ConnectionManager to build mappings
            core_mappings = self.connection_manager.build_connection_mappings(
                connections, nodes
            )
            
            # Convert core mappings to our format if needed
            enhanced_mappings = {}
            for node_id, core_mapping in core_mappings.items():
                # The core mapping is already in the right format
                enhanced_mappings[node_id] = core_mapping
            
            # Store connection statistics
            self._connection_stats = self.connection_manager.get_connection_stats()

            logger.info(f" Enhanced connection mappings built successfully")
            logger.info(f" Connection Stats: {self._connection_stats}")

            return enhanced_mappings
            
        except Exception as e:
            raise ConnectionError(
                f"Enhanced connection mapping failed: {str(e)}",
                validation_errors=[str(e)]
            ) from e
    
    def apply_connection_mappings(
        self,
        connection_mappings: Dict[str, CoreNodeConnectionMap],
        nodes: NodeInstanceRegistry
    ) -> None:
        """
        Apply enhanced connection mappings to node instances with pool-aware many-to-many support.
        
        Args:
            connection_mappings: Dictionary of connection mappings
            nodes: Dictionary of GraphNodeInstance objects
        """
        try:
            pool_enabled = self._is_pool_enabled()
            logger.info(
                f" Applying connection mappings with pool {'enabled' if pool_enabled else 'disabled'}"
            )

            for node_id, connection_map in connection_mappings.items():
                if node_id not in nodes:
                    logger.warning(f"Node {node_id} not found in node registry")
                    continue
                
                node_instance = nodes[node_id].node_instance
                
                # Convert ConnectionInfo objects to the format expected by nodes
                input_connections = {}
                output_connections = {}

                # Process input connections with pool awareness
                for handle, conn_info in connection_map.input_connections.items():
                    if pool_enabled:
                        # Pool-aware: Get multiple connections from pool
                        pool_connections = self._extract_pool_connections(node_id, handle)
                        
                        if pool_connections:
                            # CRITICAL FIX: Only use list format when there are actually multiple connections
                            if len(pool_connections) > 1:
                                # Many-to-many: Use list of connections from pool
                                input_connections[handle] = pool_connections
                                logger.debug(
                                    f"[POOL] Input: {node_id}.{handle} <- {len(pool_connections)} connections [MANY-TO-MANY]"
                                )
                            else:
                                # Single connection: Store as dict for backward compatibility
                                input_connections[handle] = pool_connections[0]
                                logger.debug(
                                    f"[POOL] Input: {node_id}.{handle} <- 1 connection [SINGLE-DICT]"
                                )
                        else:
                            # Fallback to single connection if pool has no connections
                            input_connections[handle] = {
                                "source_node_id": conn_info.source_node_id,
                                "source_handle": conn_info.source_handle,
                                "data_type": conn_info.data_type,
                                "status": conn_info.status.value,
                                "validation_errors": conn_info.validation_errors
                            }
                            logger.debug(
                                f"[POOL-FALLBACK] Input: {node_id}.{handle} <- {conn_info.source_node_id}.{conn_info.source_handle}"
                            )
                    else:
                        # Traditional one-to-one: Backward compatibility mode
                        input_connections[handle] = {
                            "source_node_id": conn_info.source_node_id,
                            "source_handle": conn_info.source_handle,
                            "data_type": conn_info.data_type,
                            "status": conn_info.status.value,
                            "validation_errors": conn_info.validation_errors
                        }
                        logger.debug(
                            f"[TRADITIONAL] Input: {node_id}.{handle} <- {conn_info.source_node_id}.{conn_info.source_handle}"
                        )

                # Process output connections (always supports multiple)
                for handle, conn_list in connection_map.output_connections.items():
                    output_connections[handle] = []
                    for conn_info in conn_list:
                        output_connections[handle].append(
                            {
                                "target_node_id": conn_info.target_node_id,
                                "target_handle": conn_info.target_handle,
                                "data_type": conn_info.data_type,
                                "status": conn_info.status.value,
                                "validation_errors": conn_info.validation_errors,
                            }
                        )
                        logger.debug(
                            f"[ENHANCED] Output: {node_id}.{handle} -> {conn_info.target_node_id}.{conn_info.target_handle}"
                        )

                # Apply connections to node instance
                if pool_enabled:
                    self._apply_pool_connections(node_instance, input_connections)
                else:
                    node_instance._input_connections = input_connections
                    
                node_instance._output_connections = output_connections
                
                # Log connection summary
                input_count = len(input_connections)
                total_input_connections = sum(
                    len(conns) if isinstance(conns, list) else 1
                    for conns in input_connections.values()
                )
                output_count = sum(len(conns) for conns in output_connections.values())
                
                if pool_enabled and total_input_connections > input_count:
                    logger.info(
                        f"    {node_id}: {input_count} handles, {total_input_connections} input connections, {output_count} outputs [MANY-TO-MANY]"
                    )
                else:
                    logger.info(
                        f"    {node_id}: {input_count} inputs, {output_count} outputs [TRADITIONAL]"
                    )

        except Exception as e:
            logger.error(f"Failed to apply connection mappings: {e}")
            raise ConnectionError(
                f"Failed to apply connection mappings: {str(e)}",
                validation_errors=[str(e)]
            ) from e
    
    def build_basic_connection_mappings(
        self, 
        connections: List[NodeConnection], 
        nodes: NodeInstanceRegistry
    ) -> None:
        """
        Fallback basic connection mapping when enhanced mapping fails.
        
        This provides a simple connection mapping implementation that directly
        maps connections without advanced validation or features.
        
        Args:
            connections: List of NodeConnection objects
            nodes: Dictionary of GraphNodeInstance objects
        """
        try:
            logger.info("Using basic connection mapping (fallback)")
            
            for node_id, gnode in nodes.items():
                # Build basic connection mapping
                input_connections = {}
                output_connections = {}
                
                # Find all connections targeting this node (inputs)
                for conn in connections:
                    if conn.target_node_id == node_id:
                        input_connections[conn.target_handle] = {
                            "source_node_id": conn.source_node_id,
                            "source_handle": conn.source_handle,
                            "data_type": conn.data_type
                        }
                        logger.debug(
                            f"[BASIC] Input mapping: {node_id}.{conn.target_handle} <- {conn.source_node_id}.{conn.source_handle}"
                        )

                    # Find all connections from this node (outputs)
                    if conn.source_node_id == node_id:
                        if conn.source_handle not in output_connections:
                            output_connections[conn.source_handle] = []
                        output_connections[conn.source_handle].append(
                            {
                                "target_node_id": conn.target_node_id,
                                "target_handle": conn.target_handle,
                                "data_type": conn.data_type,
                            }
                        )
                        logger.debug(
                            f"[BASIC] Output mapping: {node_id}.{conn.source_handle} -> {conn.target_node_id}.{conn.target_handle}"
                        )

                # Set connection mappings on the node instance
                gnode.node_instance._input_connections = input_connections
                gnode.node_instance._output_connections = output_connections
                
                # Log instantiation
                config_keys = list(gnode.user_data.keys()) if gnode.user_data else []
                logger.info(
                    f"    {node_id} ({gnode.type}) | Config: {len(config_keys)} | I/O: {len(input_connections)}/{len(output_connections)}"
                )

            # Create basic stats
            self._connection_stats = {
                "total_connections": len(connections),
                "mapping_type": "basic",
                "nodes_with_inputs": sum(1 for _, gnode in nodes.items() if hasattr(gnode.node_instance, '_input_connections') and gnode.node_instance._input_connections),
                "nodes_with_outputs": sum(1 for _, gnode in nodes.items() if hasattr(gnode.node_instance, '_output_connections') and gnode.node_instance._output_connections)
            }
            
            logger.info("Basic connection mapping completed")
            
        except Exception as e:
            logger.error(f"Basic connection mapping failed: {e}")
            raise ConnectionError(
                f"Basic connection mapping failed: {str(e)}",
                validation_errors=[str(e)]
            ) from e
    
    def _is_pool_enabled(self) -> bool:
        """
        Check if connection manager has pool enabled.
        
        Returns:
            bool: True if pool is enabled and available, False otherwise
        """
        try:
            return (hasattr(self.connection_manager, '_pool_enabled') and
                    self.connection_manager._pool_enabled and
                    hasattr(self.connection_manager, '_connection_pool') and
                    self.connection_manager._connection_pool is not None)
        except Exception as e:
            logger.debug(f"Error checking pool status: {e}")
            return False
    
    def _extract_pool_connections(self, node_id: str, handle: str) -> List[Dict[str, Any]]:
        """
        Extract connections from pool for a specific node handle.
        
        Args:
            node_id: ID of the target node
            handle: Input handle name
            
        Returns:
            List of connection dictionaries for many-to-many support
        """
        try:
            if not self._is_pool_enabled():
                return []
            
            # Get multiple connections from the connection manager's pool
            connection_infos = self.connection_manager.get_multiple_input_connections(node_id, handle)
            
            # Convert to the format expected by nodes
            pool_connections = []
            for conn_info in connection_infos:
                pool_connections.append({
                    "source_node_id": conn_info.source_node_id,
                    "source_handle": conn_info.source_handle,
                    "data_type": conn_info.data_type,
                    "status": conn_info.status.value,
                    "validation_errors": conn_info.validation_errors
                })
            
            logger.debug(f"Extracted {len(pool_connections)} pool connections for {node_id}:{handle}")
            return pool_connections
            
        except Exception as e:
            logger.error(f"Error extracting pool connections: {e}")
            return []
    
    def _apply_pool_connections(self, node_instance, input_connections: Dict[str, Any]) -> None:
        """
        Apply pool-based multiple connections to node instance.
        
        Args:
            node_instance: The node instance to apply connections to
            input_connections: Dictionary of input connections to apply
        """
        try:
            # Set the enhanced connection mappings with many-to-many support
            node_instance._input_connections = input_connections
            logger.debug(f"Applied pool-based connections to node instance")
        except Exception as e:
            logger.error(f"Error applying pool connections: {e}")
            raise ConnectionError(f"Failed to apply pool connections: {str(e)}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics and metrics.
        
        Returns:
            Dictionary containing connection statistics
        """
        return self._connection_stats.copy()
    
    def validate_connections(
        self, 
        connections: List[NodeConnection], 
        available_nodes: Dict[str, str]
    ) -> List[str]:
        """
        Validate connections against available nodes.
        
        Args:
            connections: List of connections to validate
            available_nodes: Dictionary of available node IDs and types
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for conn in connections:
            # Check if source node exists
            if conn.source_node_id not in available_nodes:
                errors.append(f"Connection references unknown source node: {conn.source_node_id}")
            
            # Check if target node exists
            if conn.target_node_id not in available_nodes:
                errors.append(
                    f"Connection references unknown target node: {conn.target_node_id}"
                )

        return errors
    
    def get_node_connection_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get connection information for a specific node.
        
        Args:
            node_id: ID of the node to get information for
            
        Returns:
            Dictionary with connection information or None if not found
        """
        input_connections = [conn for conn in self.connections if conn.target_node_id == node_id]
        output_connections = [conn for conn in self.connections if conn.source_node_id == node_id]
        
        if not input_connections and not output_connections:
            return None
        
        return {
            "node_id": node_id,
            "input_connections": [conn.__dict__ for conn in input_connections],
            "output_connections": [conn.__dict__ for conn in output_connections],
            "input_count": len(input_connections),
            "output_count": len(output_connections)
        }
    
    def clear_connections(self) -> None:
        """Clear all stored connections and statistics."""
        self.connections.clear()
        self._connection_stats.clear()
        logger.debug("Cleared all connection data")