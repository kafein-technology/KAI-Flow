"""
Compact HTTP Client Node - Streamlined HTTP Request Handler
==========================================================

A compact, efficient HTTP client node that provides essential HTTP request
capabilities while maintaining performance and usability. Designed for
both simple API calls and advanced HTTP operations.

Features:
- All HTTP methods (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
- Multiple authentication methods (Bearer, Basic, API Key)
- Template support with Jinja2
- Retry logic with configurable backoff
- SSL verification and certificate support
- Response validation and error handling
- Document output for downstream processing
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin, urlparse
import uuid

import httpx
from jinja2 import Environment, select_autoescape
from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableLambda, RunnableConfig

from app.nodes.base import NodeProperty, ProcessorNode, NodeInput, NodeOutput, NodeType, NodePosition, NodePropertyType

logger = logging.getLogger(__name__)

# HTTP constants
HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
CONTENT_TYPES = {
    "json": "application/json",
    "form": "application/x-www-form-urlencoded",
    "multipart": "multipart/form-data",
    "text": "text/plain",
    "xml": "application/xml",
}
AUTH_TYPES = ["none", "bearer", "basic", "api_key"]


class HttpRequestConfig:
    """Simplified HTTP request configuration."""

    def __init__(self, **kwargs):
        self.method = kwargs.get("method", "GET").upper()
        self.url = kwargs.get("url", "")
        self.headers = kwargs.get("headers", {})
        self.params = kwargs.get("params", {})
        self.body = kwargs.get("body")
        self.content_type = kwargs.get("content_type", "json")
        self.auth_type = kwargs.get("auth_type", "none")
        self.auth_token = kwargs.get("auth_token")
        self.auth_username = kwargs.get("auth_username")
        self.auth_password = kwargs.get("auth_password")
        self.timeout = int(kwargs.get("timeout", 30) or 30)
        self.verify_ssl = kwargs.get("verify_ssl", True)
        self.max_retries = int(kwargs.get("max_retries", 3) or 3)
        self.retry_delay = float(kwargs.get("retry_delay", 1) or 1)


class HttpResponse:
    """HTTP response model with essential data."""

    def __init__(self, status_code: int, headers: Dict[str, str], content: Union[Dict[str, Any], str, None],
                 is_json: bool, url: str, method: str, duration_ms: float, request_id: str):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.is_json = is_json
        self.url = url
        self.method = method
        self.duration_ms = duration_ms
        self.request_id = request_id
        self.timestamp = datetime.now(timezone.utc).isoformat()


class HttpClientNode(ProcessorNode):
    """Compact HTTP Client Node with streamlined functionality."""

    def __init__(self):
        super().__init__()
        self.jinja_env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._metadata = {
            "name": "HttpRequest",
            "display_name": "HTTP Client",
            "description": "Send HTTP requests with authentication, templating, and comprehensive response handling.",
            "category": "Tool",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "globe", "path": None, "alt": None},
            "colors": ["blue-500", "purple-600"],

            # Core inputs
            "inputs": [
                NodeInput(name="method", type="select", description="HTTP method", default="GET", required=True),
                NodeInput(name="url", type="text", description="Target URL (supports templating)", required=True, is_connection=True, direction=NodePosition.LEFT),
                NodeInput(name="headers", type="json", description="Request headers", default="{}"),
                NodeInput(name="params", type="json", description="URL parameters", default="{}"),
                NodeInput(name="body", type="textarea", description="Request body (supports templating)"),
                NodeInput(name="auth_type", type="select", description="Authentication method", default="none"),
                NodeInput(name="auth_token", type="password", description="Auth token/API key"),
                NodeInput(name="timeout", type="number", description="Request timeout (seconds)", default=30),
                NodeInput(name="template_context", type="dict", description="Context for templating"),
            ],

            # Core outputs
            "outputs": [
                NodeOutput(name="response", type="dict", description="Complete HTTP response",
                           is_connection=True, direction=NodePosition.RIGHT),
                NodeOutput(name="status_code", type="number", description="HTTP status code"),
                NodeOutput(name="content", type="any", description="Response content"),
                NodeOutput(name="headers", type="dict", description="Response headers"),
                NodeOutput(name="success", type="boolean", description="Request success status"),
                NodeOutput(name="documents", type="list", description="Response as Documents"),
            ],

            # Compact property definitions
            "properties": [
                # Basic Configuration
                NodeProperty(name="url", displayName="URL", type=NodePropertyType.TEXT, required=True,
                             placeholder="https://api.example.com/endpoint", tabName="basic"),
                NodeProperty(name="method", displayName="HTTP Method", type=NodePropertyType.SELECT,
                             default="GET", options=[
                        {"label": "GET - Retrieve", "value": "GET"},
                        {"label": "POST - Create", "value": "POST"},
                        {"label": "PUT - Update", "value": "PUT"},
                        {"label": "PATCH - Partial", "value": "PATCH"},
                        {"label": "DELETE - Remove", "value": "DELETE"},
                    ], tabName="basic"),
                NodeProperty(name="content_type", displayName="Content Type", type=NodePropertyType.SELECT,
                             default="application/json", options=[
                        {"label": "JSON", "value": "application/json"},
                        {"label": "Form Data", "value": "application/x-www-form-urlencoded"},
                        {"label": "Plain Text", "value": "text/plain"},
                    ], tabName="basic"),

                # Authentication
                NodeProperty(name="auth_type", displayName="Authentication", type=NodePropertyType.SELECT,
                             default="none", options=[
                        {"label": "None", "value": "none"},
                        {"label": "Bearer Token", "value": "bearer"},
                        {"label": "Basic Auth", "value": "basic"},
                        {"label": "API Key", "value": "api_key"},
                    ], tabName="auth"),
                NodeProperty(name="auth_token", displayName="Token/Key", type=NodePropertyType.PASSWORD,
                             placeholder="Bearer token or API key", tabName="auth"),
                NodeProperty(name="auth_username", displayName="Username", type=NodePropertyType.TEXT, tabName="auth"),
                NodeProperty(name="auth_password", displayName="Password", type=NodePropertyType.PASSWORD,
                             tabName="auth"),

                # Advanced Options
                NodeProperty(name="timeout", displayName="Timeout (s)", type=NodePropertyType.NUMBER,
                             min=1, max=300, default=30, tabName="advanced"),
                NodeProperty(name="max_retries", displayName="Max Retries", type=NodePropertyType.NUMBER,
                             min=0, max=10, default=3, tabName="advanced"),
                NodeProperty(name="retry_delay", displayName="Retry Delay (s)", type=NodePropertyType.NUMBER,
                             min=1, max=1000, default=1, tabName="advanced"),
                NodeProperty(name="verify_ssl", displayName="Verify SSL", type=NodePropertyType.CHECKBOX,
                             default=True, tabName="advanced"),
                NodeProperty(name="enable_templating", displayName="Enable Templates", type=NodePropertyType.CHECKBOX,
                             default=True, tabName="advanced"),

                # Headers & Body
                NodeProperty(name="custom_headers", displayName="Custom Headers", type=NodePropertyType.TEXT_AREA,
                             placeholder='{"X-Custom": "value"}', rows=3, tabName="data"),
                NodeProperty(name="url_params", displayName="URL Parameters", type=NodePropertyType.TEXT_AREA,
                             placeholder='{"key": "value"}', rows=2, tabName="data"),
                NodeProperty(name="request_body", displayName="Request Body", type=NodePropertyType.TEXT_AREA,
                             placeholder="Request body content", rows=4, tabName="data"),
            ]
        }

    def get_required_packages(self) -> list[str]:
        """Required packages for HTTP client functionality."""
        return [
            "httpx>=0.25.0",
            "jinja2>=3.1.0",
            "pydantic>=2.5.0"
        ]

    def _render_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render Jinja2 template with context."""
        try:
            template = self.jinja_env.from_string(template_str)
            return template.render(**context)
        except Exception as e:
            logger.warning(f"Template rendering failed: {e}")
            return template_str

    def _parse_json_field(self, field_value: Any, default: Dict = None) -> Dict:
        """Parse JSON field safely."""
        if default is None:
            default = {}

        if not field_value:
            return default

        if isinstance(field_value, dict):
            return field_value

        if isinstance(field_value, str):
            try:
                return json.loads(field_value) if field_value.strip() else default
            except json.JSONDecodeError:
                return default

        return default

    def _prepare_request_config(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> HttpRequestConfig:
        """Prepare HTTP request configuration from inputs."""
        # Parse complex fields
        headers = self._parse_json_field(inputs.get("custom_headers", inputs.get("headers", "{}")))
        params = self._parse_json_field(inputs.get("url_params", inputs.get("params", "{}")))

        # Apply templating if enabled
        if inputs.get("enable_templating", True):
            url = self._render_template(inputs.get("url", ""), context)
            body = self._render_template(inputs.get("request_body", inputs.get("body", "")), context)
        else:
            url = inputs.get("url", "")
            body = inputs.get("request_body", inputs.get("body"))

        return HttpRequestConfig(
            method=inputs.get("method", "GET"),
            url=url,
            headers=headers,
            params=params,
            body=body,
            content_type=inputs.get("content_type", "application/json"),
            auth_type=inputs.get("auth_type", "none"),
            auth_token=inputs.get("auth_token"),
            auth_username=inputs.get("auth_username"),
            auth_password=inputs.get("auth_password"),
            timeout=int(inputs.get("timeout", 30) or 30),
            verify_ssl=inputs.get("verify_ssl", True),
            max_retries=int(inputs.get("max_retries", 3) or 3),
            retry_delay=float(inputs.get("retry_delay", 1) or 1)
        )

    def _prepare_headers_and_auth(self, config: HttpRequestConfig) -> tuple[Dict[str, str], Optional[httpx.Auth]]:
        """Prepare headers and authentication for request."""
        headers = config.headers.copy()

        # Set content type
        if config.content_type in CONTENT_TYPES:
            headers["Content-Type"] = CONTENT_TYPES[config.content_type]

        # Add authentication
        auth = None
        if config.auth_type == "bearer" and config.auth_token:
            headers["Authorization"] = f"Bearer {config.auth_token}"
        elif config.auth_type == "api_key" and config.auth_token:
            headers["X-API-Key"] = config.auth_token
        elif config.auth_type == "basic" and config.auth_username and config.auth_password:
            auth = httpx.BasicAuth(config.auth_username, config.auth_password)

        # Add user agent
        headers.setdefault("User-Agent", "KAI-Fusion-HttpRequest/1.0")

        return headers, auth

    async def _make_http_request(self, config: HttpRequestConfig, context: Dict[str, Any]) -> HttpResponse:
        """Execute HTTP request with comprehensive error handling."""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Validate URL
        parsed_url = urlparse(config.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL: {config.url}")

        # Prepare request components
        headers, auth = self._prepare_headers_and_auth(config)

        # Prepare body based on content type
        body = None
        if config.body and config.method in ["POST", "PUT", "PATCH"]:
            if config.content_type == "json":
                try:
                    body = json.loads(config.body) if isinstance(config.body, str) else config.body
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in request body: {e}")
            else:
                body = config.body

        # Configure httpx client
        client_config = {
            "timeout": httpx.Timeout(config.timeout),
            "verify": config.verify_ssl,
        }
        if auth:
            client_config["auth"] = auth

        logger.info(f"Making {config.method} request to {config.url}")

        try:
            async with httpx.AsyncClient(**client_config) as client:
                request_kwargs = {
                    "method": config.method,
                    "url": config.url,
                    "headers": headers,
                    "params": config.params,
                }

                # Add body for supported methods
                if body is not None:
                    if config.content_type == "json":
                        request_kwargs["json"] = body
                    else:
                        request_kwargs["content"] = body

                response = await client.request(**request_kwargs)

                # Process response
                duration_ms = (time.time() - start_time) * 1000

                # Parse content
                content = None
                is_json = False
                content_type_header = response.headers.get("content-type", "").lower()

                if "application/json" in content_type_header:
                    try:
                        content = response.json()
                        is_json = True
                    except ValueError:
                        content = response.text
                else:
                    content = response.text

                return HttpResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    content=content,
                    is_json=is_json,
                    url=str(response.url),
                    method=config.method,
                    duration_ms=duration_ms,
                    request_id=request_id
                )

        except httpx.TimeoutException:
            raise ValueError(f"Request timeout after {config.timeout} seconds")
        except httpx.NetworkError as e:
            raise ValueError(f"Network error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Request failed: {str(e)}")

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request with retry logic and error handling."""
        logger.info("Executing HTTP Request")

        try:
            # Resolve URL (connection-first compatibility)
            resolved_url = inputs.get("url")

            if not resolved_url:
                # Prefer connected_nodes for connection-based URL wiring
                resolved_url = (
                    connected_nodes.get("url")
                    or connected_nodes.get("Target Url")
                    or connected_nodes.get("Target URL")
                    or connected_nodes.get("target_url")
                )

            if isinstance(resolved_url, dict):
                # If a node passes a structured payload, try common keys
                resolved_url = resolved_url.get("url") or resolved_url.get("value")

            if not resolved_url:
                # Final fallback: allow manually configured URL stored on the node instance
                node_user_data = getattr(self, "user_data", {}) or {}
                if isinstance(node_user_data, dict):
                    resolved_url = node_user_data.get("url") or node_user_data.get("Target Url") or node_user_data.get("target_url")

            if resolved_url and not inputs.get("url"):
                # Avoid mutating upstream dicts
                inputs = dict(inputs)
                inputs["url"] = resolved_url

            # Get template context
            template_context = connected_nodes.get("template_context", {})
            if not isinstance(template_context, dict):
                template_context = {}

            # Add execution context
            template_context.update({
                "inputs": inputs,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": str(uuid.uuid4()),
            })

            # Prepare request configuration
            config = self._prepare_request_config(inputs, template_context)

            # Retry logic
            max_retries = config.max_retries
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    # Execute request (run async in sync context)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        response = loop.run_until_complete(
                            self._make_http_request(config, template_context)
                        )
                    finally:
                        loop.close()

                    # Check success
                    success = 200 <= response.status_code < 300

                    # Create response document for downstream processing
                    http_document = Document(
                        page_content=str(response.content),
                        metadata={
                            "source": "http_client",
                            "url": config.url,
                            "method": config.method,
                            "status_code": response.status_code,
                            "headers": response.headers,
                            "timestamp": response.timestamp,
                            "request_id": response.request_id,
                            "duration_ms": response.duration_ms,
                            "content_type": response.headers.get("content-type", "text/plain"),
                        }
                    )

                    return {
                        "response": {
                            "status_code": response.status_code,
                            "headers": response.headers,
                            "content": response.content,
                            "is_json": response.is_json,
                            "url": response.url,
                            "method": response.method,
                            "duration_ms": response.duration_ms,
                            "request_id": response.request_id,
                            "timestamp": response.timestamp,
                        },
                        "status_code": response.status_code,
                        "content": response.content,
                        "headers": response.headers,
                        "success": success,
                        "documents": [http_document],
                    }

                except Exception as e:
                    last_error = str(e)

                    if attempt < max_retries:
                        logger.warning(
                            f"HTTP request failed (attempt {attempt + 1}/{max_retries + 1}): {last_error}")
                        time.sleep(config.retry_delay)
                    else:
                        logger.error(f"HTTP request failed after {max_retries + 1} attempts: {last_error}")

            # All retries failed
            raise ValueError(f"HTTP request failed after {max_retries + 1} attempts: {last_error}")

        except Exception as e:
            error_msg = f"HTTP Request execution failed: {str(e)}"
            logger.error(error_msg)
            # Re-raise so the error propagates and execution is marked as "failed"
            raise RuntimeError(error_msg) from e

    def as_runnable(self) -> Runnable:
        """Convert to LangChain Runnable for composition."""
        config = None
        if os.getenv("LANGCHAIN_TRACING_V2"):
            config = RunnableConfig(
                run_name="HttpRequest",
                tags=["http", "api", "external"]
            )

        runnable = RunnableLambda(
            lambda params: self.execute(
                inputs=params.get("inputs", {}),
                connected_nodes=params.get("connected_nodes", {})
            ),
            name="HttpRequest"
        )

        if config:
            runnable = runnable.with_config(config)

        return runnable


__all__ = ["HttpClientNode", "HttpRequestConfig", "HttpResponse"]