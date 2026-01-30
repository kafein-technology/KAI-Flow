"""
GraphBuilder Control Flow Manager
================================

Handles all control flow logic (conditional, loop, parallel) for the GraphBuilder system.
Provides clean separation of control flow management from the main orchestrator.

AUTHORS: KAI-Fusion Workflow Orchestration Team
VERSION: 2.1.0
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Fusion Platform
"""

from typing import Dict, Any, List, Optional, Callable
import logging

from .types import NodeConnection, ControlFlowType, CONTROL_FLOW_NODE_TYPES
from .exceptions import ControlFlowError
from app.core.state import FlowState
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class ControlFlowManager:
    """
    Handles all control flow logic (conditional, loop, parallel).
    
    Provides clean separation of control flow management including:
    - Control flow edge addition to LangGraph
    - Conditional branching with condition evaluation
    - Loop logic with iteration control
    - Parallel execution with fan-out patterns
    - Condition evaluation for different types
    """
    
    def __init__(self, connections: Optional[List[NodeConnection]] = None):
        self.connections = connections or []
        self.control_flow_nodes: Dict[str, Dict[str, Any]] = {}
        self._control_flow_stats = {}
    
    def set_connections(self, connections: List[NodeConnection]) -> None:
        """Set the connections for control flow processing."""
        self.connections = connections
    
    def set_control_flow_nodes(self, control_flow_nodes: Dict[str, Dict[str, Any]]) -> None:
        """Set the control flow nodes configuration."""
        self.control_flow_nodes = control_flow_nodes
    
    def add_control_flow_edges(self, graph: StateGraph, control_flow_nodes: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """
        Add all control flow edges to the graph.
        
        Args:
            graph: LangGraph StateGraph instance
            control_flow_nodes: Dictionary of control flow node configurations
        """
        try:
            nodes_to_process = control_flow_nodes or self.control_flow_nodes
            
            if not nodes_to_process:
                logger.debug("No control flow nodes to process")
                return
            
            logger.info(f"🔀 Adding control flow edges for {len(nodes_to_process)} nodes")
            
            for node_id, info in nodes_to_process.items():
                ctype: ControlFlowType = info["type"]
                cdata = info["data"]
                
                try:
                    if ctype == ControlFlowType.CONDITIONAL:
                        self.add_conditional_routing(graph, node_id, cdata)
                        logger.debug(f"Added conditional routing for {node_id}")
                    elif ctype == ControlFlowType.LOOP:
                        self.add_loop_logic(graph, node_id, cdata)
                        logger.debug(f"Added loop logic for {node_id}")
                    elif ctype == ControlFlowType.PARALLEL:
                        self.add_parallel_fanout(graph, node_id, cdata)
                        logger.debug(f"Added parallel fanout for {node_id}")
                    else:
                        logger.warning(f"Unknown control flow type for {node_id}: {ctype}")
                        
                except Exception as e:
                    logger.error(f"Failed to add control flow for {node_id}: {e}")
                    raise ControlFlowError(
                        f"Failed to add control flow for {node_id}: {str(e)}",
                        control_flow_type=str(ctype),
                        node_id=node_id,
                        condition_config=cdata
                    ) from e
            
            # Update stats
            self._control_flow_stats = {
                "total_control_nodes": len(nodes_to_process),
                "conditional_nodes": sum(1 for info in nodes_to_process.values() if info["type"] == ControlFlowType.CONDITIONAL),
                "loop_nodes": sum(1 for info in nodes_to_process.values() if info["type"] == ControlFlowType.LOOP),
                "parallel_nodes": sum(1 for info in nodes_to_process.values() if info["type"] == ControlFlowType.PARALLEL)
            }
            
            logger.info(f"Control flow edges added successfully. Stats: {self._control_flow_stats}")
            
        except Exception as e:
            logger.error(f"Failed to add control flow edges: {e}")
            raise ControlFlowError(f"Failed to add control flow edges: {str(e)}") from e
    
    def add_conditional_routing(self, graph: StateGraph, node_id: str, cfg: Dict[str, Any]) -> None:
        """
        Add conditional branching logic.
        
        Args:
            graph: LangGraph StateGraph instance
            node_id: ID of the conditional node
            cfg: Configuration dictionary for the conditional logic
        """
        try:
            outgoing = [c for c in self.connections if c.source_node_id == node_id]
            if len(outgoing) < 2:
                logger.warning(f"Conditional node {node_id} has less than 2 outgoing connections")
                return

            cond_field = cfg.get("condition_field", "last_output")
            cond_type = cfg.get("condition_type", "contains")

            def route(state: FlowState) -> str:
                """Route function for conditional logic."""
                try:
                    value = state.get_variable(cond_field, state.last_output)
                    
                    for conn in outgoing:
                        branch_cfg = cfg.get(f"branch_{conn.target_node_id}", {})
                        if self.evaluate_condition(value, branch_cfg, cond_type):
                            logger.debug(f"Conditional route: {node_id} -> {conn.target_node_id}")
                            return conn.target_node_id
                    
                    # Default to first connection
                    default_target = outgoing[0].target_node_id
                    logger.debug(f"Conditional route (default): {node_id} -> {default_target}")
                    return default_target
                    
                except Exception as e:
                    logger.error(f"Error in conditional routing for {node_id}: {e}")
                    return outgoing[0].target_node_id  # Fallback to first connection

            # Add dummy pass-through node and conditional edges
            graph.add_node(node_id, lambda s: s)
            graph.add_conditional_edges(
                node_id,
                route,
                {c.target_node_id: c.target_node_id for c in outgoing},
            )
            
            logger.debug(f"Added conditional routing for {node_id} with {len(outgoing)} branches")
            
        except Exception as e:
            logger.error(f"Failed to add conditional routing for {node_id}: {e}")
            raise ControlFlowError(
                f"Failed to add conditional routing for {node_id}: {str(e)}",
                control_flow_type="conditional",
                node_id=node_id,
                condition_config=cfg
            ) from e
    
    def add_loop_logic(self, graph: StateGraph, node_id: str, cfg: Dict[str, Any]) -> None:
        """
        Add a loop construct that repeats until a condition is met.
        
        Args:
            graph: LangGraph StateGraph instance
            node_id: ID of the loop node
            cfg: Configuration dictionary for the loop logic
        """
        try:
            outgoing = [c for c in self.connections if c.source_node_id == node_id]
            if not outgoing:
                logger.warning(f"Loop node {node_id} has no outgoing connections")
                return

            max_iterations = cfg.get("max_iterations", 10)
            loop_condition = cfg.get("loop_condition", "continue")

            def should_continue(state: FlowState) -> str:
                """Determine if loop should continue."""
                try:
                    iterations = state.get_variable(f"{node_id}_iterations", 0)
                    
                    if iterations >= max_iterations:
                        logger.debug(f"Loop {node_id} reached max iterations ({max_iterations})")
                        return "exit"
                    
                    # Evaluate loop condition
                    if loop_condition == "continue":
                        target = outgoing[0].target_node_id
                        logger.debug(f"Loop {node_id} continuing to {target}")
                        return target
                    else:
                        # Custom condition evaluation
                        if self.evaluate_condition(state.last_output, cfg, "contains"):
                            logger.debug(f"Loop {node_id} exiting due to condition")
                            return "exit"
                        else:
                            target = outgoing[0].target_node_id
                            logger.debug(f"Loop {node_id} continuing to {target}")
                            return target
                            
                except Exception as e:
                    logger.error(f"Error in loop logic for {node_id}: {e}")
                    return "exit"  # Safe fallback

            # Add loop node that increments iteration counter
            def loop_node(state: FlowState) -> Dict[str, Any]:
                current_iterations = state.get_variable(f"{node_id}_iterations", 0)
                return {
                    **state.model_dump(),
                    f"{node_id}_iterations": current_iterations + 1
                }

            graph.add_node(node_id, loop_node)
            graph.add_conditional_edges(
                node_id,
                should_continue,
                {outgoing[0].target_node_id: outgoing[0].target_node_id, "exit": END},
            )
            
            logger.debug(f"Added loop logic for {node_id} with max {max_iterations} iterations")
            
        except Exception as e:
            logger.error(f"Failed to add loop logic for {node_id}: {e}")
            raise ControlFlowError(
                f"Failed to add loop logic for {node_id}: {str(e)}",
                control_flow_type="loop",
                node_id=node_id,
                condition_config=cfg
            ) from e
    
    def add_parallel_fanout(self, graph: StateGraph, node_id: str, cfg: Dict[str, Any]) -> None:
        """
        Add a fan-out node that duplicates state to multiple branches.
        
        Args:
            graph: LangGraph StateGraph instance
            node_id: ID of the parallel node
            cfg: Configuration dictionary for the parallel logic
        """
        try:
            outgoing = [c for c in self.connections if c.source_node_id == node_id]
            if not outgoing:
                logger.warning(f"Parallel node {node_id} has no outgoing connections")
                return

            branch_ids = [c.target_node_id for c in outgoing]

            def fan_out(state: FlowState) -> Dict[str, Any]:
                """Fan-out function for parallel execution."""
                try:
                    # Create mapping of channel -> state to create parallel branches
                    logger.debug(f"Parallel fanout from {node_id} to {branch_ids}")
                    return {bid: state.model_copy() for bid in branch_ids}
                except Exception as e:
                    logger.error(f"Error in parallel fanout for {node_id}: {e}")
                    # Fallback to single state
                    return {branch_ids[0]: state} if branch_ids else {}

            graph.add_node(node_id, fan_out)
            
            # Add edges to all branches
            for bid in branch_ids:
                graph.add_edge(node_id, bid)
            
            logger.debug(f"Added parallel fanout for {node_id} to {len(branch_ids)} branches")
            
        except Exception as e:
            logger.error(f"Failed to add parallel fanout for {node_id}: {e}")
            raise ControlFlowError(
                f"Failed to add parallel fanout for {node_id}: {str(e)}",
                control_flow_type="parallel",
                node_id=node_id,
                condition_config=cfg
            ) from e
    
    def evaluate_condition(self, value: Any, branch_cfg: Dict[str, Any], cond_type: str) -> bool:
        """
        Evaluate control flow condition.
        
        Args:
            value: Value to evaluate
            branch_cfg: Branch configuration
            cond_type: Type of condition to evaluate
            
        Returns:
            Boolean result of condition evaluation
        """
        try:
            if cond_type == "contains":
                condition_value = str(branch_cfg.get("value", ""))
                return condition_value in str(value)
            elif cond_type == "equals":
                condition_value = branch_cfg.get("value", "")
                return str(value) == str(condition_value)
            elif cond_type == "greater_than":
                condition_value = float(branch_cfg.get("value", 0))
                return float(value) > condition_value
            elif cond_type == "less_than":
                condition_value = float(branch_cfg.get("value", 0))
                return float(value) < condition_value
            elif cond_type == "custom":
                expression = branch_cfg.get("expression", "False")
                # Safe evaluation with limited context
                safe_globals = {"value": value, "__builtins__": {}}
                return bool(eval(expression, safe_globals))
            else:
                logger.warning(f"Unknown condition type: {cond_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    def identify_control_flow_nodes(self, nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Detect control-flow constructs like conditional, loop, parallel.
        
        Args:
            nodes: List of node definitions
            
        Returns:
            Dictionary of control flow node configurations
        """
        control_flow_nodes = {}
        
        for node_def in nodes:
            node_type = node_def.get("type", "")
            
            if node_type in CONTROL_FLOW_NODE_TYPES:
                flow_type_map = {
                    "ConditionalNode": ControlFlowType.CONDITIONAL,
                    "LoopNode": ControlFlowType.LOOP,
                    "ParallelNode": ControlFlowType.PARALLEL,
                }
                
                control_flow_nodes[node_def["id"]] = {
                    "type": flow_type_map[node_type],
                    "data": node_def.get("data", {}),
                }
                
                logger.debug(f"Identified control flow node: {node_def['id']} ({node_type})")
        
        self.control_flow_nodes = control_flow_nodes
        logger.info(f"Identified {len(control_flow_nodes)} control flow nodes")
        
        return control_flow_nodes
    
    def get_control_flow_stats(self) -> Dict[str, Any]:
        """
        Get control flow statistics and metrics.
        
        Returns:
            Dictionary containing control flow statistics
        """
        return self._control_flow_stats.copy()
    
    def validate_control_flow_configuration(self, node_id: str, cfg: Dict[str, Any], flow_type: ControlFlowType) -> List[str]:
        """
        Validate control flow configuration.
        
        Args:
            node_id: ID of the control flow node
            cfg: Configuration to validate
            flow_type: Type of control flow
            
        Returns:
            List of validation errors
        """
        errors = []
        
        try:
            if flow_type == ControlFlowType.CONDITIONAL:
                # Validate conditional configuration
                if not cfg.get("condition_type"):
                    errors.append(f"Conditional node {node_id} missing condition_type")
                
                # Check if node has enough outgoing connections
                outgoing = [c for c in self.connections if c.source_node_id == node_id]
                if len(outgoing) < 2:
                    errors.append(f"Conditional node {node_id} needs at least 2 outgoing connections")
            
            elif flow_type == ControlFlowType.LOOP:
                # Validate loop configuration
                max_iterations = cfg.get("max_iterations", 10)
                if not isinstance(max_iterations, int) or max_iterations < 1:
                    errors.append(f"Loop node {node_id} has invalid max_iterations: {max_iterations}")
                
                # Check if node has outgoing connections
                outgoing = [c for c in self.connections if c.source_node_id == node_id]
                if not outgoing:
                    errors.append(f"Loop node {node_id} has no outgoing connections")
            
            elif flow_type == ControlFlowType.PARALLEL:
                # Validate parallel configuration
                outgoing = [c for c in self.connections if c.source_node_id == node_id]
                if len(outgoing) < 2:
                    errors.append(f"Parallel node {node_id} needs at least 2 outgoing connections")
        
        except Exception as e:
            errors.append(f"Error validating control flow for {node_id}: {str(e)}")
        
        return errors