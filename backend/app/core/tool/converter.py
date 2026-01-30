"""
KAI-Fusion Auto-Discovery Tool Converter - Node to Tool Transformation
===================================================================

This module handles the automatic conversion of detected tool-capable nodes
into actual agent tools. It provides conversion strategies for different
types of nodes and ensures proper tool integration with the agent system.

Conversion Strategies:
1. Direct Tool Conversion: For nodes that already output BaseTool
2. Retriever Conversion: For search/retrieval nodes
3. API Response Conversion: For HTTP/API response nodes
4. Custom Conversion: For nodes implementing IAgentTool

Authors: KAI-Fusion Tool Integration Team
Version: 1.0.0
License: Proprietary
"""

import logging
from typing import Any, Optional, Callable, Dict
from langchain_core.tools import BaseTool
from langchain_core.retrievers import BaseRetriever

from .interfaces import NodeToolInfo, ToolCompatibilityInfo
from .detector import AutoToolDetector

logger = logging.getLogger(__name__)


class AutoToolConverter:
    """
    Intelligent tool converter that transforms detected nodes into agent tools.

    This converter uses the detection results to apply appropriate conversion
    strategies, ensuring optimal tool integration with minimal configuration.
    """

    def __init__(self, detector: AutoToolDetector = None):
        """Initialize converter with optional detector instance."""
        self.detector = detector or AutoToolDetector()
        self.conversion_cache = {}

    def convert_to_tool(self, node_instance) -> Optional[BaseTool]:
        """
        Convert a node instance to an agent tool using detected compatibility.

        Args:
            node_instance: Node instance to convert

        Returns:
            BaseTool instance if conversion successful, None otherwise
        """
        try:
            # Get compatibility analysis
            compatibility = self.detector.detect_tool_capability(node_instance)

            if not compatibility.is_compatible:
                logger.debug(f"Node {type(node_instance).__name__} not tool-compatible")
                return None

            # Check cache
            node_class_name = type(node_instance).__name__
            cache_key = f"{node_class_name}_{compatibility.detection_strategy}"

            if cache_key in self.conversion_cache:
                return self.conversion_cache[cache_key]

            # Apply conversion strategy
            tool = self._apply_conversion_strategy(node_instance, compatibility)

            if tool:
                self.conversion_cache[cache_key] = tool
                logger.info(f"Successfully converted {node_class_name} to tool: {tool.name}")

            return tool

        except Exception as e:
            logger.error(f"Tool conversion failed for {type(node_instance).__name__}: {e}")
            return None

    def _apply_conversion_strategy(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """
        Apply the appropriate conversion strategy based on detection results.

        Args:
            node_instance: Node to convert
            compatibility: Compatibility analysis results

        Returns:
            Converted tool or None
        """
        strategy = compatibility.detection_strategy

        if strategy == "interface":
            return self._convert_via_interface(node_instance)
        elif strategy == "metadata_output":
            return self._convert_via_metadata(node_instance, compatibility)
        elif strategy == "category_heuristic":
            return self._convert_via_category(node_instance, compatibility)
        elif strategy == "execution_result":
            return self._convert_via_execution(node_instance, compatibility)
        else:
            logger.warning(f"Unknown conversion strategy: {strategy}")
            return None

    def _convert_via_interface(self, node_instance) -> Optional[BaseTool]:
        """Convert node that implements IAgentTool interface."""
        try:
            if hasattr(node_instance, 'to_agent_tool'):
                return node_instance.to_agent_tool()
            else:
                logger.warning(f"Node {type(node_instance).__name__} implements IAgentTool but missing to_agent_tool method")
                return None
        except Exception as e:
            logger.error(f"Interface conversion failed: {e}")
            return None

    def _convert_via_metadata(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert node based on metadata output analysis."""
        try:
            output_type = compatibility.tool_metadata.get('output_type')
            output_handle = compatibility.tool_metadata.get('output_handle')

            if output_type == 'BaseRetriever' or output_type == 'VectorStoreRetriever':
                return self._convert_retriever_node(node_instance, compatibility)
            elif output_type == 'BaseTool':
                return self._convert_direct_tool_node(node_instance, compatibility)
            elif output_type == 'dict':
                return self._convert_api_response_node(node_instance, compatibility)
            elif output_type == 'HttpResponse':
                return self._convert_http_response_node(node_instance, compatibility)
            else:
                return self._convert_generic_output_node(node_instance, compatibility)

        except Exception as e:
            logger.error(f"Metadata conversion failed: {e}")
            return None

    def _convert_via_category(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert node based on category heuristics."""
        try:
            category = compatibility.tool_metadata.get('category', '').lower()

            if 'retriever' in category or 'search' in category:
                return self._convert_retriever_node(node_instance, compatibility)
            elif 'api' in category:
                return self._convert_api_response_node(node_instance, compatibility)
            elif 'tool' in category:
                return self._convert_direct_tool_node(node_instance, compatibility)
            else:
                return self._convert_generic_node(node_instance, compatibility)

        except Exception as e:
            logger.error(f"Category conversion failed: {e}")
            return None

    def _convert_via_execution(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert node based on execution result analysis."""
        try:
            result_type = compatibility.tool_metadata.get('result_type')

            if result_type == 'BaseRetriever':
                return self._convert_retriever_node(node_instance, compatibility)
            elif result_type == 'BaseTool':
                return self._convert_direct_tool_node(node_instance, compatibility)
            elif result_type == 'dict':
                return self._convert_api_response_node(node_instance, compatibility)
            else:
                return self._convert_generic_output_node(node_instance, compatibility)

        except Exception as e:
            logger.error(f"Execution conversion failed: {e}")
            return None

    def _convert_retriever_node(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert retriever-type nodes to tools."""
        from langchain_core.tools import tool

        @tool
        def retriever_tool(query: str) -> str:
            """Search for relevant information using the retriever."""
            try:
                # Execute node to get retriever
                result = node_instance.execute()
                if isinstance(result, BaseRetriever):
                    docs = result.get_relevant_documents(query)
                    return "\n".join([doc.page_content for doc in docs])
                else:
                    return f"Expected retriever, got {type(result)}"
            except Exception as e:
                return f"Retriever search failed: {e}"

        retriever_tool.name = compatibility.tool_metadata.get('name', 'retriever_tool')
        retriever_tool.description = compatibility.tool_metadata.get('description', 'Search tool using retriever')

        return retriever_tool

    def _convert_direct_tool_node(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert nodes that directly output BaseTool instances."""
        try:
            result = node_instance.execute()
            if isinstance(result, BaseTool):
                return result
            else:
                logger.warning(f"Expected BaseTool, got {type(result)}")
                return None
        except Exception as e:
            logger.error(f"Direct tool conversion failed: {e}")
            return None

    def _convert_api_response_node(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert API response nodes to tools."""
        from langchain_core.tools import tool

        @tool
        def api_tool(query: str) -> str:
            """Execute API call and return formatted response."""
            try:
                result = node_instance.execute()
                if isinstance(result, dict):
                    # Format dict response as string
                    return "\n".join([f"{k}: {v}" for k, v in result.items()])
                else:
                    return str(result)
            except Exception as e:
                return f"API call failed: {e}"

        api_tool.name = compatibility.tool_metadata.get('name', 'api_tool')
        api_tool.description = compatibility.tool_metadata.get('description', 'API tool for data retrieval')

        return api_tool

    def _convert_http_response_node(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert HTTP response nodes to tools."""
        from langchain_core.tools import tool

        @tool
        def http_tool(url: str) -> str:
            """Make HTTP request and return response."""
            try:
                result = node_instance.execute()
                if hasattr(result, 'text'):
                    return result.text
                elif hasattr(result, 'content'):
                    return result.content.decode('utf-8')
                else:
                    return str(result)
            except Exception as e:
                return f"HTTP request failed: {e}"

        http_tool.name = compatibility.tool_metadata.get('name', 'http_tool')
        http_tool.description = compatibility.tool_metadata.get('description', 'HTTP tool for web requests')

        return http_tool

    def _convert_generic_output_node(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Convert generic output nodes to tools."""
        from langchain_core.tools import tool

        @tool
        def generic_tool(input_text: str) -> str:
            """Process input using the node and return result."""
            try:
                result = node_instance.execute()
                return str(result)
            except Exception as e:
                return f"Processing failed: {e}"

        generic_tool.name = compatibility.tool_metadata.get('name', 'generic_tool')
        generic_tool.description = compatibility.tool_metadata.get('description', 'Generic processing tool')

        return generic_tool

    def _convert_generic_node(self, node_instance, compatibility: ToolCompatibilityInfo) -> Optional[BaseTool]:
        """Fallback conversion for generic nodes."""
        return self._convert_generic_output_node(node_instance, compatibility)

    def get_conversion_report(self, node_instance) -> Dict[str, Any]:
        """
        Generate detailed conversion report for debugging.

        Args:
            node_instance: Node to analyze

        Returns:
            Dictionary with conversion details
        """
        compatibility = self.detector.detect_tool_capability(node_instance)

        report = {
            "node_class": type(node_instance).__name__,
            "is_compatible": compatibility.is_compatible,
            "detection_strategy": compatibility.detection_strategy,
            "confidence": compatibility.confidence,
            "tool_metadata": compatibility.tool_metadata,
            "conversion_successful": False,
            "error_message": compatibility.error_message
        }

        if compatibility.is_compatible:
            tool = self.convert_to_tool(node_instance)
            report["conversion_successful"] = tool is not None
            if tool:
                report["tool_name"] = tool.name
                report["tool_description"] = tool.description

        return report