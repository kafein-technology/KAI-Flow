"""
Comprehensive logging configuration for KAI Fusion Backend.

This module provides structured logging capabilities with:
- JSON format for production environments
- Human-readable format for development
- Rotating log files with size limits
- Separate log files by category (app, database, api, errors)
- Performance monitoring and timing
- Security event logging
"""

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .constants import LOG_LEVEL, ENVIRONMENT


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""

    def format(self, record: logging.LogRecord) -> str:
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

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development environments."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset to default
    }

    def __init__(self, use_colors=True):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s:%(lineno)-4d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.use_colors = (
            use_colors and os.name != "nt"
        )  # Disable colors on Windows by default

    def format(self, record: logging.LogRecord) -> str:
        # Store the original levelname
        original_levelname = record.levelname

        if self.use_colors:
            # Add color to levelname
            if record.levelname in self.COLORS:
                colored_levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
                record.levelname = colored_levelname

        # Format the message
        formatted_message = super().format(record)

        # Restore original levelname
        record.levelname = original_levelname

        return formatted_message


class ColoredLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that provides colored logging methods."""

    def yellow(self, message, *args, **kwargs):
        """Log a message with yellow color."""
        if self.isEnabledFor(logging.INFO):
            # Use ANSI yellow color for the entire message
            yellow_message = f"\033[33m{message}\033[0m"
            self.log(logging.INFO, yellow_message, *args, **kwargs)


class DatabaseFilter(logging.Filter):
    """Filter to identify database-related log entries."""

    def filter(self, record: logging.LogRecord) -> bool:
        db_keywords = [
            "database",
            "db_",
            "sql",
            "postgres",
            "connection",
            "session",
            "query",
        ]
        message = record.getMessage().lower()
        logger_name = record.name.lower()

        return any(
            keyword in message or keyword in logger_name for keyword in db_keywords
        )


class APIFilter(logging.Filter):
    """Filter to identify API-related log entries."""

    def filter(self, record: logging.LogRecord) -> bool:
        api_keywords = [
            "api",
            "request",
            "response",
            "endpoint",
            "middleware",
            "fastapi",
        ]
        message = record.getMessage().lower()
        logger_name = record.name.lower()

        return any(
            keyword in message or keyword in logger_name for keyword in api_keywords
        )


class ErrorFilter(logging.Filter):
    """Filter to identify error and warning log entries."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING


class SecurityFilter(logging.Filter):
    """Filter to identify security-related log entries."""

    def filter(self, record: logging.LogRecord) -> bool:
        security_keywords = [
            "security",
            "auth",
            "authentication",
            "authorization",
            "suspicious",
            "attack",
            "malicious",
            "unauthorized",
        ]
        message = record.getMessage().lower()
        logger_name = record.name.lower()

        return any(
            keyword in message or keyword in logger_name
            for keyword in security_keywords
        )


def setup_log_directories():
    """Create log directories if they don't exist."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    return log_dir


def create_rotating_file_handler(
    filename: str,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    log_filter: Optional[logging.Filter] = None,
) -> logging.handlers.RotatingFileHandler:
    """Create a rotating file handler with optional filtering."""
    handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=max_bytes, backupCount=backup_count
    )

    # Use JSON formatter for production, human-readable for development
    if ENVIRONMENT == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanReadableFormatter())

    if log_filter:
        handler.addFilter(log_filter)

    return handler


def setup_comprehensive_logging():
    """
    Setup comprehensive logging system with console output.

    Optimized for development and production environments:
    - Console output with appropriate formatting
    - File logging disabled to prevent disk usage issues
    - Structured JSON logs in production
    """

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler for immediate feedback
    console_handler = logging.StreamHandler(sys.stdout)
    if ENVIRONMENT == "production":
        console_handler.setFormatter(JSONFormatter())
        console_handler.setLevel(logging.INFO)
    else:
        # Use colored formatter for development
        console_handler.setFormatter(HumanReadableFormatter(use_colors=True))
        console_handler.setLevel(logging.DEBUG)

    root_logger.addHandler(console_handler)

    # Configure specific loggers
    configure_third_party_loggers()

    # Log startup message
    logger = logging.getLogger(__name__)
<<<<<<< HEAD
    logger.info("Console logging system initialized", extra={
        "environment": ENVIRONMENT,
        "log_level": LOG_LEVEL,
        "handlers_count": len(root_logger.handlers)
    })
=======
    logger.info(
        " Console logging system initialized",
        extra={
            "environment": ENVIRONMENT,
            "log_level": LOG_LEVEL,
            "handlers_count": len(root_logger.handlers),
        },
    )
>>>>>>> serialization_fixes


def configure_third_party_loggers():
    """Configure logging levels for third-party libraries."""

    # SQLAlchemy logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)

    # FastAPI/Uvicorn logging
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Asyncio
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger_with_context(name: str, **context: Any) -> ColoredLoggerAdapter:
    """
    Get a logger with additional context that will be included in all log messages.
    Supports colored logging with .yellow() method.

    Args:
        name: Logger name
        **context: Additional context to include in log messages

    Returns:
        ColoredLoggerAdapter with context and colored logging support
    """
    logger = logging.getLogger(name)
    return ColoredLoggerAdapter(logger, context)


def get_colored_logger(name: str) -> ColoredLoggerAdapter:
    """
    Get a colored logger for the specified name.

    Args:
        name: Logger name

    Returns:
        ColoredLoggerAdapter with colored logging support
    """
    logger = logging.getLogger(name)
    return ColoredLoggerAdapter(logger, {})


def log_performance(func_name: str, duration: float, **extra_context: Any):
    """
    Log performance metrics for function execution.

    Args:
        func_name: Name of the function
        duration: Execution duration in seconds
        **extra_context: Additional context
    """
    logger = logging.getLogger("performance")
    logger.info(
        f"Performance: {func_name} executed",
        extra={
            "function": func_name,
            "duration_seconds": round(duration, 4),
            "duration_ms": round(duration * 1000, 2),
            **extra_context,
        },
    )


def log_security_event(
    event_type: str, details: Dict[str, Any], severity: str = "info"
):
    """
    Log security-related events.

    Args:
        event_type: Type of security event
        details: Event details
        severity: Event severity (info, warning, error)
    """
    logger = logging.getLogger("security")

    log_method = getattr(logger, severity.lower(), logger.info)
    log_method(
        f"Security event: {event_type}",
        extra={"event_type": event_type, "security_event": True, **details},
    )


def log_database_operation(
    operation: str, table: str, duration: float, **extra_context: Any
):
    """
    Log database operations with timing and context.

    Args:
        operation: Database operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration: Operation duration in seconds
        **extra_context: Additional context
    """
    logger = logging.getLogger("database")
    logger.info(
        f"Database {operation} on {table}",
        extra={
            "db_operation": operation,
            "db_table": table,
            "duration_seconds": round(duration, 4),
            "duration_ms": round(duration * 1000, 2),
            **extra_context,
        },
    )


def log_api_request(
    method: str, path: str, status_code: int, duration: float, **extra_context: Any
):
    """
    Log API requests with timing and response information.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration: Request duration in seconds
        **extra_context: Additional context
    """
    logger = logging.getLogger("api")

    log_level = logging.INFO
    if status_code >= 400:
        log_level = logging.WARNING if status_code < 500 else logging.ERROR

    logger.log(
        log_level,
        f"{method} {path} {status_code}",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "duration_seconds": round(duration, 4),
            "duration_ms": round(duration * 1000, 2),
            **extra_context,
        },
    )
