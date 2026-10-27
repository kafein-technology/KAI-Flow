"""Standalone MCP tool invocation node."""

from __future__ import annotations

from typing import Any
import json

from .mcp_common import (
    call_mcp_tool,
    list_mcp_tools,
    parse_mcp_config,
    run_mcp_sync,
    tool_arguments,
    validate_tool_arguments,
)
from ..base import NodeInput, NodeOutput, NodePosition, NodeProperty, NodePropertyType, NodeType, ProcessorNode


class McpClientNode(ProcessorNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "McpClient",
            "display_name": "MCP Client",
            "description": "Call a selected tool on an MCP server and pass its result to the workflow.",
            "category": "Integration",
            "node_type": NodeType.PROCESSOR,
            "colors": ["teal-500", "cyan-600"],
            "icon": {"name": "mcp", "path": "icons/mcp.svg", "alt": "MCP Client"},
            "inputs": [NodeInput(name="input", displayName="Input", type="any", required=False,
                                 is_connection=True, direction=NodePosition.LEFT,
                                 description="Optional workflow items to process with this MCP tool.")],
            "outputs": [NodeOutput(name="result", displayName="Result", type="dict", is_connection=True,
                                   direction=NodePosition.RIGHT, description="MCP tool response.")],
            "properties": [
                NodeProperty(name="credential_id", displayName="Credentials", type=NodePropertyType.CREDENTIAL_SELECT,
                             serviceType="mcp", required=False,
                             description="Select an MCP credential, or leave None for a server without authentication."),
                NodeProperty(name="transport", displayName="Server Transport", type=NodePropertyType.SELECT,
                             default="httpStreamable", options=[
                                 {"label": "HTTP Streamable", "value": "httpStreamable"},
                                 {"label": "Server Sent Events (Deprecated)", "value": "sse"},
                             ]),
                NodeProperty(name="endpoint_url", displayName="MCP Endpoint URL", type=NodePropertyType.TEXT,
                             placeholder="https://my-mcp-server.ai/mcp"),
                NodeProperty(name="tool", displayName="Tool", type=NodePropertyType.DYNAMIC_SELECT,
                             optionsMethod="load_tools", optionsDependsOn=["endpoint_url"],
                             optionsOptionalDependsOn=["transport", "credential_id"],
                             placeholder="Select or type an MCP tool name"),
                NodeProperty(name="input_mode", displayName="Input Mode", type=NodePropertyType.SELECT,
                             default="manual", options=[
                                 {"label": "Manual", "value": "manual"},
                                 {"label": "JSON", "value": "json"},
                             ]),
                NodeProperty(name="parameters", displayName="Parameters", type=NodePropertyType.MCP_PARAMETERS,
                             default="{}", optionsMethod="load_tool_schema",
                             displayOptions={"show": {"input_mode": "manual"}}),
                NodeProperty(name="json_input", displayName="JSON", type=NodePropertyType.JSON_EDITOR,
                             default="{}", displayOptions={"show": {"input_mode": "json"}}),
                NodeProperty(name="convert_to_binary", displayName="Convert Images and Audio to Binary",
                             type=NodePropertyType.CHECKBOX, default=True, tabName="advanced",
                             description="Place base64 media in the binary output instead of content."),
                NodeProperty(name="timeout_ms", displayName="Timeout (ms)", type=NodePropertyType.NUMBER,
                             default=60000, min=1, max=300000, tabName="advanced"),
                NodeProperty(name="continue_on_fail", displayName="Continue on Failure", type=NodePropertyType.CHECKBOX,
                             default=False, tabName="advanced"),
            ],
        }

    def get_required_packages(self) -> list[str]:
        return ["mcp==2.3.0", "httpx2>=2.10.0", "jsonschema>=4.20.0"]

    def load_tools(self, values: dict[str, Any]) -> list[dict[str, str]]:
        config = parse_mcp_config(values, self.get_credential)
        return [
            {"label": str(tool["name"]), "value": str(tool["name"]),
             "description": str(tool.get("description") or "")}
            for tool in run_mcp_sync(lambda: list_mcp_tools(config))
        ]

    def load_tool_schema(self, values: dict[str, Any]) -> dict[str, Any]:
        name = str(values.get("tool") or "").strip()
        if not name:
            return {"type": "object", "properties": {}}
        config = parse_mcp_config(values, self.get_credential)
        tool = next((item for item in run_mcp_sync(lambda: list_mcp_tools(config)) if item["name"] == name), None)
        if tool is None:
            raise ValueError(f'MCP tool "{name}" was not found on the server.')
        return tool.get("inputSchema") or {"type": "object", "properties": {}}

    def execute(self, inputs: dict[str, Any], connected_nodes: dict[str, Any]) -> dict[str, Any]:
        values = {**(self.user_data or {}), **inputs}
        config = parse_mcp_config(values, self.get_credential)
        name = str(values.get("tool") or "").strip()
        if not name:
            raise ValueError("Select an MCP tool to call.")
        tool = next((item for item in run_mcp_sync(lambda: list_mcp_tools(config)) if item["name"] == name), None)
        schema = (tool.get("inputSchema") or {"type": "object", "properties": {}}) if tool else None
        source = connected_nodes.get("input")
        items = source if isinstance(source, list) else [source]
        results: list[dict[str, Any]] = []
        for index, _item in enumerate(items):
            try:
                if tool is None:
                    raise ValueError(f'MCP tool "{name}" was not found on the server.')
                mode = values.get("input_mode", "manual")
                if mode not in ("manual", "json"):
                    raise ValueError("Input Mode must be Manual or JSON.")
                arguments = tool_arguments(values.get("parameters" if mode == "manual" else "json_input") or "{}")
                validate_tool_arguments(schema, arguments)
                response = run_mcp_sync(lambda: call_mcp_tool(config, name, arguments))
                content: list[dict[str, Any]] = []
                binary: dict[str, dict[str, str]] = {}
                for part in response.get("content", []):
                    if part.get("type") == "text":
                        text = part.get("text", "")
                        try:
                            text = json.loads(text)
                        except (TypeError, json.JSONDecodeError):
                            pass
                        content.append({**part, "text": text})
                    elif values.get("convert_to_binary", True) and part.get("type") in ("image", "audio"):
                        binary[f"data_{len(binary)}"] = {"data": part.get("data", ""), "mimeType": part.get("mimeType", "")}
                    else:
                        content.append(part)
                result: dict[str, Any] = {"content": content, "pairedItem": {"item": index}}
                if response.get("structuredContent") is not None:
                    result["structuredContent"] = response["structuredContent"]
                if binary:
                    result["binary"] = binary
                results.append(result)
            except Exception as exc:
                if not values.get("continue_on_fail", False):
                    raise
                results.append({"error": {"message": str(exc)}, "pairedItem": {"item": index}})
        return {"result": results[0] if len(results) == 1 else results}
