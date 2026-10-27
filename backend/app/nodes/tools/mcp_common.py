"""Shared MCP client behavior for the standalone and agent-tool nodes."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, TypeVar
from urllib.parse import urlparse
import json
import re
import hashlib

import httpx2
from jsonschema import ValidationError, validate as validate_json_schema
from langchain_core.tools import StructuredTool, ToolException
from mcp.client import Client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client


T = TypeVar("T")


def run_mcp_sync(factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run SDK calls from sync node and option-loader methods."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(factory())).result()


@dataclass(frozen=True)
class McpConfig:
    endpoint_url: str
    transport: str = "httpStreamable"
    authentication: str = "none"
    credential: dict[str, Any] | None = None
    timeout_ms: int = 60000

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint_url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("MCP Endpoint URL must be an http:// or https:// URL without embedded credentials.")
        if self.transport not in ("httpStreamable", "sse"):
            raise ValueError("Server Transport must be HTTP Streamable or SSE.")
        if self.authentication not in ("none", "bearerAuth", "headerAuth", "multipleHeadersAuth", "mcpOAuth2Api"):
            raise ValueError("Unsupported MCP authentication method.")
        if not 1 <= self.timeout_ms <= 300000:
            raise ValueError("MCP timeout must be between 1 and 300000 ms.")
        if self.authentication != "none":
            if not self.credential:
                raise ValueError("Select an MCP credential for the chosen authentication method.")
            expected = self.credential.get("authentication")
            if expected != self.authentication:
                raise ValueError("The selected MCP credential uses a different authentication method.")
            allowed = self.credential.get("allowed_domains")
            if isinstance(allowed, str) and allowed.strip():
                domains = {part.strip().lower() for part in allowed.split(",") if part.strip()}
                if parsed.hostname.lower() not in domains:
                    raise ValueError("MCP endpoint host is not in the credential's allowed domains.")

    def headers(self) -> dict[str, str]:
        secret = self.credential or {}
        if self.authentication in ("bearerAuth", "mcpOAuth2Api"):
            token = secret.get("token") if self.authentication == "bearerAuth" else secret.get("access_token")
            if not isinstance(token, str) or not token.strip():
                raise ValueError("The selected MCP credential has no access token.")
            return {"Authorization": f"Bearer {token.strip()}"}
        if self.authentication == "headerAuth":
            name, value = secret.get("header_name"), secret.get("header_value")
            if not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
                raise ValueError("MCP credential has an invalid header name.")
            if not isinstance(value, str) or not value:
                raise ValueError("MCP credential has no header value.")
            return {name: value}
        if self.authentication == "multipleHeadersAuth":
            raw = secret.get("headers_json")
            try:
                headers = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError as exc:
                raise ValueError("MCP credential headers must be a JSON object.") from exc
            if not isinstance(headers, dict) or not headers:
                raise ValueError("MCP credential headers must be a nonempty JSON object.")
            if any(not isinstance(k, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", k)
                   or not isinstance(v, str) for k, v in headers.items()):
                raise ValueError("MCP credential headers must contain valid names and string values.")
            return headers
        return {}


def parse_mcp_config(values: dict[str, Any], credential_lookup: Callable[[str], Any]) -> McpConfig:
    credential_id = values.get("credential_id")
    credential = credential_lookup(str(credential_id)) if credential_id else None
    if credential_id and (not credential or credential.get("service_type") != "mcp"):
        raise ValueError("The selected MCP credential could not be found.")
    secret = credential.get("secret") if credential else None
    if credential and not isinstance(secret, dict):
        raise ValueError("The selected MCP credential has no valid secret.")
    raw_timeout = values.get("timeout_ms") or 60000
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("MCP timeout must be a whole number of milliseconds.") from exc
    return McpConfig(
        endpoint_url=str(values.get("endpoint_url") or ""),
        transport=str(values.get("transport") or "httpStreamable"),
        authentication=str(secret.get("authentication") or "") if credential else "none",
        credential=secret,
        timeout_ms=timeout,
    )


async def with_mcp_client(config: McpConfig, action: Callable[[Client], Coroutine[Any, Any, T]]) -> T:
    """Open a transport for one operation and always close it afterward."""
    headers = config.headers()
    timeout_seconds = config.timeout_ms / 1000
    try:
        if config.transport == "sse":
            transport = sse_client(config.endpoint_url, headers=headers, timeout=timeout_seconds)
            async with Client(transport) as client:
                return await action(client)
        async with httpx2.AsyncClient(
            headers=headers,
            timeout=httpx2.Timeout(timeout_seconds, read=timeout_seconds),
        ) as http_client:
            async with Client(streamable_http_client(config.endpoint_url, http_client=http_client)) as client:
                return await action(client)
    except ExceptionGroup as group:
        error: Exception = group
        while isinstance(error, ExceptionGroup) and len(error.exceptions) == 1:
            error = error.exceptions[0]
        raise error from group


async def list_mcp_tools(config: McpConfig) -> list[dict[str, Any]]:
    async def list_all(client: Client) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page = await client.list_tools(cursor=cursor)
            tools.extend(tool.model_dump(by_alias=True, exclude_none=True) for tool in page.tools)
            cursor = page.next_cursor
            if not cursor:
                return tools
            if cursor in seen_cursors:
                raise ValueError("MCP server repeated a tool-list cursor.")
            seen_cursors.add(cursor)
    return await with_mcp_client(config, list_all)


async def call_mcp_tool(config: McpConfig, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def call(client: Client) -> dict[str, Any]:
        result = await client.call_tool(name, arguments, read_timeout_seconds=config.timeout_ms / 1000)
        data = result.model_dump(by_alias=True, exclude_none=True)
        if result.is_error:
            message = next((part.text for part in result.content if getattr(part, "type", None) == "text"), None)
            raise ValueError(message or f'MCP tool "{name}" returned an error.')
        return data
    return await with_mcp_client(config, call)


def tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("MCP tool parameters must be a JSON object.") from exc
    if not isinstance(value, dict):
        raise ValueError("MCP tool parameters must be a JSON object.")
    return value


def validate_tool_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    try:
        validate_json_schema(instance=arguments, schema=schema)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.path)
        label = f"MCP parameter {location}" if location else "MCP parameters"
        raise ValueError(f"{label}: {exc.message}") from exc


def mcp_tool_name(node_name: str, tool_name: str) -> str:
    prefix = re.sub(r"[^a-zA-Z0-9_]", "_", node_name).strip("_") or "mcp"
    suffix = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name).strip("_") or "tool"
    if len(suffix) > 40:
        digest = hashlib.sha256(tool_name.encode("utf-8")).hexdigest()[:8]
        suffix = f"{suffix[:31]}_{digest}"
    return f"{prefix[:63 - len(suffix)]}_{suffix}"


def build_agent_tools(config: McpConfig, node_name: str, tools: list[dict[str, Any]]) -> list[StructuredTool]:
    result: list[StructuredTool] = []
    used_names: set[str] = set()
    for spec in tools:
        remote_name = str(spec["name"])
        local_name = mcp_tool_name(node_name, remote_name)
        if local_name in used_names:
            digest = hashlib.sha256(remote_name.encode("utf-8")).hexdigest()[:8]
            local_name = f"{local_name[:55]}_{digest}"
        if local_name in used_names:
            raise ValueError(f'Duplicate MCP tool name "{remote_name}".')
        used_names.add(local_name)
        schema = spec.get("inputSchema") or {"type": "object", "properties": {}}
        if not isinstance(schema, dict) or schema.get("type") != "object":
            schema = {"type": "object", "properties": {"value": schema}}

        async def invoke_remote(_name: str = remote_name, _schema: dict = schema, **kwargs: Any) -> Any:
            validate_tool_arguments(_schema, kwargs)
            try:
                response = await call_mcp_tool(config, _name, kwargs)
            except Exception as exc:
                raise ToolException(f'MCP tool "{_name}" failed: {exc}') from exc
            structured = response.get("structuredContent")
            return structured if structured is not None else response.get("content", [])

        def invoke_sync(_name: str = remote_name, _schema: dict = schema, **kwargs: Any) -> Any:
            validate_tool_arguments(_schema, kwargs)
            try:
                response = run_mcp_sync(lambda: call_mcp_tool(config, _name, kwargs))
            except Exception as exc:
                raise ToolException(f'MCP tool "{_name}" failed: {exc}') from exc
            structured = response.get("structuredContent")
            return structured if structured is not None else response.get("content", [])

        result.append(StructuredTool(
            name=local_name,
            description=str(spec.get("description") or f"Call the {remote_name} MCP tool"),
            args_schema=schema,
            func=invoke_sync,
            coroutine=invoke_remote,
            handle_tool_error=True,
        ))
    return result
