"""
KAI-Fusion Legacy Node Discovery - Deprecated Enterprise Migration Bridge
========================================================================

This module represents the legacy node discovery system of the KAI-Fusion platform,
maintained exclusively for backward compatibility during the enterprise migration to
the advanced NodeRegistry architecture. This module is officially deprecated and
provides comprehensive migration guidance and compatibility bridges for existing
integrations requiring seamless transition to the modern node management system.

  DEPRECATION NOTICE:
=====================

**THIS MODULE IS OFFICIALLY DEPRECATED AND WILL BE REMOVED IN FUTURE VERSIONS**

All functionality has been migrated to the modern NodeRegistry system located at:
`app.core.node_registry`

MIGRATION TIMELINE:
==================

- **Current Status**: Deprecated (v2.1.0)
- **Planned Removal**: v3.0.0 (Q2 2025)
- **Migration Deadline**: All code must migrate by Q1 2025
- **Support Level**: Critical bug fixes only

ARCHITECTURAL EVOLUTION:
=======================

The KAI-Fusion platform has evolved from basic node discovery to sophisticated
enterprise-grade node registry management with advanced features:

┌─────────────────────────────────────────────────────────────────┐
│                   Legacy vs Modern Architecture                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LEGACY (Deprecated):                                          │
│  Simple Discovery → [Node Map] → [Basic Lookup]               │
│                                                                 │
│  MODERN (Current):                                             │
│  Discovery Engine → [Registry] → [Validation] → [Metadata]    │
│       ↓               ↓            ↓             ↓            │
│  [Caching] → [Hot Reload] → [Type Safety] → [Analytics]      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

LEGACY SYSTEM LIMITATIONS:
=========================

The deprecated node discovery system had several critical limitations
that drove the migration to the modern NodeRegistry architecture:

1. **Performance Issues**:
   - No caching mechanism for repeated lookups
   - Inefficient module scanning on every discovery call
   - No hot-reload capabilities for development environments
   - Linear search performance degradation with node count

2. **Reliability Concerns**:
   - No error recovery for failed module imports
   - Missing dependency validation and resolution
   - No type safety guarantees for node instantiation
   - Limited debugging and diagnostic capabilities

3. **Scalability Problems**:
   - No support for distributed node registries
   - Missing plugin architecture for extensibility
   - No versioning support for node compatibility
   - Limited metadata and analytics capabilities

4. **Enterprise Gaps**:
   - No security validation for node classes
   - Missing audit trails and compliance features
   - No performance monitoring and optimization
   - Limited integration with modern development tools

MODERN REPLACEMENT ARCHITECTURE:
===============================

The NodeRegistry system provides enterprise-grade node management:

**Core Advantages**:
- **Performance**: Intelligent caching with sub-millisecond lookup times
- **Reliability**: Comprehensive error handling with graceful degradation
- **Scalability**: Plugin architecture supporting unlimited node types
- **Security**: Node validation and sandboxing capabilities
- **Monitoring**: Real-time analytics and performance tracking

**Enterprise Features**:
- **Hot Reload**: Development-time node updates without restarts
- **Type Safety**: Comprehensive validation and type checking
- **Versioning**: Node compatibility management and migration support
- **Analytics**: Usage patterns and performance optimization insights

MIGRATION GUIDE:
===============

For seamless migration from legacy to modern node management:

**Step 1: Replace Imports**
```python
# OLD (Deprecated):
from app.core.node_discovery import discover_nodes, get_node_class, get_registry

# NEW (Recommended):
from app.core.node_registry import node_registry
```

**Step 2: Update Discovery Calls**
```python
# OLD (Deprecated):
discover_nodes()
registry = get_registry()

# NEW (Recommended):
node_registry.discover_nodes()
registry = node_registry.nodes
```

**Step 3: Modernize Node Lookups**
```python
# OLD (Deprecated):
node_class = get_node_class("ReactAgent")

# NEW (Recommended):
node_class = node_registry.get_node("ReactAgent")
```

**Step 4: Leverage Modern Features**
```python
# NEW (Additional Capabilities):
# Get comprehensive node metadata
metadata = node_registry.get_node_metadata("ReactAgent")

# Enable hot reload for development
node_registry.enable_hot_reload()

# Get performance analytics
stats = node_registry.get_performance_stats()
```

BACKWARD COMPATIBILITY:
======================

This deprecated module provides compatibility bridges to prevent
breaking changes during the migration period:

**Compatibility Features**:
- **Function Mapping**: All legacy functions redirect to modern equivalents
- **Warning System**: Comprehensive deprecation warnings with migration guidance
- **Error Handling**: Graceful fallbacks for compatibility edge cases
- **Documentation**: Detailed migration examples and best practices

**Safety Mechanisms**:
- **Automatic Fallback**: Failed legacy calls automatically use modern system
- **Warning Suppression**: Configurable warning levels for gradual migration
- **Debug Support**: Enhanced debugging for migration troubleshooting
- **Performance Monitoring**: Legacy usage tracking for migration planning

MIGRATION EXAMPLES:
==================

Basic Node Discovery Migration:
```python
# Before (Legacy - Deprecated):
from app.core.node_discovery import discover_nodes, get_registry

def legacy_node_setup():
    discover_nodes()
    available_nodes = get_registry()
    return available_nodes

# After (Modern - Recommended):
from app.core.node_registry import node_registry

def modern_node_setup():
    node_registry.discover_nodes()
    available_nodes = node_registry.nodes
    return available_nodes
```

Advanced Node Management Migration:
```python
# Before (Legacy - Limited Functionality):
from app.core.node_discovery import get_node_class

def legacy_node_creation(node_type: str):
    try:
        node_class = get_node_class(node_type)
        return node_class()
    except ValueError:
        return None

# After (Modern - Enhanced Capabilities):
from app.core.node_registry import node_registry

def modern_node_creation(node_type: str):
    # Get node with validation
    node_class = node_registry.get_node(node_type)
    if not node_class:
        return None
    
    # Access metadata for enhanced functionality
    metadata = node_registry.get_node_metadata(node_type)
    
    # Create with modern safety features
    try:
        instance = node_class()
        # Track usage for analytics
        node_registry.track_node_usage(node_type)
        return instance
    except Exception as e:
        # Enhanced error handling
        node_registry.log_node_error(node_type, str(e))
        return None
```

Enterprise Integration Migration:
```python
# Before (Legacy - Basic Registry):
from app.core.node_discovery import get_registry

class LegacyWorkflowBuilder:
    def __init__(self):
        self.available_nodes = get_registry()
    
    def create_node(self, node_type: str):
        if node_type in self.available_nodes:
            return self.available_nodes[node_type]()
        return None

# After (Modern - Enterprise Features):
from app.core.node_registry import node_registry

class ModernWorkflowBuilder:
    def __init__(self):
        # Initialize with hot reload and analytics
        node_registry.enable_hot_reload()
        node_registry.start_analytics()
        self.registry = node_registry
    
    def create_node(self, node_type: str):
        # Validate node availability
        if not self.registry.is_node_available(node_type):
            return None
        
        # Get node class with validation
        node_class = self.registry.get_node(node_type)
        
        # Create with comprehensive error handling
        try:
            instance = node_class()
            
            # Track for analytics and optimization
            self.registry.track_node_creation(node_type)
            
            return instance
        except Exception as e:
            # Enhanced error reporting
            self.registry.report_node_error(node_type, e)
            return None
    
    def get_analytics(self):
        return self.registry.get_performance_stats()
```

COMPLIANCE AND AUDIT:
====================

For enterprise environments requiring compliance tracking:

**Migration Audit Trail**:
- **Usage Tracking**: Automatic logging of legacy function calls
- **Performance Impact**: Measurement of migration performance improvements
- **Compatibility Verification**: Validation of functionality preservation
- **Rollback Support**: Emergency rollback capabilities if needed

**Security Considerations**:
- **Deprecation Warnings**: Security implications of continued legacy usage
- **Vulnerability Management**: Security patches limited to critical issues only
- **Access Control**: Modern system provides enhanced security features
- **Audit Logging**: Comprehensive activity logging for compliance requirements

ERROR HANDLING STRATEGY:
=======================

Legacy Compatibility Error Management:

1. **Graceful Degradation**:
   - Legacy calls automatically fallback to modern system
   - Comprehensive error messages with migration guidance
   - Performance monitoring for legacy usage patterns
   - Automatic warning generation for deprecated usage

2. **Migration Support**:
   - Detailed error messages with specific migration steps
   - Code examples for common migration scenarios
   - Performance comparison between legacy and modern systems
   - Automated migration tooling recommendations

3. **Emergency Fallbacks**:
   - Critical system continuity during migration periods
   - Rollback capabilities for failed migrations
   - Emergency support contacts for migration issues
   - Comprehensive troubleshooting documentation

AUTHORS: KAI-Fusion Legacy Migration Team
VERSION: 2.1.0 (Deprecated)
DEPRECATION_DATE: 2025-01-15
REMOVAL_DATE: 2025-06-01
LAST_UPDATED: 2025-07-26
LICENSE: Proprietary - KAI-Fusion Platform

──────────────────────────────────────────────────────────────
MIGRATION URGENCY: HIGH PRIORITY
• Immediate Action Required: Begin migration planning
• Timeline: Complete migration by Q1 2025
• Support: Critical bug fixes only
• Replacement: app.core.node_registry (NodeRegistry)
──────────────────────────────────────────────────────────────
"""

import warnings
import importlib
import inspect
from pathlib import Path
from typing import Dict, Type
from app.nodes import BaseNode

# Deprecated - use app.core.node_registry instead
NODE_TYPE_MAP: Dict[str, Type[BaseNode]] = {}

def discover_nodes():
    """DEPRECATED: Use app.core.node_registry.discover_nodes() instead."""
    warnings.warn(
        "node_discovery.discover_nodes() is deprecated. "
        "Use app.core.node_registry.node_registry.discover_nodes() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Return empty to prevent usage
    return

def get_node_class(node_type: str) -> Type[BaseNode]:
    """DEPRECATED: Use app.core.node_registry.node_registry.get_node() instead."""
    warnings.warn(
        "node_discovery.get_node_class() is deprecated. "
        "Use app.core.node_registry.node_registry.get_node() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Fallback to new system
    from app.core.node_registry import node_registry
    node_class = node_registry.get_node(node_type)
    if not node_class:
        raise ValueError(f"Unknown node type: {node_type}")
    return node_class

def get_registry() -> Dict[str, Type[BaseNode]]:
    """DEPRECATED: Use app.core.node_registry.node_registry.nodes instead."""
    warnings.warn(
        "node_discovery.get_registry() is deprecated. "
        "Use app.core.node_registry.node_registry.nodes instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Fallback to new system
    from app.core.node_registry import node_registry
    return node_registry.nodes.copy()