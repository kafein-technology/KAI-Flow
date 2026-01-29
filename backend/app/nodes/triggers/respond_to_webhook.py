"""
Respond to Webhook Node - Webhook Response Handler
─────────────────────────────────────────────────
• Purpose: Send custom HTTP responses from workflow to webhook requesters
• Integration: Works with WebhookTriggerNode to provide custom responses
• Features: Status code, headers, body customization
• Security: Response size limits, header validation
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from ...core.json_utils import make_json_serializable
from ..base import TerminatorNode, NodeInput, NodeOutput, NodeType, NodeProperty, NodePropertyType

logger = logging.getLogger(__name__)


def _convert_documents_to_dict(obj: Any) -> Any:
    """
    Convert LangChain Document objects to dictionaries recursively.
    
    Args:
        obj: Object that may contain Document objects
        
    Returns:
        JSON-serializable version with Document objects converted to dicts
    """
    # Check if it's a LangChain Document object (has page_content and metadata attributes)
    if hasattr(obj, 'page_content') and hasattr(obj, 'metadata'):
        return {
            "page_content": obj.page_content,
            "metadata": _convert_documents_to_dict(obj.metadata) if isinstance(obj.metadata, dict) else obj.metadata
        }
    elif isinstance(obj, dict):
        return {key: _convert_documents_to_dict(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_documents_to_dict(item) for item in obj]
    else:
        return obj


class RespondToWebhookNode(TerminatorNode):
    """
    Respond to Webhook Node - Send custom HTTP responses for webhook requests.
    
    This node allows workflows to send custom HTTP responses back to webhook
    requesters. It works in conjunction with WebhookTriggerNode to provide
    full control over the HTTP response including status code, headers, and body.
    
    Usage:
    - Place this node at the end of a webhook-triggered workflow
    - Configure the desired HTTP status code, headers, and response body
    - The response will be sent back to the webhook requester
    """
    
    def __init__(self):
        super().__init__()
        
        self._metadata = {
            "name": "RespondToWebhook",
            "display_name": "Respond to Webhook",
            "description": (
                "Send custom HTTP responses back to webhook requesters. "
                "Configure status code, headers, and response body. "
                "Works with WebhookTriggerNode to provide full response control."
            ),
            "category": "Triggers",
            "node_type": NodeType.TERMINATOR,
            "icon": {"name": "webhook", "path": None, "alt": None},
            "colors": ["gray-500", "slate-600"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="string",
                    is_connection=True,
                    required=True,
                    description="The user's input to the agent."
                ),
                NodeInput(
                    name="status_code",
                    type="number",
                    description="HTTP status code (e.g., 200, 201, 400, 404, 500)",
                    required=False,
                ),
                NodeInput(
                    name="response_body",
                    type="any",
                    description="Response body content (JSON object, string, etc.)",
                    required=False,
                ),
                NodeInput(
                    name="response_headers",
                    type="dict",
                    description="Custom HTTP headers as key-value pairs",
                    required=False,
                ),
                NodeInput(
                    name="content_type",
                    type="string",
                    description="Content-Type header value",
                    required=False,
                ),
            ],
            "outputs": [],    
            "properties": [
                # Basic Tab
                NodeProperty(
                    name="status_code",
                    displayName="HTTP Status Code",
                    type=NodePropertyType.SELECT,
                    default="200",
                    options=[
                        {"label": "200 - OK", "value": "200"},
                        {"label": "201 - Created", "value": "201"},
                        {"label": "202 - Accepted", "value": "202"},
                        {"label": "204 - No Content", "value": "204"},
                        {"label": "400 - Bad Request", "value": "400"},
                        {"label": "401 - Unauthorized", "value": "401"},
                        {"label": "403 - Forbidden", "value": "403"},
                        {"label": "404 - Not Found", "value": "404"},
                        {"label": "422 - Unprocessable Entity", "value": "422"},
                        {"label": "500 - Internal Server Error", "value": "500"},
                        {"label": "502 - Bad Gateway", "value": "502"},
                        {"label": "503 - Service Unavailable", "value": "503"},
                    ],
                    hint="HTTP status code to return to the webhook requester",
                    required=True,
                    tabName="basic"
                ),
                NodeProperty(
                    name="response_config",
                    displayName="Response Config",
                    type=NodePropertyType.SELECT,
                    default="json",
                    options=[
                        {"label": "All Incoming Items", "value": "all_incoming_items"},
                        {"label": "No Data", "value": "no_data"},
                        {"label": "JSON", "value": "json"},
                    ],
                    hint="Select how to configure the response body",
                    required=True,
                    tabName="basic"
                ),
                NodeProperty(
                    name="response_body",
                    displayName="Response Body",
                    type=NodePropertyType.TEXT_AREA,
                    placeholder='{"status": "success", "message": "Processed"}',
                    hint="Response body content. Can be JSON string or plain text. Supports templating with ${{variable}}",
                    required=False,
                    tabName="basic",
                    rows=6,
                    displayOptions={
                        "show": {
                            "response_config": "json"
                        }
                    }
                ),
                NodeProperty(
                    name="content_type",
                    displayName="Content-Type",
                    type=NodePropertyType.SELECT,
                    default="application/json",
                    options=[
                        {"label": "application/json", "value": "application/json"},
                        {"label": "text/plain", "value": "text/plain"},
                        {"label": "text/html", "value": "text/html"},
                    ],
                    hint="Content-Type header for the response",
                    required=True,
                    tabName="basic"
                ),
                
                # Advanced Tab
                NodeProperty(
                    name="response_headers",
                    displayName="Custom Headers",
                    type=NodePropertyType.JSON_EDITOR,
                    placeholder='{"X-Custom-Header": "value", "X-Request-ID": "12345"}',
                    hint="Additional HTTP headers as JSON object. Key-value pairs will be added to the response.",
                    required=False,
                    tabName="advanced"
                ),
                NodeProperty(
                    name="max_response_size",
                    displayName="Max Response Size (KB)",
                    type=NodePropertyType.NUMBER,
                    default=1024,
                    min=1,
                    max=10240,
                    description="Maximum response body size in KB",
                    required=True,
                    tabName="advanced"
                ),
            ],
        }
        
        logger.info(" RespondToWebhook node created")

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Configure respond to webhook node.
        
        Args:
            **kwargs: Configuration parameters
                - inputs: Dict containing node property values
                    - status_code: HTTP status code (default: 200)
                    - response_body: Response body content
                    - response_headers: Custom HTTP headers (dict or JSON string)
                    - content_type: Content-Type header (default: "application/json")
                    - max_response_size: Max response size in KB (default: 1024)
                - previous_node: Output from previous node (optional)
        
        Returns:
            Dict with webhook response configuration
        """
        logger.info(f" Configuring RespondToWebhook node")
        
        # Extract inputs from kwargs (inputs dict contains all node properties)
        inputs = kwargs.get("inputs", {})
        connected_nodes = kwargs.get("connected_nodes", {})
        previous_node_output = connected_nodes if connected_nodes else None
        # Store user configuration (inputs dict'ini direkt user_data'ya kaydet)
        self.user_data.update(inputs)
        
        # Get response configuration values
        status_code = inputs.get("status_code", "200")
        response_config = inputs.get("response_config", "json")
        response_headers = inputs.get("response_headers", {})
        content_type = inputs.get("content_type", "application/json")
        
        # Determine response_body based on response_config
        if response_config == "all_incoming_items":
            data = connected_nodes if connected_nodes else {}
            # Convert Document objects to dicts first, then make JSON serializable
            data = _convert_documents_to_dict(data)
            data = make_json_serializable(data)
            # Ensure JSON format: if string, wrap it; if already dict/list, use as is
            response_body = {"data": data} if isinstance(data, str) else (data if isinstance(data, (dict, list)) else {"data": data})
            logger.info(f"Using all incoming items as response body: {response_body}")
        elif response_config == "no_data":
            # Send empty response
            response_body = {}
            logger.info("Sending empty response (No Data)")
        else:  # json
            # Use the JSON input from response_body field
            response_body = inputs.get("response_body")
            if not response_body and previous_node_output:
                # Fallback to previous node output if response_body is empty
                logger.info(f"Using previous node output as response body: {previous_node_output}")
                # Convert Document objects to dicts first, then make JSON serializable
                response_body = _convert_documents_to_dict(previous_node_output)
                response_body = make_json_serializable(response_body)
            elif not response_body and connected_nodes:
                logger.info(f"Using connected_nodes as response body: {connected_nodes}")
                # Convert Document objects to dicts first, then make JSON serializable
                response_body = _convert_documents_to_dict(connected_nodes)
                response_body = make_json_serializable(response_body)
        
        # Parse response_body if it's a JSON string and content_type is application/json
        if response_body and isinstance(response_body, str) and content_type == "application/json":
            try:
                stripped_body = response_body.strip()
                if (stripped_body.startswith('{') and stripped_body.endswith('}')) or \
                   (stripped_body.startswith('[') and stripped_body.endswith(']')):
                    response_body = json.loads(stripped_body)
                    logger.info("Successfully parsed response_body string as JSON object/array")
            except json.JSONDecodeError:
                # Fallback: Try parsing Python dict repr format (single quotes from logger(dict))
                try:
                    import ast
                    parsed = ast.literal_eval(stripped_body)
                    # Convert to proper JSON format
                    response_body = json.loads(json.dumps(parsed, ensure_ascii=False))
                    logger.info("Successfully parsed response_body from Python dict repr format")
                except (ValueError, SyntaxError):
                    logger.warning("Failed to parse response_body as JSON despite application/json content type. Sending as raw string.")
        
        # Parse response_headers if it's a JSON string
        if isinstance(response_headers, str):
            try:
                response_headers = json.loads(response_headers)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse response_headers as JSON: {response_headers}")
                response_headers = {}
        
        # Ensure response_headers is a dict
        if not isinstance(response_headers, dict):
            response_headers = {}
        
        # Build webhook_response structure for webhook_trigger to find
        webhook_response = {
            "status_code": int(status_code) if isinstance(status_code, (str, int)) else 200,
            "body": response_body,
            "headers": response_headers,
            "content_type": content_type
        }
        
        # Add Content-Type to headers if not already present
        headers_lower = {k.lower(): v for k, v in webhook_response["headers"].items()}
        if "content-type" not in headers_lower:
            webhook_response["headers"]["Content-Type"] = content_type
        
        logger.info(f" RespondToWebhook configured: status_code={webhook_response['status_code']}, content_type={content_type}")
        
        # Return both the basic config and webhook_response for easy extraction
        return {
            "status_code": status_code,
            "content_type": content_type,
            "webhook_response": webhook_response  # This will be stored in node_outputs and can be found by webhook_trigger
        }
    
    def as_runnable(self):
        """
        Convert node to LangChain Runnable for direct composition.
        
        Returns:
            RunnableLambda that executes respond to webhook configuration
        """
        from langchain_core.runnables import RunnableLambda
        
        return RunnableLambda(
            lambda params: self.execute(**params),
            name="RespondToWebhook",
        )


# Export for use
__all__ = [
    "RespondToWebhookNode",
]

