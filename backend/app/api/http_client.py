"""
HTTP Client API Endpoints
========================

This module provides API endpoints for testing HTTP Client nodes from the UI.
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from app.core.constants import API_START,API_VERSION

from app.nodes.tools import HttpClientNode

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"/{API_START}/http-client", tags=["HTTP Client"])


class HttpClientTestRequest(BaseModel):
    """HTTP Client test request model"""
    method: str
    url: str
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    timeout: Optional[int] = 10
    auth_type: Optional[str] = "none"
    auth_token: Optional[str] = None
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    api_key_header: Optional[str] = "X-API-Key"
    content_type: Optional[str] = "application/json"
    verify_ssl: Optional[bool] = True
    follow_redirects: Optional[bool] = True
    max_retries: Optional[int] = 3
    enable_templating: Optional[bool] = False


@router.get("")
async def http_client_health():
    """HTTP Client router health check"""
    return {
        "status": "healthy",
        "router": "http_client",
        "message": "HTTP Client API is operational"
    }


@router.post("/{node_id}/test")
async def test_http_client(node_id: str, test_request: HttpClientTestRequest):
    """
    Test HTTP Client node functionality
    
    Args:
        node_id: HTTP Client node ID
        test_request: HTTP request configuration
        
    Returns:
        HTTP response data and stats
    """
    logger.info(f"Testing HTTP Client node: {node_id}")
    
    try:
        # Create HTTP Client node instance
        http_client = HttpClientNode()
        
        # Prepare configuration from request
        config = {
            "method": test_request.method.upper(),
            "url": test_request.url,
            "timeout": test_request.timeout or 10
        }
        
        # Add optional parameters
        if test_request.headers:
            config["headers"] = json.dumps(test_request.headers)
            
        if test_request.body:
            config["body"] = test_request.body
            
        if test_request.auth_type and test_request.auth_type != "none":
            config["auth_type"] = test_request.auth_type
            
        if test_request.auth_token:
            config["auth_token"] = test_request.auth_token
            
        if test_request.auth_username:
            config["auth_username"] = test_request.auth_username
            
        if test_request.auth_password:
            config["auth_password"] = test_request.auth_password
            
        if test_request.api_key_header:
            config["api_key_header"] = test_request.api_key_header
            
        if test_request.content_type:
            config["content_type"] = test_request.content_type
            
        config["verify_ssl"] = test_request.verify_ssl
        config["follow_redirects"] = test_request.follow_redirects
        config["max_retries"] = test_request.max_retries
        config["enable_templating"] = test_request.enable_templating
        
        # Execute HTTP request in thread pool to avoid event loop conflicts
        def run_http_client():
            return http_client.execute(config, {})
        
        # Run in thread pool executor to avoid async/sync conflicts
        with ThreadPoolExecutor() as executor:
            result = await asyncio.get_event_loop().run_in_executor(executor, run_http_client)
        
        # Check if result is None or empty
        if not result:
            raise ValueError("HTTP Client returned empty result")
        
        logger.info(f"HTTP Client test successful: {node_id} -> {result.get('status_code')}")
        
        # Format response for UI (handle different response formats)
        response_time = 0
        if "response" in result and result["response"]:
            response_time = result["response"].get("duration_ms", 0) / 1000
        elif "request_stats" in result and result["request_stats"]:
            response_time = result["request_stats"].get("duration_ms", 0) / 1000
            
        response_data = {
            "success": result.get("success", False),
            "status_code": result.get("status_code"),
            "content": result.get("content"),
            "headers": result.get("headers", {}),
            "request_stats": result.get("request_stats", {}),
            "response_time": response_time,
            "node_id": node_id,
            "timestamp": result.get("request_stats", {}).get("timestamp"),
            "raw_result": result  # Include full result for debugging
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"HTTP Client test failed: {node_id} - {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"HTTP Client test failed: {str(e)}"
        )


@router.get("/{node_id}/stats")
async def get_http_client_stats(node_id: str):
    """
    Get HTTP Client node statistics
    
    Args:
        node_id: HTTP Client node ID
        
    Returns:
        Node statistics and configuration
    """
    return {
        "node_id": node_id,
        "node_type": "HttpClient",
        "status": "ready",
        "capabilities": {
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
            "auth_types": ["none", "bearer", "basic", "api_key"],
            "content_types": ["application/json", "application/xml", "text/plain", "application/x-www-form-urlencoded"],
            "features": ["templating", "ssl_verification", "redirects", "retries"]
        },
        "defaults": {
            "timeout": 10,
            "max_retries": 3,
            "verify_ssl": True,
            "follow_redirects": True
        }
    }