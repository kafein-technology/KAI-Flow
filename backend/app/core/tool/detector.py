"""
KAI-Fusion Auto-Discovery Tool Detector - Intelligent Node Analysis
================================================================

This module provides sophisticated automatic detection of tool-capable nodes
through reflection-based analysis. It examines node metadata, output types,
and execution results to determine tool compatibility without manual configuration.

Key Features:
- Reflection-based tool capability detection
- Output type analysis for automatic classification
- Execution result inspection for runtime compatibility
- Confidence scoring for tool conversion quality
- Zero-configuration tool discovery

Authors: KAI-Fusion Tool Integration Team
Version: 1.0.0
License: Proprietary
"""

import logging
from typing import Optional, Dict, Any, Type
from .interfaces import IAgentTool, NodeToolInfo, ToolCompatibilityInfo

logger = logging.getLogger(__name__)


class AutoToolDetector:
    """
    Intelligent tool capability detector using reflection and analysis.
    
    This detector examines nodes through multiple strategies to determine
    if they can be converted to agent tools automatically.
    """
    
    # Output types that can be converted to agent tools
    TOOL_COMPATIBLE_OUTPUTS = {
        'BaseRetriever': 'retriever',
        'VectorStoreRetriever': 'retriever',
        'BaseTool': 'direct_tool',
        'tool': 'direct_tool',
        'TavilySearch': 'search_api',
        'TavilySearchResults': 'search_api',
        'dict': 'api_response',
        'HttpResponse': 'http_api',
        'str': 'text_processor',
        'list': 'list_processor'
    }
    
    # Node categories that are typically tool-compatible
    TOOL_COMPATIBLE_CATEGORIES = {
        'Tool', 'Search', 'API', 'Retriever', 'External'
    }
    
    def __init__(self):
        self.detection_cache = {}
    
    def detect_tool_capability(self, node_instance) -> ToolCompatibilityInfo:
        """
        Primary detection method - analyzes node for tool compatibility.
        
        Uses multiple detection strategies:
        1. IAgentTool interface check (highest confidence)
        2. Metadata output type analysis (high confidence)  
        3. Category-based heuristics (medium confidence)
        4. Execution result analysis (lower confidence)
        
        Args:
            node_instance: Node instance to analyze
            
        Returns:
            ToolCompatibilityInfo: Comprehensive compatibility analysis
        """
        node_class_name = type(node_instance).__name__
        
        # Check cache first
        if node_class_name in self.detection_cache:
            return self.detection_cache[node_class_name]
        
        logger.debug(f" Analyzing tool compatibility for {node_class_name}")
        
        # Strategy 1: Check IAgentTool interface implementation
        if isinstance(node_instance, IAgentTool):
            result = ToolCompatibilityInfo(
                is_compatible=True,
                detection_strategy="interface",
                confidence=1.0,
                tool_metadata={
                    "name": node_instance.get_tool_name(),
                    "description": node_instance.get_tool_description(),
                    "category": "custom"
                },
                converter_function=lambda n: n.to_agent_tool()
            )
            self.detection_cache[node_class_name] = result
            return result
        
        # Strategy 2: Metadata output analysis
        metadata_result = self._analyze_metadata_outputs(node_instance)
        if metadata_result.is_compatible:
            self.detection_cache[node_class_name] = metadata_result
            return metadata_result
        
        # Strategy 3: Category-based heuristics
        category_result = self._analyze_node_category(node_instance)
        if category_result.is_compatible:
            self.detection_cache[node_class_name] = category_result
            return category_result
        
        # Strategy 4: Execution result analysis (lowest confidence)
        execution_result = self._analyze_execution_result(node_instance)
        if execution_result.is_compatible:
            self.detection_cache[node_class_name] = execution_result
            return execution_result
        
        # Not compatible
        result = ToolCompatibilityInfo(
            is_compatible=False,
            detection_strategy="none",
            confidence=0.0,
            tool_metadata={},
            error_message=f"No tool conversion strategy found for {node_class_name}"
        )
        self.detection_cache[node_class_name] = result
        return result
    
    def _analyze_metadata_outputs(self, node_instance) -> ToolCompatibilityInfo:
        """Analyze node metadata outputs for tool compatibility."""
        try:
            metadata = getattr(node_instance, 'metadata', None)
            if not metadata or not metadata.outputs:
                return ToolCompatibilityInfo(
                    is_compatible=False,
                    detection_strategy="metadata",
                    confidence=0.0,
                    tool_metadata={},
                    error_message="No metadata or outputs found"
                )
            
            # Check each output for tool compatibility
            for output in metadata.outputs:
                if output.type in self.TOOL_COMPATIBLE_OUTPUTS:
                    tool_category = self.TOOL_COMPATIBLE_OUTPUTS[output.type]
                    
                    return ToolCompatibilityInfo(
                        is_compatible=True,
                        detection_strategy="metadata_output",
                        confidence=0.9,
                        tool_metadata={
                            "name": self._generate_tool_name(metadata),
                            "description": self._generate_tool_description(metadata),
                            "category": tool_category,
                            "output_handle": output.name,
                            "output_type": output.type
                        }
                    )
            
            return ToolCompatibilityInfo(
                is_compatible=False,
                detection_strategy="metadata",
                confidence=0.0,
                tool_metadata={},
                error_message=f"No tool-compatible output types found: {[o.type for o in metadata.outputs]}"
            )
            
        except Exception as e:
            return ToolCompatibilityInfo(
                is_compatible=False,
                detection_strategy="metadata",
                confidence=0.0,
                tool_metadata={},
                error_message=f"Metadata analysis failed: {e}"
            )
    
    def _analyze_node_category(self, node_instance) -> ToolCompatibilityInfo:
        """Analyze node category for tool compatibility hints."""
        try:
            metadata = getattr(node_instance, 'metadata', None)
            if not metadata:
                return ToolCompatibilityInfo(is_compatible=False, detection_strategy="category", confidence=0.0, tool_metadata={})
            
            category = getattr(metadata, 'category', '')
            
            if category in self.TOOL_COMPATIBLE_CATEGORIES:
                return ToolCompatibilityInfo(
                    is_compatible=True,
                    detection_strategy="category_heuristic",
                    confidence=0.6,
                    tool_metadata={
                        "name": self._generate_tool_name(metadata),
                        "description": self._generate_tool_description(metadata),
                        "category": category.lower()
                    }
                )
            
            return ToolCompatibilityInfo(
                is_compatible=False,
                detection_strategy="category",
                confidence=0.0,
                tool_metadata={},
                error_message=f"Category '{category}' not in tool-compatible categories"
            )
            
        except Exception as e:
            return ToolCompatibilityInfo(
                is_compatible=False,
                detection_strategy="category",
                confidence=0.0,
                tool_metadata={},
                error_message=f"Category analysis failed: {e}"
            )
    
    def _analyze_execution_result(self, node_instance) -> ToolCompatibilityInfo:
        """Analyze execution result for runtime tool compatibility."""
        try:
            # Attempt safe execution
            result = node_instance.execute()
            result_type = type(result).__name__
            
            if result_type in self.TOOL_COMPATIBLE_OUTPUTS:
                tool_category = self.TOOL_COMPATIBLE_OUTPUTS[result_type]
                
                metadata = getattr(node_instance, 'metadata', None)
                
                return ToolCompatibilityInfo(
                    is_compatible=True,
                    detection_strategy="execution_result",
                    confidence=0.7,
                    tool_metadata={
                        "name": self._generate_tool_name(metadata) if metadata else f"tool_{type(node_instance).__name__.lower()}",
                        "description": self._generate_tool_description(metadata) if metadata else f"Tool created from {type(node_instance).__name__}",
                        "category": tool_category,
                        "result_type": result_type
                    }
                )
            
            return ToolCompatibilityInfo(
                is_compatible=False,
                detection_strategy="execution",
                confidence=0.0,
                tool_metadata={},
                error_message=f"Execution result type '{result_type}' not tool-compatible"
            )
            
        except Exception as e:
            return ToolCompatibilityInfo(
                is_compatible=False,
                detection_strategy="execution",
                confidence=0.0,
                tool_metadata={},
                error_message=f"Execution analysis failed: {e}"
            )
    
    def _generate_tool_name(self, metadata) -> str:
        """Generate appropriate tool name from node metadata."""
        if not metadata:
            return "auto_tool"
        
        name = getattr(metadata, 'name', '')
        category = getattr(metadata, 'category', '')
        
        # Generate meaningful tool name based on node type
        if 'retriever' in name.lower() or 'search' in name.lower():
            return "knowledge_search"
        elif 'http' in name.lower() or 'api' in name.lower():
            return "api_client"
        elif 'tavily' in name.lower() or 'web' in name.lower():
            return "web_search"
        elif category:
            return f"{category.lower()}_tool"
        else:
            return f"{name.lower()}_tool" if name else "auto_tool"
    
    def _generate_tool_description(self, metadata) -> str:
        """Generate appropriate tool description from node metadata."""
        if not metadata:
            return "Automatically generated tool from node"
        
        description = getattr(metadata, 'description', '')
        name = getattr(metadata, 'name', '')
        category = getattr(metadata, 'category', '')
        
        if description:
            # Use existing description with tool context
            return f"Tool that {description.lower()}"
        elif name and category:
            return f"{category} tool created from {name} node"
        elif name:
            return f"Tool created from {name} node"
        else:
            return "Automatically generated tool from node"