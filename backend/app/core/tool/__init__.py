"""
KAI-Flow Auto-Discovery Tool Integration System
================================================

This package provides automatic discovery and integration of tool-capable nodes
within the KAI-Flow workflow system. It enables seamless conversion of
workflow nodes into agent tools without manual configuration.

Main Components:
- AutoToolDetector: Intelligent node analysis and compatibility detection
- AutoToolConverter: Automatic conversion of compatible nodes to tools
- AutoToolManager: Central orchestration and tool registry management
- IAgentTool: Interface for explicit tool-capable node implementations

Quick Start:
    from backend.app.core.tool import AutoToolManager

    manager = AutoToolManager()
    results = manager.discover_and_register_tools(node_instances)

    # Get registered tools
    tools = manager.get_registered_tools()

Features:
- Zero-configuration tool discovery
- Multiple detection strategies (interface, metadata, execution)
- Parallel processing for large node sets
- Comprehensive compatibility analysis
- Tool registry with caching and statistics

Authors: KAI-Flow Tool Integration Team
Version: 1.0.0
License: Proprietary
"""

from .interfaces import IAgentTool, NodeToolInfo, ToolCompatibilityInfo
from .detector import AutoToolDetector
from .converter import AutoToolConverter
from .manager import AutoToolManager

__version__ = "1.0.0"
__author__ = "KAI-Fusion Tool Integration Team"
__license__ = "Proprietary"

__all__ = [
    # Core classes
    "AutoToolDetector",
    "AutoToolConverter",
    "AutoToolManager",

    # Interfaces
    "IAgentTool",
    "NodeToolInfo",
    "ToolCompatibilityInfo",

    # Version info
    "__version__",
    "__author__",
    "__license__"
]


def create_tool_manager(max_workers: int = 4) -> AutoToolManager:
    """
    Factory function to create a configured AutoToolManager instance.

    Args:
        max_workers: Maximum number of worker threads for parallel processing

    Returns:
        Configured AutoToolManager instance
    """
    return AutoToolManager(max_workers=max_workers)


def discover_tools_from_nodes(node_instances: list, parallel: bool = True) -> dict:
    """
    Convenience function for quick tool discovery from node instances.

    Args:
        node_instances: List of node instances to analyze
        parallel: Whether to use parallel processing for large batches

    Returns:
        Dictionary with discovery results
    """
    manager = AutoToolManager()

    if parallel and len(node_instances) > 10:
        return manager.discover_and_register_tools(node_instances)
    else:
        # Force sequential processing
        results = []
        for node in node_instances:
            try:
                compatibility = manager.detector.detect_tool_capability(node)
                tool = manager.converter.convert_to_tool(node) if compatibility.is_compatible else None

                result = {
                    "node_class": type(node).__name__,
                    "is_compatible": compatibility.is_compatible,
                    "detection_strategy": compatibility.detection_strategy,
                    "confidence": compatibility.confidence,
                    "tool_registered": tool is not None,
                    "tool_name": tool.name if tool else None,
                    "tool": tool
                }
                results.append(result)

                if tool:
                    manager.registered_tools[tool.name] = tool
            except Exception as e:
                results.append({
                    "node_class": type(node).__name__,
                    "is_compatible": False,
                    "tool_registered": False,
                    "error": str(e)
                })

        return {
            "batch_results": {
                "nodes_processed": len(results),
                "tools_found": sum(1 for r in results if r["is_compatible"]),
                "tools_registered": sum(1 for r in results if r["tool_registered"]),
                "errors": sum(1 for r in results if not r["is_compatible"] or not r["tool_registered"])
            },
            "global_stats": manager.get_statistics(),
            "registered_tools": list(manager.registered_tools.keys())
        }


def get_tool_compatibility_report(node_instance) -> dict:
    """
    Generate a detailed compatibility report for a single node.

    Args:
        node_instance: Node instance to analyze

    Returns:
        Dictionary with detailed compatibility information
    """
    detector = AutoToolDetector()
    converter = AutoToolConverter(detector)

    compatibility = detector.detect_tool_capability(node_instance)
    conversion_report = converter.get_conversion_report(node_instance)

    return {
        "compatibility_analysis": {
            "is_compatible": compatibility.is_compatible,
            "detection_strategy": compatibility.detection_strategy,
            "confidence": compatibility.confidence,
            "tool_metadata": compatibility.tool_metadata,
            "error_message": compatibility.error_message
        },
        "conversion_analysis": conversion_report
    }


# Global instance for simple use cases
_default_manager = None

def get_default_manager() -> AutoToolManager:
    """Get or create the default tool manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = AutoToolManager()
    return _default_manager