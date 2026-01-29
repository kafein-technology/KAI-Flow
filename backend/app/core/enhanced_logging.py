"""
KAI-Fusion Enhanced Logging Configuration - Production-Ready Workflow Logging
=============================================================================

This module integrates the enhanced logging utilities into the existing KAI-Fusion
logging infrastructure, providing seamless migration from the current system while
adding advanced workflow-specific capabilities.

Key Integration Points:
• Extends existing logging_config.py without breaking changes
• Provides workflow-specific formatters and handlers  
• Integrates with tracing system for comprehensive observability
• Maintains backward compatibility with current logging patterns

Enhanced Features:
• Workflow Phase Tracking: Visual progress indicators
• Smart Data Filtering: Automatic embedding/vector summarization
• Error Categorization: Proper severity classification
• Performance Monitoring: Trend analysis and alerts
• Context-Aware Verbosity: Component-specific log levels

Architecture Integration:
┌─────────────────────────────────────────────────────────────────┐
│                Logging Integration Architecture                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ [Existing logging_config.py] ← [Enhanced Integration]          │
│           ↓                           ↓                        │
│ [WorkflowFormatter] → [SmartFilter] → [ContextLogger]         │
│           ↓                           ↓                        │
│ [Progress Tracker] → [Error Categorizer] → [Clean Output]      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
"""

import os
import sys
import json
import logging
import logging.handlers
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path

# Import existing logging infrastructure
from .logging_config import (
    JSONFormatter, HumanReadableFormatter, setup_log_directories,
    create_rotating_file_handler, configure_third_party_loggers,
    log_performance, log_security_event, log_database_operation, log_api_request
)

# Import enhanced logging utilities
from .logging_utils import (
    WorkflowLogger, ComponentType, WorkflowPhase, LogLevel,
    SmartDataFilter, DataSummary, get_workflow_logger, LoggingConfig
)

# Import constants
from .constants import LOG_LEVEL, ENVIRONMENT, ENABLE_WORKFLOW_TRACING


class WorkflowFormatter(HumanReadableFormatter):
    """Enhanced formatter for workflow-specific logging."""
    
    def __init__(self, show_progress: bool = True, show_context: bool = True):
        super().__init__()
        self.show_progress = show_progress
        self.show_context = show_context
        self.data_filter = SmartDataFilter()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with workflow enhancements."""
        # Apply smart filtering to record extra data
        if hasattr(record, '__dict__'):
            filtered_dict = {}
            for key, value in record.__dict__.items():
                if key.startswith('_') or key in [
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                    'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                    'thread', 'threadName', 'processName', 'process', 'getMessage'
                ]:
                    filtered_dict[key] = value
                else:
                    # Apply smart filtering to extra fields
                    if isinstance(value, dict):
                        filtered_dict[key] = self.data_filter.filter_dict(value)
                    elif isinstance(value, str) and len(value) > 200:
                        filtered_dict[key] = f"{value[:100]}...({len(value)} chars)"
                    else:
                        filtered_dict[key] = value
            
            # Replace record dict with filtered version
            record.__dict__.update(filtered_dict)
        
        # Get base format
        base_message = super().format(record)
        
        # Add workflow-specific enhancements
        enhancements = []
        
        # Add progress information
        if self.show_progress and hasattr(record, 'progress_percent'):
            progress = record.progress_percent
            if progress > 0:
                enhancements.append(f"Progress: {progress:.1f}%")
        
        # Add workflow context
        if self.show_context:
            context_parts = []
            if hasattr(record, 'workflow_id'):
                context_parts.append(f"WF:{record.workflow_id[:8]}")
            if hasattr(record, 'component'):
                context_parts.append(f"Component:{record.component}")
            if hasattr(record, 'node_id'):
                context_parts.append(f"Node:{record.node_id}")
            
            if context_parts:
                enhancements.append(f"[{' | '.join(context_parts)}]")
        
        # Combine message with enhancements
        if enhancements:
            return f"{base_message} {' '.join(enhancements)}"
        
        return base_message


class WorkflowJSONFormatter(JSONFormatter):
    """Enhanced JSON formatter for workflow logging in production."""
    
    def __init__(self):
        super().__init__()
        self.data_filter = SmartDataFilter()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with workflow enhancements."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add workflow-specific fields with smart filtering
        workflow_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'getMessage'
            ]:
                # Apply smart filtering
                if isinstance(value, dict):
                    workflow_fields[key] = self.data_filter.filter_dict(value)
                elif isinstance(value, str) and len(value) > 1000:
                    workflow_fields[key] = f"{value[:200]}...({len(value)} chars)"
                else:
                    workflow_fields[key] = value
        
        # Add workflow fields to log entry
        if workflow_fields:
            log_entry["workflow"] = workflow_fields
        
        return json.dumps(log_entry, default=str)


class ComponentLogFilter(logging.Filter):
    """Filter logs based on component type and configuration."""
    
    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter record based on component configuration."""
        # Get component from record
        component_name = getattr(record, 'component', None)
        if not component_name:
            return True  # Allow non-component logs through
        
        try:
            component = ComponentType(component_name)
        except ValueError:
            return True  # Allow unknown components
        
        # Check debug/trace settings
        if record.levelno <= logging.DEBUG:
            return self.config.is_debug_enabled(component) or self.config.is_trace_enabled(component)
        
        return True


def create_enhanced_workflow_handler(
    filename: str,
    component: Optional[ComponentType] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5
) -> logging.handlers.RotatingFileHandler:
    """Create enhanced workflow-specific log handler."""
    handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=max_bytes, backupCount=backup_count
    )
    
    # Use enhanced formatters
    if ENVIRONMENT == "production":
        handler.setFormatter(WorkflowJSONFormatter())
    else:
        handler.setFormatter(WorkflowFormatter(show_progress=True, show_context=True))
    
    # Add component filter if specified
    if component:
        config = LoggingConfig()
        handler.addFilter(ComponentLogFilter(config))
    
    return handler


def setup_enhanced_workflow_logging(
    enable_file_logging: bool = False,
    workflow_log_level: str = "INFO",
    debug_components: Optional[List[str]] = None,
    trace_components: Optional[List[str]] = None
):
    """
    Setup enhanced workflow logging system.
    
    Args:
        enable_file_logging: Enable file-based logging (disabled by default for performance)
        workflow_log_level: Log level for workflow components
        debug_components: Components to enable debug logging for
        trace_components: Components to enable trace logging for
    """
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # Set workflow log level
    workflow_level = getattr(logging, workflow_log_level.upper(), logging.INFO)
    
    # Create enhanced console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if ENVIRONMENT == "production":
        console_handler.setFormatter(WorkflowJSONFormatter())
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setFormatter(WorkflowFormatter(show_progress=True, show_context=True))
        console_handler.setLevel(workflow_level)
    
    # Replace existing console handler
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            root_logger.removeHandler(handler)
    
    root_logger.addHandler(console_handler)
    
    # Configure component-specific logging
    if debug_components or trace_components:
        config = LoggingConfig()
        
        if debug_components:
            for component_name in debug_components:
                try:
                    component = ComponentType(component_name)
                    config.enable_debug_for_component(component)
                except ValueError:
                    logging.warning(f"Unknown component for debug logging: {component_name}")
        
        if trace_components:
            for component_name in trace_components:
                try:
                    component = ComponentType(component_name)
                    config.enable_trace_for_component(component)
                except ValueError:
                    logging.warning(f"Unknown component for trace logging: {component_name}")
        
        # Add component filter to console handler
        console_handler.addFilter(ComponentLogFilter(config))
    
    # Setup file logging if enabled
    if enable_file_logging:
        log_dir = setup_log_directories()
        
        # Create component-specific log files
        workflow_handler = create_enhanced_workflow_handler(
            log_dir / "workflow.log"
        )
        workflow_handler.setLevel(workflow_level)
        
        # Add filters for workflow logs
        class WorkflowLogFilter(logging.Filter):
            def filter(self, record):
                return hasattr(record, 'component') or 'workflow' in record.name.lower()
        
        workflow_handler.addFilter(WorkflowLogFilter())
        root_logger.addHandler(workflow_handler)
        
        # Create error-specific log file
        error_handler = create_enhanced_workflow_handler(
            log_dir / "workflow_errors.log"
        )
        error_handler.setLevel(logging.WARNING)
        root_logger.addHandler(error_handler)
    
    # Configure third-party loggers to reduce noise
    configure_third_party_loggers()
    
    # Additional noise reduction for development
    if ENVIRONMENT != "production":
        # Reduce SQLAlchemy noise
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        
        # Reduce HTTP client noise
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Log startup message
    logger = get_workflow_logger(ComponentType.WORKFLOW_ENGINE)
    logger.info("Enhanced workflow logging system initialized", 
               environment=ENVIRONMENT,
               file_logging=enable_file_logging,
               debug_components=debug_components or [],
               trace_components=trace_components or [])


# Integration with existing tracing system
def integrate_with_tracing():
    """Integrate enhanced logging with existing tracing system."""
    try:
        from .tracing import WorkflowTracer
        
        # Monkey patch WorkflowTracer to use enhanced logging
        original_start_workflow = WorkflowTracer.start_workflow
        original_start_node_execution = WorkflowTracer.start_node_execution
        original_end_node_execution = WorkflowTracer.end_node_execution
        original_end_workflow = WorkflowTracer.end_workflow
        
        def enhanced_start_workflow(self, workflow_id=None, flow_data=None, correlation_id=None):
            # Use enhanced logger
            logger = get_workflow_logger(
                ComponentType.WORKFLOW_ENGINE,
                workflow_id=workflow_id,
                session_id=self.session_id
            )
            
            # Extract workflow info
            node_count = len(flow_data.get("nodes", [])) if flow_data else 0
            edge_count = len(flow_data.get("edges", [])) if flow_data else 0
            
            logger.start_workflow_phase(
                WorkflowPhase.EXECUTE,
                total_steps=node_count,
                workflow_id=workflow_id,
                node_count=node_count,
                edge_count=edge_count
            )
            
            # Call original
            return original_start_workflow(self, workflow_id, flow_data, correlation_id)
        
        def enhanced_start_node_execution(self, node_id, node_type, inputs, parent_span_id=None):
            logger = get_workflow_logger(
                ComponentType.NODE_EXECUTOR,
                workflow_id=getattr(self, 'workflow_id', None),
                session_id=self.session_id
            )
            
            logger.log_node_execution(node_id, node_type, inputs)
            
            # Call original
            return original_start_node_execution(self, node_id, node_type, inputs, parent_span_id)
        
        def enhanced_end_node_execution(self, node_id, node_type, outputs, success=True, error_message=None, exception=None):
            logger = get_workflow_logger(
                ComponentType.NODE_EXECUTOR,
                workflow_id=getattr(self, 'workflow_id', None),
                session_id=self.session_id
            )
            
            if success:
                logger.info(f" Node completed: {node_id} ({node_type})",
                           node_id=node_id,
                           node_type=node_type,
                           output_keys=list(outputs.keys()) if outputs else [])
                logger.update_progress(1, f"Completed {node_id}")
            else:
                logger.error(f" Node failed: {node_id} ({node_type})",
                            error=exception,
                            node_id=node_id,
                            node_type=node_type,
                            error_message=error_message)
            
            # Call original
            return original_end_node_execution(self, node_id, node_type, outputs, success, error_message, exception)
        
        def enhanced_end_workflow(self, success, error=None, exception=None, final_metrics=None):
            logger = get_workflow_logger(
                ComponentType.WORKFLOW_ENGINE,
                workflow_id=getattr(self, 'workflow_id', None),
                session_id=self.session_id
            )
            
            phase = WorkflowPhase.COMPLETE if success else WorkflowPhase.ERROR
            logger.end_workflow_phase(
                phase,
                success=success,
                error_message=error,
                final_metrics=final_metrics or {}
            )
            
            # Call original
            return original_end_workflow(self, success, error, exception, final_metrics)
        
        # Apply monkey patches
        WorkflowTracer.start_workflow = enhanced_start_workflow
        WorkflowTracer.start_node_execution = enhanced_start_node_execution
        WorkflowTracer.end_node_execution = enhanced_end_node_execution
        WorkflowTracer.end_workflow = enhanced_end_workflow
        
        logging.info("Enhanced logging integrated with tracing system")
        
    except ImportError:
        logging.warning("Could not integrate with tracing system - tracing module not available")


# Environment-based configuration presets
def setup_development_logging():
    """Setup logging configuration optimized for development."""
    setup_enhanced_workflow_logging(
        enable_file_logging=False,  # Console only for development
        workflow_log_level="DEBUG",
        debug_components=["workflow_engine", "node_executor"],
        trace_components=[]
    )
    integrate_with_tracing()


def setup_production_logging():
    """Setup logging configuration optimized for production."""
    setup_enhanced_workflow_logging(
        enable_file_logging=True,  # Enable file logging for production
        workflow_log_level="INFO",
        debug_components=[],  # No debug in production
        trace_components=[]
    )
    integrate_with_tracing()


def setup_debugging_logging():
    """Setup logging configuration for debugging specific issues."""
    setup_enhanced_workflow_logging(
        enable_file_logging=True,
        workflow_log_level="DEBUG",
        debug_components=["workflow_engine", "node_executor", "database", "vector_store"],
        trace_components=["memory_manager"]
    )
    integrate_with_tracing()


# Auto-configuration based on environment and settings
def auto_configure_enhanced_logging():
    """Automatically configure logging based on environment and user settings."""
    from .logging_settings import get_logging_settings
    
    settings = get_logging_settings()
    
    setup_enhanced_workflow_logging(
        enable_file_logging=settings.enable_file_logging,
        workflow_log_level=settings.log_level,
        debug_components=settings.debug_components,
        trace_components=settings.trace_components
    )
    integrate_with_tracing()


# Utility functions for existing code migration
def get_enhanced_logger(component_name: str, **context) -> WorkflowLogger:
    """Get enhanced logger - migration helper for existing code."""
    try:
        component = ComponentType(component_name)
    except ValueError:
        component = ComponentType.CUSTOM
    
    return get_workflow_logger(
        component=component,
        workflow_id=context.get('workflow_id'),
        session_id=context.get('session_id')
    )


def migrate_logger_calls(old_logger: logging.Logger, component_name: str) -> WorkflowLogger:
    """Migrate from old logger to enhanced logger."""
    return get_enhanced_logger(component_name)


# Backward compatibility aliases
log_workflow_performance = log_performance
log_workflow_security_event = log_security_event
log_workflow_database_operation = log_database_operation
log_workflow_api_request = log_api_request