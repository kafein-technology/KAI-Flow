"""
KAI-Fusion Auto-Discovery Tool Manager - Integration Orchestrator
===============================================================

This module provides the central orchestration system for automatic tool
discovery and integration. It manages the lifecycle of tool detection,
conversion, and registration within the agent system.

Key Features:
- Automatic node scanning and tool discovery
- Batch processing for multiple nodes
- Tool registry management
- Integration with agent systems
- Performance monitoring and caching

Authors: KAI-Fusion Tool Integration Team
Version: 1.0.0
License: Proprietary
"""

import logging
from typing import List, Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from .detector import AutoToolDetector
from .converter import AutoToolConverter
from .interfaces import ToolCompatibilityInfo

logger = logging.getLogger(__name__)


class AutoToolManager:
    """
    Central orchestrator for automatic tool discovery and integration.

    This manager coordinates the entire tool integration pipeline:
    1. Node discovery and scanning
    2. Tool compatibility detection
    3. Automatic conversion to agent tools
    4. Tool registration and management
    """

    def __init__(self, max_workers: int = 4):
        """Initialize the tool manager with detector and converter."""
        self.detector = AutoToolDetector()
        self.converter = AutoToolConverter(self.detector)
        self.max_workers = max_workers

        # Tool registry
        self.registered_tools = {}
        self.compatibility_cache = {}

        # Statistics
        self.stats = {
            "nodes_scanned": 0,
            "tools_discovered": 0,
            "tools_converted": 0,
            "conversion_failures": 0,
            "cache_hits": 0
        }

    def discover_and_register_tools(self, node_instances: List[Any]) -> Dict[str, Any]:
        """
        Discover and register tools from a list of node instances.

        This is the main entry point for automatic tool integration.
        It processes nodes in parallel for optimal performance.

        Args:
            node_instances: List of node instances to analyze

        Returns:
            Dictionary with discovery results and statistics
        """
<<<<<<< HEAD
        logger.info(f"Starting tool discovery for {len(node_instances)} nodes")
=======
        logger.info(f" Starting tool discovery for {len(node_instances)} nodes")
>>>>>>> serialization_fixes

        # Reset stats for this batch
        batch_stats = {
            "nodes_processed": 0,
            "tools_found": 0,
            "tools_registered": 0,
            "errors": 0
        }

        # Process nodes (use parallel processing for large batches)
        if len(node_instances) > 10:
            results = self._process_nodes_parallel(node_instances)
        else:
            results = self._process_nodes_sequential(node_instances)

        # Process results
        for result in results:
            batch_stats["nodes_processed"] += 1

            if result["is_compatible"]:
                batch_stats["tools_found"] += 1

                if result["tool_registered"]:
                    batch_stats["tools_registered"] += 1
                    self.registered_tools[result["tool_name"]] = result["tool"]
                else:
                    batch_stats["errors"] += 1
            else:
                batch_stats["errors"] += 1

        # Update global stats
        self.stats["nodes_scanned"] += batch_stats["nodes_processed"]
        self.stats["tools_discovered"] += batch_stats["tools_found"]
        self.stats["tools_converted"] += batch_stats["tools_registered"]

<<<<<<< HEAD
        logger.info(f"Discovery complete: {batch_stats['tools_registered']} tools registered from {batch_stats['nodes_processed']} nodes")
=======
        logger.info(f" Discovery complete: {batch_stats['tools_registered']} tools registered from {batch_stats['nodes_processed']} nodes")
>>>>>>> serialization_fixes

        return {
            "batch_results": batch_stats,
            "global_stats": self.stats.copy(),
            "registered_tools": list(self.registered_tools.keys())
        }

    def _process_nodes_sequential(self, node_instances: List[Any]) -> List[Dict[str, Any]]:
        """Process nodes sequentially for smaller batches."""
        results = []

        for node in node_instances:
            try:
                result = self._process_single_node(node)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process node {type(node).__name__}: {e}")
                results.append({
                    "node_class": type(node).__name__,
                    "is_compatible": False,
                    "tool_registered": False,
                    "error": str(e)
                })

        return results

    def _process_nodes_parallel(self, node_instances: List[Any]) -> List[Dict[str, Any]]:
        """Process nodes in parallel for larger batches."""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_node = {
                executor.submit(self._process_single_node, node): node
                for node in node_instances
            }

            # Collect results as they complete
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process node {type(node).__name__}: {e}")
                    results.append({
                        "node_class": type(node).__name__,
                        "is_compatible": False,
                        "tool_registered": False,
                        "error": str(e)
                    })

        return results

    def _process_single_node(self, node_instance) -> Dict[str, Any]:
        """Process a single node for tool compatibility and conversion."""
        node_class_name = type(node_instance).__name__

        # Check if already processed
        if node_class_name in self.compatibility_cache:
            self.stats["cache_hits"] += 1
            cached_result = self.compatibility_cache[node_class_name]

            if cached_result["is_compatible"] and cached_result["tool_name"] in self.registered_tools:
                return {
                    **cached_result,
                    "tool_registered": True,
                    "cached": True
                }

        # Detect compatibility
        compatibility = self.detector.detect_tool_capability(node_instance)

        result = {
            "node_class": node_class_name,
            "is_compatible": compatibility.is_compatible,
            "detection_strategy": compatibility.detection_strategy,
            "confidence": compatibility.confidence,
            "tool_registered": False,
            "tool_name": None,
            "tool": None,
            "error": compatibility.error_message,
            "cached": False
        }

        if compatibility.is_compatible:
            # Attempt conversion
            tool = self.converter.convert_to_tool(node_instance)

            if tool:
                result["tool_registered"] = True
                result["tool_name"] = tool.name
                result["tool"] = tool
                result["error"] = None
            else:
                result["error"] = "Tool conversion failed"
                self.stats["conversion_failures"] += 1

        # Cache result
        self.compatibility_cache[node_class_name] = result

        return result

    def get_registered_tools(self) -> Dict[str, Any]:
        """
        Get all currently registered tools.

        Returns:
            Dictionary mapping tool names to tool instances
        """
        return self.registered_tools.copy()

    def get_tool_by_name(self, tool_name: str) -> Optional[Any]:
        """
        Retrieve a specific tool by name.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            Tool instance if found, None otherwise
        """
        return self.registered_tools.get(tool_name)

    def unregister_tool(self, tool_name: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            tool_name: Name of the tool to remove

        Returns:
            True if tool was removed, False if not found
        """
        if tool_name in self.registered_tools:
            del self.registered_tools[tool_name]
<<<<<<< HEAD
            logger.info(f"Unregistered tool: {tool_name}")
=======
            logger.info(f" Unregistered tool: {tool_name}")
>>>>>>> serialization_fixes
            return True

        return False

    def clear_registry(self):
        """Clear all registered tools and reset statistics."""
        self.registered_tools.clear()
        self.compatibility_cache.clear()
        self.stats = {
            "nodes_scanned": 0,
            "tools_discovered": 0,
            "tools_converted": 0,
            "conversion_failures": 0,
            "cache_hits": 0
        }
<<<<<<< HEAD
        logger.info("Tool registry cleared")
=======
        logger.info(" Tool registry cleared")
>>>>>>> serialization_fixes

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about tool discovery and conversion.

        Returns:
            Dictionary with detailed statistics
        """
        stats = self.stats.copy()
        stats["registered_tools_count"] = len(self.registered_tools)
        stats["cached_nodes_count"] = len(self.compatibility_cache)
        stats["conversion_success_rate"] = (
            stats["tools_converted"] / stats["tools_discovered"] * 100
            if stats["tools_discovered"] > 0 else 0
        )

        return stats

    def scan_workflow_nodes(self, workflow_nodes: List[Any]) -> Dict[str, Any]:
        """
        Specialized method for scanning workflow nodes.

        This method is optimized for workflow environments where nodes
        may have interdependencies and specific execution contexts.

        Args:
            workflow_nodes: List of workflow node instances

        Returns:
            Discovery results with workflow-specific analysis
        """
<<<<<<< HEAD
        logger.info(f"Scanning workflow with {len(workflow_nodes)} nodes")
=======
        logger.info(f" Scanning workflow with {len(workflow_nodes)} nodes")
>>>>>>> serialization_fixes

        # Basic discovery
        results = self.discover_and_register_tools(workflow_nodes)

        # Add workflow-specific analysis
        workflow_analysis = {
            "total_nodes": len(workflow_nodes),
            "tool_capable_nodes": results["batch_results"]["tools_found"],
            "tool_capable_percentage": (
                results["batch_results"]["tools_found"] / len(workflow_nodes) * 100
                if workflow_nodes else 0
            ),
            "most_common_detection_strategy": self._get_most_common_strategy(),
            "high_confidence_tools": self._count_high_confidence_tools()
        }

        results["workflow_analysis"] = workflow_analysis

        return results

    def _get_most_common_strategy(self) -> str:
        """Get the most commonly used detection strategy."""
        strategies = {}

        for result in self.compatibility_cache.values():
            strategy = result.get("detection_strategy", "unknown")
            strategies[strategy] = strategies.get(strategy, 0) + 1

        if not strategies:
            return "none"

        return max(strategies, key=strategies.get)

    def _count_high_confidence_tools(self) -> int:
        """Count tools with high confidence scores (>0.8)."""
        count = 0

        for result in self.compatibility_cache.values():
            if result.get("is_compatible", False) and result.get("confidence", 0) > 0.8:
                count += 1

        return count

    def export_tool_registry(self) -> Dict[str, Any]:
        """
        Export the current tool registry for persistence or analysis.

        Returns:
            Dictionary containing all registered tools and metadata
        """
        export_data = {
            "export_timestamp": "2024-01-01T00:00:00Z",  # Would use datetime.now() in real implementation
            "registered_tools": {},
            "statistics": self.get_statistics(),
            "compatibility_cache": self.compatibility_cache
        }

        for tool_name, tool in self.registered_tools.items():
            export_data["registered_tools"][tool_name] = {
                "name": tool.name,
                "description": tool.description,
                "type": type(tool).__name__
            }

        return export_data