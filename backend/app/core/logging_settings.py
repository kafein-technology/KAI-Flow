"""
KAI-Flow Enhanced Logging Settings - User Configuration Interface
===================================================================

This module provides user-configurable settings for the enhanced logging system.
Users can customize logging behavior through environment variables or configuration
files to control verbosity, component-specific debugging, and output formatting.

Environment Variables:
• KAI_FUSION_LOG_LEVEL: Overall log level (DEBUG, INFO, WARNING, ERROR)
• KAI_FUSION_DEBUG_COMPONENTS: Comma-separated list of components for debug logging
• KAI_FUSION_TRACE_COMPONENTS: Comma-separated list of components for trace logging
• KAI_FUSION_FILE_LOGGING: Enable file logging (true/false)
• KAI_FUSION_PROGRESS_LOGGING: Enable progress tracking (true/false)
• KAI_FUSION_FILTER_EMBEDDINGS: Filter embedding data from logs (true/false)

Example Usage:
```bash
# Enable debug logging for workflow engine and database components
export KAI_FUSION_DEBUG_COMPONENTS="workflow_engine,database"

# Enable trace logging for vector store operations
export KAI_FUSION_TRACE_COMPONENTS="vector_store"

# Enable file logging in production
export KAI_FUSION_FILE_LOGGING=true

# Disable progress tracking for cleaner logs
export KAI_FUSION_PROGRESS_LOGGING=false
```

Configuration Presets:
• development: Verbose console logging, no file logging
• production: Structured JSON logging, file logging enabled
• debugging: Maximum verbosity, all components traced
• minimal: Only errors and warnings, no debug/trace
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .constants import ENVIRONMENT, LOG_LEVEL


@dataclass
class EnhancedLoggingSettings:
    """Configuration settings for enhanced logging system."""
    
    # Basic settings
    log_level: str = "INFO"
    environment: str = "development"
    enable_file_logging: bool = False
    enable_progress_tracking: bool = True
    enable_performance_monitoring: bool = True
    
    # Component-specific settings
    debug_components: List[str] = None
    trace_components: List[str] = None
    
    # Data filtering settings
    filter_embeddings: bool = True
    truncate_threshold: int = 500
    max_embedding_log_size: int = 100
    
    # Progress and visualization settings
    show_progress_bars: bool = True
    progress_update_interval: int = 25  # Percent
    show_context_info: bool = True
    
    # Performance monitoring settings
    performance_warning_threshold: float = 2.0  # 2x average
    track_memory_usage: bool = True
    track_database_queries: bool = True
    
    # Output formatting settings
    use_colors: bool = True
    use_emojis: bool = True
    timestamp_format: str = "%H:%M:%S"
    
    def __post_init__(self):
        """Initialize default values."""
        if self.debug_components is None:
            self.debug_components = []
        if self.trace_components is None:
            self.trace_components = []


def load_settings_from_environment() -> EnhancedLoggingSettings:
    """Load settings from environment variables."""
    settings = EnhancedLoggingSettings()
    
    # Basic settings
    settings.log_level = os.getenv("KAI_FUSION_LOG_LEVEL", LOG_LEVEL).upper()
    settings.environment = os.getenv("ENVIRONMENT", ENVIRONMENT)
    settings.enable_file_logging = os.getenv("KAI_FUSION_FILE_LOGGING", "false").lower() == "true"
    settings.enable_progress_tracking = os.getenv("KAI_FUSION_PROGRESS_LOGGING", "true").lower() == "true"
    
    # Component-specific settings
    debug_components = os.getenv("KAI_FUSION_DEBUG_COMPONENTS", "")
    if debug_components:
        settings.debug_components = [c.strip() for c in debug_components.split(",") if c.strip()]
    
    trace_components = os.getenv("KAI_FUSION_TRACE_COMPONENTS", "")
    if trace_components:
        settings.trace_components = [c.strip() for c in trace_components.split(",") if c.strip()]
    
    # Data filtering settings
    settings.filter_embeddings = os.getenv("KAI_FUSION_FILTER_EMBEDDINGS", "true").lower() == "true"
    
    try:
        settings.truncate_threshold = int(os.getenv("KAI_FUSION_TRUNCATE_THRESHOLD", "500"))
    except ValueError:
        pass
    
    # Performance settings
    try:
        settings.performance_warning_threshold = float(os.getenv("KAI_FUSION_PERF_THRESHOLD", "2.0"))
    except ValueError:
        pass
    
    # Output formatting
    settings.use_colors = os.getenv("KAI_FUSION_USE_COLORS", "true").lower() == "true"
    settings.use_emojis = os.getenv("KAI_FUSION_USE_EMOJIS", "true").lower() == "true"
    
    return settings


def get_preset_settings(preset: str) -> EnhancedLoggingSettings:
    """Get predefined configuration presets."""
    base_settings = EnhancedLoggingSettings()
    
    if preset == "development":
        return EnhancedLoggingSettings(
            log_level="DEBUG",
            environment="development",
            enable_file_logging=False,
            enable_progress_tracking=True,
            debug_components=["workflow_engine"],
            trace_components=[],
            use_colors=True,
            use_emojis=True,
            show_progress_bars=True
        )
    
    elif preset == "production":
        return EnhancedLoggingSettings(
            log_level="INFO",
            environment="production",
            enable_file_logging=True,
            enable_progress_tracking=False,  # Less verbose for production
            debug_components=[],
            trace_components=[],
            use_colors=False,  # Better for log aggregation
            use_emojis=False,
            show_progress_bars=False,
            filter_embeddings=True,
            truncate_threshold=200  # More aggressive truncation
        )
    
    elif preset == "debugging":
        return EnhancedLoggingSettings(
            log_level="DEBUG",
            environment="development", 
            enable_file_logging=True,
            enable_progress_tracking=True,
            debug_components=["workflow_engine", "node_executor", "database", "vector_store"],
            trace_components=["memory_manager", "llm_client"],
            use_colors=True,
            use_emojis=True,
            show_progress_bars=True,
            performance_warning_threshold=1.5,  # More sensitive
            track_memory_usage=True,
            track_database_queries=True
        )
    
    elif preset == "minimal":
        return EnhancedLoggingSettings(
            log_level="WARNING",
            environment="production",
            enable_file_logging=False,
            enable_progress_tracking=False,
            debug_components=[],
            trace_components=[],
            use_colors=False,
            use_emojis=False,
            show_progress_bars=False,
            filter_embeddings=True,
            truncate_threshold=100
        )
    
    elif preset == "testing":
        return EnhancedLoggingSettings(
            log_level="ERROR",  # Suppress most logs during testing
            environment="testing",
            enable_file_logging=False,
            enable_progress_tracking=False,
            debug_components=[],
            trace_components=[],
            use_colors=False,
            use_emojis=False,
            show_progress_bars=False
        )
    
    else:
        return base_settings


def create_settings_from_dict(config: Dict[str, Any]) -> EnhancedLoggingSettings:
    """Create settings from a configuration dictionary."""
    settings = EnhancedLoggingSettings()
    
    for key, value in config.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    return settings


# Default settings based on environment
def get_default_settings() -> EnhancedLoggingSettings:
    """Get default settings based on current environment."""
    
    # Check for preset environment variable
    preset = os.getenv("KAI_FUSION_LOGGING_PRESET")
    if preset:
        base_settings = get_preset_settings(preset)
    else:
        # Auto-select based on environment
        if ENVIRONMENT == "production":
            base_settings = get_preset_settings("production")
        elif ENVIRONMENT == "development":
            base_settings = get_preset_settings("development") 
        elif ENVIRONMENT == "testing":
            base_settings = get_preset_settings("testing")
        else:
            base_settings = EnhancedLoggingSettings()
    
    # Override with environment variables
    env_settings = load_settings_from_environment()
    
    # Merge settings (environment variables take precedence)
    merged_settings = EnhancedLoggingSettings()
    
    # Copy base settings
    for field in base_settings.__dataclass_fields__:
        setattr(merged_settings, field, getattr(base_settings, field))
    
    # Override with environment settings where they differ from defaults
    default_settings = EnhancedLoggingSettings()
    for field in env_settings.__dataclass_fields__:
        env_value = getattr(env_settings, field)
        default_value = getattr(default_settings, field)
        
        # Only override if environment value is different from default
        if env_value != default_value:
            setattr(merged_settings, field, env_value)
    
    return merged_settings


# Configuration validation
def validate_settings(settings: EnhancedLoggingSettings) -> List[str]:
    """Validate settings and return list of warnings/errors."""
    warnings = []
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if settings.log_level not in valid_levels:
        warnings.append(f"Invalid log level '{settings.log_level}', using INFO")
        settings.log_level = "INFO"
    
    # Validate component names
    valid_components = [
        "workflow_engine", "node_executor", "memory_manager", "database",
        "vector_store", "llm_client", "api_endpoint", "custom"
    ]
    
    for component in settings.debug_components:
        if component not in valid_components:
            warnings.append(f"Unknown debug component '{component}'")
    
    for component in settings.trace_components:
        if component not in valid_components:
            warnings.append(f"Unknown trace component '{component}'")
    
    # Validate thresholds
    if settings.truncate_threshold < 50:
        warnings.append("Truncate threshold too small, setting to 50")
        settings.truncate_threshold = 50
    
    if settings.performance_warning_threshold < 1.0:
        warnings.append("Performance warning threshold too small, setting to 1.0")
        settings.performance_warning_threshold = 1.0
    
    return warnings


# Settings singleton
_global_settings: Optional[EnhancedLoggingSettings] = None


def get_logging_settings() -> EnhancedLoggingSettings:
    """Get global logging settings."""
    global _global_settings
    if _global_settings is None:
        _global_settings = get_default_settings()
        warnings = validate_settings(_global_settings)
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(f"Logging configuration: {warning}")
    
    return _global_settings


def update_logging_settings(settings: EnhancedLoggingSettings):
    """Update global logging settings."""
    global _global_settings
    warnings = validate_settings(settings)
    if warnings:
        import logging
        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"Logging configuration: {warning}")
    
    _global_settings = settings


def reset_logging_settings():
    """Reset logging settings to defaults."""
    global _global_settings
    _global_settings = None


# Convenience functions for common configurations
def enable_debug_logging(components: List[str]):
    """Enable debug logging for specific components."""
    settings = get_logging_settings()
    settings.debug_components.extend(components)
    update_logging_settings(settings)


def enable_trace_logging(components: List[str]):
    """Enable trace logging for specific components."""
    settings = get_logging_settings()
    settings.trace_components.extend(components)
    update_logging_settings(settings)


def set_log_level(level: str):
    """Set global log level."""
    settings = get_logging_settings()
    settings.log_level = level.upper()
    update_logging_settings(settings)


def enable_file_logging():
    """Enable file logging."""
    settings = get_logging_settings()
    settings.enable_file_logging = True
    update_logging_settings(settings)


def disable_progress_tracking():
    """Disable progress tracking for minimal logs."""
    settings = get_logging_settings()
    settings.enable_progress_tracking = False
    settings.show_progress_bars = False
    update_logging_settings(settings)


# Export current settings as configuration
def export_current_settings() -> Dict[str, Any]:
    """Export current settings as a dictionary."""
    settings = get_logging_settings()
    return {
        field: getattr(settings, field)
        for field in settings.__dataclass_fields__
    }