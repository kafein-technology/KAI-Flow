"""
KAI-Fusion Enhanced Connection Management System
==============================================

Advanced connection mapping with reliability, validation, and caching.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict
import time

from .connection_pool import ConnectionPool, PooledConnection

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection validation status."""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """Enhanced connection information with validation."""
    source_node_id: str
    source_handle: str
    target_node_id: str
    target_handle: str
    data_type: str = "any"
    status: ConnectionStatus = ConnectionStatus.PENDING
    validation_errors: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_validated: Optional[float] = None


@dataclass
class NodeConnectionMap:
    """Complete connection mapping for a node."""
    node_id: str
    input_connections: Dict[str, ConnectionInfo] = field(default_factory=dict)
    output_connections: Dict[str, List[ConnectionInfo]] = field(default_factory=dict)
    validation_status: ConnectionStatus = ConnectionStatus.PENDING
    validation_errors: List[str] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


class ConnectionManager:
    """
    Enterprise-grade connection management with validation and caching.
    
    Features:
    - Connection validation with type checking
    - Error handling and recovery
    - Connection caching for performance
    - Dependency resolution
    - Circular dependency detection
    """
    
    def __init__(self):
        self._connection_cache: Dict[str, NodeConnectionMap] = {}
        self._connection_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self._validation_cache: Dict[str, Tuple[bool, List[str]]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # CHANGED: Auto-enable connection pool by default
        self._pool_enabled = True
        self._connection_pool = ConnectionPool()
        logger.info(
            " Connection Pool auto-enabled - Many-to-many connections now active by default"
        )
    def build_connection_mappings(
        self, connections: List[Any], nodes: Dict[str, Any]
    ) -> Dict[str, NodeConnectionMap]:
        """
        Build comprehensive connection mappings with validation.
        
        Args:
            connections: List of NodeConnection objects
            nodes: Dictionary of node instances
            
        Returns:
            Dictionary mapping node_id to NodeConnectionMap
        """
        logger.info(f" Building connection mappings for {len(nodes)} nodes")
        # Clear previous mappings
        self._connection_cache.clear()
        self._connection_graph.clear()
        self._reverse_graph.clear()
        
        # Clear connection pool to prevent duplicates
        if self._pool_enabled and self._connection_pool is not None:
            self._connection_pool.clear()
            logger.debug(" Connection pool cleared to prevent duplicates")
        
        # Initialize node mappings
        for node_id in nodes.keys():
            self._connection_cache[node_id] = NodeConnectionMap(node_id=node_id)
        
        # Process connections
        valid_connections = 0
        invalid_connections = 0
        
        for conn in connections:
            try:
                conn_info = self._create_connection_info(conn)
                
                # Validate connection
                is_valid, errors = self._validate_connection(conn_info, nodes)
                conn_info.status = ConnectionStatus.VALID if is_valid else ConnectionStatus.INVALID
                conn_info.validation_errors = errors
                conn_info.last_validated = time.time()
                
                if is_valid:
                    self._add_connection_to_mappings(conn_info)
                    valid_connections += 1
                else:
                    invalid_connections += 1
                    logger.warning(f"Invalid connection: {conn_info.source_node_id} -> {conn_info.target_node_id}: {errors}")
                    
            except Exception as e:
                logger.error(f"Error processing connection: {e}")
                invalid_connections += 1
        
        # Validate overall graph structure
        self._validate_graph_structure()
        
        logger.info(f"Connection mapping complete: {valid_connections} valid, {invalid_connections} invalid")
        return self._connection_cache.copy()
    def _create_connection_info(self, conn: Any) -> ConnectionInfo:
        """Create ConnectionInfo from connection object."""
        return ConnectionInfo(
            source_node_id=conn.source_node_id,
            source_handle=conn.source_handle,
            target_node_id=conn.target_node_id,
            target_handle=conn.target_handle,
            data_type=getattr(conn, "data_type", "any"),
        )
    
    def _validate_connection(
        self, 
        conn_info: ConnectionInfo, 
        nodes: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate a single connection with comprehensive checks.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check cache first
        cache_key = f"{conn_info.source_node_id}:{conn_info.source_handle}->{conn_info.target_node_id}:{conn_info.target_handle}"
        if cache_key in self._validation_cache:
            self._cache_hits += 1
            return self._validation_cache[cache_key]
        
        self._cache_misses += 1
        
        # 1. Check if nodes exist
        if conn_info.source_node_id not in nodes:
            errors.append(f"Source node '{conn_info.source_node_id}' not found")
        
        if conn_info.target_node_id not in nodes:
            errors.append(f"Target node '{conn_info.target_node_id}' not found")
        
        if errors:
            result = (False, errors)
            self._validation_cache[cache_key] = result
            return result
        
        # 2. Validate node handles
        source_node = nodes[conn_info.source_node_id]
        target_node = nodes[conn_info.target_node_id]
        
        # Check source output handle
        if not self._validate_output_handle(source_node, conn_info.source_handle):
            errors.append(f"Invalid source handle '{conn_info.source_handle}' on node '{conn_info.source_node_id}'")
        
        # Check target input handle
        if not self._validate_input_handle(target_node, conn_info.target_handle):
            errors.append(f"Invalid target handle '{conn_info.target_handle}' on node '{conn_info.target_node_id}'")
        
        # 3. Type compatibility check
        if not self._validate_type_compatibility(source_node, target_node, conn_info):
            errors.append(f"Type incompatibility: {conn_info.source_handle} -> {conn_info.target_handle}")
        
        # 4. Check for circular dependencies
        if self._creates_circular_dependency(conn_info.source_node_id, conn_info.target_node_id):
            errors.append(f"Circular dependency detected: {conn_info.source_node_id} -> {conn_info.target_node_id}")
        
        result = (len(errors) == 0, errors)
        self._validation_cache[cache_key] = result
        return result
    
    def _validate_output_handle(self, node: Any, handle: str) -> bool:
        """Validate if node has the specified output handle."""
        try:
            metadata = getattr(node, 'metadata', None)
            if not metadata:
                return True  # Allow if no metadata (backward compatibility)
            
            outputs = getattr(metadata, 'outputs', [])
            valid_handles = [output.name for output in outputs] + ['output']  # Default handle
            return handle in valid_handles
        except Exception:
            return True  # Allow on error (backward compatibility)
    
    def _validate_input_handle(self, node: Any, handle: str) -> bool:
        """Validate if node has the specified input handle."""
        try:
            metadata = getattr(node, 'metadata', None)
            if not metadata:
                return True  # Allow if no metadata (backward compatibility)
            
            inputs = getattr(metadata, 'inputs', [])
            valid_handles = [inp.name for inp in inputs] + ['input']  # Default handle
            return handle in valid_handles
        except Exception:
            return True  # Allow on error (backward compatibility)
    
    def _validate_type_compatibility(self, source_node: Any, target_node: Any, conn_info: ConnectionInfo) -> bool:
        """Validate type compatibility between connected handles."""
        try:
            # For now, allow all connections (can be enhanced with strict typing)
            return True
        except Exception:
            return True
    
    def _creates_circular_dependency(self, source_id: str, target_id: str) -> bool:
        """Check if adding this connection would create a circular dependency."""
        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            if node_id in rec_stack:
                return True
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            # Check all outgoing connections
            for neighbor in self._connection_graph.get(node_id, set()):
                if has_cycle(neighbor):
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        # Temporarily add the new connection
        self._connection_graph[source_id].add(target_id)
        
        # Check for cycles
        cycle_detected = has_cycle(source_id)
        
        # Remove the temporary connection
        self._connection_graph[source_id].discard(target_id)
        
        return cycle_detected
    
    def _add_connection_to_mappings(self, conn_info: ConnectionInfo):
        """Add validated connection to mappings."""
        # Add to target node's input connections
        target_map = self._connection_cache[conn_info.target_node_id]
        
        # Handle input connections: support many-to-many when pool enabled
        if self._pool_enabled:
            # When pool is enabled, we still keep one connection in traditional mapping for backward compatibility
            # The pool will handle the many-to-many aspect
            target_map.input_connections[conn_info.target_handle] = conn_info
        else:
            # Traditional one-to-one behavior when pool is disabled
            target_map.input_connections[conn_info.target_handle] = conn_info
        
        # Add to source node's output connections (always supports multiple)
        source_map = self._connection_cache[conn_info.source_node_id]
        if conn_info.source_handle not in source_map.output_connections:
            source_map.output_connections[conn_info.source_handle] = []
        source_map.output_connections[conn_info.source_handle].append(conn_info)
        
        # Update graph structures
        self._connection_graph[conn_info.source_node_id].add(conn_info.target_node_id)
        self._reverse_graph[conn_info.target_node_id].add(conn_info.source_node_id)
        
        # Add to connection pool if enabled
        if self._pool_enabled and self._connection_pool is not None:
            logger.debug(f"Attempting to add connection to pool: {conn_info.source_node_id}:{conn_info.source_handle} -> {conn_info.target_node_id}:{conn_info.target_handle}")
            try:
                pool_conn_id = self._connection_pool.add_connection(
                    source_node_id=conn_info.source_node_id,
                    source_handle=conn_info.source_handle,
                    target_node_id=conn_info.target_node_id,
                    target_handle=conn_info.target_handle,
                    data_type=conn_info.data_type,
                    priority=0  # Default priority
                )
                logger.info(f"Connection added to pool: {pool_conn_id}")
            except Exception as e:
                logger.warning(f"Failed to add connection to pool: {e}")
                # Log the detailed error for debugging
                import traceback
                logger.warning(f"Pool add error details: {traceback.format_exc()}")
        else:
            logger.debug(f"Pool not enabled or not initialized: enabled={self._pool_enabled}, pool={self._connection_pool is not None}")
        
        # Update timestamps
        target_map.last_updated = time.time()
        source_map.last_updated = time.time()
    
    def _validate_graph_structure(self):
        """Validate overall graph structure."""
        logger.info("Validating graph structure")
        
        # Check for isolated nodes
        isolated_nodes = []
        for node_id, node_map in self._connection_cache.items():
            if not node_map.input_connections and not node_map.output_connections:
                isolated_nodes.append(node_id)
        if isolated_nodes:
            logger.warning(f"Isolated nodes detected: {isolated_nodes}")
        # Validate all node mappings
        for node_id, node_map in self._connection_cache.items():
            if node_map.validation_errors:
                node_map.validation_status = ConnectionStatus.ERROR
            else:
                node_map.validation_status = ConnectionStatus.VALID
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection management statistics."""
        total_connections = sum(
            len(node_map.input_connections) 
            for node_map in self._connection_cache.values()
        )
        valid_connections = sum(
            1 for node_map in self._connection_cache.values()
            for conn in node_map.input_connections.values()
            if conn.status == ConnectionStatus.VALID
        )
        
        return {
            "total_nodes": len(self._connection_cache),
            "total_connections": total_connections,
            "valid_connections": valid_connections,
            "invalid_connections": total_connections - valid_connections,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
        }
    
    def enable_connection_pool(self) -> None:
        """
        Initialize and enable connection pool for many-to-many support.
        
        This method creates a new ConnectionPool instance and enables pool features.
        All future connections will be added to the pool alongside existing functionality.
        """
        try:
            if self._pool_enabled:
                logger.info("Connection Pool already enabled")
                return
                
            self._connection_pool = ConnectionPool()
            self._pool_enabled = True
            logger.info(
                " Connection Pool enabled - Many-to-many connections now active"
            )
        except Exception as e:
            logger.error(f"Failed to enable connection pool: {e}")
            raise

    def disable_connection_pool(self) -> None:
        """
        Disable connection pool while maintaining backward compatibility.
        
        This method disables the pool feature but keeps all existing functionality intact.
        The pool instance is cleared but not destroyed to preserve statistics.
        """
        try:
            if self._pool_enabled:
                self._pool_enabled = False
                if self._connection_pool:
                    self._connection_pool.clear()
                logger.info("Connection pool disabled - reverted to one-to-one connections")
            else:
                logger.info("Connection pool is already disabled")
        except Exception as e:
            logger.error(f"Failed to disable connection pool: {e}")

    def get_multiple_input_connections(self, node_id: str, handle: str) -> List[ConnectionInfo]:
        """
        Get all input connections for a specific node handle (many-to-many support).
        
        This method returns multiple connections when pool is enabled, otherwise
        returns the single connection from traditional mapping for backward compatibility.
        
        Args:
            node_id: ID of the target node
            handle: Input handle name
            
        Returns:
            List[ConnectionInfo]: All input connections for the handle
        """
        try:
            if self._pool_enabled and self._connection_pool:
                # Use pool for many-to-many connections
                pooled_connections = self._connection_pool.get_input_connections(node_id, handle)
                
                # Convert PooledConnection to ConnectionInfo for compatibility
                connection_infos = []
                for pooled_conn in pooled_connections:
                    conn_info = ConnectionInfo(
                        source_node_id=pooled_conn.source_node_id,
                        source_handle=pooled_conn.source_handle,
                        target_node_id=pooled_conn.target_node_id,
                        target_handle=pooled_conn.target_handle,
                        data_type=pooled_conn.data_type,
                        status=ConnectionStatus.VALID if pooled_conn.status == "valid" else ConnectionStatus.INVALID,
                        created_at=pooled_conn.created_at
                    )
                    connection_infos.append(conn_info)
                
                logger.debug(f"Retrieved {len(connection_infos)} pooled input connections for {node_id}:{handle}")
                return connection_infos
            else:
                # Fallback to traditional single connection mapping
                if node_id in self._connection_cache:
                    node_map = self._connection_cache[node_id]
                    if handle in node_map.input_connections:
                        return [node_map.input_connections[handle]]
                
                return []
                
        except Exception as e:
            logger.error(f"Error getting multiple input connections: {e}")
            return []

    def has_multiple_input_connections(self, node_id: str, handle: str) -> bool:
        """
        Check if a node handle has multiple input connections.
        
        Args:
            node_id: ID of the target node
            handle: Input handle name
            
        Returns:
            bool: True if multiple connections exist, False otherwise
        """
        try:
            connections = self.get_multiple_input_connections(node_id, handle)
            has_multiple = len(connections) > 1
            
            logger.debug(f"Node {node_id}:{handle} has {'multiple' if has_multiple else 'single/no'} input connections ({len(connections)} total)")
            return has_multiple
            
        except Exception as e:
            logger.error(f"Error checking multiple input connections: {e}")
            return False

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection management statistics with optional pool stats."""
        # Get traditional stats
        total_connections = sum(
            len(node_map.input_connections)
            for node_map in self._connection_cache.values()
        )
        
        valid_connections = sum(
            1 for node_map in self._connection_cache.values()
            for conn in node_map.input_connections.values()
            if conn.status == ConnectionStatus.VALID
        )
        
        stats = {
            "total_nodes": len(self._connection_cache),
            "total_connections": total_connections,
            "valid_connections": valid_connections,
            "invalid_connections": total_connections - valid_connections,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
            "pool_enabled": self._pool_enabled
        }
        
        # Add pool statistics if enabled
        if self._pool_enabled and self._connection_pool:
            try:
                pool_stats = self._connection_pool.get_stats()
                stats["pool_stats"] = pool_stats
                stats["pool_total_connections"] = pool_stats.get("total_connections", 0)
                stats["pool_unique_nodes"] = pool_stats.get("unique_nodes", 0)
                logger.debug("Added connection pool statistics to manager stats")
            except Exception as e:
                logger.warning(f"Failed to get pool statistics: {e}")
                stats["pool_stats"] = {"error": str(e)}
        elif self._pool_enabled:
            # Pool is enabled but not initialized - provide empty stats
            stats["pool_stats"] = {
                "total_connections": 0,
                "unique_nodes": 0,
                "error": "Pool not initialized"
            }
        
        return stats

    def clear_cache(self):
        """Clear validation cache and connection pool to prevent duplicates."""
        self._validation_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Clear connection pool when clearing cache to prevent duplicates
        if self._pool_enabled and self._connection_pool is not None:
            self._connection_pool.clear()
            logger.debug("Connection pool cleared with cache")
        
        logger.info("Connection validation cache cleared")