"""
KAI-Fusion Enhanced Logging Utilities - Clean & Structured Workflow Logging
===========================================================================

This module provides enhanced logging utilities specifically designed to address
the readability issues in KAI-Fusion workflow execution logs. It implements smart
data filtering, structured progress tracking, and context-aware logging to make
logs actually useful for debugging and monitoring.

Key Features:
• Smart Data Filtering: Never logs raw embeddings, truncates long parameters
• Structured Progress Tracking: Clear workflow phases with visual indicators  
• Context-Aware Logging: Different verbosity for different components
• Error Categorization: Proper separation of critical vs recoverable errors
• Performance-Optimized: Minimal overhead with lazy evaluation

Problem Areas Addressed:
1. Raw embedding data dumps (32KB+ vectors) → Embedding summaries
2. Excessive DEBUG messages → Smart filtering by context
3. Database errors mixed with normal flow → Error categorization
4. No clear progress indication → Structured workflow phases
5. Memory addresses and IDs clutter → Clean object representations

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                Enhanced Logging Architecture                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Smart Filters] → [Context Logger] → [Progress Tracker]      │
│       ↓               ↓                    ↓                   │
│  [Data Summarizer] → [Error Categorizer] → [Format Engine]     │
│       ↓               ↓                    ↓                   │
│  [Output Formatter] → [Performance Monitor] → [Clean Logs]     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Usage:
```python
from app.core.logging_utils import WorkflowLogger, get_workflow_logger

# Get contextual logger
logger = get_workflow_logger("workflow_engine", workflow_id="wf_123")

# Log workflow phases with progress
logger.start_workflow_phase("Build", total_nodes=5)
logger.log_node_execution("node_1", "OpenAINode", {"input": "text"})
logger.end_workflow_phase("Build", success=True)

# Smart data filtering automatically applied
logger.log_embedding_operation("store", dimensions=1536, count=100)  
logger.log_database_query("SELECT", table="embeddings", duration=0.05)
```
"""

import json
import time
import logging
import hashlib
import traceback
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections import defaultdict, deque

# Import existing logging config
from .logging_config import get_logger_with_context

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Enhanced log levels for workflow components."""

    CRITICAL = "critical"  # System failures that stop workflows
    ERROR = "error"  # Node failures that can be recovered
    WARNING = "warning"  # Issues that don't block execution
    INFO = "info"  # Normal workflow progress
    DEBUG = "debug"  # Only when explicitly enabled
    TRACE = "trace"  # Ultra-verbose for debugging


class WorkflowPhase(Enum):
    """Workflow execution phases for progress tracking."""

    VALIDATE = "validate"
    BUILD = "build"
    EXECUTE = "execute"
    COMPLETE = "complete"
    ERROR = "error"


class ComponentType(Enum):
    """Component types for context-aware logging."""

    WORKFLOW_ENGINE = "workflow_engine"
    NODE_EXECUTOR = "node_executor"
    MEMORY_MANAGER = "memory_manager"
    DATABASE = "database"
    VECTOR_STORE = "vector_store"
    LLM_CLIENT = "llm_client"
    API_ENDPOINT = "api_endpoint"
    CUSTOM = "custom"


@dataclass
class DataSummary:
    """Summary of data objects to avoid logging raw content."""

    type_name: str
    size: int
    sample: Optional[str] = None
    hash_digest: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_data(cls, data: Any, max_sample_size: int = 100) -> "DataSummary":
        """Create summary from any data object."""
        if data is None:
            return cls(type_name="NoneType", size=0)
        
        type_name = type(data).__name__
        
        # Calculate size based on data type
        if isinstance(data, (str, bytes)):
            size = len(data)
            sample = str(data)[:max_sample_size] if size > max_sample_size else str(data)
        elif isinstance(data, (list, tuple)):
            size = len(data)
            sample = f"[{type_name} with {size} items]"
            if size > 0 and size <= 3:
                sample = str(data)[:max_sample_size]
        elif isinstance(data, dict):
            size = len(data)
            keys = list(data.keys())[:3]
            sample = f"Dict with keys: {keys}"
        elif hasattr(data, '__len__'):
            try:
                size = len(data)
                sample = f"[{type_name} with {size} items]"
            except:
                size = 1  # Fallback
                sample = f"[{type_name} object]"
        else:
            size = 1
            sample = f"[{type_name} object]"
        
        # Create hash for large objects
        hash_digest = None
        if size > 1000:  # Only hash large objects
            try:
                data_str = str(data)[:10000]  # First 10KB for hashing
                hash_digest = hashlib.md5(data_str.encode()).hexdigest()[:8]
            except:
                pass
        
        return cls(
            type_name=type_name,
            size=size, 
            sample=sample,
            hash_digest=hash_digest
        )
    
    def __str__(self) -> str:
        """String representation for logging."""
        if self.size == 0:
            return "None"
        elif self.size == 1:
            return f"{self.type_name}"
        elif self.hash_digest:
            return f"{self.type_name}(size={self.size}, hash={self.hash_digest})"
        else:
            return f"{self.type_name}(size={self.size}): {self.sample}"


@dataclass
class WorkflowProgress:
    """Track workflow execution progress."""
    workflow_id: str
    phase: WorkflowPhase
    current_step: int = 0
    total_steps: int = 0
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property 
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return min(100.0, (self.current_step / self.total_steps) * 100.0)
    
    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds."""
        return time.time() - self.start_time
    
    def format_progress_bar(self, width: int = 30) -> str:
        """Format progress bar for logging."""
        if self.total_steps == 0:
            return f"[{'=' * width}] ∞"
        
        filled = int((self.progress_percent / 100.0) * width)
        bar = '=' * filled + '-' * (width - filled)
        return f"[{bar}] {self.progress_percent:.1f}%"


class SmartDataFilter:
    """Smart filtering for common problematic data patterns."""
    
    def __init__(self):
        self.embedding_keywords = ['embedding', 'vector', 'embeddings']
        self.truncate_threshold = 500  # Characters
        self.max_list_items = 5
        self.max_dict_keys = 10
    
    def should_filter_key(self, key: str) -> bool:
        """Check if a key contains data that should be filtered."""
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in self.embedding_keywords)
    
    def filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter dictionary with smart truncation."""
        if not isinstance(data, dict):
            return {"filtered": DataSummary.from_data(data)}
        
        filtered = {}
        truncated_keys = []
        
        for key, value in data.items():
            if self.should_filter_key(key):
                # Special handling for embeddings/vectors
                if isinstance(value, list) and len(value) > 10:
                    # Likely embedding vector
                    filtered[key] = f"<embedding vector: {len(value)} dimensions>"
                else:
                    filtered[key] = str(DataSummary.from_data(value))
            elif isinstance(value, str) and len(value) > self.truncate_threshold:
                # Truncate long strings
                filtered[key] = f"{value[:100]}...({len(value)} chars total)"
                truncated_keys.append(key)
            elif isinstance(value, list) and len(value) > self.max_list_items:
                # Truncate long lists
                filtered[key] = {
                    "items": value[:self.max_list_items],
                    "total_count": len(value),
                    "truncated": True
                }
                truncated_keys.append(key)
            elif isinstance(value, dict) and len(value) > self.max_dict_keys:
                # Truncate large dicts
                truncated_dict = dict(list(value.items())[:self.max_dict_keys])
                truncated_dict["_truncated"] = f"...and {len(value) - self.max_dict_keys} more keys"
                filtered[key] = truncated_dict
                truncated_keys.append(key)
            else:
                filtered[key] = value
        
        if truncated_keys:
            filtered["_kai_fusion_truncated_keys"] = truncated_keys
        
        return filtered
    
    def summarize_embedding_operation(self, operation: str, **kwargs) -> str:
        """Create clean summary for embedding operations."""
        parts = [f"Embedding {operation}"]
        
        if 'dimensions' in kwargs:
            parts.append(f"{kwargs['dimensions']} dims")
        if 'count' in kwargs:
            parts.append(f"{kwargs['count']} vectors")
        if 'duration' in kwargs:
            parts.append(f"{kwargs['duration']:.3f}s")
        if 'size_mb' in kwargs:
            parts.append(f"{kwargs['size_mb']:.1f}MB")
        
        return " | ".join(parts)
    
    def summarize_database_query(self, operation: str, table: str, **kwargs) -> str:
        """Create clean summary for database queries."""
        parts = [f"DB {operation}", f"table:{table}"]
        
        if 'rows' in kwargs:
            parts.append(f"{kwargs['rows']} rows")
        if 'duration' in kwargs:
            parts.append(f"{kwargs['duration']:.3f}s")
        if "conditions" in kwargs:
            parts.append(f"conditions:{len(kwargs['conditions'])}")
        
        return " | ".join(parts)


class WorkflowLogger:
    """Enhanced logger with workflow-specific functionality."""
    
    def __init__(
        self, 
        component: ComponentType,
        workflow_id: Optional[str] = None,
        session_id: Optional[str] = None,
        base_logger: Optional[logging.Logger] = None
    ):
        self.component = component
        self.workflow_id = workflow_id
        self.session_id = session_id
        
        # Create contextual logger
        context = {}
        if workflow_id:
            context['workflow_id'] = workflow_id
        if session_id:
            context['session_id'] = session_id
        context['component'] = component.value
        
        self.logger = base_logger or get_logger_with_context(
            f"kai_fusion.{component.value}", **context
        )
        
        self.data_filter = SmartDataFilter()
        self.progress_tracker: Optional[WorkflowProgress] = None
        
        # Performance tracking
        self.operation_timings: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
    def set_progress_tracker(self, tracker: WorkflowProgress):
        """Set progress tracker for this logger."""
        self.progress_tracker = tracker
    
    def log_with_context(self, level: LogLevel, message: str, **extra):
        """Log with enhanced context and filtering."""
        # Apply smart filtering to extra data
        filtered_extra = self.data_filter.filter_dict(extra)
        
        # Add component context
        filtered_extra.update({
            'component': self.component.value,
            'timestamp': datetime.utcnow().isoformat(),
        })
        
        if self.workflow_id:
            filtered_extra['workflow_id'] = self.workflow_id
        if self.session_id:
            filtered_extra['session_id'] = self.session_id
        
        # Add progress if available
        if self.progress_tracker:
            filtered_extra.update({
                'workflow_phase': self.progress_tracker.phase.value,
                'progress_percent': self.progress_tracker.progress_percent,
                'elapsed_time': self.progress_tracker.elapsed_time
            })
        
        # Log with appropriate level
        log_method = getattr(self.logger, level.value)
        log_method(message, extra=filtered_extra)

    def start_workflow_phase(
        self, phase: WorkflowPhase, total_steps: int = 0, **details
    ):
        """Start a new workflow phase with progress tracking."""
        self.progress_tracker = WorkflowProgress(
            workflow_id=self.workflow_id or "unknown",
            phase=phase,
            total_steps=total_steps,
            details=details,
        )

        phase_symbols = {
            WorkflowPhase.VALIDATE: "[VALIDATE]",
            WorkflowPhase.BUILD: "[BUILD]", 
            WorkflowPhase.EXECUTE: "[EXECUTE]",
            WorkflowPhase.COMPLETE: "[COMPLETE]",
            WorkflowPhase.ERROR: "[ERROR]"
        }
        
        symbol = phase_symbols.get(phase, "⚙️")
        message = f"{symbol} WORKFLOW {phase.value.upper()} STARTED"
        
        if total_steps > 0:
            message += f" ({total_steps} steps)"
        
        self.log_with_context(LogLevel.INFO, message, **details)
        logger.info("=" * 60)
        logger.info(message)
        if details:
            for key, value in details.items():
                logger.info(f"   {key}: {value}")
        logger.info("=" * 60)

    def end_workflow_phase(self, phase: WorkflowPhase, success: bool = True, **details):
        """End workflow phase with summary."""
        if not self.progress_tracker:
            self.progress_tracker = WorkflowProgress(
                workflow_id=self.workflow_id or "unknown", phase=phase
            )
        
        status_symbol = "✅" if success else "❌"
        status_text = "COMPLETED" if success else "FAILED"
        elapsed = self.progress_tracker.elapsed_time
        
        message = f"{status_symbol} WORKFLOW {phase.value.upper()} {status_text} ({elapsed:.2f}s)"
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        self.log_with_context(
            level, message, success=success, elapsed_time=elapsed, **details
        )

        logger.info(
            f"{status_symbol} {phase.value.upper()} {status_text} in {elapsed:.2f}s"
        )
        if details:
            for key, value in details.items():
                logger.info(f"   {key}: {value}")
        logger.info("=" * 60)

    def log_node_execution(
        self, node_id: str, node_type: str, inputs: Dict[str, Any], **extra
    ):
        """Log node execution with smart filtering."""
        # Filter inputs to avoid embedding dumps
        filtered_inputs = self.data_filter.filter_dict(inputs)

        # Create clean input summary
        input_summary = []
        for key, value in filtered_inputs.items():
            if key.startswith("_kai_fusion"):
                continue
            if isinstance(value, str) and "embedding vector" in value:
                input_summary.append(f"{key}=<vector>")
            elif isinstance(value, dict) and "total_count" in value:
                input_summary.append(f"{key}=[{value['total_count']} items]")
            else:
                input_summary.append(f"{key}={type(value).__name__}")
        
        message = f"🎯 Node: {node_id} ({node_type}) | Inputs: {', '.join(input_summary)}"
        
        self.log_with_context(
            LogLevel.INFO,
            message,
            node_id=node_id,
            node_type=node_type,
            input_keys=list(inputs.keys()),
            **extra,
        )
    
    def log_embedding_operation(self, operation: str, **kwargs):
        """Log embedding operations with clean summaries."""
        summary = self.data_filter.summarize_embedding_operation(operation, **kwargs)
        message = f"🧠 {summary}"
        
        self.log_with_context(LogLevel.INFO, message, operation_type="embedding", **kwargs)
    
    def log_database_query(self, operation: str, table: str, **kwargs):
        """Log database queries with clean summaries.""" 
        summary = self.data_filter.summarize_database_query(operation, table, **kwargs)
        message = f"💾 {summary}"
        
        self.log_with_context(LogLevel.INFO, message, operation_type="database", **kwargs)
    
    def log_database_error(self, error: Exception, query_type: str = "unknown", **context):
        """Log database errors with proper categorization."""
        error_type = type(error).__name__
        
        # Categorize database errors
        if "UndefinedColumn" in error_type:
            level = LogLevel.WARNING  # Schema issue, recoverable
            category = "schema_error"
        elif "connection" in str(error).lower():
            level = LogLevel.ERROR  # Connection issue, serious
            category = "connection_error"
        else:
            level = LogLevel.ERROR  # Generic database error
            category = "database_error"
        
        message = f"Database Error ({category}): {error_type}"
        
        self.error_counts[category] += 1
        
        self.log_with_context(
            level,
            message,
            error_type=error_type,
            error_category=category,
            query_type=query_type,
            error_message=str(error)[:500],  # Truncate long error messages
            error_count=self.error_counts[category],
            **context,
        )
    
    def log_performance_metric(self, operation: str, duration: float, **metrics):
        """Log performance metrics with trend analysis."""
        self.operation_timings[operation].append(duration)
        
        # Calculate trend
        recent_times = self.operation_timings[operation][-10:]  # Last 10 operations
        avg_time = sum(recent_times) / len(recent_times)
        
        # Performance status
        if duration > avg_time * 2:
            status = "SLOW"
            level = LogLevel.WARNING
        elif duration > avg_time * 1.5:
            status = "DEGRADED"
            level = LogLevel.WARNING
        else:
            status = "NORMAL"
            level = LogLevel.DEBUG
        message = f"{status} {operation}: {duration:.3f}s (avg: {avg_time:.3f}s)"
        self.log_with_context(
            level,
            message,
            operation=operation,
            duration=duration,
            average_duration=avg_time,
            sample_size=len(recent_times),
            **metrics
        )
    def update_progress(self, completed_steps: int = 1, details: Optional[str] = None):
        """Update workflow progress."""
        if not self.progress_tracker:
            return
        self.progress_tracker.current_step += completed_steps
        self.progress_tracker.last_update = time.time()
        if details:
            self.progress_tracker.details.update({"last_action": details})
        # Log progress at intervals
        progress = self.progress_tracker.progress_percent
        if progress > 0 and (progress % 25 == 0 or progress >= 100):
            bar = self.progress_tracker.format_progress_bar()
            message = f"Progress: {bar}"
            if details:
                message += f" | {details}"
            self.log_with_context(LogLevel.INFO, message, progress_percent=progress)
    @contextmanager
    def timed_operation(self, operation_name: str):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.log_performance_metric(operation_name, duration)
    def debug(self, message: str, **extra):
        """Debug logging (only when debug enabled)."""
        self.log_with_context(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra):
        """Info logging for normal workflow progress."""
        self.log_with_context(LogLevel.INFO, message, **extra)

    def warning(self, message: str, **extra):
        """Warning logging for issues that don't block execution."""
        self.log_with_context(LogLevel.WARNING, message, **extra)

    def error(self, message: str, error: Optional[Exception] = None, **extra):
        """Error logging for recoverable failures."""
        if error:
            extra.update(
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "stack_trace": traceback.format_exc(),
                }
            )
        self.log_with_context(LogLevel.ERROR, message, **extra)
    
    def critical(self, message: str, error: Optional[Exception] = None, **extra):
        """Critical logging for system failures."""
        if error:
            extra.update({
                'error_type': type(error).__name__,
                'error_message': str(error),
                'stack_trace': traceback.format_exc()
            })
        self.log_with_context(LogLevel.CRITICAL, message, **extra)


# Global logger factory
_loggers: Dict[str, WorkflowLogger] = {}


def get_workflow_logger(
    component: Union[ComponentType, str],
    workflow_id: Optional[str] = None,
    session_id: Optional[str] = None,
    base_logger: Optional[logging.Logger] = None
) -> WorkflowLogger:
    """Get or create a workflow logger instance."""
    if isinstance(component, str):
        try:
            component = ComponentType(component)
        except ValueError:
            component = ComponentType.CUSTOM
    
    # Create cache key
    cache_key = f"{component.value}:{workflow_id or 'none'}:{session_id or 'none'}"
    
    if cache_key not in _loggers:
        _loggers[cache_key] = WorkflowLogger(
            component=component,
            workflow_id=workflow_id,
            session_id=session_id,
            base_logger=base_logger
        )
    
    return _loggers[cache_key]


def clear_logger_cache():
    """Clear logger cache (useful for testing)."""
    global _loggers
    _loggers.clear()


# Configuration utilities
class LoggingConfig:
    """Configuration for enhanced logging system."""
    
    def __init__(self):
        self.debug_components: List[ComponentType] = []
        self.trace_components: List[ComponentType] = []
        self.truncate_threshold = 500
        self.max_embedding_log_size = 100
        self.progress_update_interval = 25  # Percent
        self.performance_warning_threshold = 2.0  # 2x average
        
    def enable_debug_for_component(self, component: ComponentType):
        """Enable debug logging for specific component."""
        if component not in self.debug_components:
            self.debug_components.append(component)
    
    def enable_trace_for_component(self, component: ComponentType):
        """Enable trace logging for specific component."""
        if component not in self.trace_components:
            self.trace_components.append(component)
    
    def is_debug_enabled(self, component: ComponentType) -> bool:
        """Check if debug is enabled for component."""
        return component in self.debug_components
    
    def is_trace_enabled(self, component: ComponentType) -> bool:
        """Check if trace is enabled for component."""
        return component in self.trace_components


# Global configuration
_logging_config = LoggingConfig()


def get_logging_config() -> LoggingConfig:
    """Get global logging configuration."""
    return _logging_config


def configure_logging(
    debug_components: Optional[List[str]] = None,
    trace_components: Optional[List[str]] = None,
    **kwargs
):
    """Configure enhanced logging system."""
    config = get_logging_config()
    
    if debug_components:
        for component_name in debug_components:
            try:
                component = ComponentType(component_name)
                config.enable_debug_for_component(component)
            except ValueError:
                pass
    
    if trace_components:
        for component_name in trace_components:
            try:
                component = ComponentType(component_name)
                config.enable_trace_for_component(component)
            except ValueError:
                pass
    
    # Apply other configuration
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)