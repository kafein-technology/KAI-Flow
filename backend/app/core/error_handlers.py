
import uuid
import traceback
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from sqlalchemy.exc import (
    SQLAlchemyError, 
    IntegrityError,
    OperationalError,
    ProgrammingError,
    DataError,
    DatabaseError
)

from app.core.logging_config import log_security_event


logger = logging.getLogger(__name__)


class ErrorLogger:
    """Utility class for centralized error logging."""
    
    @staticmethod
    def log_error(
        error: Exception,
        request: Optional[Request] = None,
        error_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an error with comprehensive context information.
        
        Args:
            error: The exception that occurred
            request: FastAPI request object (if available)
            error_id: Unique error ID (generated if not provided)
            context: Additional context information
        
        Returns:
            str: Unique error ID for tracking
        """
        if not error_id:
            error_id = str(uuid.uuid4())
        
        # Build error context
        error_context = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Add request context if available
        if request:
            error_context.update({
                "request_method": request.method,
                "request_path": request.url.path,
                "request_query": dict(request.query_params),
                "client_ip": ErrorLogger._extract_client_ip(request),
                "user_agent": request.headers.get("user-agent", "unknown"),
                "request_id": getattr(request.state, "request_id", "unknown")
            })
        
        # Add additional context
        if context:
            error_context.update(context)
        
        # Add stack trace for debugging
        error_context["stack_trace"] = traceback.format_exc()
        
        # Log error with appropriate level
        if isinstance(error, (HTTPException, StarletteHTTPException)):
            if error.status_code >= 500:
                logger.error("HTTP server error occurred", extra=error_context)
            else:
                logger.warning("HTTP client error occurred", extra=error_context)
        elif isinstance(error, SQLAlchemyError):
            logger.error("Database error occurred", extra=error_context)
        elif isinstance(error, ValidationError):
            logger.warning("Validation error occurred", extra=error_context)
        else:
            logger.error("Unexpected error occurred", extra=error_context)
        
        return error_id
    
    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        """Extract client IP address from request."""
        # Check X-Forwarded-For header (proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


def create_error_response(
    status_code: int,
    message: str,
    error_id: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        message: Error message
        error_id: Unique error ID
        details: Additional error details
    
    Returns:
        JSONResponse: Standardized error response
    """
    response_data = {
        "error": True,
        "message": message,
        "error_id": error_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    if details:
        response_data["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPException errors.
    
    Args:
        request: FastAPI request object
        exc: HTTPException instance
    
    Returns:
        JSONResponse: Standardized error response
    """
    error_id = ErrorLogger.log_error(
        error=exc,
        request=request,
        context={"status_code": exc.status_code}
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_id=error_id
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle Starlette HTTPException errors.
    
    Args:
        request: FastAPI request object
        exc: StarletteHTTPException instance
    
    Returns:
        JSONResponse: Standardized error response
    """
    error_id = ErrorLogger.log_error(
        error=exc,
        request=request,
        context={"status_code": exc.status_code}
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        error_id=error_id
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    
    Args:
        request: FastAPI request object
        exc: ValidationError instance
    
    Returns:
        JSONResponse: Standardized error response with validation details
    """
    error_id = ErrorLogger.log_error(
        error=exc,
        request=request,
        context={"validation_errors": exc.errors()}
    )
    
    # Format validation errors for user-friendly response
    validation_details = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        validation_details.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Validation error",
        error_id=error_id,
        details={"validation_errors": validation_details}
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.
    
    Args:
        request: FastAPI request object
        exc: SQLAlchemyError instance
    
    Returns:
        JSONResponse: Standardized error response
    """
    error_id = ErrorLogger.log_error(
        error=exc,
        request=request,
        context={
            "database_error": True,
            "error_code": getattr(exc, "code", None),
            "original_error": str(getattr(exc, "orig", None))
        }
    )
    
    # Determine appropriate status code and message based on error type
    if isinstance(exc, IntegrityError):
        status_code = status.HTTP_409_CONFLICT
        message = "Data integrity constraint violation"
    elif isinstance(exc, OperationalError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        message = "Database operation failed"
    elif isinstance(exc, ProgrammingError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        message = "Database programming error"
    elif isinstance(exc, DataError):
        status_code = status.HTTP_400_BAD_REQUEST
        message = "Invalid data provided"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        message = "Database error occurred"
    
    # Log as security event if it might be an injection attempt
    if any(keyword in str(exc).lower() for keyword in ["syntax error", "malformed", "invalid"]):
        log_security_event(
            event_type="potential_sql_injection",
            details={
                "error_id": error_id,
                "error_message": str(exc),
                "request_path": request.url.path,
                "client_ip": ErrorLogger._extract_client_ip(request)
            },
            severity="warning"
        )
    
    return create_error_response(
        status_code=status_code,
        message=message,
        error_id=error_id,
        details={"database_error": True}
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all other unexpected exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
    
    Returns:
        JSONResponse: Standardized error response
    """
    error_id = ErrorLogger.log_error(
        error=exc,
        request=request,
        context={"unexpected_error": True}
    )
    
    # Log as security event if it's a potential attack
    if any(keyword in str(exc).lower() for keyword in ["injection", "attack", "malicious", "exploit"]):
        log_security_event(
            event_type="potential_attack_detected",
            details={
                "error_id": error_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "request_path": request.url.path,
                "client_ip": ErrorLogger._extract_client_ip(request)
            },
            severity="error"
        )
    
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred",
        error_id=error_id,
        details={"unexpected_error": True}
    )


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle database-related exceptions."""
    
    request_id = str(uuid.uuid4())
    
    # Collect detailed error information
    error_details = {
        "exception_type": exc.__class__.__name__,
        "error_message": str(exc),
        "request_path": request.url.path,
        "request_method": request.method,
        "request_id": request_id
    }
    
    # Detail SQLAlchemy errors
    if hasattr(exc, 'orig'):
        error_details["original_error"] = str(exc.orig)
        error_details["original_error_type"] = exc.orig.__class__.__name__
    
    # Handle constraint violations specially
    if "constraint" in str(exc).lower() or "foreign key" in str(exc).lower():
        error_details["error_category"] = "CONSTRAINT_VIOLATION"
        logger.error(f"Database constraint violation [{request_id}]: {exc}", extra=error_details)
        
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": "CONSTRAINT_VIOLATION",
                "message": "Database constraint violation occurred",
                "details": error_details,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # Foreign key violations
    if "foreign key" in str(exc).lower():
        error_details["error_category"] = "FOREIGN_KEY_VIOLATION"
        logger.error(f"Foreign key violation [{request_id}]: {exc}", extra=error_details)
        
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": "FOREIGN_KEY_VIOLATION", 
                "message": "Referenced record does not exist",
                "details": error_details,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # Unique constraint violations
    if "unique" in str(exc).lower():
        error_details["error_category"] = "UNIQUE_CONSTRAINT_VIOLATION"
        logger.error(f"Unique constraint violation [{request_id}]: {exc}", extra=error_details)
        
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": "UNIQUE_CONSTRAINT_VIOLATION",
                "message": "Record already exists",
                "details": error_details,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # General database error
    logger.error(f"Database error [{request_id}]: {exc}", extra=error_details)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "DATABASE_ERROR",
            "message": "Database operation failed",
            "details": error_details,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    
    # Validation errors
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # Database errors
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(IntegrityError, sqlalchemy_exception_handler)
    app.add_exception_handler(OperationalError, sqlalchemy_exception_handler)
    app.add_exception_handler(ProgrammingError, sqlalchemy_exception_handler)
    app.add_exception_handler(DataError, sqlalchemy_exception_handler)
    app.add_exception_handler(DatabaseError, sqlalchemy_exception_handler)
    
    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("All exception handlers registered successfully")


class ErrorContext:
    """Context manager for error handling with automatic logging."""
    
    def __init__(
        self, 
        operation: str, 
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.request = request
        self.additional_context = additional_context or {}
        self.error_id = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.error_id = ErrorLogger.log_error(
                error=exc_val,
                request=self.request,
                context={
                    "operation": self.operation,
                    **self.additional_context
                }
            )
        return False  # Don't suppress the exception
    
    def get_error_id(self) -> Optional[str]:
        """Get the error ID if an error occurred."""
        return self.error_id