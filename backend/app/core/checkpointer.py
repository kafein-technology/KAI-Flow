

import os
import time
import logging
from .constants import DISABLE_DATABASE, DATABASE_URL
import warnings
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from .logging_config import log_performance

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-untyped]
    _POSTGRES_AVAILABLE = True
    logger.info("PostgresSaver import successful")
except ImportError as e:
    _POSTGRES_AVAILABLE = False
    PostgresSaver = None  # type: ignore[assignment]
    logger.warning(f"PostgresSaver import failed: {e}")
    logger.info("Will use in-memory checkpointer instead")


def create_checkpointer(
    database_url: Optional[str] = None,
    use_memory: bool = False
) -> BaseCheckpointSaver:
    """
    Create an appropriate checkpointer based on configuration.
    
    Args:
        database_url: PostgreSQL connection URL (optional)
        use_memory: Force use of in-memory checkpointer
    
    Returns:
        BaseCheckpointSaver: Configured checkpointer instance
    """
    start_time = time.time()
    
    # Check if database is disabled via environment variable
    database_disabled = (DISABLE_DATABASE or "").lower() == "true"
    
    logger.info("Creating checkpointer", extra={
        "database_url_provided": bool(database_url),
        "use_memory_forced": use_memory,
        "database_disabled": database_disabled,
        "postgres_available": _POSTGRES_AVAILABLE
    })
    
    if use_memory or database_disabled or not database_url or not _POSTGRES_AVAILABLE:
        reason = []
        if use_memory:
            reason.append("memory forced")
        if database_disabled:
            reason.append("database disabled")
        if not database_url:
            reason.append("no database URL")
        if not _POSTGRES_AVAILABLE:
            reason.append("PostgresSaver not available")
        
        duration = time.time() - start_time
        logger.info("Using in-memory checkpointer", extra={
            "reason": ", ".join(reason),
            "setup_duration_ms": round(duration * 1000, 2)
        })
        log_performance("create_memory_checkpointer", duration, checkpointer_type="memory")
        
        return MemorySaver()
    
    try:
        logger.info("Attempting to create PostgreSQL checkpointer", extra={
            "database_url_length": len(database_url) if database_url else 0
        })
        
        if PostgresSaver is None:
            raise ImportError("PostgresSaver not available")
        
        # Time the connection setup
        setup_start = time.time()
        checkpointer = PostgresSaver.from_conn_string(database_url)
        connection_duration = time.time() - setup_start
        
        logger.info("PostgreSQL checkpointer created", extra={
            "connection_duration_ms": round(connection_duration * 1000, 2)
        })
        
        # Test connection setup - PostgresSaver uses async context manager pattern
        test_start = time.time()
        try:
            # Try to setup if the method exists
            if hasattr(checkpointer, 'setup') and callable(checkpointer.setup):
                checkpointer.setup()
            else:
                logger.info("PostgreSQL checkpointer doesn't require explicit setup")
        except Exception as setup_error:
            logger.warning(f"PostgreSQL checkpointer setup failed, but continuing: {setup_error}")
        test_duration = time.time() - test_start
        
        total_duration = time.time() - start_time
        
        logger.info("PostgreSQL checkpointer initialized successfully", extra={
            "test_duration_ms": round(test_duration * 1000, 2),
            "total_duration_ms": round(total_duration * 1000, 2)
        })
        
        log_performance("create_postgres_checkpointer", total_duration, 
                       checkpointer_type="postgres",
                       connection_duration_ms=round(connection_duration * 1000, 2),
                       test_duration_ms=round(test_duration * 1000, 2))
        
        return checkpointer
                
    except Exception as e:
        duration = time.time() - start_time
        
        logger.error("Failed to create PostgreSQL checkpointer", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(duration * 1000, 2),
            "database_disabled": database_disabled
        })
        
        if not database_disabled:  # Only warn if database was expected to work
            warnings.warn(f"Could not create PostgreSQL checkpointer: {e}")
        
        logger.info("Falling back to in-memory checkpointer", extra={
            "fallback_reason": "postgres_failed",
            "postgres_error": str(e)
        })
        
        log_performance("create_checkpointer_fallback", duration, 
                       checkpointer_type="memory_fallback",
                       original_error=str(e))
        
        return MemorySaver()


def get_default_checkpointer() -> BaseCheckpointSaver:
    """
    Get the default checkpointer for the application.
    
    Returns:
        BaseCheckpointSaver: Default checkpointer instance
    """
    start_time = time.time()
    database_url = DATABASE_URL
    
    logger.info("Getting default checkpointer", extra={
        "database_url_configured": bool(database_url)
    })
    
    checkpointer = create_checkpointer(database_url)
    
    duration = time.time() - start_time
    checkpointer_type = "postgres" if hasattr(checkpointer, 'conn') else "memory"
    
    logger.info("Default checkpointer created", extra={
        "checkpointer_type": checkpointer_type,
        "total_duration_ms": round(duration * 1000, 2)
    })
    
    log_performance("get_default_checkpointer", duration, 
                   checkpointer_type=checkpointer_type)
    
    return checkpointer 