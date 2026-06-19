"""
Comprehensive logging middleware for FastAPI applications.

This module provides multiple middleware classes for different aspects of logging:
- DetailedLoggingMiddleware: Complete request/response logging with timing
- DatabaseQueryLoggingMiddleware: Database usage tracking per request
- SecurityLoggingMiddleware: Security event monitoring and suspicious activity detection
"""

import time
import uuid
import json
import logging
import re
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse, parse_qs

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging_config import log_api_request, log_security_event, log_performance
from app.core.database import get_database_stats
from app.core.constants import API_START,API_VERSION


logger = logging.getLogger(__name__)


class DetailedLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for detailed API request/response logging.
    
    Logs:
    - Request method, path, headers, query parameters
    - Response status, headers, timing
    - Request/response body (configurable)
    - Client IP address and user agent
    - Request ID for correlation
    """
    
    def __init__(
        self, 
        app: ASGIApp,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 1024,
        exclude_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.exclude_paths = set(exclude_paths) if exclude_paths else {"/health", "/docs", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next):
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        
        # Extract client information
        client_ip = self._extract_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Prepare request data
        request_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "headers": self._sanitize_headers(dict(request.headers)),
            "content_type": request.headers.get("content-type"),
            "content_length": request.headers.get("content-length")
        }
        
        # Log request body if enabled
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    if request.headers.get("content-type", "").startswith("application/json"):
                        try:
                            request_data["request_body"] = json.loads(body.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            request_data["request_body"] = body.decode(errors="replace")[:self.max_body_size]
                    else:
                        request_data["request_body"] = body.decode(errors="replace")[:self.max_body_size]
                else:
                    request_data["request_body_size"] = len(body)
                    request_data["request_body"] = f"<body too large: {len(body)} bytes>"
                
                # Rebuild request for downstream processing
                request._body = body
            except Exception as e:
                request_data["request_body_error"] = str(e)
        
        # Log request start
        logger.info("API request started", extra=request_data)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate timing
            duration = time.time() - start_time
            
            # Prepare response data
            response_data = {
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_seconds": round(duration, 4),
                "duration_ms": round(duration * 1000, 2),
                "response_headers": self._sanitize_headers(dict(response.headers)),
                "content_type": response.headers.get("content-type")
            }
            
            # Log response body if enabled and response is not too large
            if self.log_response_body and hasattr(response, 'body'):
                try:
                    if len(response.body) <= self.max_body_size:
                        if response.headers.get("content-type", "").startswith("application/json"):
                            try:
                                response_data["response_body"] = json.loads(response.body.decode())
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                response_data["response_body"] = response.body.decode(errors="replace")[:self.max_body_size]
                        else:
                            response_data["response_body"] = response.body.decode(errors="replace")[:self.max_body_size]
                    else:
                        response_data["response_body_size"] = len(response.body)
                        response_data["response_body"] = f"<body too large: {len(response.body)} bytes>"
                except Exception as e:
                    response_data["response_body_error"] = str(e)
            
            # Log API request with timing
            log_api_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=duration,
                request_id=request_id,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            # Log detailed response
            logger.info("API request completed", extra=response_data)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            logger.error("API request failed", extra={
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_seconds": round(duration, 4),
                "duration_ms": round(duration * 1000, 2)
            })
            
            raise
    
    def _extract_client_ip(self, request: Request) -> str:
        """Extract client IP address, considering proxy headers."""
        # Check X-Forwarded-For header (proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Get the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers by removing sensitive information."""
        sensitive_headers = {
            "authorization", "cookie", "x-api-key", "x-auth-token",
            "x-csrf-token", "x-access-token", "x-refresh-token"
        }
        
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "<redacted>"
            else:
                sanitized[key] = value
        
        return sanitized


class DatabaseQueryLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tracking database usage per request.
    
    Logs database statistics and query counts for each API request.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        # Get initial database stats
        initial_stats = get_database_stats()
        start_queries = initial_stats.get("total_queries", 0)
        
        # Process request
        response = await call_next(request)
        
        # Get final database stats
        final_stats = get_database_stats()
        end_queries = final_stats.get("total_queries", 0)
        
        # Calculate queries made during this request
        queries_count = end_queries - start_queries
        
        # Log database usage if any queries were made
        if queries_count > 0:
            request_id = getattr(request.state, "request_id", "unknown")
            
            logger.info("Request database usage", extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "queries_count": queries_count,
                "total_queries": end_queries,
                "slow_queries": final_stats.get("slow_queries", 0),
                "failed_queries": final_stats.get("failed_queries", 0),
                "avg_query_duration_ms": final_stats.get("average_query_duration_ms", 0),
                "pool_status": final_stats.get("async_pool_status", {})
            })
        
        return response


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for security event monitoring and suspicious activity detection.
    
    Monitors for:
    - SQL injection attempts
    - XSS attempts
    - Path traversal attempts
    - Suspicious user agents
    - Rate limiting violations
    - Authentication failures
    """
    
    def __init__(
        self, 
        app: ASGIApp,
        enable_suspicious_detection: bool = True,
        log_all_security_headers: bool = False
    ):
        super().__init__(app)
        self.enable_suspicious_detection = enable_suspicious_detection
        self.log_all_security_headers = log_all_security_headers
        
        # Suspicious patterns for detection
        self.sql_injection_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter)\b)",
            r"(--|\/\*|\*\/)",
            r"(\b(or|and)\b\s+\d+\s*=\s*\d+)",
            r"(\bor\b\s+\d+\s*>\s*\d+)",
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e\\",
        ]
        
        self.suspicious_user_agents = [
            "sqlmap", "nmap", "nikto", "burp", "zap", "w3af",
            "acunetix", "netsparker", "appscan", "websecurify"
        ]
        
        # Compile regex patterns
        self.compiled_patterns = {
            "sql_injection": [re.compile(pattern, re.IGNORECASE) for pattern in self.sql_injection_patterns],
            "xss": [re.compile(pattern, re.IGNORECASE) for pattern in self.xss_patterns],
            "path_traversal": [re.compile(pattern, re.IGNORECASE) for pattern in self.path_traversal_patterns],
        }
    
    async def dispatch(self, request: Request, call_next):
        # Extract security-relevant information
        client_ip = self._extract_client_ip(request)
        user_agent = request.headers.get("user-agent", "").lower()
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        
        # Check for suspicious patterns if enabled
        if self.enable_suspicious_detection:
            # Skip detection for legitimate endpoints (whitelist)
            whitelisted_paths = [
                f"/{API_START}/http-client/",
                f"/{API_START}/{API_VERSION}/webhook/",
                f"/{API_START}/{API_VERSION}/webhook-test/",
                f"/{API_START}/{API_VERSION}/nodes/",
                f"/{API_START}/{API_VERSION}/workflows/",
                f"/{API_START}/{API_VERSION}/ai-builder/"
            ]
            
            should_detect = True
            for whitelisted_path in whitelisted_paths:
                if request.url.path.startswith(whitelisted_path):
                    should_detect = False
                    break
            
            if should_detect:
                await self._detect_suspicious_activity(request, client_ip, user_agent, request_id)
        
        # Log security headers if enabled
        if self.log_all_security_headers:
            self._log_security_headers(request, request_id)
        
        # Process request
        response = await call_next(request)
        
        # Log authentication/authorization failures
        if response.status_code in [401, 403]:
            log_security_event(
                event_type="authentication_failure",
                details={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "client_ip": client_ip,
                    "user_agent": request.headers.get("user-agent", "unknown")
                },
                severity="warning"
            )
        
        return response
    
    async def _detect_suspicious_activity(
        self, 
        request: Request, 
        client_ip: str, 
        user_agent: str, 
        request_id: str
    ):
        """Detect and log suspicious activity patterns."""
        suspicious_events = []
        
        # Check user agent
        if any(suspicious in user_agent for suspicious in self.suspicious_user_agents):
            suspicious_events.append({
                "type": "suspicious_user_agent",
                "pattern": user_agent,
                "severity": "warning"
            })
        
        # Check URL path
        url_path = str(request.url)
        for pattern_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(url_path):
                    suspicious_events.append({
                        "type": f"suspicious_{pattern_type}_in_url",
                        "pattern": pattern.pattern,
                        "matched_text": url_path,
                        "severity": "error"
                    })
                    break
        
        # Check query parameters
        for param_name, param_value in request.query_params.items():
            for pattern_type, patterns in self.compiled_patterns.items():
                for pattern in patterns:
                    if pattern.search(param_value):
                        suspicious_events.append({
                            "type": f"suspicious_{pattern_type}_in_query",
                            "parameter": param_name,
                            "pattern": pattern.pattern,
                            "matched_text": param_value[:100],  # Limit for logging
                            "severity": "error"
                        })
                        break
        
        # Check request body for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode(errors="ignore")[:1000]  # Limit size for performance
                    
                    for pattern_type, patterns in self.compiled_patterns.items():
                        for pattern in patterns:
                            if pattern.search(body_str):
                                suspicious_events.append({
                                    "type": f"suspicious_{pattern_type}_in_body",
                                    "pattern": pattern.pattern,
                                    "matched_text": body_str[:100],  # Limit for logging
                                    "severity": "error"
                                })
                                break
                    
                    # Rebuild request body for downstream processing
                    request._body = body
            except Exception as e:
                logger.warning(f"Error reading request body for security analysis: {e}")
        
        # Log all suspicious events
        for event in suspicious_events:
            log_security_event(
                event_type=event["type"],
                details={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "method": request.method,
                    "path": request.url.path,
                    "pattern": event.get("pattern"),
                    "matched_text": event.get("matched_text"),
                    "parameter": event.get("parameter")
                },
                severity=event["severity"]
            )
    
    def _log_security_headers(self, request: Request, request_id: str):
        """Log security-relevant headers."""
        security_headers = {
            "x-forwarded-for", "x-real-ip", "x-forwarded-proto",
            "authorization", "cookie", "x-api-key", "x-csrf-token",
            "origin", "referer", "host"
        }
        
        relevant_headers = {
            key: ("<redacted>" if key.lower() in ["authorization", "cookie", "x-api-key"] else value)
            for key, value in request.headers.items()
            if key.lower() in security_headers
        }
        
        if relevant_headers:
            logger.info("Security headers", extra={
                "request_id": request_id,
                "security_headers": relevant_headers
            })
    
    def _extract_client_ip(self, request: Request) -> str:
        """Extract client IP address, considering proxy headers."""
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