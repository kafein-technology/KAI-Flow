"""Expose selected remote MCP tools to KAI-Flow agents."""

from __future__ import annotations

from typing import Any

from .mcp_common import build_agent_tools, list_mcp_tools, parse_mcp_config, run_mcp_sync
from ..base import NodeInput, NodeOutput, NodePosition, NodeProperty, NodePropertyType, NodeType, ProviderNode


class McpClientToolNode(ProviderNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "McpClientTool",
            "display_name": "MCP Client Tool",
            "description": "Connect selected MCP server tools to an Agent's Tools input.",
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "colors": ["teal-500", "cyan-600"],
            "icon": {"name": "mcp", "path": "icons/mcp.svg", "alt": "MCP Client Tool"},
            "inputs": [
                NodeInput(name=name, displayName=name.replace("_", " ").title(), type="str",
                          description="MCP tool configuration", required=False, is_connection=False)
                for name in ("endpoint_url", "transport", "credential_id",
                             "include", "include_tools", "exclude_tools", "timeout_ms")
            ],
            "outputs": [NodeOutput(name="tools", displayName="Tools", type="Sequence[BaseTool]",
                                   is_connection=True, direction=NodePosition.TOP,
                                   description="Connect to an Agent's Tools input.")],
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
                NodeProperty(name="include", displayName="Tools to Include", type=NodePropertyType.SELECT,
                             default="all", options=[
                                 {"label": "All", "value": "all"},
                                 {"label": "Selected", "value": "selected"},
                                 {"label": "All Except", "value": "except"},
                             ]),
                NodeProperty(name="include_tools", displayName="Tools to Include", type=NodePropertyType.DYNAMIC_SELECT,
                             multiple=True, optionsMethod="load_tools", optionsDependsOn=["endpoint_url"],
                             optionsOptionalDependsOn=["transport", "credential_id"],
                             displayOptions={"show": {"include": "selected"}}),
                NodeProperty(name="exclude_tools", displayName="Tools to Exclude", type=NodePropertyType.DYNAMIC_SELECT,
                             multiple=True, optionsMethod="load_tools", optionsDependsOn=["endpoint_url"],
                             optionsOptionalDependsOn=["transport", "credential_id"],
                             displayOptions={"show": {"include": "except"}}),
                NodeProperty(name="timeout_ms", displayName="Timeout (ms)", type=NodePropertyType.NUMBER,
                             default=60000, min=1, max=300000, tabName="advanced"),
            ],
        }

    def get_required_packages(self) -> list[str]:
        return ["mcp==2.3.0", "httpx2>=2.10.0", "jsonschema>=4.20.0"]

    def load_tools(self, values: dict[str, Any]) -> list[dict[str, str]]:
        config = parse_mcp_config(values, self.get_credential)
        return [{"label": str(tool["name"]), "value": str(tool["name"]),
                 "description": str(tool.get("description") or "")}
                for tool in run_mcp_sync(lambda: list_mcp_tools(config))]

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        user_data = self.user_data or {}
        nested_inputs = user_data.get("inputs")
        values = {
            **user_data,
            **(nested_inputs if isinstance(nested_inputs, dict) else {}),
            **kwargs,
        }
        config = parse_mcp_config(values, self.get_credential)
        all_tools = run_mcp_sync(lambda: list_mcp_tools(config))
        include = values.get("include", "all")
        if include not in ("all", "selected", "except"):
            raise ValueError("Tools to Include must be All, Selected, or All Except.")
        def selected(key: str) -> set[str]:
            raw = values.get(key) or ""
            if isinstance(raw, list):
                return {str(part).strip() for part in raw if str(part).strip()}
            return {part.strip() for part in str(raw).split(",") if part.strip()}
        names = selected("include_tools" if include == "selected" else "exclude_tools")
        if include == "selected":
            all_tools = [tool for tool in all_tools if tool["name"] in names]
        elif include == "except":
            all_tools = [tool for tool in all_tools if tool["name"] not in names]
        if not all_tools:
            raise ValueError("MCP server returned no tools for the selected filter.")
        node_name = str(values.get("node_name") or self.node_id or self._metadata["display_name"])
        return {"tools": build_agent_tools(config, node_name, all_tools)}
