"""
GraphBuilder Validation Engine
=============================

Handles workflow validation and error checking for the GraphBuilder system.
Provides clean separation of validation logic from the main orchestrator.

AUTHORS: KAI-Fusion Workflow Orchestration Team
VERSION: 2.1.0
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Fusion Platform
"""

from typing import Dict, Any, List, Optional, Type, Set
import logging
from collections import defaultdict

from .types import (
    ValidationResult, NodeRegistry, START_NODE_TYPE, END_NODE_TYPE,
    TERMINAL_NODE_TYPES, PooledConnection, ConnectionPoolStats, ConnectionPoolConfig,
    DEFAULT_POOL_ENABLED, POOL_FEATURE_FLAG
)
from .exceptions import ValidationError
from app.nodes import BaseNode
from app.core.connection_pool import ConnectionPool

logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    Handles workflow validation and error checking.
    
    Provides comprehensive validation including:
    - Node structure and configuration validation
    - Connection validation
    - Required node presence validation
    - Workflow topology validation
    - Control flow validation
    """
    
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
        self._validation_stats = {}

        # Ensure node_registry has get_node method if it's a dict
        if isinstance(self.node_registry, dict) and not hasattr(
            self.node_registry, "get_node"
        ):
            # It's a dict, we need to wrap it or handle it
            self._node_registry_dict = self.node_registry
            # Monkey patch or use a helper method
            self.get_node = lambda type_name: self._node_registry_dict.get(type_name)
        else:
            self.get_node = self.node_registry.get_node

    # ... inside methods, use self.get_node(node_type) instead of self.node_registry.get_node(node_type)

    def validate_workflow(self, flow_data: Dict[str, Any]) -> ValidationResult:
        """
        Enhanced workflow validation before building.

        Args:
            flow_data: Complete workflow data including nodes and edges

        Returns:
            ValidationResult with comprehensive validation information

        Raises:
            ValidationError: If validation fails critically
        """
        try:
            logger.info(" Validating workflow structure")

            # Initialize validation result
            result = ValidationResult(
                valid=True, errors=[], warnings=[], node_count=0, connection_count=0
            )

            # Extract nodes and edges
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])

            result.node_count = len(nodes)
            result.connection_count = len(edges)

            # Perform validation steps
            self._validate_nodes(nodes, result)
            self._validate_edges(edges, nodes, result)
            self._validate_multiple_connections(edges, nodes, result)
            self._validate_required_nodes(nodes, result)
            self._validate_workflow_topology(nodes, edges, result)

            # Final validation status
            result.valid = len(result.errors) == 0

            # Update validation stats
            self._validation_stats = {
                "node_count": result.node_count,
                "connection_count": result.connection_count,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
                "validation_passed": result.valid,
            }

            # Log results
            status = "VALID" if result.valid else "INVALID"
            logger.info(f" Validation complete: {status}")

            if result.errors:
                logger.error(f" Validation errors: {result.errors}")

            if result.warnings:
                logger.warning(f" Validation warnings: {result.warnings}")

            return result

        except Exception as e:
            logger.error(f"Validation engine failed: {e}")
            raise ValidationError(
                f"Validation engine failed: {str(e)}", validation_errors=[str(e)]
            ) from e

    def _validate_nodes(
        self, nodes: List[Dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Validate individual nodes.

        Args:
            nodes: List of node definitions
            result: ValidationResult to update
        """
        try:
            node_ids = set()
            start_node_ids = set()

            for node in nodes:
                node_id = node.get("id")
                node_type = node.get("type")

                # Check for required fields
                if not node_id:
                    result.add_error("Node missing ID")
                    continue

                # Check for duplicate IDs
                if node_id in node_ids:
                    result.add_error(f"Duplicate node ID: {node_id}")
                node_ids.add(node_id)

                # Track StartNode IDs separately since they are filtered out during build
                if node_type == START_NODE_TYPE:
                    start_node_ids.add(node_id)
                    continue

                # Check for node type
                if not node_type:
                    result.add_error(f"Node {node_id} missing type")
                    continue

                # Check if node type is registered
                # node_registry.get_node() instead of node_registry.get_node
                node_class = self.get_node(node_type)
                if not node_class:
                    result.add_error(f"Unknown node type: {node_type}")
                    continue

                # Validate node configuration
                self._validate_node_configuration(node, result)

            logger.debug(
                f"Node validation complete: {len(nodes)} nodes, {len(result.errors)} errors"
            )

        except Exception as e:
            result.add_error(f"Node validation failed: {str(e)}")

    def _validate_node_configuration(
        self, node: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        Validate individual node configuration.

        Args:
            node: Node definition
            result: ValidationResult to update
        """
        try:
            node_id = node.get("id")
            node_type = node.get("type")
            node_data = node.get("data", {})

            # Get node class for validation
            node_class = self.get_node(node_type)
            if not node_class:
                return  # Already handled in _validate_nodes

            # Check for required configuration fields
            # This could be expanded based on node-specific requirements
            if not isinstance(node_data, dict):
                result.add_error(f"Node {node_id} has invalid data format")

            # Additional node-specific validation could be added here
            # For example, checking required fields for specific node types

        except Exception as e:
            result.add_error(
                f"Configuration validation failed for node {node.get('id', 'unknown')}: {str(e)}"
            )

    def _validate_edges(
        self,
        edges: List[Dict[str, Any]],
        nodes: List[Dict[str, Any]],
        result: ValidationResult,
    ) -> None:
        """
        Validate edge connections.

        Args:
            edges: List of edge definitions
            nodes: List of node definitions
            result: ValidationResult to update
        """
        try:
            # Build node ID sets
            node_ids = {node.get("id") for node in nodes if node.get("id")}
            start_node_ids = {
                node.get("id")
                for node in nodes
                if node.get("type") == START_NODE_TYPE and node.get("id")
            }

            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")

                # Check for required fields
                if not source or not target:
                    result.add_error("Edge missing source or target")
                    continue

                # Check if source is a StartNode (handled separately in build process)
                if source in start_node_ids:
                    continue

                # Validate source node exists
                if source not in node_ids:
                    result.add_error(f"Edge references unknown source node: {source}")

                # Validate target node exists
                if target not in node_ids and target not in start_node_ids:
                    result.add_error(f"Edge references unknown target node: {target}")

                # Validate handles if present
                source_handle = edge.get("sourceHandle")
                target_handle = edge.get("targetHandle")

                if source_handle is not None and not isinstance(source_handle, str):
                    result.add_error(
                        f"Edge has invalid sourceHandle format: {source_handle}"
                    )

                if target_handle is not None and not isinstance(target_handle, str):
                    result.add_error(
                        f"Edge has invalid targetHandle format: {target_handle}"
                    )

            logger.debug(f"Edge validation complete: {len(edges)} edges")

        except Exception as e:
            result.add_error(f"Edge validation failed: {str(e)}")

    def _validate_multiple_connections(
        self,
        edges: List[Dict[str, Any]],
        nodes: List[Dict[str, Any]],
        result: ValidationResult,
    ) -> None:
        """
        Validate many-to-many connection scenarios.

        This method performs comprehensive validation of multiple connections
        to the same target handle, ensuring compatibility and detecting
        potential issues with many-to-many connection patterns.

        Args:
            edges: List of edge definitions
            nodes: List of node definitions
            result: ValidationResult to update
        """
        try:
            logger.debug(" Validating many-to-many connections")

            # Group edges by target (node_id + handle)
            target_groups = defaultdict(list)
            for edge in edges:
                target_node = edge.get("target")
                target_handle = edge.get("targetHandle", "input")
                if target_node:
                    target_key = f"{target_node}#{target_handle}"
                    target_groups[target_key].append(edge)

            # Validate each target that has multiple connections
            many_to_many_targets = 0
            for target_key, target_edges in target_groups.items():
                if len(target_edges) > 1:
                    many_to_many_targets += 1
                    self._validate_many_to_many_target(
                        target_key, target_edges, nodes, result
                    )

                    # Check for excessive connections (performance warning)
                    if len(target_edges) > 10:
                        result.add_warning(
                            f"Very high connection count ({len(target_edges)}) to {target_key} - "
                            "consider architectural refactoring for better performance"
                        )

            # Log summary
            if many_to_many_targets > 0:
                logger.info(
                    f" Many-to-many validation: {many_to_many_targets} targets with multiple connections"
                )
            else:
                logger.debug("No many-to-many connections found")

        except Exception as e:
            logger.error(f"Multiple connections validation failed: {e}")
            result.add_error(f"Many-to-many validation failed: {str(e)}")

    def _validate_many_to_many_target(
        self,
        target_key: str,
        edges: List[Dict[str, Any]],
        nodes: List[Dict[str, Any]],
        result: ValidationResult,
    ) -> None:
        """
        Validate a specific many-to-many target.

        Performs detailed validation of multiple connections targeting
        the same node handle, including data type consistency,
        node capability checks, and potential conflict detection.

        Args:
            target_key: Target identifier in format "node_id#handle"
            edges: List of edges targeting this handle
            nodes: List of node definitions
            result: ValidationResult to update
        """
        try:
            target_node_id, target_handle = target_key.split("#", 1)

            # Find target node definition
            target_node = next(
                (n for n in nodes if n.get("id") == target_node_id), None
            )
            if not target_node:
                result.add_error(
                    f"Target node not found for many-to-many validation: {target_node_id}"
                )
                return

            # Validate data type consistency
            self._validate_data_type_consistency(target_key, edges, result)

            # Check connection compatibility
            self._check_connection_compatibility(target_key, edges, target_node, result)

            # Validate many-to-many constraints
            self._check_many_to_many_constraints(target_key, edges, target_node, result)

            # Performance impact assessment
            connection_count = len(edges)
            if connection_count > 5:
                result.add_warning(
                    f"High connection count ({connection_count}) to {target_key} may impact performance - "
                    "consider connection pooling or data aggregation"
                )

        except ValueError:
            result.add_error(f"Invalid target key format: {target_key}")
        except Exception as e:
            logger.error(f"Many-to-many target validation failed for {target_key}: {e}")
            result.add_error(
                f"Many-to-many target validation failed for {target_key}: {str(e)}"
            )

    def _validate_data_type_consistency(
        self, target_key: str, edges: List[Dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Ensure data types are consistent across multiple connections.

        Validates that all connections to the same target handle have
        compatible data types to prevent runtime type conflicts.

        Args:
            target_key: Target identifier in format "node_id#handle"
            edges: List of edges targeting this handle
            result: ValidationResult to update
        """
        try:
            # Extract data types from edges (with fallback to 'any')
            data_types = []
            for edge in edges:
                edge_type = edge.get("type", edge.get("data_type", "any"))
                data_types.append(edge_type)

            # Remove None values and normalize
            data_types = [dt for dt in data_types if dt is not None]
            unique_types = set(data_types)

            # Check for type consistency
            if len(unique_types) > 1:
                # Allow 'any' type to be compatible with everything
                non_any_types = unique_types - {"any"}
                if len(non_any_types) > 1:
                    result.add_warning(
                        f"Multiple incompatible data types connecting to {target_key}: {sorted(non_any_types)} "
                        "- this may cause runtime type errors"
                    )
                else:
                    logger.debug(
                        f"Mixed types with 'any' for {target_key}: {unique_types}"
                    )

            # Check for potential data aggregation needs
            if len(data_types) > 3 and len(unique_types) == 1:
                specific_type = list(unique_types)[0]
                if specific_type != "any":
                    result.add_warning(
                        f"Multiple connections of same type ({specific_type}) to {target_key} - "
                        "consider if data aggregation/merging logic is needed"
                    )

        except Exception as e:
            logger.error(
                f"Data type consistency validation failed for {target_key}: {e}"
            )
            result.add_warning(
                f"Could not validate data type consistency for {target_key}"
            )

    def _check_connection_compatibility(
        self,
        target_key: str,
        edges: List[Dict[str, Any]],
        target_node: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """
        Check if multiple connections are compatible with the target node.

        Validates that the target node can handle multiple input connections
        and that the connection patterns are supported.

        Args:
            target_key: Target identifier in format "node_id#handle"
            edges: List of edges targeting this handle
            target_node: Target node definition
            result: ValidationResult to update
        """
        try:
            node_type = target_node.get("type")
            node_id = target_node.get("id")

            # Check if node type supports many-to-many inputs
            # This could be enhanced with more sophisticated node capability detection
            many_to_many_supported_types = {
                "ReactAgent",
                "ToolAgentNode",
                "Agent",  # Agents can handle multiple inputs
                "BufferMemory",
                "ConversationMemory",  # Memory nodes can aggregate
                "VectorStoreOrchestrator",  # Vector stores can handle multiple queries
                "ChunkSplitter",  # Splitters can process multiple documents
                "HttpClient",  # HTTP clients can make multiple requests
            }

            if node_type not in many_to_many_supported_types:
                result.add_warning(
                    f"Node type '{node_type}' at {target_key} may not fully support multiple input connections "
                    "- verify node implementation handles connection aggregation properly"
                )

            # Check for source node conflicts
            source_nodes = [edge.get("source") for edge in edges if edge.get("source")]
            unique_sources = set(source_nodes)

            if len(unique_sources) != len(source_nodes):
                result.add_warning(
                    f"Duplicate source connections detected for {target_key} - "
                    "this may cause data duplication or race conditions"
                )

            # Validate handle consistency
            target_handles = [edge.get("targetHandle", "input") for edge in edges]
            if len(set(target_handles)) > 1:
                result.add_error(
                    f"Inconsistent target handles for {target_key}: {set(target_handles)}"
                )

        except Exception as e:
            logger.error(f"Connection compatibility check failed for {target_key}: {e}")
            result.add_warning(
                f"Could not validate connection compatibility for {target_key}"
            )

    def _check_many_to_many_constraints(
        self,
        target_key: str,
        edges: List[Dict[str, Any]],
        target_node: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """
        Validate specific many-to-many business rules and constraints.

        Checks for domain-specific rules and constraints that apply
        to many-to-many connection scenarios.

        Args:
            target_key: Target identifier in format "node_id#handle"
            edges: List of edges targeting this handle
            target_node: Target node definition
            result: ValidationResult to update
        """
        try:
            node_type = target_node.get("type")
            connection_count = len(edges)

            # Node-specific constraint checks
            if node_type == "EndNode" and connection_count > 1:
                result.add_warning(
                    f"Multiple connections to EndNode at {target_key} - "
                    "ensure proper workflow termination logic"
                )

            elif node_type in ["OpenAINode", "LLMNode"] and connection_count > 3:
                result.add_warning(
                    f"High connection count ({connection_count}) to LLM node at {target_key} - "
                    "this may impact response time and token usage"
                )

            elif node_type == "BufferMemory" and connection_count > 5:
                result.add_warning(
                    f"Very high connection count ({connection_count}) to memory node at {target_key} - "
                    "consider memory partitioning or separate memory instances"
                )

            # Check for circular dependency risks with many-to-many
            source_nodes = [edge.get("source") for edge in edges if edge.get("source")]
            target_node_id = target_key.split("#")[0]

            if target_node_id in source_nodes:
                result.add_warning(
                    f"Self-referencing connection detected in many-to-many pattern at {target_key} - "
                    "verify this doesn't create infinite loops"
                )

            # Validate connection ordering if priorities are specified
            priorities = []
            for edge in edges:
                priority = edge.get("priority", 0)
                if isinstance(priority, (int, float)):
                    priorities.append(priority)

            if priorities and len(set(priorities)) == 1 and len(priorities) > 1:
                result.add_warning(
                    f"All connections to {target_key} have same priority ({priorities[0]}) - "
                    "consider setting different priorities for deterministic execution order"
                )

        except Exception as e:
            logger.error(f"Many-to-many constraints check failed for {target_key}: {e}")
            result.add_warning(
                f"Could not validate many-to-many constraints for {target_key}"
            )

    def _validate_required_nodes(
        self, nodes: List[Dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Validate presence of required nodes.

        Args:
            nodes: List of node definitions
            result: ValidationResult to update
        """
        try:
            # Check for required StartNode and EndNode
            # WebhookTrigger nodes can also serve as entry points
            start_nodes = [n for n in nodes if n.get("type") == START_NODE_TYPE]
            webhook_trigger_nodes = [
                n for n in nodes if n.get("type") == "WebhookTrigger"
            ]
            entry_nodes = start_nodes + webhook_trigger_nodes

            # Check for terminal nodes (EndNode OR RespondToWebhook)
            # These are valid workflow exit points
            terminal_nodes = [n for n in nodes if n.get("type") in TERMINAL_NODE_TYPES]
            end_nodes = [n for n in nodes if n.get("type") == END_NODE_TYPE]
            respond_to_webhook_nodes = [
                n for n in nodes if n.get("type") == "RespondToWebhook"
            ]

            if not entry_nodes:
                result.add_error(
                    "Workflow must contain at least one StartNode or WebhookTrigger node"
                )

            # Only warn if NO terminal nodes exist (neither EndNode nor RespondToWebhook)
            if not terminal_nodes:
                result.add_warning("No EndNode found - virtual EndNode will be created")
            elif respond_to_webhook_nodes and not end_nodes:
                # RespondToWebhook is present as terminal - this is valid, log it
                logger.debug(
                    f"Workflow uses RespondToWebhook as terminal node ({len(respond_to_webhook_nodes)} found)"
                )

            # Check for multiple start nodes (allowed but should be noted)
            if len(entry_nodes) > 1:
                result.add_warning(
                    f"Workflow has {len(start_nodes)} StartNode(s) and {len(webhook_trigger_nodes)} WebhookTrigger node(s) - ensure this is intentional"
                )

            logger.debug(
                f"Required node validation: {len(start_nodes)} start, {len(webhook_trigger_nodes)} webhook trigger, {len(terminal_nodes)} terminal nodes"
            )

        except Exception as e:
            result.add_error(f"Required node validation failed: {str(e)}")

    def _validate_workflow_topology(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        result: ValidationResult,
    ) -> None:
        """
        Validate workflow topology and connectivity.

        Args:
            nodes: List of node definitions
            edges: List of edge definitions
            result: ValidationResult to update
        """
        try:
            if not edges:
                result.add_warning("Workflow has no connections between nodes")
                return

            # Build topology maps
            node_ids = {node.get("id") for node in nodes if node.get("id")}
            source_nodes = {edge.get("source") for edge in edges if edge.get("source")}
            target_nodes = {edge.get("target") for edge in edges if edge.get("target")}

            # Find isolated nodes (nodes with no connections)
            connected_nodes = source_nodes | target_nodes
            isolated_nodes = node_ids - connected_nodes

            # Filter out StartNode and EndNode from isolated check
            start_end_types = {START_NODE_TYPE, END_NODE_TYPE}
            truly_isolated = []

            for node_id in isolated_nodes:
                node = next((n for n in nodes if n.get("id") == node_id), None)
                if node and node.get("type") not in start_end_types:
                    truly_isolated.append(node_id)

            if truly_isolated:
                result.add_warning(
                    f"Isolated nodes found (not connected): {truly_isolated}"
                )

            # Check for potential cycles (simplified check)
            self._check_for_cycles(edges, result)

            logger.debug(f"Topology validation complete")

        except Exception as e:
            result.add_error(f"Topology validation failed: {str(e)}")

    def _check_for_cycles(
        self, edges: List[Dict[str, Any]], result: ValidationResult
    ) -> None:
        """
        Check for potential cycles in the workflow.

        Args:
            edges: List of edge definitions
            result: ValidationResult to update
        """
        try:
            # Build adjacency list
            graph = {}
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")

                if source and target:
                    if source not in graph:
                        graph[source] = []
                    graph[source].append(target)

            # Simple cycle detection using DFS
            visited = set()
            rec_stack = set()

            def has_cycle(node: str) -> bool:
                if node in rec_stack:
                    return True
                if node in visited:
                    return False

                visited.add(node)
                rec_stack.add(node)

                for neighbor in graph.get(node, []):
                    if has_cycle(neighbor):
                        return True

                rec_stack.remove(node)
                return False

            # Check each node
            for node in graph:
                if node not in visited:
                    if has_cycle(node):
                        result.add_warning(
                            f"Potential cycle detected involving node: {node}"
                        )
                        break  # Only report first cycle found

        except Exception as e:
            logger.debug(f"Cycle detection failed: {e}")
            # Don't add this as an error since it's not critical

    def validate_node_connections(
        self, node_id: str, connections: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Validate connections for a specific node.

        Args:
            node_id: ID of the node to validate
            connections: List of connections to validate

        Returns:
            List of validation errors
        """
        errors = []

        try:
            for conn in connections:
                # Validate connection structure
                required_fields = ["source", "target", "sourceHandle", "targetHandle"]
                for field in required_fields:
                    if field not in conn:
                        errors.append(f"Connection missing required field: {field}")

                # Validate connection involves the specified node
                if conn.get("source") != node_id and conn.get("target") != node_id:
                    errors.append(f"Connection does not involve node {node_id}")

        except Exception as e:
            errors.append(f"Connection validation failed for {node_id}: {str(e)}")

        return errors

    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation statistics and metrics.

        Returns:
            Dictionary containing validation statistics
        """
        return self._validation_stats.copy()

    def create_validation_report(self, result: ValidationResult) -> Dict[str, Any]:
        """
        Create a comprehensive validation report.

        Args:
            result: ValidationResult to create report from

        Returns:
            Dictionary containing validation report
        """
        return {
            "summary": {
                "valid": result.valid,
                "node_count": result.node_count,
                "connection_count": result.connection_count,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
            },
            "details": {"errors": result.errors, "warnings": result.warnings},
            "recommendations": self._generate_recommendations(result),
            "stats": self.get_validation_stats(),
        }

    def _generate_recommendations(self, result: ValidationResult) -> List[str]:
        """
        Generate recommendations based on validation results.

        Args:
            result: ValidationResult to generate recommendations from

        Returns:
            List of recommendations
        """
        recommendations = []

        try:
            if not result.valid:
                recommendations.append(
                    "Fix all validation errors before building workflow"
                )

            if result.warnings:
                recommendations.append(
                    "Review validation warnings for potential issues"
                )

            if result.connection_count == 0:
                recommendations.append(
                    "Add connections between nodes to create workflow flow"
                )

            if result.node_count == 0:
                recommendations.append("Add nodes to create a functional workflow")

            if result.node_count > 50:
                recommendations.append(
                    "Consider breaking large workflows into smaller sub-workflows"
                )

        except Exception as e:
            logger.debug(f"Failed to generate recommendations: {e}")

        return recommendations
