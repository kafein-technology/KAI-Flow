"""
GraphBuilder Type Definitions
============================

Shared type definitions, dataclasses, enums, and protocols for the
GraphBuilder system providing strong typing and clear interfaces.

AUTHORS: KAI-Flow Workflow Orchestration Team  
VERSION: 2.1.0
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Flow Platform
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Protocol, Union, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from app.nodes import BaseNode
from app.core.state import FlowState
from app.core.connection_pool import PooledConnection


@dataclass
class NodeConnection:
    """
    Represents a connection (edge) between two nodes in the workflow UI.
    
    Contains all information needed to establish data flow between nodes
    including source/target identification and handle mapping.
    """
    source_node_id: str
    source_handle: str 
    target_node_id: str
    target_handle: str
    data_type: str = "any"
    
    def __str__(self) -> str:
        """String representation of the connection."""
        return f"{self.source_node_id}[{self.source_handle}] → {self.target_node_id}[{self.target_handle}]"
    
    def get_connection_id(self) -> str:
        """Generate unique identifier for this connection."""
        return f"{self.source_node_id}_{self.source_handle}_{self.target_node_id}_{self.target_handle}"


@dataclass
class GraphNodeInstance:
    """
    A concrete node instance ready to execute inside LangGraph.
    
    Wraps the BaseNode instance with additional metadata and configuration
    needed for workflow execution and state management.
    """
    id: str
    type: str
    node_instance: BaseNode
    metadata: Dict[str, Any]
    user_data: Dict[str, Any]
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of node configuration."""
        return {
            "id": self.id,
            "type": self.type,
            "config_keys": list(self.user_data.keys()) if self.user_data else [],
            "metadata_keys": list(self.metadata.keys()) if self.metadata else [],
            "has_instance": self.node_instance is not None
        }


class ControlFlowType(Enum):
    """
    Enumeration of supported control flow types.
    
    Defines the different control flow constructs available
    in the workflow system for advanced execution patterns.
    """
    CONDITIONAL = "conditional"
    LOOP = "loop" 
    PARALLEL = "parallel"
    
    def __str__(self) -> str:
        return self.value


class ConnectionStatus(Enum):
    """Status of a connection validation/mapping operation."""
    VALID = "valid"
    INVALID = "invalid" 
    PENDING = "pending"
    ERROR = "error"
    
    def __str__(self) -> str:
        return self.value


class NodeExecutionMode(Enum):
    """Execution mode for different node types."""
    STANDARD = "standard"        # Regular nodes (Provider, etc.)
    PROCESSOR = "processor"      # Processor nodes (ReactAgent, etc.)
    MEMORY = "memory"           # Memory nodes
    CONTROL_FLOW = "control_flow"  # Control flow nodes
    
    def __str__(self) -> str:
        return self.value


@dataclass
class ConnectionInfo:
    """
    Information about a specific connection for mapping purposes.
    
    Used by ConnectionMapper to track connection validation,
    status, and error information.
    """
    source_node_id: str
    source_handle: str
    target_node_id: str  
    target_handle: str
    data_type: str
    status: ConnectionStatus
    validation_errors: List[str]
    
    def is_valid(self) -> bool:
        """Check if connection is valid."""
        return self.status == ConnectionStatus.VALID and len(self.validation_errors) == 0


@dataclass
class NodeConnectionMap:
    """
    Complete connection mapping for a single node.
    
    Contains all input and output connections for a node
    organized by handle names for efficient lookup.
    """
    node_id: str
    input_connections: Dict[str, ConnectionInfo]
    output_connections: Dict[str, List[ConnectionInfo]]
    _pool_connection_ids: List[str] = field(default_factory=list)
    
    def get_input_count(self) -> int:
        """Get total number of input connections."""
        return len(self.input_connections)
    
    def get_output_count(self) -> int:
        """Get total number of output connections."""
        return sum(len(conns) for conns in self.output_connections.values())
    
    def has_valid_connections(self) -> bool:
        """Check if all connections are valid."""
        # Check input connections
        for conn in self.input_connections.values():
            if not conn.is_valid():
                return False
        
        # Check output connections
        for conn_list in self.output_connections.values():
            for conn in conn_list:
                if not conn.is_valid():
                    return False
        
        return True
    
    def get_multiple_inputs(self, handle: str) -> List[ConnectionInfo]:
        """
        Get multiple input connections for a handle (pool support).
        
        Args:
            handle: The input handle to get connections for
            
        Returns:
            List of ConnectionInfo objects for the handle
        """
        if handle in self.input_connections:
            return [self.input_connections[handle]]
        return []
    
    def has_pool_support(self) -> bool:
        """
        Check if this node connection map has pool support enabled.
        
        Returns:
            True if pool connections are configured, False otherwise
        """
        return len(self._pool_connection_ids) > 0
    
    def get_pool_connection_count(self) -> int:
        """
        Get the number of pool connections for this node.
        
        Returns:
            Number of pool connections configured
        """
        return len(self._pool_connection_ids)


@dataclass
class ValidationResult:
    """
    Result of workflow validation operation.
    
    Contains comprehensive validation information including
    errors, warnings, and statistics.
    """
    valid: bool
    errors: List[str]
    warnings: List[str]
    node_count: int
    connection_count: int
    
    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "node_count": self.node_count,
            "connection_count": self.connection_count,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }


@dataclass
class BuildMetrics:
    """
    Metrics collected during workflow build process.
    
    Provides insights into build performance and statistics
    for monitoring and optimization purposes.
    """
    node_count: int
    connection_count: int
    build_duration: float
    connection_stats: Dict[str, Any]
    validation_duration: Optional[float] = None
    compilation_duration: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "node_count": self.node_count,
            "connection_count": self.connection_count, 
            "build_duration": self.build_duration,
            "connection_stats": self.connection_stats,
            "validation_duration": self.validation_duration,
            "compilation_duration": self.compilation_duration
        }


# Protocol definitions for component interfaces

class ConnectionMapperProtocol(Protocol):
    """Protocol for connection mapping components."""
    
    def parse_connections(self, edges: List[Dict[str, Any]]) -> List[NodeConnection]:
        """Parse edges into internal connection format."""
        ...
    
    def build_connection_mappings(
        self, 
        connections: List[NodeConnection], 
        nodes: Dict[str, BaseNode]
    ) -> Dict[str, NodeConnectionMap]:
        """Build connection mappings for nodes."""
        ...


class NodeExecutorProtocol(Protocol):
    """Protocol for node execution components."""
    
    def setup_node_session(self, gnode: GraphNodeInstance, state: FlowState, node_id: str) -> None:
        """Setup session information for nodes."""
        ...
    
    def execute_node(self, gnode: GraphNodeInstance, state: FlowState, node_id: str) -> Dict[str, Any]:
        """Execute a node and return results."""
        ...


class ControlFlowManagerProtocol(Protocol):
    """Protocol for control flow management components."""
    
    def add_control_flow_edges(self, graph: Any, control_flow_nodes: Dict[str, Dict[str, Any]]) -> None:
        """Add control flow edges to graph."""
        ...
    
    def evaluate_condition(self, value: Any, config: Dict[str, Any], condition_type: str) -> bool:
        """Evaluate control flow condition."""
        ...


class ValidationEngineProtocol(Protocol):
    """Protocol for workflow validation components."""
    
    def validate_workflow(self, flow_data: Dict[str, Any]) -> ValidationResult:
        """Validate workflow structure and configuration."""
        ...


# Type aliases for common use cases
NodeRegistry = Dict[str, Type[BaseNode]]
NodeInstanceRegistry = Dict[str, GraphNodeInstance]
ConnectionMappings = Dict[str, NodeConnectionMap]
ControlFlowNodes = Dict[str, Dict[str, Any]]
WorkflowData = Dict[str, Any]
ExecutionResult = Dict[str, Any]

# Pool-related type aliases
PooledConnectionRegistry = Dict[str, 'PooledConnection']
ConnectionPoolStats = Dict[str, Any]
ConnectionPoolConfig = Dict[str, Any]

# Function type aliases
NodeWrapper = Callable[[FlowState], Dict[str, Any]]
ConditionEvaluator = Callable[[Any, Dict[str, Any], str], bool]
RouteFunction = Callable[[FlowState], str]

# Common constants
DEFAULT_INPUT_HANDLE = "input"
DEFAULT_OUTPUT_HANDLE = "output"
START_NODE_TYPE = "StartNode"
END_NODE_TYPE = "EndNode"

# Terminal node types that can serve as valid workflow exit points
# These nodes can replace EndNode in workflows (e.g., webhook workflows)
TERMINAL_NODE_TYPES = {END_NODE_TYPE, "RespondToWebhook"}

# Pool-related constants
DEFAULT_POOL_ENABLED = False
POOL_FEATURE_FLAG = "connection_pool_enabled"

# Node type categories
PROCESSOR_NODE_TYPES = {'ReactAgent', 'ToolAgentNode', 'Agent', 'LLMRedTeam'}
MEMORY_NODE_TYPES = {'BufferMemory', 'ConversationMemory', 'Memory'}
PROVIDER_NODE_TYPES = {'Provider', 'OpenAINode', 'TavilySearchNode'}
CONTROL_FLOW_NODE_TYPES = {'ConditionalNode', 'LoopNode', 'ParallelNode'}