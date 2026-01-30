"""
KAI-Fusion Connection Pool System
================================

Advanced connection pooling system for managing many-to-many connections between workflow nodes.
This module provides the foundation for converting the connection manager from one-to-one 
to many-to-many connections.

Features:
- Efficient connection indexing and retrieval
- Connection lifecycle management
- Pool statistics and monitoring
- Type-safe connection handling
- Comprehensive logging and error handling
"""

import time
import uuid
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .exceptions import AgentFlowException, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class PooledConnection:
    """
    Represents a single connection in the connection pool.
    
    This dataclass encapsulates all necessary information about a connection
    between two node handles, including metadata for tracking and validation.
    
    Attributes:
        connection_id: Unique identifier for this connection
        source_node_id: ID of the source node
        source_handle: Output handle name on the source node
        target_node_id: ID of the target node
        target_handle: Input handle name on the target node
        data_type: Type of data flowing through this connection
        status: Current status of the connection (valid, invalid, pending)
        created_at: Timestamp when connection was created
        priority: Connection priority for ordering (higher = more important)
    """
    connection_id: str
    source_node_id: str
    source_handle: str
    target_node_id: str
    target_handle: str
    data_type: str = "any"
    status: str = "valid"
    created_at: float = field(default_factory=time.time)
    priority: int = 0

    def __post_init__(self):
        """Validate connection data after initialization."""
        if not self.connection_id:
            raise ValidationError("Connection ID cannot be empty")
        if not self.source_node_id:
            raise ValidationError("Source node ID cannot be empty")
        if not self.target_node_id:
            raise ValidationError("Target node ID cannot be empty")
        if not self.source_handle:
            raise ValidationError("Source handle cannot be empty")
        if not self.target_handle:
            raise ValidationError("Target handle cannot be empty")

    @property
    def connection_key(self) -> str:
        """Generate a unique key for this connection."""
        return f"{self.source_node_id}:{self.source_handle}->{self.target_node_id}:{self.target_handle}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert connection to dictionary representation."""
        return {
            "connection_id": self.connection_id,
            "source_node_id": self.source_node_id,
            "source_handle": self.source_handle,
            "target_node_id": self.target_node_id,
            "target_handle": self.target_handle,
            "data_type": self.data_type,
            "status": self.status,
            "created_at": self.created_at,
            "priority": self.priority,
            "connection_key": self.connection_key
        }


class ConnectionPoolException(AgentFlowException):
    """Specific exception for connection pool operations."""
    pass


class ConnectionPool:
    """
    Advanced connection pool for managing many-to-many node connections.
    
    This class provides efficient storage and retrieval of connections between
    workflow nodes, supporting multiple connections per handle and advanced
    connection management features.
    
    Features:
    - Many-to-many connection support
    - Efficient indexing for fast lookups
    - Connection lifecycle management
    - Pool statistics and monitoring
    - Priority-based connection ordering
    - Thread-safe operations (future enhancement)
    
    Internal Structure:
    - _connections: Primary storage for all connections by ID
    - _input_index: Fast lookup for input connections by node/handle
    - _output_index: Fast lookup for output connections by node/handle
    """

    def __init__(self):
        """
        Initialize the connection pool with empty storage and indexes.
        
        Sets up the internal data structures for efficient connection
        management and retrieval.
        """
        # Primary connection storage: connection_id -> PooledConnection
        self._connections: Dict[str, PooledConnection] = {}
        
        # Input index: node_id -> handle -> [connection_ids]
        # Maps each node's input handles to lists of connection IDs
        self._input_index: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        
        # Output index: node_id -> handle -> [connection_ids]  
        # Maps each node's output handles to lists of connection IDs
        self._output_index: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        
        # Connection key mapping for duplicate detection
        self._connection_keys: Dict[str, str] = {}
        
        # Pool statistics
        self._stats = {
            "total_connections": 0,
            "connections_added": 0,
            "connections_removed": 0,
            "pool_created_at": time.time()
        }
        
        logger.info("ConnectionPool initialized")

    def add_connection(
        self, 
        source_node_id: str,
        source_handle: str,
        target_node_id: str,
        target_handle: str,
        data_type: str = "any",
        priority: int = 0,
        connection_id: Optional[str] = None
    ) -> str:
        """
        Add a new connection to the pool.
        
        Creates a new pooled connection and adds it to all relevant indexes
        for efficient retrieval. Validates connection parameters and prevents
        duplicate connections.
        
        Args:
            source_node_id: ID of the source node
            source_handle: Output handle name on the source node
            target_node_id: ID of the target node
            target_handle: Input handle name on the target node
            data_type: Type of data flowing through connection (default: "any")
            priority: Connection priority for ordering (default: 0)
            connection_id: Optional custom connection ID (auto-generated if None)
            
        Returns:
            str: The connection ID of the newly created connection
            
        Raises:
            ConnectionPoolException: If connection is invalid or already exists
            ValidationError: If required parameters are missing or invalid
        """
        try:
            # Generate connection ID if not provided
            if connection_id is None:
                connection_id = f"conn_{uuid.uuid4().hex[:8]}"
            
            # Create the pooled connection
            connection = PooledConnection(
                connection_id=connection_id,
                source_node_id=source_node_id,
                source_handle=source_handle,
                target_node_id=target_node_id,
                target_handle=target_handle,
                data_type=data_type,
                priority=priority
            )
            
            # Check for duplicate connections
            connection_key = connection.connection_key
            if connection_key in self._connection_keys:
                existing_id = self._connection_keys[connection_key]
                logger.warning(f"Duplicate connection detected: {connection_key} (existing: {existing_id})")
                raise ConnectionPoolException(
                    f"Connection already exists: {connection_key}",
                    details={"existing_connection_id": existing_id}
                )
            
            # Check if connection ID already exists
            if connection_id in self._connections:
                raise ConnectionPoolException(
                    f"Connection ID already exists: {connection_id}",
                    details={"connection_id": connection_id}
                )
            
            # Add to primary storage
            self._connections[connection_id] = connection
            self._connection_keys[connection_key] = connection_id
            
            # Add to input index (target node)
            self._input_index[target_node_id][target_handle].append(connection_id)
            
            # Add to output index (source node)
            self._output_index[source_node_id][source_handle].append(connection_id)
            
            # Sort connections by priority (higher priority first)
            self._input_index[target_node_id][target_handle].sort(
                key=lambda conn_id: self._connections[conn_id].priority, 
                reverse=True
            )
            self._output_index[source_node_id][source_handle].sort(
                key=lambda conn_id: self._connections[conn_id].priority, 
                reverse=True
            )
            
            # Update statistics
            self._stats["total_connections"] += 1
            self._stats["connections_added"] += 1
            
            logger.info(
                f"Connection added: {connection_key}",
                extra={
                    "connection_id": connection_id,
                    "source": f"{source_node_id}:{source_handle}",
                    "target": f"{target_node_id}:{target_handle}",
                    "data_type": data_type,
                    "priority": priority
                }
            )
            
            return connection_id
            
        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(f"Failed to add connection: {e}")
            raise ConnectionPoolException(f"Failed to add connection: {e}")

    def get_input_connections(self, node_id: str, handle: str) -> List[PooledConnection]:
        """
        Get all input connections for a specific node handle.
        
        Retrieves all connections that target the specified node and handle,
        ordered by priority (highest first).
        
        Args:
            node_id: ID of the target node
            handle: Input handle name
            
        Returns:
            List[PooledConnection]: List of connections targeting this handle,
                                   ordered by priority (highest first)
        """
        try:
            connection_ids = self._input_index[node_id][handle]
            connections = [self._connections[conn_id] for conn_id in connection_ids]
            
            logger.debug(
                f"Retrieved {len(connections)} input connections",
                extra={
                    "node_id": node_id,
                    "handle": handle,
                    "connection_count": len(connections)
                }
            )
            
            return connections
            
        except KeyError:
            # Handle case where node or handle doesn't exist
            logger.debug(f"No input connections found for {node_id}:{handle}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving input connections: {e}")
            raise ConnectionPoolException(f"Failed to get input connections: {e}")

    def get_output_connections(self, node_id: str, handle: str) -> List[PooledConnection]:
        """
        Get all output connections for a specific node handle.
        
        Retrieves all connections that originate from the specified node and handle,
        ordered by priority (highest first).
        
        Args:
            node_id: ID of the source node
            handle: Output handle name
            
        Returns:
            List[PooledConnection]: List of connections originating from this handle,
                                   ordered by priority (highest first)
        """
        try:
            connection_ids = self._output_index[node_id][handle]
            connections = [self._connections[conn_id] for conn_id in connection_ids]
            
            logger.debug(
                f"Retrieved {len(connections)} output connections",
                extra={
                    "node_id": node_id,
                    "handle": handle,
                    "connection_count": len(connections)
                }
            )
            
            return connections
            
        except KeyError:
            # Handle case where node or handle doesn't exist
            logger.debug(f"No output connections found for {node_id}:{handle}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving output connections: {e}")
            raise ConnectionPoolException(f"Failed to get output connections: {e}")

    def remove_connection(self, connection_id: str) -> bool:
        """
        Remove a specific connection from the pool.
        
        Removes the connection from all storage structures and indexes,
        ensuring complete cleanup.
        
        Args:
            connection_id: ID of the connection to remove
            
        Returns:
            bool: True if connection was removed, False if not found
            
        Raises:
            ConnectionPoolException: If removal operation fails
        """
        try:
            # Check if connection exists
            if connection_id not in self._connections:
                logger.warning(f"Connection not found for removal: {connection_id}")
                return False
            
            # Get connection details before removal
            connection = self._connections[connection_id]
            connection_key = connection.connection_key
            
            # Remove from primary storage
            del self._connections[connection_id]
            del self._connection_keys[connection_key]
            
            # Remove from input index
            input_connections = self._input_index[connection.target_node_id][connection.target_handle]
            if connection_id in input_connections:
                input_connections.remove(connection_id)
                
                # Clean up empty lists and dictionaries
                if not input_connections:
                    del self._input_index[connection.target_node_id][connection.target_handle]
                    if not self._input_index[connection.target_node_id]:
                        del self._input_index[connection.target_node_id]
            
            # Remove from output index
            output_connections = self._output_index[connection.source_node_id][connection.source_handle]
            if connection_id in output_connections:
                output_connections.remove(connection_id)
                
                # Clean up empty lists and dictionaries
                if not output_connections:
                    del self._output_index[connection.source_node_id][connection.source_handle]
                    if not self._output_index[connection.source_node_id]:
                        del self._output_index[connection.source_node_id]
            
            # Update statistics
            self._stats["total_connections"] -= 1
            self._stats["connections_removed"] += 1
            
            logger.info(
                f"Connection removed: {connection_key}",
                extra={
                    "connection_id": connection_id,
                    "source": f"{connection.source_node_id}:{connection.source_handle}",
                    "target": f"{connection.target_node_id}:{connection.target_handle}"
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove connection {connection_id}: {e}")
            raise ConnectionPoolException(f"Failed to remove connection: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the connection pool.
        
        Returns detailed information about pool usage, performance,
        and current state for monitoring and debugging.
        
        Returns:
            Dict[str, Any]: Dictionary containing pool statistics including:
                - total_connections: Current number of connections
                - connections_added: Total connections added since creation
                - connections_removed: Total connections removed since creation
                - unique_nodes: Number of unique nodes with connections
                - input_handles: Number of unique input handles
                - output_handles: Number of unique output handles
                - avg_connections_per_input: Average connections per input handle
                - avg_connections_per_output: Average connections per output handle
                - pool_age_seconds: Age of the pool in seconds
                - data_type_distribution: Distribution of connection data types
                - priority_distribution: Distribution of connection priorities
        """
        try:
            # Basic statistics
            stats = dict(self._stats)
            stats["pool_age_seconds"] = round(time.time() - self._stats["pool_created_at"], 2)
            
            # Analyze current connections
            if self._connections:
                # Unique nodes
                input_nodes = set(self._input_index.keys())
                output_nodes = set(self._output_index.keys())
                stats["unique_nodes"] = len(input_nodes | output_nodes)
                stats["unique_input_nodes"] = len(input_nodes)
                stats["unique_output_nodes"] = len(output_nodes)
                
                # Handle statistics
                total_input_handles = sum(len(handles) for handles in self._input_index.values())
                total_output_handles = sum(len(handles) for handles in self._output_index.values())
                stats["input_handles"] = total_input_handles
                stats["output_handles"] = total_output_handles
                
                # Average connections per handle
                if total_input_handles > 0:
                    total_input_connections = sum(
                        len(connections) 
                        for node_handles in self._input_index.values()
                        for connections in node_handles.values()
                    )
                    stats["avg_connections_per_input"] = round(
                        total_input_connections / total_input_handles, 2
                    )
                else:
                    stats["avg_connections_per_input"] = 0
                
                if total_output_handles > 0:
                    total_output_connections = sum(
                        len(connections) 
                        for node_handles in self._output_index.values()
                        for connections in node_handles.values()
                    )
                    stats["avg_connections_per_output"] = round(
                        total_output_connections / total_output_handles, 2
                    )
                else:
                    stats["avg_connections_per_output"] = 0
                
                # Data type distribution
                data_types = {}
                priorities = {}
                for connection in self._connections.values():
                    data_types[connection.data_type] = data_types.get(connection.data_type, 0) + 1
                    priorities[connection.priority] = priorities.get(connection.priority, 0) + 1
                
                stats["data_type_distribution"] = data_types
                stats["priority_distribution"] = priorities
                
            else:
                # Empty pool
                stats.update({
                    "unique_nodes": 0,
                    "unique_input_nodes": 0,
                    "unique_output_nodes": 0,
                    "input_handles": 0,
                    "output_handles": 0,
                    "avg_connections_per_input": 0,
                    "avg_connections_per_output": 0,
                    "data_type_distribution": {},
                    "priority_distribution": {}
                })
            
            logger.debug(f"Pool statistics generated: {stats['total_connections']} connections")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to generate pool statistics: {e}")
            raise ConnectionPoolException(f"Failed to get pool statistics: {e}")

    def clear(self) -> int:
        """
        Clear all connections from the pool.
        
        Removes all connections and resets all internal indexes and statistics.
        This is useful for testing or complete pool resets.
        
        Returns:
            int: Number of connections that were removed
        """
        try:
            connection_count = len(self._connections)
            
            # Clear all data structures
            self._connections.clear()
            self._connection_keys.clear()
            self._input_index.clear()
            self._output_index.clear()
            
            # Reset statistics (preserve creation time and add/remove counts)
            self._stats["total_connections"] = 0
            
            logger.info(
                f" ConnectionPool cleared: {connection_count} connections removed",
                extra={"connections_cleared": connection_count}
            )
            
            return connection_count
            
        except Exception as e:
            logger.error(f"Failed to clear connection pool: {e}")
            raise ConnectionPoolException(f"Failed to clear pool: {e}")

    def get_connection(self, connection_id: str) -> Optional[PooledConnection]:
        """
        Get a specific connection by ID.
        
        Args:
            connection_id: ID of the connection to retrieve
            
        Returns:
            Optional[PooledConnection]: The connection if found, None otherwise
        """
        return self._connections.get(connection_id)

    def get_all_connections(self) -> List[PooledConnection]:
        """
        Get all connections in the pool.
        
        Returns:
            List[PooledConnection]: All connections in the pool
        """
        return list(self._connections.values())

    def has_connection(self, connection_id: str) -> bool:
        """
        Check if a connection exists in the pool.
        
        Args:
            connection_id: ID of the connection to check
            
        Returns:
            bool: True if connection exists, False otherwise
        """
        return connection_id in self._connections

    def get_node_connections(self, node_id: str) -> Dict[str, List[PooledConnection]]:
        """
        Get all connections for a specific node (both input and output).
        
        Args:
            node_id: ID of the node
            
        Returns:
            Dict with 'inputs' and 'outputs' keys containing connection lists
        """
        result = {
            "inputs": [],
            "outputs": []
        }
        
        # Get all input connections for this node
        if node_id in self._input_index:
            for handle, connection_ids in self._input_index[node_id].items():
                connections = [self._connections[conn_id] for conn_id in connection_ids]
                result["inputs"].extend(connections)
        
        # Get all output connections for this node
        if node_id in self._output_index:
            for handle, connection_ids in self._output_index[node_id].items():
                connections = [self._connections[conn_id] for conn_id in connection_ids]
                result["outputs"].extend(connections)
        
        return result

    def __len__(self) -> int:
        """Return the number of connections in the pool."""
        return len(self._connections)

    def __contains__(self, connection_id: str) -> bool:
        """Check if a connection ID exists in the pool."""
        return connection_id in self._connections

    def __repr__(self) -> str:
        """Return a string representation of the connection pool."""
        return f"ConnectionPool(connections={len(self._connections)}, nodes={len(set(list(self._input_index.keys()) + list(self._output_index.keys())))})"