"""
KAI-Flow Graph Builder - Enterprise Workflow Orchestration & Execution Engine

This module implements sophisticated workflow graph construction for the KAI-Flow platform,
providing enterprise-grade LangGraph orchestration with advanced control flow management,
intelligent node connectivity, and production-ready execution capabilities. Built for
complex AI workflows requiring reliable state management and seamless node integration.

ARCHITECTURAL OVERVIEW:

The Graph Builder system serves as the workflow orchestration engine of KAI-Flow,
transforming visual flow definitions into executable LangGraph pipelines with advanced
control flow, state management, and comprehensive error handling for production environments.

PHASE 3 ARCHITECTURE: Clean, Modular Components
This version implements Phase 3 of the refactoring, extracting specialized components
into separate modules while maintaining a clean main GraphBuilder orchestrator class.

Components:
- ConnectionMapper: Handles connection parsing and mapping
- NodeExecutor: Manages node execution and session handling  
- ControlFlowManager: Manages control flow logic (conditional, loop, parallel)
- ValidationEngine: Handles workflow validation
- Exception classes: Structured error handling
- Type definitions: Strong typing and protocols

AUTHORS: KAI-Flow Workflow Orchestration Team
VERSION: 2.1.0
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Flow Platform
"""

from __future__ import annotations
import datetime
import traceback
import uuid
import asyncio
import logging
import os
import time
from typing import Dict, Any, List, Optional, Callable, Type, Union, AsyncGenerator

# Core LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import Runnable, RunnableConfig

# Local imports - core
from app.core.state import FlowState
from app.nodes import BaseNode
from app.core.tracing import get_workflow_tracer
from app.core.node_handlers import node_handler_registry
from app.core.output_cache import default_connection_extractor
from app.core.connection_manager import ConnectionManager

# Extracted component imports
from .types import (
    NodeConnection, GraphNodeInstance, ControlFlowType, NodeRegistry,
    NodeInstanceRegistry, BuildMetrics, ValidationResult, TERMINAL_NODE_TYPES
)
from .exceptions import (
    WorkflowError, NodeExecutionError, ConnectionError, 
    ValidationError, GraphCompilationError
)
from .connection_mapper import ConnectionMapper
from .node_executor import NodeExecutor
from .control_flow import ControlFlowManager
from .validation import ValidationEngine

# Export key types and classes for backward compatibility
__all__ = [
    "GraphBuilder", "NodeConnection", "GraphNodeInstance", "ControlFlowType",
    "WorkflowError", "NodeExecutionError", "ConnectionError", "ValidationError"
]

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Clean, Focused Workflow Orchestration Engine (Phase 3 Architecture)
    ==================================================================
    
    This is the main orchestrator that coordinates all specialized components
    to build and execute workflows. The class is now significantly smaller
    and focused purely on orchestration, with actual work delegated to
    specialized components.
    
    Key Improvements:
    - Under 200 lines of orchestration code
    - Clean separation of concerns
    - Enhanced testability with isolated components
    - Improved maintainability and debuggability
    - Preserved backward compatibility
    - All tool aggregation functionality maintained
    
    Components:
    - ConnectionMapper: Handles connection logic
    - NodeExecutor: Handles node execution
    - ControlFlowManager: Handles control flow
    - ValidationEngine: Handles validation
    """

    def __init__(self, node_registry: NodeRegistry, checkpointer=None):
        self.node_registry = node_registry
        self.checkpointer = checkpointer or self._get_checkpointer()
        
        # Ensure node_registry has get_node method if it's a dict
        if isinstance(self.node_registry, dict) and not hasattr(self.node_registry, 'get_node'):
             # It's a dict, we need to wrap it or handle it
            self._node_registry_dict = self.node_registry
            self.get_node = lambda type_name: self._node_registry_dict.get(type_name)
        else:
            self.get_node = self.node_registry.get_node

        # Initialize specialized components
        self.connection_mapper = ConnectionMapper(ConnectionManager())
        self.node_executor = NodeExecutor(default_connection_extractor, node_handler_registry)
        self.control_flow_manager = ControlFlowManager([])
        self.validation_engine = ValidationEngine(node_registry)
        
        # State management (rebuilt on every build_from_flow)
        self.nodes: NodeInstanceRegistry = {}
        self.connections: List[NodeConnection] = []
        self.control_flow_nodes: Dict[str, Dict[str, Any]] = {}
        self.explicit_start_nodes: set[str] = set()
        self.end_nodes_for_connections: Dict[str, Dict[str, Any]] = {}
        self.graph: Optional[CompiledStateGraph] = None
        
        # Enhanced metrics and monitoring
        self._build_metrics: Dict[str, Any] = {}

    # ---------------------------------------------------------------------
    # Public API - Main orchestration methods
    # ---------------------------------------------------------------------
    
    def build_from_flow(self, flow_data: Dict[str, Any], user_id: Optional[str] = None) -> CompiledStateGraph:
        """
        Main orchestration method that builds workflow using extracted components.
        
        This method coordinates all specialized components to transform flow data
        into an executable LangGraph while maintaining full backward compatibility.
        """
        logger.info("Starting workflow build with Phase 3 architecture")
        start_time = time.time()
        
        try:
            # Step 1: Validate workflow first using ValidationEngine
            validation_result = self.validation_engine.validate_workflow(flow_data)
            if not validation_result.valid:
                raise ValidationError(
                    f"Workflow validation failed: {validation_result.errors}",
                    validation_errors=validation_result.errors,
                    validation_warnings=validation_result.warnings,
                    node_count=validation_result.node_count,
                    connection_count=validation_result.connection_count
                )
            
            # Step 2: Prepare workflow data
            workflow_data = self._prepare_workflow_data(flow_data)
            
            # Step 3: Handle StartNode and EndNode special cases
            processed_data = self._handle_start_end_nodes(workflow_data)
            
            # Step 4: Build workflow components using specialized classes
            self._build_workflow_components(processed_data)
            
            # Step 5: Compile final LangGraph
            compiled_graph = self._compile_final_graph()
            
            # Step 6: Record build metrics
            build_duration = time.time() - start_time
            self._build_metrics = {
                "build_duration": build_duration,
                "node_count": len(self.nodes),
                "connection_count": len(self.connections),
                "validation_result": validation_result.to_dict(),
                "connection_stats": self.connection_mapper.get_connection_stats(),
                "control_flow_stats": self.control_flow_manager.get_control_flow_stats(),
                "validation_stats": self.validation_engine.get_validation_stats()
            }
            
            logger.info(f"Workflow build completed successfully in {build_duration:.3f}s")
            logger.info(f"Build metrics: {self._build_metrics}")
            
            return compiled_graph
            
        except Exception as e:
            build_duration = time.time() - start_time
            logger.error(f"Workflow build failed after {build_duration:.3f}s: {e}")
            
            if isinstance(e, (ValidationError, ConnectionError, NodeExecutionError)):
                raise  # Re-raise our custom exceptions
            else:
                raise GraphCompilationError(
                    f"Graph compilation failed: {str(e)}",
                    compilation_stage="build_from_flow",
                    node_count=len(self.nodes),
                    edge_count=len(self.connections),
                    langgraph_error=e
                ) from e

    def validate_workflow(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced workflow validation - now delegated to ValidationEngine.
        
        Maintained for backward compatibility.
        """
        result = self.validation_engine.validate_workflow(flow_data)
        return result.to_dict()

    def get_build_metrics(self) -> Dict[str, Any]:
        """Get detailed build metrics from all components."""
        return self._build_metrics.copy()

    # ---------------------------------------------------------------------
    # Workflow preparation and data handling
    # ---------------------------------------------------------------------
    
    def _prepare_workflow_data(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare and validate workflow data - unchanged from original."""
        # SAFE: Create copies to avoid mutating original data
        nodes = flow_data.get("nodes", []).copy()
        edges = flow_data.get("edges", []).copy()

        # Reset builder state
        self.nodes.clear()
        self.connections.clear()
        self.control_flow_nodes.clear()
        self.explicit_start_nodes.clear()
        self.end_nodes_for_connections.clear()

        # Analyze existing nodes
        start_nodes = [n for n in nodes if n.get("type") == "StartNode"]
        webhook_trigger_nodes = [n for n in nodes if n.get("type") == "WebhookTrigger"]
        entry_nodes = start_nodes + webhook_trigger_nodes
        end_nodes = [n for n in nodes if n.get("type") == "EndNode"]
        start_node_ids = {n["id"] for n in start_nodes}
        webhook_trigger_node_ids = {n["id"] for n in webhook_trigger_nodes}
        entry_node_ids = start_node_ids | webhook_trigger_node_ids
        end_node_ids = {n["id"] for n in end_nodes}

        if not entry_nodes:
            raise ValueError("Workflow must contain at least one StartNode or WebhookTrigger node.")

        return {
            "nodes": nodes,
            "edges": edges,
            "start_nodes": start_nodes,
            "webhook_trigger_nodes": webhook_trigger_nodes,
            "entry_nodes": entry_nodes,
            "end_nodes": end_nodes,
            "start_node_ids": start_node_ids,
            "webhook_trigger_node_ids": webhook_trigger_node_ids,
            "entry_node_ids": entry_node_ids,
            "end_node_ids": end_node_ids
        }

    def _handle_start_end_nodes(self, workflow_data: Dict) -> Dict[str, Any]:
        """Handle StartNode, WebhookTrigger, and EndNode special cases."""
        nodes = workflow_data["nodes"]
        edges = workflow_data["edges"]
        start_nodes = workflow_data["start_nodes"]
        webhook_trigger_nodes = workflow_data.get("webhook_trigger_nodes", [])
        end_nodes = workflow_data["end_nodes"]
        start_node_ids = workflow_data["start_node_ids"]
        webhook_trigger_node_ids = workflow_data.get("webhook_trigger_node_ids", set())
        entry_node_ids = workflow_data.get("entry_node_ids", start_node_ids | webhook_trigger_node_ids)
        end_node_ids = workflow_data["end_node_ids"]

        # Check for terminal nodes (EndNode OR RespondToWebhook)
        terminal_nodes = [n for n in nodes if n.get("type") in TERMINAL_NODE_TYPES]

        # Handle missing terminal node BEFORE any filtering
        # Only create virtual EndNode if no terminal node exists
        if not terminal_nodes:
            logger.info("No terminal node found. Creating virtual EndNode for workflow completion.")

            # Create virtual EndNode
            virtual_end_node = {
                "id": "virtual-end-node",
                "type": "EndNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "name": "EndNode",
                    "description": "Virtual end node for workflow completion",
                    "metadata": {"name": "EndNode", "node_type": "terminator"}
                }
            }

            # SAFE: Add virtual node to working copy
            nodes.append(virtual_end_node)

            # Find the last nodes in the workflow (BEFORE filtering)
            all_targets = {e["target"] for e in edges}
            all_sources = {e["source"] for e in edges}
            last_nodes = all_sources - all_targets - entry_node_ids

            # SAFE: Add virtual edges to working copy
            for node_id in last_nodes:
                virtual_edge = {
                    "id": f"virtual-{node_id}-to-end",
                    "source": node_id,
                    "target": "virtual-end-node",
                    "sourceHandle": "output",
                    "targetHandle": "input"
                }
                edges.append(virtual_edge)
                logger.debug(f"Auto-connected {node_id} -> virtual-end-node")

            # Update end_nodes and end_node_ids after adding virtual node
            end_nodes.append(virtual_end_node)
            end_node_ids.add("virtual-end-node")

        # Identify explicit start connections from StartNodes
        start_node_targets = {e["target"] for e in edges if e.get("source") in start_node_ids}
        
        # Identify explicit start connections from WebhookTrigger nodes
        webhook_trigger_targets = {e["target"] for e in edges if e.get("source") in webhook_trigger_node_ids}
        
        # If WebhookTrigger nodes have outgoing edges, use those targets as start nodes
        # Otherwise, use the WebhookTrigger nodes themselves as start nodes
        webhook_start_nodes = set()
        if webhook_trigger_targets:
            # WebhookTrigger nodes have outgoing edges, use the targets
            webhook_start_nodes = webhook_trigger_targets
        elif webhook_trigger_node_ids:
            # WebhookTrigger nodes have no outgoing edges, use the nodes themselves
            webhook_start_nodes = webhook_trigger_node_ids
        
        # Combine all start targets
        self.explicit_start_nodes = start_node_targets | webhook_start_nodes

        # Debug logging
        logger.debug(f"Edge filtering analysis: {len(edges)} edges")
        edges_from_start_nodes = [e for e in edges if e.get("source") in start_node_ids]
        edges_from_webhook_triggers = [e for e in edges if e.get("source") in webhook_trigger_node_ids]
        logger.debug(f"Found {len(edges_from_start_nodes)} edges FROM StartNodes")
        logger.debug(f"Found {len(edges_from_webhook_triggers)} edges FROM WebhookTrigger nodes")
        logger.debug(f"Explicit start nodes: {self.explicit_start_nodes}")

        # SAFE filtering AFTER all additions
        # Filter out StartNodes for processing, but keep EndNodes
        processed_nodes = [n for n in nodes if n.get("type") != "StartNode"]

        # Filter out edges connected to StartNodes (both directions)
        processed_edges = [e for e in edges
                          if e.get("source") not in start_node_ids
                          and e.get("target") not in start_node_ids]

        logger.debug(f"After filtering: {len(processed_nodes)} nodes, {len(processed_edges)} edges")

        # Store terminal nodes (EndNode and RespondToWebhook) for connection tracking
        terminal_nodes_for_processing = [n for n in processed_nodes if n.get("type") in TERMINAL_NODE_TYPES]
        self.end_nodes_for_connections = {n["id"]: n for n in terminal_nodes_for_processing}

        return {
            "processed_nodes": processed_nodes,
            "processed_edges": processed_edges
        }

    def _build_workflow_components(self, processed_data: Dict[str, Any]) -> None:
        """Build all workflow components using specialized classes."""
        processed_nodes = processed_data["processed_nodes"]
        processed_edges = processed_data["processed_edges"]
        
        logger.info("Building workflow components with specialized classes")
        
        # Step 1: Parse connections using ConnectionMapper
        self.connections = self.connection_mapper.parse_connections(processed_edges)
        
        # Step 2: Identify control flow nodes using ControlFlowManager
        self.control_flow_nodes = self.control_flow_manager.identify_control_flow_nodes(processed_nodes)
        
        # Step 3: Instantiate nodes with enhanced connection mapping
        self._instantiate_nodes_with_components(processed_nodes)
        
        # Step 4: Update components with current state
        self.control_flow_manager.set_connections(self.connections)
        self.control_flow_manager.set_control_flow_nodes(self.control_flow_nodes)
    
    def _instantiate_nodes_with_components(self, nodes: List[Dict[str, Any]]) -> None:
        """Enhanced node instantiation using ConnectionMapper."""
        if nodes:
            logger.info(f"ENHANCED NODE INSTANTIATION with Components ({len(nodes)} nodes)")
        
        start_time = time.time()
        
        # First pass: Create all node instances (unchanged)
        for node_def in nodes:
            node_id = node_def["id"]
            node_type = node_def["type"]
            user_data = node_def.get("data", {})

            if node_id in self.control_flow_nodes:
                continue  # Skip control flow nodes

            try:
                # Get node class and create instance
                # Use self.get_node helper which handles both dict and NodeRegistry object
                node_cls = self.get_node(node_type)
                if not node_cls:
                    available_nodes = self.node_registry.get_all_nodes()
                    available_types = [node.name for node in available_nodes]
                    logger.error(f"Unknown node type: {node_type}. Available: {available_types}")
                    raise ValueError(f"Unknown node type: {node_type}. Available types: {available_types}")

                instance = node_cls()
                instance.node_id = node_id
                instance.user_data = user_data

                # Create GraphNodeInstance
                self.nodes[node_id] = GraphNodeInstance(
                    id=node_id,
                    type=node_type,
                    node_instance=instance,
                    metadata={},
                    user_data=user_data,
                )
                
                logger.debug(f"Created {node_id} ({node_type})")
                
            except Exception as e:
                logger.error(f"Failed to create node {node_id}: {e}")
                raise NodeExecutionError(node_id, node_type, e) from e
        
        # Second pass: Build connection mappings using ConnectionMapper
        try:
            logger.info("Building enhanced connection mappings with ConnectionMapper")
            
            # Build enhanced mappings
            connection_mappings = self.connection_mapper.build_enhanced_connection_mappings(
                self.connections,
                {node_id: gnode.node_instance for node_id, gnode in self.nodes.items()}
            )
            
            # Apply connection mappings to node instances
            self.connection_mapper.apply_connection_mappings(connection_mappings, self.nodes)
            
            # Update NodeExecutor with nodes registry for connection extraction
            self.node_executor.set_nodes_registry(self.nodes)
            
        except Exception as e:
            logger.error(f"Enhanced connection mapping failed, falling back to basic mapping: {e}")
            # Fallback to basic connection mapping
            self.connection_mapper.build_basic_connection_mappings(self.connections, self.nodes)
        
        # Record build metrics
        build_duration = time.time() - start_time
        logger.info(f"Enhanced instantiation completed in {build_duration:.3f}s")

    def _compile_final_graph(self) -> CompiledStateGraph:
        """Compile final LangGraph using all components."""
        logger.info("Compiling final LangGraph")
        
        try:
            graph = StateGraph(FlowState)

            # 1) Add regular nodes with enhanced node wrapper
            for node_id, gnode in self.nodes.items():
                graph.add_node(node_id, self._wrap_node_enhanced(node_id, gnode))

            # 2) Add control-flow constructs using ControlFlowManager
            self.control_flow_manager.add_control_flow_edges(graph)

            # 3) Add regular edges
            self._add_regular_edges(graph)

            # 4) Add START & END connections
            self._add_start_end_connections(graph)

            # Compile with checkpointer
            compiled_graph = graph.compile(checkpointer=self.checkpointer)
            
            self.graph = compiled_graph
            logger.info("LangGraph compilation successful")
            
            return compiled_graph
            
        except Exception as e:
            logger.error(f"LangGraph compilation failed: {e}")
            raise GraphCompilationError(
                f"LangGraph compilation failed: {str(e)}",
                compilation_stage="graph_compile",
                node_count=len(self.nodes),
                edge_count=len(self.connections),
                langgraph_error=e
            ) from e

    def _wrap_node_enhanced(self, node_id: str, gnode: GraphNodeInstance) -> Callable[[FlowState], Dict[str, Any]]:
        """Enhanced node wrapper that uses NodeExecutor for execution."""
        
        def wrapper(state: FlowState) -> Dict[str, Any]:
            try:
                logger.info(f"EXECUTING: {node_id} ({gnode.type}) with NodeExecutor")
                
                # Merge user data into node instance before execution
                gnode.node_instance.user_data.update(gnode.user_data)
                
                # Setup session using NodeExecutor
                self.node_executor.setup_node_session(gnode, state, node_id)
                
                # Execute node using NodeExecutor based on node type
                # Both 'processor' and 'terminator' nodes benefit from NodeExecutor's templating and connection handling
                if gnode.node_instance.metadata.node_type.value in ["processor", "terminator"]:
                    # Use NodeExecutor for processor and terminator nodes
                    result = self.node_executor.execute_processor_node(gnode, state, node_id)
                else:
                    # Use NodeExecutor for standard nodes (provider, etc.)
                    result = self.node_executor.execute_standard_node(gnode, state, node_id)
                
                logger.info(f"Node {node_id} ({gnode.type}) completed successfully with NodeExecutor")
                return result
                
            except Exception as e:
                # Enhanced error handling
                error_details = {
                    "node_id": node_id,
                    "node_type": gnode.type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": str(datetime.datetime.now()),
                    "stack_trace": traceback.format_exc()
                }
                
                logger.error(f"Node {node_id} ({gnode.type}) execution failed: {str(e)}")
                
                # Update state with error
                if hasattr(state, 'add_error'):
                    state.add_error(f"Node {node_id} failed: {str(e)}")
                else:
                    if not hasattr(state, 'errors'):
                        state.errors = []
                    state.errors.append(f"Node {node_id} failed: {str(e)}")
                
                # Store detailed error information
                if not hasattr(state, 'error_details'):
                    state.error_details = {}
                state.error_details[node_id] = error_details
                
                state.last_output = f"ERROR in {node_id}: {str(e)}"
                
                # Raise the exception to stop execution
                if isinstance(e, NodeExecutionError):
                    raise  # Re-raise NodeExecutor exceptions
                else:
                    raise NodeExecutionError(node_id, gnode.type, e) from e

        wrapper.__name__ = f"node_{node_id}"
        return wrapper

    # ---------------------------------------------------------------------
    # Graph building helpers - simplified with component delegation
    # ---------------------------------------------------------------------

    def _get_checkpointer(self):
        """Get the appropriate checkpointer for this graph builder."""
        return MemorySaver()

    def _add_regular_edges(self, graph: StateGraph):
        """Add regular node-to-node edges to the LangGraph."""
        logger.info(f"ADDING REGULAR EDGES ({len(self.connections)} connections)")
        
        # Track ConditionNode connections for conditional routing
        condition_node_connections: Dict[str, Dict[str, str]] = {}
        
        for conn in self.connections:
            source_id = conn.source_node_id
            target_id = conn.target_node_id
            source_handle = conn.source_handle
            
            # Skip if either node is not in our graph (StartNode/EndNode handled separately)
            if source_id not in self.nodes or target_id not in self.nodes:
                logger.debug(f"Skipping edge {source_id} -> {target_id} (node not in graph)")
                continue
            
            # Check if source is a ConditionNode
            source_node = self.nodes.get(source_id)
            if source_node and source_node.type == "ConditionNode":
                # Collect connections for conditional routing
                if source_id not in condition_node_connections:
                    condition_node_connections[source_id] = {}
                condition_node_connections[source_id][source_handle] = target_id
                logger.debug(f"Collected ConditionNode connection: {source_id}[{source_handle}] -> {target_id}")
                continue  # Don't add regular edge - will use conditional edge
                
            # Add regular edge to LangGraph
            try:
                graph.add_edge(source_id, target_id)
                logger.debug(f"Added edge: {source_id} -> {target_id}")
            except Exception as e:
                logger.error(f"Failed to add edge {source_id} -> {target_id}: {e}")
        
        # Add conditional edges for ConditionNodes
        for node_id, targets in condition_node_connections.items():
            self._add_condition_node_edges(graph, node_id, targets)
    
    def _add_condition_node_edges(self, graph: StateGraph, node_id: str, targets: Dict[str, str]):
        """Add conditional edges for a ConditionNode based on its _route output."""
        logger.info(f"Adding conditional edges for ConditionNode: {node_id}")
        
        true_target = targets.get("true_output")
        false_target = targets.get("false_output")
        
        # Fallback to "output" handle if specific handles not found
        if not true_target and not false_target:
            default_target = targets.get("output")
            if default_target:
                logger.debug(f"   Using default output target: {default_target}")
                graph.add_edge(node_id, default_target)
                return
            else:
                # No connections at all - raise error
                raise ValidationError(
                    f"ConditionNode '{node_id}' has no output connections. "
                    "Connect at least one output (True or False) to continue.",
                    validation_errors=[f"Missing output connections for {node_id}"]
                )
        
        # Store connection status for runtime error handling
        has_true = true_target is not None
        has_false = false_target is not None
        
        def route_condition(state: FlowState) -> str:
            """Route based on ConditionNode's _route output."""
            # Get the node's output from state
            node_outputs = getattr(state, 'node_outputs', {})
            condition_output = node_outputs.get(node_id, {})
            
            # Check for _route key in output
            route = condition_output.get("_route", "true_output")
            condition_result = condition_output.get("condition_result", True)
            
            logger.info(f"ConditionNode {node_id} - Result: {condition_result}, Route: {route}")
            
            # Route based on condition result
            if condition_result:
                # Condition is TRUE - need true_output connection
                if has_true:
                    logger.info(f"Routing to TRUE path: {true_target}")
                    return true_target
                else:
                    # TRUE path not connected - raise error
                    error_msg = (
                        f"ConditionNode '{node_id}' evaluated to TRUE but 'True' output is not connected. "
                        "Please connect the 'True' output to a node."
                    )
                    logger.error(f"{error_msg}")
                    raise NodeExecutionError(node_id, "ConditionNode", Exception(error_msg))
            else:
                # Condition is FALSE - need false_output connection
                if has_false:
                    logger.info(f"Routing to FALSE path: {false_target}")
                    return false_target
                else:
                    # FALSE path not connected - raise error
                    error_msg = (
                        f"ConditionNode '{node_id}' evaluated to FALSE but 'False' output is not connected. "
                        "Please connect the 'False' output to a node."
                    )
                    logger.error(f"{error_msg}")
                    raise NodeExecutionError(node_id, "ConditionNode", Exception(error_msg))
        
        # Build routing map - only include connected paths
        routing_map = {}
        if true_target:
            routing_map[true_target] = true_target
        if false_target:
            routing_map[false_target] = false_target
            
        try:
            graph.add_conditional_edges(node_id, route_condition, routing_map)
            logger.info(f"Added conditional edges: {node_id} -> True:{true_target}, False:{false_target}")
        except Exception as e:
            logger.error(f"Failed to add conditional edges for {node_id}: {e}")
            raise

    def _add_start_end_connections(self, graph: StateGraph):
        """Add START and END connections to the LangGraph."""
        logger.info(f"ADDING START/END CONNECTIONS")
        
        # Add START connections
        if self.explicit_start_nodes:
            logger.info(f"START -> {list(self.explicit_start_nodes)}")
            for start_target in self.explicit_start_nodes:
                if start_target in self.nodes:
                    graph.add_edge(START, start_target)
                    logger.debug(f"START -> {start_target}")
                else:
                    logger.warning(f"START target {start_target} not found in nodes")
        else:
            logger.warning("No explicit start nodes found")
        
        # Add END connections - find nodes that connect to EndNodes
        end_connections = []
        for conn in self.connections:
            if conn.target_node_id in self.end_nodes_for_connections:
                end_connections.append(conn.source_node_id)
        
        if end_connections:
            logger.info(f"{end_connections} -> END")
            for end_source in end_connections:
                if end_source in self.nodes:
                    graph.add_edge(end_source, END)
                    logger.debug(f"{end_source} -> END")
                else:
                    logger.warning(f"END source {end_source} not found in nodes")
        else:
            # If no explicit END connections, connect the last nodes
            logger.debug("No explicit END connections, finding last nodes")
            all_targets = {conn.target_node_id for conn in self.connections}
            all_sources = {conn.source_node_id for conn in self.connections}
            last_nodes = [node_id for node_id in all_sources if node_id not in all_targets and node_id in self.nodes]
            
            if last_nodes:
                logger.info(f"Auto-connecting last nodes to END: {last_nodes}")
                for last_node in last_nodes:
                    graph.add_edge(last_node, END)
                    logger.debug(f"{last_node} -> END")

    # ---------------------------------------------------------------------
    # Execution methods - preserved for backward compatibility
    # ---------------------------------------------------------------------

    async def execute(
        self,
        inputs: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Run the compiled graph - preserved from original implementation."""
        if not self.graph:
            raise ValueError("Graph has not been built. Call build_from_flow().")

        # Prepare initial FlowState
        initial_input = inputs.get("input", "")

        webhook_data = inputs.get("webhook_data")
        
        init_state = FlowState(
            current_input=initial_input,
            last_output=initial_input,
            session_id=session_id or str(uuid.uuid4()),
            user_id=user_id,
            owner_id=owner_id,
            workflow_id=workflow_id,
            variables=inputs,
            webhook_data=webhook_data,  # Add webhook data for templating
        )
        config: RunnableConfig = {"configurable": {"thread_id": init_state.session_id}}

        if stream:
            return self._execute_stream(init_state, config)
        else:
            return await self._execute_sync(init_state, config)

    async def _execute_sync(self, init_state: FlowState, config: RunnableConfig) -> Dict[str, Any]:
        """Synchronous execution - preserved from original."""
        logger.info(f"Starting synchronous workflow execution")
        
        try:
            result_state = await self.graph.ainvoke(init_state, config=config)
            logger.info(f"Graph execution completed successfully")
            
            # Convert FlowState to serializable format
            try:
                # Check if result_state is a dict (LangGraph sometimes returns dict)
                if isinstance(result_state, dict):
                    state_dict = result_state
                    logger.debug(f"Result state is dict, keys: {list(state_dict.keys())}")
                elif hasattr(result_state, 'model_dump'):
                    state_dict = result_state.model_dump()
                    logger.debug(f"Result state is FlowState, dumped to dict")
                elif hasattr(result_state, 'values') and isinstance(result_state.values, dict):
                    # LangGraph StateSnapshot format
                    state_dict = result_state.values
                    logger.debug(f"Result state is StateSnapshot, using values dict")
                else:
                    # Try to get attributes directly
                    state_dict = {
                        "last_output": getattr(result_state, "last_output", ""),
                        "executed_nodes": getattr(result_state, "executed_nodes", []),
                        "node_outputs": getattr(result_state, "node_outputs", {}),
                        "session_id": getattr(result_state, "session_id", init_state.session_id)
                    }
                    logger.debug(f"Result state extracted via getattr")
                
                # Ensure last_output is set correctly
                if not state_dict.get("last_output"):
                    # Try to get from node_outputs if last_output is empty
                    node_outputs = state_dict.get("node_outputs", {})
                    if node_outputs:
                        # Get the last node's output
                        last_node_output = None
                        for node_id, output in node_outputs.items():
                            if output:
                                if isinstance(output, dict):
                                    last_node_output = output.get("output") or output.get("result") or str(output)
                                else:
                                    last_node_output = str(output)
                                break
                        
                        if last_node_output:
                            state_dict["last_output"] = last_node_output
                            logger.info(f"Extracted last_output from node_outputs: {last_node_output[:100]}")
                
            except Exception as e:
                logger.error(f"Error converting result_state to dict: {e}", exc_info=True)
                state_dict = {
                    "last_output": str(result_state) if result_state else "",
                    "executed_nodes": [],
                    "node_outputs": {},
                    "session_id": init_state.session_id
                }
            
            # Extract result from state_dict, with fallback to node_outputs
            result_output = state_dict.get("last_output", "")
            
            # If last_output is empty, try to extract from node_outputs
            if not result_output:
                node_outputs = state_dict.get("node_outputs", {})
                if node_outputs:
                    # Get the first non-empty output
                    for node_id, output in node_outputs.items():
                        if output:
                            if isinstance(output, dict):
                                result_output = output.get("output") or output.get("result") or str(output)
                            else:
                                result_output = str(output)
                            if result_output:
                                logger.info(f"Extracted result from node_outputs[{node_id}]: {result_output[:100]}")
                                break
            
            logger.info(f"Final result output: {result_output[:100] if result_output else '(empty)'}")
            
            return {
                "success": True,
                "result": result_output,
                "state": state_dict,
                "executed_nodes": state_dict.get("executed_nodes", []),
                "session_id": state_dict.get("session_id", init_state.session_id),
            }
            
        except Exception as e:
            return {
                "success": False, 
                "error": str(e), 
                "error_type": type(e).__name__, 
                "session_id": init_state.session_id
            }

    async def _execute_stream(self, init_state: FlowState, config: RunnableConfig):
        """Streaming execution - preserved from original."""
        try:
            logger.info(f"Starting streaming execution for session: {init_state.session_id}")
            yield {"type": "start", "session_id": init_state.session_id, "message": "Starting workflow execution"}
            
            # Track previously executed node to help frontend animate correct edge
            previous_node_id: str | None = None
            
            # Stream workflow execution events
            event_count = 0
            async for ev in self.graph.astream_events(init_state, config=config):
                event_count += 1
                
                # Process and yield events (simplified version of original logic)
                ev_type = ev.get("event", "")
                node_name = ev.get("name", "unknown")
                
                if ev_type == "on_chain_start":
                    yield {
                        "type": "node_start", 
                        "node_id": node_name,
                        "previous_node_id": previous_node_id  # Include previous node for edge animation
                    }
                elif ev_type == "on_chain_end":
                    # Extract output from the event data for node_end
                    ev_data = ev.get("data", {})
                    node_output = ev_data.get("output", {})
                    
                    # Try to extract meaningful output from various formats
                    output_data = {}
                    if isinstance(node_output, dict):
                        # Check for common output keys
                        if "last_output" in node_output:
                            output_data["output"] = node_output.get("last_output")
                        elif "output" in node_output:
                            output_data["output"] = node_output.get("output")
                        elif "node_outputs" in node_output:
                            output_data = node_output.get("node_outputs", {})
                        else:
                            output_data = node_output
                    elif node_output:
                        output_data["output"] = str(node_output)
                    
                    yield {
                        "type": "node_end",
                        "node_id": node_name,
                        "output": output_data
                    }
                    
                    # Update previous node after successful completion
                    previous_node_id = node_name
                elif ev_type == "on_llm_new_token":
                    yield {"type": "token", "content": ev.get("data", {}).get("chunk", "")}
                elif ev_type == "on_chain_error":
                    error_msg = str(ev.get("data", {}).get("error", "Unknown error"))
                    yield {"type": "error", "error": error_msg, "node_id": ev.get("name", "unknown")}
            
            # Get final state
            final_state = await self.graph.aget_state(config)
            if hasattr(final_state, 'values') and final_state.values:
                last_output = final_state.values.get('last_output', 'No output')
                executed_nodes = final_state.values.get('executed_nodes', [])
                node_outputs = final_state.values.get('node_outputs', {})
            else:
                last_output = ""
                executed_nodes = []
                node_outputs = {}
            
            # Yield completion event with node_outputs for frontend display
            yield {
                "type": "complete",
                "result": last_output,
                "executed_nodes": executed_nodes,
                "node_outputs": node_outputs,
                "session_id": init_state.session_id,
            }
            
        except Exception as e:
            yield {
                "type": "error", 
                "error": str(e), 
                "error_type": type(e).__name__, 
                "session_id": init_state.session_id
            }

    async def execute_with_monitoring(
            self,
            inputs: Dict[str, Any],
            session_id: Optional[str] = None,
            user_id: Optional[str] = None,
            owner_id: Optional[str] = None,
            workflow_id: Optional[str] = None,
            stream: bool = False,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Execute workflow with enhanced monitoring - preserved from original."""
        logger.info(f"Starting enhanced execution (session: {session_id})")
        execution_start = time.time()

        try:
            result = await self.execute(inputs, session_id, user_id, owner_id, workflow_id, stream)
            execution_duration = time.time() - execution_start
            logger.info(f"Enhanced execution completed in {execution_duration:.3f}s")
            return result

        except Exception as e:
            execution_duration = time.time() - execution_start
            logger.error(f"Enhanced execution failed after {execution_duration:.3f}s: {e}")
            raise
            raise