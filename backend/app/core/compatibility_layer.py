"""
Phase 2: Backward Compatibility Layer
====================================

Provides seamless backward compatibility for existing hardcoded imports while
using the dynamic type detection system under the hood. This allows existing
code to continue working without modifications during the migration.

Key Features:
- Drop-in replacement for hardcoded sets in types.py
- Dynamic updates when new nodes are registered
- Performance optimization with lazy loading
- Transparent fallback to dynamic detection
- Zero breaking changes to existing code

Usage (existing code continues to work):
```python
# Old way (still works)
from app.core.graph_builder.types import PROCESSOR_NODE_TYPES
if node_type in PROCESSOR_NODE_TYPES:
    # Session management logic

# New way (behind the scenes uses dynamic detection)
# PROCESSOR_NODE_TYPES is now dynamically populated
```

AUTHORS: KAI-Fusion Workflow Orchestration Team  
VERSION: 2.1.0 - Phase 2
LAST_UPDATED: 2025-09-16
LICENSE: Proprietary - KAI-Fusion Platform
"""

from typing import Set, Dict, Any, Optional
import logging
from functools import lru_cache
from app.core.dynamic_type_detection import dynamic_type_detector

logger = logging.getLogger(__name__)

class CompatibilitySet:
    """
    Dynamic set that behaves like a regular Python set but updates automatically
    when new nodes are registered. Provides transparent compatibility with
    existing hardcoded set usage patterns.
    """
    
    def __init__(self, set_name: str, fetch_function):
        self.set_name = set_name
        self.fetch_function = fetch_function
        self._cached_set: Optional[Set[str]] = None
        self._cache_invalidated = True
        
    def _ensure_fresh_data(self):
        """Ensure we have fresh data from the dynamic detector"""
        if self._cache_invalidated or self._cached_set is None:
            try:
                self._cached_set = self.fetch_function()
                self._cache_invalidated = False
                logger.debug(f" Refreshed {self.set_name}: {len(self._cached_set)} items")
            except Exception as e:
                logger.warning(f"Failed to refresh {self.set_name}: {e}")
                # Fallback to empty set
                if self._cached_set is None:
                    self._cached_set = set()
    
    def invalidate_cache(self):
        """Invalidate cache to force refresh on next access"""
        self._cache_invalidated = True
        
    # Set interface methods
    def __contains__(self, item):
        """Support for 'in' operator"""
        self._ensure_fresh_data()
        return item in self._cached_set
    
    def __iter__(self):
        """Support for iteration"""
        self._ensure_fresh_data()
        return iter(self._cached_set)
    
    def __len__(self):
        """Support for len() function"""
        self._ensure_fresh_data()
        return len(self._cached_set)
    
    def __bool__(self):
        """Support for boolean evaluation"""
        self._ensure_fresh_data()
        return bool(self._cached_set)
    
    def __str__(self):
        """String representation"""
        self._ensure_fresh_data()
        return str(self._cached_set)
    
    def __repr__(self):
        """Detailed representation"""
        self._ensure_fresh_data()
        return f"CompatibilitySet({self.set_name}, {len(self._cached_set)} items)"
    
    # Set methods
    def copy(self):
        """Return a copy of the current set"""
        self._ensure_fresh_data()
        return self._cached_set.copy()
    
    def issubset(self, other):
        """Test whether every element is in other"""
        self._ensure_fresh_data()
        return self._cached_set.issubset(other)
    
    def issuperset(self, other):
        """Test whether every element in other is in this set"""
        self._ensure_fresh_data()
        return self._cached_set.issuperset(other)
    
    def union(self, *others):
        """Return union with other sets"""
        self._ensure_fresh_data()
        return self._cached_set.union(*others)
    
    def intersection(self, *others):
        """Return intersection with other sets"""
        self._ensure_fresh_data()
        return self._cached_set.intersection(*others)
    
    def difference(self, *others):
        """Return difference with other sets"""
        self._ensure_fresh_data()
        return self._cached_set.difference(*others)

class BackwardCompatibilityLayer:
    """
     PHASE 2: Seamless Backward Compatibility Layer
    
    Provides drop-in replacement for hardcoded node type sets while using
    dynamic detection system. Existing code continues to work unchanged
    while benefiting from dynamic node discovery.
    
    Features:
    - Transparent dynamic set updates
    - Performance optimized with smart caching
    - Full Python set interface compatibility  
    - Automatic refresh when nodes are registered
    - Zero breaking changes to existing code
    """
    
    def __init__(self, detector=None):
        self.detector = detector or dynamic_type_detector
        self._compatibility_sets: Dict[str, CompatibilitySet] = {}
        self._initialized = False
        self._setup_compatibility_sets()
        
        logger.info(" Phase 2: Backward Compatibility Layer initialized")
    
    def _setup_compatibility_sets(self):
        """Setup all compatibility sets for legacy hardcoded mappings"""
        
        # Create compatibility sets that dynamically fetch from detector
        self._compatibility_sets = {
            'PROCESSOR_NODE_TYPES': CompatibilitySet(
                'PROCESSOR_NODE_TYPES',
                self.detector.get_processor_node_types
            ),
            'MEMORY_NODE_TYPES': CompatibilitySet(
                'MEMORY_NODE_TYPES', 
                self.detector.get_memory_node_types
            ),
            'PROVIDER_NODE_TYPES': CompatibilitySet(
                'PROVIDER_NODE_TYPES',
                self.detector.get_provider_node_types
            ),
            'CONTROL_FLOW_NODE_TYPES': CompatibilitySet(
                'CONTROL_FLOW_NODE_TYPES',
                self.detector.get_control_flow_node_types
            )
        }
        
        self._initialized = True
        logger.debug(" Compatibility sets initialized")
    
    @property
    def PROCESSOR_NODE_TYPES(self) -> CompatibilitySet:
        """ COMPATIBILITY: Dynamic replacement for hardcoded PROCESSOR_NODE_TYPES"""
        return self._compatibility_sets['PROCESSOR_NODE_TYPES']
    
    @property
    def MEMORY_NODE_TYPES(self) -> CompatibilitySet:
        """ COMPATIBILITY: Dynamic replacement for hardcoded MEMORY_NODE_TYPES"""
        return self._compatibility_sets['MEMORY_NODE_TYPES']
        
    @property
    def PROVIDER_NODE_TYPES(self) -> CompatibilitySet:
        """ COMPATIBILITY: Dynamic replacement for hardcoded PROVIDER_NODE_TYPES"""
        return self._compatibility_sets['PROVIDER_NODE_TYPES']
        
    @property
    def CONTROL_FLOW_NODE_TYPES(self) -> CompatibilitySet:
        """ COMPATIBILITY: Dynamic replacement for hardcoded CONTROL_FLOW_NODE_TYPES"""
        return self._compatibility_sets['CONTROL_FLOW_NODE_TYPES']
    
    def refresh_all_sets(self):
        """Refresh all compatibility sets (useful when new nodes are registered)"""
        for compat_set in self._compatibility_sets.values():
            compat_set.invalidate_cache()
        
        logger.info(" All compatibility sets refreshed")
    
    def get_compatibility_stats(self) -> Dict[str, Any]:
        """Get statistics about compatibility layer usage"""
        stats = {
            "initialized": self._initialized,
            "total_sets": len(self._compatibility_sets),
            "set_sizes": {}
        }
        
        for name, compat_set in self._compatibility_sets.items():
            stats["set_sizes"][name] = len(compat_set)
        
        return stats
    
    def validate_compatibility(self) -> Dict[str, Any]:
        """Validate that compatibility layer is working correctly"""
        validation = {
            "status": "healthy",
            "issues": [],
            "set_validations": {}
        }
        
        for name, compat_set in self._compatibility_sets.items():
            try:
                # Test basic operations
                size = len(compat_set)
                can_iterate = bool(list(compat_set)[:1])  # Test iteration
                
                validation["set_validations"][name] = {
                    "size": size,
                    "iterable": can_iterate,
                    "status": "ok"
                }
                
                if size == 0:
                    validation["issues"].append(f"{name} is empty - may indicate detection issues")
                    
            except Exception as e:
                validation["status"] = "error"
                validation["issues"].append(f"{name} failed validation: {str(e)}")
                validation["set_validations"][name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return validation

#  Global instance for Phase 2 - provides the compatibility interface
compatibility_layer = BackwardCompatibilityLayer(dynamic_type_detector)

#  BACKWARD COMPATIBILITY EXPORTS
# These provide drop-in replacement for existing hardcoded imports
PROCESSOR_NODE_TYPES = compatibility_layer.PROCESSOR_NODE_TYPES
MEMORY_NODE_TYPES = compatibility_layer.MEMORY_NODE_TYPES  
PROVIDER_NODE_TYPES = compatibility_layer.PROVIDER_NODE_TYPES
CONTROL_FLOW_NODE_TYPES = compatibility_layer.CONTROL_FLOW_NODE_TYPES

def refresh_node_types():
    """
     UTILITY: Refresh all node types (useful after new nodes are registered)
    
    This function can be called by the node registry or other components
    when new nodes are discovered to ensure compatibility sets are updated.
    """
    compatibility_layer.refresh_all_sets()
    logger.info(" Node types refreshed via compatibility layer")

# Export convenience functions for external use
__all__ = [
    'BackwardCompatibilityLayer',
    'CompatibilitySet', 
    'compatibility_layer',
    'PROCESSOR_NODE_TYPES',
    'MEMORY_NODE_TYPES',
    'PROVIDER_NODE_TYPES', 
    'CONTROL_FLOW_NODE_TYPES',
    'refresh_node_types'
]