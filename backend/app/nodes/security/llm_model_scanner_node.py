"""Automatic full-scan node for model artifact security analysis."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict

from app.services.model_artifact_analysis_service import (
    DEFAULT_MAX_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_MAX_BYTES,
    installed_static_analysis_version,
)
from app.services.llm_model_scanner_service import (
    LLMModelScannerService,
    llm_model_scanner_service,
)
from app.services.pickle_security_service import (
    DEFAULT_PICKLE_MAX_BYTES,
    MAX_PICKLE_MEMORY_BYTES,
    PICKLE_ENGINE_VERSION,
)
from app.services.security_audit_service import present_security_result

from ..base import (
    NodeInput,
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProcessorNode,
)


class LLMModelScannerNode(ProcessorNode):
    """Scan one local/shared, managed-upload, or MinIO model source."""

    def __init__(self, service: LLMModelScannerService | None = None):
        super().__init__()
        self._service = service or llm_model_scanner_service
        self._metadata = {
            "name": "LLMModelScanner",
            "display_name": "LLM Model Scanner",
            "description": (
                "Scans a model file, ZIP, or directory in place when a local/shared "
                "path is available, with managed upload and MinIO fallbacks."
            ),
            "category": "Security",
            "node_type": NodeType.PROCESSOR,
            "version": "2.0.0",
            "tags": [
                "security",
                "model",
                "static_analysis",
                "pickle_security",
                "gate",
            ],
            "colors": ["orange-500", "red-600"],
            "icon": {
                "name": "llm_model_scanner",
                "path": "icons/llm_model_scanner.svg",
                "alt": "LLM Model Scanner",
            },
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="any",
                    description="Optional upstream workflow input; never interpreted as model content.",
                    is_connection=True,
                    required=False,
                    direction=NodePosition.LEFT,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="Dict[str, Any]",
                    description="Stable security decision, scanner summaries, and one findings list.",
                    format="json",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
            ],
            "properties": self._properties(),
        }

    @staticmethod
    def _properties() -> list[NodeProperty]:
        return [
            NodeProperty(
                name="artifact_source",
                displayName="Model Path",
                type=NodePropertyType.MODEL_ARTIFACT_SOURCE,
                default={
                    "source_type": "path",
                    "storage": "local_path",
                    "path": "",
                },
                description=(
                    "Enter an approved absolute path visible to the scan service for "
                    "zero-copy file, ZIP, or directory scanning; or use the browser-upload "
                    "and MinIO fallbacks."
                ),
                required=True,
                tabName="basic",
            ),
            NodeProperty(
                name="pickle_max_bytes",
                displayName="Specialized Analysis Maximum Size",
                type=NodePropertyType.NUMBER,
                default=DEFAULT_PICKLE_MAX_BYTES,
                min=1024 * 1024,
                max=MAX_PICKLE_MEMORY_BYTES,
                step=1024 * 1024,
                unit="MB",
                description=(
                    "Resource limit for automatically detected Pickle/PyTorch content, "
                    "entered in MB. It is ignored for other formats."
                ),
                required=False,
                tabName="advanced",
            ),
            NodeProperty(
                name="max_bytes",
                displayName="Maximum Artifact Size",
                type=NodePropertyType.NUMBER,
                default=DEFAULT_MAX_BYTES,
                min=1024 * 1024,
                max=MAX_MAX_BYTES,
                step=1024 * 1024,
                unit="MB",
                description=(
                    "Maximum admitted size for a local/shared artifact, directory total, "
                    "or MinIO object, entered in MB. Archive expansion is controlled by "
                    "the deployment policy."
                ),
                required=False,
                tabName="advanced",
            ),
            NodeProperty(
                name="timeout_seconds",
                displayName="Scan Timeout",
                type=NodePropertyType.NUMBER,
                default=DEFAULT_TIMEOUT_SECONDS,
                min=1,
                max=3600,
                description="Shared deadline for hashing, staging, extraction, and analysis.",
                required=False,
                tabName="advanced",
            ),
            NodeProperty(
                name="include_details",
                displayName="Include Diagnostic Details",
                type=NodePropertyType.CHECKBOX,
                default=False,
                description=(
                    "Returns the bounded internal audit record with IDs, hashes, timestamps, "
                    "per-file checks, and engine diagnostics instead of the concise public result."
                ),
                required=False,
                tabName="advanced",
            ),
        ]

    def _setting(self, inputs: Mapping[str, Any], name: str, default: Any) -> Any:
        if inputs.get(name) not in (None, ""):
            return inputs[name]
        data = self.user_data if isinstance(self.user_data, dict) else {}
        return data.get(name, default)

    def execute(
        self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]
    ) -> Dict[str, Any]:
        values = inputs or {}
        detailed_audit = self._service.scan(
            self._setting(values, "artifact_source", None),
            credential_lookup=self.get_credential,
            owner_id=getattr(self, "user_id", None),
            pickle_max_bytes=self._setting(
                values, "pickle_max_bytes", DEFAULT_PICKLE_MAX_BYTES
            ),
            max_bytes=self._setting(values, "max_bytes", DEFAULT_MAX_BYTES),
            timeout_seconds=self._setting(
                values, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS
            ),
        )
        audit = present_security_result(
            detailed_audit,
            include_details=self._setting(values, "include_details", False),
        )
        result = dict(audit)
        if str(audit.get("decision") or "").lower() == "error":
            result.update(
                {
                    "success": False,
                    "error": audit.get("message", "Model security scan failed."),
                }
            )
        return {"output": result}

    def get_required_packages(self) -> list[str]:
        return [
            f"modelaudit=={installed_static_analysis_version()}",
            f"fickling=={PICKLE_ENGINE_VERSION}",
        ]


__all__ = ["LLMModelScannerNode"]
