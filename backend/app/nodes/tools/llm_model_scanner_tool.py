"""Agent tool for automatic full model-security analysis."""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict

from app.nodes.security.llm_model_scanner_node import LLMModelScannerNode
from app.services.pickle_security_service import (
    DEFAULT_PICKLE_MAX_BYTES,
    PICKLE_ENGINE_VERSION,
)
from app.services.llm_model_scanner_service import (
    LLMModelScannerService,
    llm_model_scanner_service,
)
from app.services.model_artifact_analysis_service import (
    DEFAULT_MAX_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    installed_static_analysis_version,
)
from app.services.security_audit_service import present_security_result

from ..base import NodeOutput, NodePosition, NodeType, ProviderNode


class SecurityToolCallInput(BaseModel):
    """The tool accepts no agent-controlled scan or presentation settings."""

    model_config = ConfigDict(extra="forbid")


class LLMModelScannerToolNode(ProviderNode):
    """Expose the configured LLM model scanner as one Agent tool."""

    def __init__(self, service: LLMModelScannerService | None = None):
        super().__init__()
        self._service = service or llm_model_scanner_service
        self._metadata = {
            "name": "LLMModelScannerTool",
            "display_name": "LLM Model Scanner Tool",
            "description": (
                "Agent tool for fail-closed, zero-copy local/shared model scanning with "
                "managed-upload and MinIO fallbacks."
            ),
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "version": "2.0.0",
            "tags": [
                "tool",
                "security",
                "model",
                "artifact",
                "static_analysis",
                "pickle_security",
            ],
            "colors": ["orange-500", "red-600"],
            "icon": {
                "name": "llm_model_scanner_tool",
                "path": "icons/llm_model_scanner.svg",
                "alt": "LLM Model Scanner Tool",
            },
            "inputs": [],
            "outputs": [
                NodeOutput(
                    name="tool",
                    displayName="LLM Model Scanner Tool",
                    type="BaseTool",
                    description="Connect this single security tool to the Agent node's tools input.",
                    is_connection=True,
                    direction=NodePosition.TOP,
                )
            ],
            "properties": LLMModelScannerNode._properties(),
        }

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        user_data = self.user_data if isinstance(self.user_data, dict) else {}
        artifact = user_data.get("artifact_source")
        values = {
            "pickle_max_bytes": user_data.get("pickle_max_bytes")
            or DEFAULT_PICKLE_MAX_BYTES,
            "max_bytes": user_data.get("max_bytes") or DEFAULT_MAX_BYTES,
            "timeout_seconds": user_data.get("timeout_seconds")
            or DEFAULT_TIMEOUT_SECONDS,
        }

        def scan_llm_model() -> Dict[str, Any]:
            detailed = self._service.scan(
                artifact,
                credential_lookup=self.get_credential,
                owner_id=getattr(self, "user_id", None),
                **values,
            )
            return present_security_result(detailed, include_details=False)

        tool = StructuredTool.from_function(
            name="llm_model_scanner_tool",
            func=scan_llm_model,
            description=(
                "Automatically routes a configured model file, ZIP, or directory to every "
                "applicable security analysis and returns one strict, fail-closed decision. "
                "The Agent cannot replace the artifact, policy, or resource limits."
            ),
            args_schema=SecurityToolCallInput,
        )
        return {"tool": {"tool": tool}}

    def get_required_packages(self) -> list[str]:
        return [
            f"modelaudit=={installed_static_analysis_version()}",
            f"fickling=={PICKLE_ENGINE_VERSION}",
        ]


__all__ = ["LLMModelScannerToolNode"]
