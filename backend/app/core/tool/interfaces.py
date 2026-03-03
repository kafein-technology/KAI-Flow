"""
KAI-Flow Auto-Discovery Tool Integration - Core Interfaces
==========================================================

This module defines the core interfaces and data models for the automatic
tool integration system. It provides abstract contracts that enable generic,
type-safe tool conversion without hardcoded node-specific logic.

Key Components:
- IAgentTool: Optional interface for nodes that want custom tool conversion
- NodeToolInfo: Data model containing tool conversion metadata
- ToolCompatibilityInfo: Analysis result for tool compatibility detection

Authors: KAI-Flow Tool Integration Team
Version: 1.0.0
License: Proprietary
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
from langchain_core.tools import BaseTool


class IAgentTool(ABC):
    """
    Optional interface for nodes that provide custom agent tool conversion.
    
    Nodes implementing this interface get priority in tool conversion,
    allowing for optimized, node-specific tool creation logic.
    """
    
    @abstractmethod
    def to_agent_tool(self) -> BaseTool:
        """
        Convert this node instance to a BaseTool for agent use.
        
        Returns:
            BaseTool: Ready-to-use tool for ReactAgent integration
        """
        pass
    
    @abstractmethod
    def get_tool_name(self) -> str:
        """
        Get the preferred tool name for agent integration.
        
        Returns:
            str: Tool name (e.g., "knowledge_search", "api_client")
        """
        pass
    
    @abstractmethod
    def get_tool_description(self) -> str:
        """
        Get the tool description for agent planning.
        
        Returns:
            str: Detailed description for agent decision making
        """
        pass


@dataclass
class NodeToolInfo:
    """
    Comprehensive tool conversion metadata for a node.
    
    Contains all information needed to convert a node instance
    to an agent tool, including conversion strategy and parameters.
    """
    
    node_class: type
    tool_name: str
    tool_description: str
    conversion_strategy: str  # "interface", "output_analysis", "execution_analysis"
    output_handle: Optional[str] = None
    output_type: Optional[str] = None
    tool_category: str = "general"
    is_tool_compatible: bool = True
    
    
@dataclass  
class ToolCompatibilityInfo:
    """
    Result of tool compatibility analysis for a node.
    
    Contains detection strategy, confidence level, and conversion parameters
    for automatic tool generation.
    """
    
    is_compatible: bool
    detection_strategy: str
    confidence: float
    tool_metadata: Dict[str, Any]
    converter_function: Optional[Callable] = None
    error_message: Optional[str] = None