"""
Dynamic Type Detection Service - Phase 1 Implementation
======================================================

Enterprise Dynamic Type Detection Service that replaces hardcoded static node type mappings 
with dynamic metadata-driven type detection using the existing node registry infrastructure.

This Phase 1 implementation provides:
- Dynamic metadata extraction from node registry
- Intelligent caching with performance monitoring  
- Fallback to legacy mappings for compatibility
- Comprehensive error handling and recovery
- Real-time performance metrics and optimization

AUTHORS: KAI-Fusion Workflow Orchestration Team
VERSION: 2.1.0 - Phase 1
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Fusion Platform
"""

from typing import Dict, Set, Optional, Any, List, Union
from enum import Enum
from dataclasses import dataclass, field
from functools import lru_cache, wraps
import logging
import time
from app.nodes.base import NodeType
from app.core.node_registry import node_registry

logger = logging.getLogger(__name__)

@dataclass
class NodeTypeInfo:
    """Comprehensive node type information from dynamic metadata"""
    node_type: NodeType
    category: str
    is_control_flow: bool = False
    session_aware: bool = False
    metadata: Optional[Dict[str, Any]] = None
    detection_source: str = "dynamic"  # dynamic, legacy_fallback, error_fallback
    detection_timestamp: float = field(default_factory=time.time)

class DetectionStats:
    """Performance and usage statistics for the dynamic type detector"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.dynamic_detections = 0
        self.fallback_uses = 0
        self.errors = 0
        self.total_lookups = 0
        self.avg_lookup_time_ms = 0.0
        self.lookup_times = []
    
    def record_lookup(self, lookup_time_ms: float, source: str):
        self.total_lookups += 1
        self.lookup_times.append(lookup_time_ms)
        
        # Update rolling average (last 1000 lookups)
        if len(self.lookup_times) > 1000:
            self.lookup_times = self.lookup_times[-1000:]
        
        self.avg_lookup_time_ms = sum(self.lookup_times) / len(self.lookup_times)
        
        # Update counters based on detection source
        if source == "cache":
            self.cache_hits += 1
        elif source == "dynamic":
            self.cache_misses += 1
            self.dynamic_detections += 1
        elif source == "fallback":
            self.fallback_uses += 1
        elif source == "error":
            self.errors += 1
    
    @property
    def cache_hit_rate(self) -> float:
        total_cache_attempts = self.cache_hits + self.cache_misses
        if total_cache_attempts == 0:
            return 0.0
        return self.cache_hits / total_cache_attempts
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_lookups": self.total_lookups,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "dynamic_detections": self.dynamic_detections,
            "fallback_uses": self.fallback_uses,
            "errors": self.errors,
            "avg_lookup_time_ms": round(self.avg_lookup_time_ms, 2),
            "performance_grade": self._calculate_performance_grade()
        }
    
    def _calculate_performance_grade(self) -> str:
        """Calculate overall performance grade A-F"""
        if self.total_lookups == 0:
            return "N/A"
        
        score = 0
        
        # Cache hit rate (40% of score)
        if self.cache_hit_rate > 0.9:
            score += 40
        elif self.cache_hit_rate > 0.8:
            score += 35
        elif self.cache_hit_rate > 0.7:
            score += 30
        else:
            score += 20
        
        # Lookup speed (30% of score)
        if self.avg_lookup_time_ms < 1.0:
            score += 30
        elif self.avg_lookup_time_ms < 2.0:
            score += 25
        elif self.avg_lookup_time_ms < 5.0:
            score += 20
        else:
            score += 10
        
        # Dynamic detection rate (20% of score)
        dynamic_rate = self.dynamic_detections / self.total_lookups if self.total_lookups > 0 else 0
        if dynamic_rate > 0.8:
            score += 20
        elif dynamic_rate > 0.6:
            score += 15
        else:
            score += 10
        
        # Error rate (10% of score)
        error_rate = self.errors / self.total_lookups if self.total_lookups > 0 else 0
        if error_rate < 0.01:
            score += 10
        elif error_rate < 0.05:
            score += 5
        else:
            score += 0
        
        # Convert to letter grade
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

def performance_monitor(func):
    """Decorator to monitor performance of detection methods"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(self, *args, **kwargs)
            
            # Determine detection source
            detection_source = "dynamic"
            if hasattr(result, 'detection_source'):
                detection_source = result.detection_source

            # Record successful lookup
            lookup_time_ms = (time.time() - start_time) * 1000
            self._stats.record_lookup(lookup_time_ms, detection_source)
            
            return result
            
        except Exception as e:
            # Record error
            lookup_time_ms = (time.time() - start_time) * 1000
            self._stats.record_lookup(lookup_time_ms, "error")
            raise
    
    return wrapper

class DynamicTypeDetector:
    """
<<<<<<< HEAD
    PHASE 1: Core Dynamic Type Detection Service
=======
     PHASE 1: Core Dynamic Type Detection Service
>>>>>>> serialization_fixes
    
    Sophisticated metadata-driven node type detection system that replaces
    hardcoded static mappings with dynamic analysis of node metadata.
    
    Key Features:
    - Dynamic metadata extraction from node registry
    - Intelligent caching with performance monitoring
    - Fallback to legacy mappings for compatibility
    - Comprehensive error handling and recovery
    - Real-time performance metrics and optimization
    """
    
    def __init__(self, node_registry=None):
        self.node_registry = node_registry or globals().get('node_registry')
        self._type_cache: Dict[str, NodeTypeInfo] = {}
        self._stats = DetectionStats()
        
<<<<<<< HEAD
        # FALLBACK: Legacy compatibility mappings (transitional only)
=======
        #  FALLBACK: Legacy compatibility mappings (transitional only)
>>>>>>> serialization_fixes
        self._legacy_mappings = {
            # Processor nodes
            'ReactAgent': NodeType.PROCESSOR,
            'ToolAgentNode': NodeType.PROCESSOR, 
            'Agent': NodeType.PROCESSOR,
            
            # Memory nodes
            'BufferMemory': NodeType.MEMORY,
            'ConversationMemory': NodeType.MEMORY,
            'Memory': NodeType.MEMORY,
            
            # Provider nodes
            'Provider': NodeType.PROVIDER,
            'OpenAINode': NodeType.PROVIDER,
            'TavilySearchNode': NodeType.PROVIDER,
            'OpenAIChat': NodeType.PROVIDER,
            'OpenAIEmbeddingsProvider': NodeType.PROVIDER,
            
            # Control flow (when implemented)
            "ConditionalNode": NodeType.PROCESSOR,  # Control flow nodes are typically processors
            "LoopNode": NodeType.PROCESSOR,
            "ParallelNode": NodeType.PROCESSOR,
        }
        
        logger.info(" Dynamic Type Detector initialized - Phase 1")
    
    @performance_monitor
    def get_node_type_info(self, node_type_name: str) -> Optional[NodeTypeInfo]:
        """
         CORE METHOD: Get comprehensive node type information from metadata
        
        Returns NodeTypeInfo with complete type classification and metadata.
        Uses multi-level detection strategy: cache -> dynamic -> fallback -> error
        """
        
        # LEVEL 1: Cache lookup
        if node_type_name in self._type_cache:
            cached_info = self._type_cache[node_type_name]
            cached_info.detection_source = "cache"
            return cached_info
        
<<<<<<< HEAD
        # LEVEL 2: Dynamic detection from node registry
=======
        #  LEVEL 2: Dynamic detection from node registry
>>>>>>> serialization_fixes
        try:
            type_info = self._detect_from_metadata(node_type_name)
            if type_info:
                type_info.detection_source = "dynamic"
                # Cache the successful detection
                self._type_cache[node_type_name] = type_info
                logger.debug(f"DYNAMIC: {node_type_name} -> {type_info.node_type.value}")
                return type_info
        
        except Exception as e:
            logger.warning(f"Dynamic detection failed for {node_type_name}: {e}")
        
        #  LEVEL 3: Fallback to legacy mappings
        fallback_info = self._get_fallback_type_info(node_type_name)
        if fallback_info:
            fallback_info.detection_source = "legacy_fallback"
            self._type_cache[node_type_name] = fallback_info
            return fallback_info
        
        #  LEVEL 4: Error fallback
        logger.error(f"Could not detect type for {node_type_name} - all methods failed")
        error_info = NodeTypeInfo(
            node_type=NodeType.PROVIDER,  # Safe default
            category="Unknown",
            detection_source="error_fallback",
            metadata={"error": "Type detection failed", "node_name": node_type_name},
        )
        
        return error_info
    
    def _detect_from_metadata(self, node_type_name: str) -> Optional[NodeTypeInfo]:
        """ DYNAMIC: Core metadata-based type detection"""
        
        # Get node class from registry
        node_class = self.node_registry.get_node(node_type_name)
        if not node_class:
            logger.debug(f"Node {node_type_name} not found in registry")
            return None
        
        # Extract metadata dynamically
        try:
            node_instance = node_class()
            metadata = node_instance.metadata
            
            # Create comprehensive type info
            type_info = NodeTypeInfo(
                node_type=metadata.node_type,
                category=metadata.category or "Other", 
                is_control_flow=self._analyze_control_flow_indicators(node_type_name, metadata),
                session_aware=self._determine_session_awareness(metadata.node_type),
                metadata=metadata.model_dump()
            )
            
            logger.info(f"DYNAMIC: {node_type_name} classified as {type_info.node_type.value} "
                       f"({type_info.category}){' [CONTROL_FLOW]' if type_info.is_control_flow else ''}")
            
            return type_info
            
        except Exception as e:
            logger.error(f"Failed to extract metadata for {node_type_name}: {e}")
            return None
    
    def _analyze_control_flow_indicators(self, node_name: str, metadata) -> bool:
        """SMART: Analyze if node is a control flow node using multiple indicators"""

        control_flow_keywords = [
            'conditional', 'condition', 'if', 'branch', 'switch', 'case',
            'loop', 'while', 'for', 'repeat', 'iterate', 
            'parallel', 'fork', 'split', 'concurrent',
            'route', 'router', 'gateway', 'decision'
        ]
        
        # 1. Check node name
        node_name_lower = node_name.lower()
        if any(keyword in node_name_lower for keyword in control_flow_keywords):
            logger.debug(f"CONTROL_FLOW detected via node name: {node_name}")
            return True
        
        # 2. Check category
        category_lower = metadata.category.lower()
        control_flow_categories = ["control", "flow", "routing", "logic", "decision"]
        if any(cat in category_lower for cat in control_flow_categories):
            logger.debug(f" CONTROL_FLOW detected via category: {metadata.category}")
            return True
        
        # 3. Check tags if available
        if hasattr(metadata, 'tags') and metadata.tags:
            tags_text = ' '.join(metadata.tags).lower()
            if any(keyword in tags_text for keyword in control_flow_keywords):
                logger.debug(f"CONTROL_FLOW detected via tags: {metadata.tags}")
                return True

        # 4. Check description for control flow patterns
        if hasattr(metadata, "description") and metadata.description:
            description_lower = metadata.description.lower()
            if any(keyword in description_lower for keyword in control_flow_keywords):
                logger.debug(f" CONTROL_FLOW detected via description")
                return True
        
        return False
    
    def _determine_session_awareness(self, node_type: NodeType) -> bool:
        """Determine if node type requires session management"""
        session_aware_types = {NodeType.PROCESSOR, NodeType.MEMORY}
        return node_type in session_aware_types
    
    def _get_fallback_type_info(self, node_type_name: str) -> Optional[NodeTypeInfo]:
        """FALLBACK: Use legacy mappings when dynamic detection fails"""
        
        if node_type_name in self._legacy_mappings:
            fallback_type = self._legacy_mappings[node_type_name]

            logger.warning(
                f"FALLBACK: Using legacy mapping {node_type_name} -> {fallback_type.value}"
            )

            return NodeTypeInfo(
                node_type=fallback_type,
                category="Legacy",
                is_control_flow=False,  # Conservative assumption
                session_aware=self._determine_session_awareness(fallback_type),
                metadata={"source": "legacy_fallback", "original_name": node_type_name},
            )

        return None
<<<<<<< HEAD
    
    # PUBLIC API: Replacement methods for hardcoded sets
    
=======

    #  PUBLIC API: Replacement methods for hardcoded sets

>>>>>>> serialization_fixes
    def get_processor_node_types(self) -> Set[str]:
        """ DYNAMIC: Get all processor node types"""
        return self._get_nodes_by_type(NodeType.PROCESSOR)

    def get_memory_node_types(self) -> Set[str]:
        """ DYNAMIC: Get all memory node types"""
        return self._get_nodes_by_type(NodeType.MEMORY)

    def get_provider_node_types(self) -> Set[str]:
        """ DYNAMIC: Get all provider node types"""
        return self._get_nodes_by_type(NodeType.PROVIDER)

    def get_control_flow_node_types(self) -> Set[str]:
        """ DYNAMIC: Get all control flow node types"""
        control_flow_nodes = set()

        # Get all registered nodes and check each one
        all_nodes = self.node_registry.get_all_nodes()

        for metadata in all_nodes:
            type_info = self.get_node_type_info(metadata.name)
            if type_info and type_info.is_control_flow:
                control_flow_nodes.add(metadata.name)

        logger.info(
            f" DYNAMIC: Found {len(control_flow_nodes)} control flow nodes: {control_flow_nodes}"
        )
        return control_flow_nodes
    
    def _get_nodes_by_type(self, target_type: NodeType) -> Set[str]:
        """Get all nodes of a specific type (registry + legacy fallbacks)"""
        nodes_of_type = set()
        
        # Get all registered nodes from the registry
        all_nodes = self.node_registry.get_all_nodes()
        
        for metadata in all_nodes:
            # Use metadata.node_type directly for efficiency
            if metadata.node_type == target_type:
                nodes_of_type.add(metadata.name)
        
        # COMPATIBILITY: Also include legacy mapping nodes of this type
        registry_node_names = {n.name for n in all_nodes}
        for node_name, legacy_type in self._legacy_mappings.items():
            if legacy_type == target_type:
                # Only add if not already in registry (avoid duplicates)
                if node_name not in registry_node_names:
                    nodes_of_type.add(node_name)
                    logger.debug(f" Added legacy node {node_name} to {target_type.value} set")
        
        logger.debug(f"🔍 DYNAMIC+LEGACY: Found {len(nodes_of_type)} {target_type.value} nodes")
        return nodes_of_type
    
    # CONVENIENCE METHODS: Boolean checks
    
    def is_processor_node(self, node_type_name: str) -> bool:
        """Check if node is a processor type"""
        type_info = self.get_node_type_info(node_type_name)
        return type_info and type_info.node_type == NodeType.PROCESSOR
    
    def is_memory_node(self, node_type_name: str) -> bool:
        """Check if node is a memory type"""
        type_info = self.get_node_type_info(node_type_name)
        return type_info and type_info.node_type == NodeType.MEMORY
    
    def is_provider_node(self, node_type_name: str) -> bool:
        """Check if node is a provider type"""
        type_info = self.get_node_type_info(node_type_name)
        return type_info and type_info.node_type == NodeType.PROVIDER
    
    def is_session_aware_node(self, node_type_name: str) -> bool:
        """Check if node requires session management"""
        type_info = self.get_node_type_info(node_type_name)
        return type_info and type_info.session_aware
    
    def is_control_flow_node(self, node_type_name: str) -> bool:
        """Check if node is a control flow node"""
        type_info = self.get_node_type_info(node_type_name)
        return type_info and type_info.is_control_flow
    
    #  MANAGEMENT METHODS
    
    def clear_cache(self):
        """Clear the type detection cache"""
        self._type_cache.clear()
        logger.info("Dynamic type detection cache cleared")
    
    def refresh_node_types(self):
        """Refresh cached node types (useful after new nodes are registered)"""
        self.clear_cache()
        
        # Pre-warm cache with all registered nodes
        all_nodes = self.node_registry.get_all_nodes()
        for metadata in all_nodes:
            self.get_node_type_info(metadata.name)

        logger.info(f" Cache pre-warmed with {len(all_nodes)} node types")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance and usage statistics"""
        return {
            "service_info": {
                "phase": "Phase 1 - Core Service",
                "cache_size": len(self._type_cache),
                "registry_nodes": len(self.node_registry.get_all_nodes()),
                "legacy_mappings": len(self._legacy_mappings),
            },
            **self._stats.to_dict(),
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check of the service"""
        health = {
            "status": "healthy",
            "issues": [],
            "recommendations": []
        }
        
        # Check registry availability
        if not self.node_registry:
            health["status"] = "unhealthy"
            health["issues"].append("Node registry not available")
        
        # Check cache performance
        if self._stats.cache_hit_rate < 0.7:
            health["recommendations"].append("Consider increasing cache size or pre-warming")
        
        # Check error rate
        if self._stats.errors > 0:
            health["issues"].append(f"Detected {self._stats.errors} errors in type detection")
        
        # Check performance
        if self._stats.avg_lookup_time_ms > 5.0:
            health["recommendations"].append("Lookup performance is slow, consider optimization")
        
        return health

# Global instance for Phase 1
dynamic_type_detector = DynamicTypeDetector(node_registry)