"""Fail-closed orchestration for automatic model-security analysis."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from app.services.model_artifact_analysis_service import (
    ArtifactDiskSpaceError,
    DEFAULT_MAX_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    ModelArtifactAnalysisService,
    model_artifact_analysis_service,
    staged_source_is_unchanged,
    stage_model_artifact,
)
from app.services.pickle_security_service import (
    DEFAULT_PICKLE_MAX_BYTES,
    PickleSecurityService,
    pickle_security_service,
)
from app.services.security_audit_service import (
    SecurityPolicyService,
    collect_layer_results,
    make_layer_result,
    security_policy_service,
)


logger = logging.getLogger(__name__)


def _resolve_delegated_pickle_coverage(
    static_layer: Mapping[str, Any], pickle_layer: Mapping[str, Any]
) -> dict[str, Any]:
    """Complete a static Pickle coverage gap when the specialist completed it."""

    static_coverage = (
        static_layer.get("coverage")
        if isinstance(static_layer.get("coverage"), Mapping)
        else {}
    )
    pickle_coverage = (
        pickle_layer.get("coverage")
        if isinstance(pickle_layer.get("coverage"), Mapping)
        else {}
    )
    reasons = {
        str(reason) for reason in list(static_coverage.get("reason_codes") or [])
    }
    delegated_reasons = {"pickle_analysis_incomplete"}
    specialist_completed = (
        pickle_layer.get("applicable") is not False
        and str(pickle_layer.get("status")) == "complete"
        and str(pickle_layer.get("decision")) not in {"error", "inconclusive"}
        and bool(pickle_coverage.get("complete"))
    )
    if (
        not reasons
        or not reasons.issubset(delegated_reasons)
        or not specialist_completed
    ):
        return dict(static_layer)

    result = deepcopy(dict(static_layer))
    summary = (
        result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    )
    if int(summary.get("critical", 0) or 0) > 0:
        decision = "block"
    elif int(summary.get("warning", 0) or 0) > 0:
        decision = "review"
    else:
        decision = "allow"
    result["decision"] = decision
    result["status"] = "complete"
    result["should_continue"] = decision == "allow"
    result["coverage"] = {
        "complete": True,
        "reason_codes": ["pickle_coverage_completed_by_specialist"],
    }
    return result


def _error_layer(
    layer_id: str,
    engine_name: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    return make_layer_result(
        layer_id=layer_id,
        engine_name=engine_name,
        engine_version="unknown",
        decision="error",
        status="error",
        applicable=True,
        coverage_complete=False,
        reason_codes=reason_codes or ["layer_error"],
    )


class LLMModelScannerService:
    """Stage once, route by artifact format, and require every applicable analysis."""

    def __init__(
        self,
        *,
        static_analysis: ModelArtifactAnalysisService | None = None,
        pickle_security: PickleSecurityService | None = None,
        policy: SecurityPolicyService | None = None,
    ):
        self._static_analysis = static_analysis or model_artifact_analysis_service
        self._pickle_security = pickle_security or pickle_security_service
        self._policy = policy or security_policy_service

    def scan(
        self,
        artifact_value: Any,
        *,
        credential_lookup: Callable[[str], Any] | None = None,
        owner_id: Any = None,
        pickle_max_bytes: Any = DEFAULT_PICKLE_MAX_BYTES,
        max_bytes: Any = DEFAULT_MAX_BYTES,
        timeout_seconds: Any = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        layers: list[dict[str, Any]] = []
        routed_layer_ids = ["static_analysis"]
        try:
            with stage_model_artifact(
                artifact_value,
                credential_lookup=credential_lookup,
                owner_id=owner_id,
                max_bytes=max_bytes,
                timeout_seconds=timeout_seconds,
                prefix="llm-model-scanner-",
            ) as staged:
                logger.info(
                    "Model security scan started: name=%s format=%s size_bytes=%s",
                    staged.name,
                    staged.format,
                    staged.size_bytes,
                )
                try:
                    raw_static = self._static_analysis.scan_staged(
                        staged,
                        policy_profile="strict",
                        scanner_allowlist=None,
                    )
                    static_layers = collect_layer_results(raw_static)
                    if not static_layers:
                        raise ValueError(
                            "Artifact security analysis returned an invalid result contract."
                        )
                    layers.append(static_layers[0])
                except Exception as exc:
                    logger.error(
                        "Artifact security layer failed: error_type=%s",
                        type(exc).__name__,
                    )
                    layers.append(
                        _error_layer("static_analysis", "Artifact security analysis")
                    )

                try:
                    pickle_layer = self._pickle_security.scan_staged(
                        staged,
                        max_bytes=pickle_max_bytes,
                    )
                    if pickle_layer.get("applicable") is not False:
                        routed_layer_ids.append("pickle_security")
                        layers.append(pickle_layer)
                        layers[0] = _resolve_delegated_pickle_coverage(
                            layers[0], pickle_layer
                        )
                except Exception as exc:
                    logger.error(
                        "Specialized serialization layer failed: error_type=%s",
                        type(exc).__name__,
                    )
                    routed_layer_ids.append("pickle_security")
                    layers.append(
                        _error_layer(
                            "pickle_security",
                            "Pickle/PyTorch security analysis",
                        )
                    )

                if not staged_source_is_unchanged(staged):
                    logger.error("Local model source changed during the security gate.")
                    layers = [
                        _error_layer(
                            layer_id,
                            (
                                "Artifact security analysis"
                                if layer_id == "static_analysis"
                                else "Pickle/PyTorch security analysis"
                            ),
                            ["artifact_changed_during_scan"],
                        )
                        for layer_id in routed_layer_ids
                    ]
        except Exception as exc:
            logger.error(
                "Model security staging failed: error_type=%s",
                type(exc).__name__,
            )
            reason_codes = (
                ["insufficient_disk_space"]
                if isinstance(exc, ArtifactDiskSpaceError)
                else ["artifact_staging_error"]
            )
            layers = [
                _error_layer(
                    "static_analysis",
                    "Artifact security analysis",
                    reason_codes,
                )
            ]

        return self._policy.evaluate(
            layers,
            profile="strict",
            required_layers=routed_layer_ids,
        )


llm_model_scanner_service = LLMModelScannerService()


__all__ = ["LLMModelScannerService", "llm_model_scanner_service"]
