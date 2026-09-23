"""Safe adapter for statically scanning model artifacts with Static model analysis.

This module deliberately keeps storage resolution, bounded streaming, direct
path handling, temporary file handling for stream-only sources, process
isolation, and result normalization outside workflow nodes.  The public
service accepts KAI-Flow artifact references, validated managed-upload or
MinIO references, and explicit service-local paths; it never accepts URLs or
raw model bytes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import stat
import tempfile
import time
import unicodedata
import uuid
import zipfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.services.model_artifact_store import (
    DISK_CHECK_INTERVAL_BYTES,
    ManagedArtifactError,
    ManagedArtifactInsufficientDiskError,
    managed_model_artifact_store,
)
from app.services.model_scan_limits import (
    configured_archive_expanded_max_bytes,
    configured_artifact_max_bytes,
    configured_staging_retention_seconds,
    configured_storage_min_free_bytes,
    configured_storage_min_free_percent,
    configured_worker_memory_bytes,
)
from app.services.model_scan_process import (
    IsolatedProcessError,
    IsolatedProcessTimeoutError,
    run_in_isolated_process,
)
from app.services.minio_service import minio_service
from app.services.model_security_error_catalog import enrich_security_finding

# Static model analysis reads these flags during import.  Keep them above every code path
# that can import the package, including the in-process test runner.
os.environ["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
os.environ["NO_ANALYTICS"] = "1"

logger = logging.getLogger(__name__)

STATIC_ANALYSIS_VERSION = "0.2.52"
SCHEMA_VERSION = "1.0"
# Local/shared-path and MinIO scans have a separate deployment policy from
# browser uploads. Keep these aliases for the public service API.
DEFAULT_MAX_BYTES = configured_artifact_max_bytes()
DEFAULT_TIMEOUT_SECONDS = 300
MAX_MAX_BYTES = DEFAULT_MAX_BYTES
MAX_TIMEOUT_SECONDS = 3600
COPY_CHUNK_BYTES = 1024 * 1024
MAX_ENGINE_FINDINGS = 32_768
MAX_ENGINE_CHECKS = 512
MAX_FINDING_TEXT = 320
MAX_ARCHIVE_ENTRIES = 512
MAX_ARCHIVE_DEPTH = 3
MAX_ARCHIVE_MEMBER_NAME = 240
MAX_LOCAL_DIRECTORY_ENTRIES = 10_000
MAX_LOCAL_DIRECTORY_DEPTH = 64

_SAFE_SCANNER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SAFE_FILENAME_CHAR = re.compile(r"[^A-Za-z0-9._-]+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_FORMAT_BY_SUFFIX = {
    ".gguf": "gguf",
    ".ggml": "ggml",
    ".pkl": "pickle",
    ".pickle": "pickle",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".bin": "pytorch",
    ".ckpt": "checkpoint",
    ".h5": "keras_h5",
    ".hdf5": "keras_h5",
    ".keras": "keras",
    ".pb": "tensorflow",
    ".meta": "tensorflow",
    ".tflite": "tflite",
    ".onnx": "onnx",
    ".safetensors": "safetensors",
    ".zip": "archive",
    ".tar": "archive",
    ".tgz": "archive",
    ".gz": "archive",
    ".bz2": "archive",
    ".xz": "archive",
    ".zst": "archive",
    ".7z": "archive",
    ".mar": "archive",
}

# These canonical model metadata files are declarative data, not executable
# model containers. A successful engine result with no applicable scanner is
# therefore a completed not-applicable file check, not a coverage failure.
_DATA_ONLY_MODEL_FILENAMES = {
    "added_tokens.json",
    "adapter_config.json",
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "trainer_state.json",
    "vocab.json",
}


def installed_static_analysis_version() -> str:
    try:
        return importlib_metadata.version("modelaudit")
    except importlib_metadata.PackageNotFoundError:
        return STATIC_ANALYSIS_VERSION


def _normalize_analysis_extension(value: Any) -> str:
    extension = str(value or "").strip().lower()
    if not extension or extension == "*":
        return ""
    return extension if extension.startswith(".") else f".{extension}"


def get_static_analysis_capabilities() -> dict[str, Any]:
    """Read supported routes from the installed Static model analysis registry at runtime."""

    fallback_extensions = sorted(set(_FORMAT_BY_SUFFIX))
    capabilities: dict[str, Any] = {
        "version": installed_static_analysis_version(),
        "extensions": fallback_extensions,
        "filenames": [],
        "scanner_extensions": {},
    }
    try:
        from modelaudit.scanners import _registry  # noqa: PLC0415

        scanner_ids = _registry.get_available_scanners()
        extensions: set[str] = set()
        filenames: set[str] = set()
        scanner_extensions: dict[str, list[str]] = {}
        for scanner_id in scanner_ids:
            info = _registry.get_scanner_info(scanner_id) or {}
            scanner_id = str(scanner_id).strip().lower()
            routes = sorted(
                {
                    normalized
                    for raw in list(info.get("extensions", []) or [])
                    + list(info.get("content_routed_extensions", []) or [])
                    if (normalized := _normalize_analysis_extension(raw))
                }
            )
            names = sorted(
                {
                    str(raw).strip().lower()
                    for raw in list(info.get("content_routed_filenames", []) or [])
                    if str(raw).strip()
                }
            )
            if routes:
                scanner_extensions[scanner_id] = routes
                extensions.update(routes)
            filenames.update(names)

        if extensions:
            capabilities["extensions"] = sorted(extensions)
        capabilities["filenames"] = sorted(filenames)
        capabilities["scanner_extensions"] = scanner_extensions
    except Exception as exc:
        logger.warning(
            "Static model analysis scanner capabilities could not be discovered: error_type=%s",
            type(exc).__name__,
        )
        capabilities["error"] = "Static model analysis scanner registry is unavailable."
    return capabilities


class ArtifactReferenceError(ValueError):
    """Raised when a value is not a trusted KAI-Flow artifact reference."""


class ArtifactTooLargeError(ValueError):
    """Raised when the configured streaming size budget is exceeded."""


class ArtifactDiskSpaceError(RuntimeError):
    """Raised when staging would consume the safety reserve on its volume."""


class ModelArtifactAnalysisRunnerError(RuntimeError):
    """Raised when the isolated scanner runner cannot produce a result."""


class ModelArtifactAnalysisTimeoutError(ModelArtifactAnalysisRunnerError):
    """Raised when the isolated scanner exceeds its deadline."""


def _ensure_staging_disk_space(
    path: str | os.PathLike[str], required_bytes: int = 0
) -> None:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        raise ArtifactDiskSpaceError(
            "The staging volume could not be checked for available disk space."
        ) from exc
    reserve = max(
        configured_storage_min_free_bytes(),
        int(usage.total * configured_storage_min_free_percent() / 100),
    )
    required = max(0, int(required_bytes)) + reserve
    if usage.free < required:
        raise ArtifactDiskSpaceError(
            "Not enough free disk space to stage this model artifact safely."
        )


class ModelArtifact(BaseModel):
    """KAI-Flow model artifact reference containing metadata, never bytes.

    The stream factory is a Pydantic private attribute, so workflow tracing and
    serialization see only the safe public metadata below.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(min_length=1, max_length=512)
    size_bytes: int | None = Field(default=None, ge=0)
    format_hint: str | None = Field(default=None, max_length=64)
    reference_id: str | None = Field(default=None, max_length=128)
    storage: str = Field(default="connected", max_length=32)
    _stream_factory: Callable[[], Any] | None = PrivateAttr(default=None)
    _direct_path: str | None = PrivateAttr(default=None)
    _expected_sha256: str | None = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        stream_factory: Callable[[], Any] | None = None,
        direct_path: str | os.PathLike[str] | None = None,
        expected_sha256: str | None = None,
        **data: Any,
    ):
        super().__init__(**data)
        self._stream_factory = stream_factory
        self._direct_path = os.fspath(direct_path) if direct_path is not None else None
        self._expected_sha256 = expected_sha256

    def open_stream(self) -> Any:
        """Open a fresh binary stream for one bounded scan."""

        if self._stream_factory is None:
            raise ArtifactReferenceError(
                "Directory artifacts do not expose a single binary stream."
            )
        stream = self._stream_factory()
        if stream is None or not callable(getattr(stream, "read", None)):
            raise ArtifactReferenceError(
                "Artifact reference did not provide a readable stream."
            )
        return stream

    @property
    def direct_path(self) -> str | None:
        """Return a validated service-local path when the source already exists on disk."""

        return self._direct_path

    @property
    def expected_sha256(self) -> str | None:
        return self._expected_sha256

    def __repr__(self) -> str:
        return "ModelArtifact(name={!r}, size_bytes={!r}, format_hint={!r}, storage={!r})".format(
            self.name,
            self.size_bytes,
            self.format_hint,
            self.storage,
        )


@dataclass(frozen=True)
class StagedModelArtifact:
    """Service-owned path shared by trusted scanner adapters for one run."""

    artifact: ModelArtifact
    path: str
    name: str
    format: str
    size_bytes: int
    sha256: str
    deadline_monotonic: float
    max_bytes: int = MAX_MAX_BYTES
    kind: str = "file"
    source_snapshot: tuple[tuple[Any, ...], ...] | None = None

    def remaining_seconds(self) -> int:
        return max(1, int(self.deadline_monotonic - time.monotonic()))


class ModelArtifactAnalysisRunner(Protocol):
    """Boundary that can later be replaced by a remote sandbox/container."""

    def run(
        self,
        path: str,
        config: dict[str, Any],
        timeout_seconds: int,
        artifact_name: str,
    ) -> dict[str, Any]:
        """Run Static model analysis against one service-owned artifact path."""


def sanitize_artifact_name(name: str | None) -> str:
    """Return a short basename safe for a private temporary directory."""

    raw = unicodedata.normalize("NFKC", str(name or "artifact.bin"))
    basename = raw.replace("\\", "/").rsplit("/", 1)[-1]
    basename = _CONTROL_CHARS.sub("", basename)
    basename = _SAFE_FILENAME_CHAR.sub("_", basename).strip(" ._")
    if not basename:
        basename = "artifact.bin"
    if len(basename) > 120:
        suffix = Path(basename).suffix[:20]
        stem_limit = max(1, 120 - len(suffix))
        basename = f"{Path(basename).stem[:stem_limit]}{suffix}"
    return basename


def detect_artifact_format(
    name: str, scanner: str | None = None, format_hint: str | None = None
) -> str:
    """Resolve a bounded format label without opening or loading the artifact."""

    hint = str(format_hint or "").strip().lower()
    if hint and _SAFE_SCANNER_ID.fullmatch(hint):
        return hint

    scanner_name = str(scanner or "").strip().lower()
    if scanner_name and scanner_name not in {"unknown", "skipped", "none"}:
        scanner_aliases = {
            "pytorch_zip": "pytorch",
            "pytorch_binary": "pytorch",
            "keras_zip": "keras",
            "keras_h5": "keras_h5",
            "tf_savedmodel": "tensorflow",
            "tf_metagraph": "tensorflow",
            "sevenzip": "archive",
            "zip": "archive",
            "tar": "archive",
            "compressed": "archive",
        }
        return scanner_aliases.get(scanner_name, scanner_name)

    lowered = name.lower()
    if lowered.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")):
        return "archive"
    known_format = _FORMAT_BY_SUFFIX.get(Path(lowered).suffix)
    if known_format:
        return known_format
    for extension in sorted(
        get_static_analysis_capabilities().get("extensions", []),
        key=len,
        reverse=True,
    ):
        if lowered.endswith(extension):
            return extension.lstrip(".").replace(".", "_") or "unknown"
    return "unknown"


def _safe_text(
    value: Any, *, replace_path: str | None = None, artifact_name: str = "artifact"
) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    if replace_path:
        text = text.replace(replace_path, artifact_name)
    text = _CONTROL_CHARS.sub("", text)
    text = " ".join(text.split())
    return text[:MAX_FINDING_TEXT]


def _severity_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    normalized = str(raw or "info").lower().split(".")[-1]
    return (
        normalized if normalized in {"critical", "warning", "info", "debug"} else "info"
    )


def _bounded_metadata_value(value: Any, *, artifact_name: str) -> Any:
    """Keep allowlisted engine metadata small, primitive, and JSON-safe."""

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value, artifact_name=artifact_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _safe_text(item, artifact_name=artifact_name) for item in list(value)[:32]
        ]
    return _safe_text(value, artifact_name=artifact_name)


def _bounded_check_results(
    checks: Any, path: str, artifact_name: str
) -> list[dict[str, Any]]:
    """Expose every bounded Static model analysis check without leaking raw details."""

    if not isinstance(checks, list):
        return []

    bounded: list[dict[str, Any]] = []
    for raw_check in checks[:MAX_ENGINE_CHECKS]:
        check = raw_check if isinstance(raw_check, Mapping) else {}
        item = {
            "name": _safe_text(
                check.get("name") or "Static model analysis check",
                artifact_name=artifact_name,
            ),
            "status": _safe_text(
                check.get("status") or "unknown",
                artifact_name=artifact_name,
            ),
            "message": _safe_text(
                check.get("message"),
                replace_path=path,
                artifact_name=artifact_name,
            ),
        }
        if check.get("severity") not in (None, ""):
            item["severity"] = _severity_value(check.get("severity"))
        for source_key, target_key in (
            ("rule_code", "rule_code"),
            ("why", "why"),
            ("location", "location"),
        ):
            if check.get(source_key) not in (None, ""):
                item[target_key] = _safe_text(
                    check[source_key],
                    replace_path=path,
                    artifact_name=artifact_name,
                )
        scanner_rule_code = item.get("rule_code")
        if scanner_rule_code:
            item.update(
                enrich_security_finding(
                    "artifact_analysis",
                    scanner_rule_code,
                    severity=check.get("severity"),
                    message=item.get("message"),
                )
            )
        bounded.append(item)
    return bounded


def _bounded_engine_payload(
    result: Any, path: str, artifact_name: str, engine_version: str
) -> dict[str, Any]:
    """Reduce Static model analysis output before it crosses the process boundary."""

    if callable(getattr(result, "model_dump", None)):
        raw = result.model_dump(mode="json")
    elif callable(getattr(result, "to_dict", None)):
        raw = result.to_dict()
    else:
        raw = result
    if not isinstance(raw, Mapping):
        raise ModelArtifactAnalysisRunnerError(
            "Static model analysis returned an invalid result contract."
        )

    raw_issues = raw.get("issues")
    issues: list[Any] = raw_issues if isinstance(raw_issues, list) else []
    raw_checks = raw.get("checks")
    tests = _bounded_check_results(raw_checks, path, artifact_name)
    counts = {"critical": 0, "warning": 0, "info": 0}
    findings: list[dict[str, Any]] = []
    severity_rank = {"critical": 0, "warning": 1, "info": 2, "debug": 3}

    for issue in issues:
        issue_map = issue if isinstance(issue, Mapping) else {}
        severity = _severity_value(issue_map.get("severity"))
        if severity != "debug":
            counts[severity] += 1
        finding = {
            "severity": severity,
            "title": _safe_text(
                issue_map.get("type") or "Static model analysis finding",
                artifact_name=artifact_name,
            ),
            "message": _safe_text(
                issue_map.get("message"), replace_path=path, artifact_name=artifact_name
            ),
        }
        rule_code = _safe_text(issue_map.get("rule_code"), artifact_name=artifact_name)
        why = _safe_text(
            issue_map.get("why"), replace_path=path, artifact_name=artifact_name
        )
        if rule_code:
            finding["rule_code"] = rule_code
        if why:
            finding["why"] = why
        location = _safe_text(
            issue_map.get("location"),
            replace_path=path,
            artifact_name=artifact_name,
        )
        if location:
            finding["location"] = location
        finding.update(
            enrich_security_finding(
                "artifact_analysis",
                rule_code,
                severity=issue_map.get("severity"),
                message=finding.get("message"),
            )
        )
        findings.append(finding)

    findings.sort(key=lambda item: severity_rank.get(str(item.get("severity")), 4))
    raw_metadata = raw.get("metadata")
    metadata: Mapping[str, Any] = (
        raw_metadata if isinstance(raw_metadata, Mapping) else {}
    )
    safe_metadata_keys = {
        "analysis_incomplete",
        "format",
        "operational_error",
        "scan_outcome",
        "scan_outcome_reasons",
        "scanner_dependency_ids",
        "skipped_scanner_ids",
        "validated_format",
    }
    safe_metadata = {
        key: _bounded_metadata_value(metadata[key], artifact_name=artifact_name)
        for key in safe_metadata_keys
        if key in metadata
    }

    return {
        "scanner": _safe_text(
            raw.get("scanner") or "unknown", artifact_name=artifact_name
        ),
        "success": bool(raw.get("success", False)),
        "duration_ms": max(0, int(float(raw.get("duration", 0.0) or 0.0) * 1000)),
        "checks": max(0, int(raw.get("total_checks", 0) or 0)),
        "counts": counts,
        "findings": findings[:MAX_ENGINE_FINDINGS],
        "findings_total": len(findings),
        "tests": tests,
        "tests_total": len(raw_checks) if isinstance(raw_checks, list) else 0,
        "tests_truncated": (
            isinstance(raw_checks, list) and len(raw_checks) > len(tests)
        ),
        "metadata": safe_metadata,
        "engine_version": engine_version,
    }


def _execute_static_analysis(
    path: str, config: dict[str, Any], artifact_name: str
) -> dict[str, Any]:
    """Import and invoke Static model analysis only after telemetry has been disabled."""

    os.environ["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
    os.environ["NO_ANALYTICS"] = "1"
    logging.getLogger("modelaudit").setLevel(logging.ERROR)
    logging.getLogger("modelaudit.scanners").setLevel(logging.ERROR)

    engine_version = importlib_metadata.version("modelaudit")
    if os.path.isdir(path):
        from modelaudit.core import (  # noqa: PLC0415 - required telemetry ordering
            scan_model_directory_or_file,
        )

        directory_config = dict(config)
        timeout = int(directory_config.pop("timeout", DEFAULT_TIMEOUT_SECONDS))
        max_file_size = int(directory_config.pop("max_file_size", 0))
        max_total_size = int(directory_config.pop("max_total_size", max_file_size))
        scanners = directory_config.pop("scanners", None)
        # These are scan_file-only presentation/cache flags, not directory policy.
        directory_config.pop("enable_progress", None)
        directory_config.pop("cache_scan_results", None)
        result = scan_model_directory_or_file(
            path,
            timeout=timeout,
            max_file_size=max_file_size,
            max_total_size=max_total_size,
            skip_file_types=True,
            scanners=scanners,
            **directory_config,
        )
        raw = result.model_dump(mode="json")
        directory_reasons: list[str] = []
        file_metadata = raw.get("file_metadata")
        if isinstance(file_metadata, Mapping):
            for file_result in file_metadata.values():
                if not isinstance(file_result, Mapping):
                    continue
                reasons = file_result.get("scan_outcome_reasons")
                if not isinstance(reasons, Sequence) or isinstance(
                    reasons, (str, bytes, bytearray)
                ):
                    continue
                for reason in reasons:
                    normalized_reason = str(reason)[:96]
                    if normalized_reason and normalized_reason not in directory_reasons:
                        directory_reasons.append(normalized_reason)
        if raw.get("has_errors") and not directory_reasons:
            directory_reasons.append("directory_analysis_incomplete")
        raw["scanner"] = "directory"
        raw["metadata"] = {
            "validated_format": "directory",
            "format": "directory",
            "analysis_incomplete": bool(raw.get("has_errors"))
            or raw.get("success") is not True,
            "operational_error": bool(raw.get("has_errors")),
            "scan_outcome": (
                "complete"
                if raw.get("success") is True and not raw.get("has_errors")
                else "inconclusive"
            ),
            "scan_outcome_reasons": directory_reasons,
        }
        result = raw
    else:
        from modelaudit import scan_file  # noqa: PLC0415 - required telemetry ordering

        result = scan_file(path, config=config)
    return _bounded_engine_payload(result, path, artifact_name, engine_version)


def _set_static_worker_limits(timeout_seconds: int) -> None:
    """Apply OS resource limits where supported (Linux/macOS workers)."""

    try:
        import resource  # noqa: PLC0415 - unavailable on Windows

        memory_limit = configured_worker_memory_bytes()
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        cpu_limit = max(1, int(timeout_seconds) + 1)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    except (ImportError, OSError, ValueError):
        # Windows still gets a dedicated killable worker and wall-clock timeout.
        return


def _static_analysis_process_entry(
    send_connection: Any,
    path: str,
    config: dict[str, Any],
    artifact_name: str,
    timeout_seconds: int,
) -> None:
    try:
        _set_static_worker_limits(timeout_seconds)
        payload = _execute_static_analysis(path, config, artifact_name)
        send_connection.send({"ok": True, "result": payload})
    except (
        BaseException
    ) as exc:  # Child failures must cross the boundary as a bounded status only.
        try:
            send_connection.send(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error_message": _safe_text(
                        exc,
                        replace_path=path,
                        artifact_name=artifact_name,
                    ),
                }
            )
        except BaseException:
            pass
    finally:
        send_connection.close()


class ProcessModelArtifactAnalysisRunner:
    """Run Static model analysis in a killable child process with a strict deadline."""

    def __init__(self, start_method: str | None = None):
        self._start_method = start_method

    def run(
        self,
        path: str,
        config: dict[str, Any],
        timeout_seconds: int,
        artifact_name: str,
    ) -> dict[str, Any]:
        memory_limit_bytes = configured_worker_memory_bytes()
        try:
            return run_in_isolated_process(
                target=_static_analysis_process_entry,
                worker_args=(path, config, artifact_name, timeout_seconds),
                timeout_seconds=timeout_seconds,
                worker_name="Static model analysis",
                memory_limit_bytes=memory_limit_bytes,
                artifact_path=path,
                artifact_name=artifact_name,
                start_method=self._start_method,
            )
        except IsolatedProcessTimeoutError as exc:
            raise ModelArtifactAnalysisTimeoutError(str(exc)) from exc
        except IsolatedProcessError as exc:
            raise ModelArtifactAnalysisRunnerError(str(exc)) from exc


class InProcessModelArtifactAnalysisRunner:
    """Deterministic runner for integration tests; production uses the process runner."""

    def run(
        self,
        path: str,
        config: dict[str, Any],
        timeout_seconds: int,
        artifact_name: str,
    ) -> dict[str, Any]:
        return _execute_static_analysis(path, config, artifact_name)


def _artifact_storage(value: Mapping[str, Any]) -> str:
    return str(value.get("storage") or value.get("source_type") or "").lower()


def _unwrap_artifact_value(value: Any, depth: int = 0) -> Any:
    if depth > 6 or not isinstance(value, Mapping):
        return value
    if _artifact_storage(value) in {"minio", "managed"}:
        return value
    for key in ("artifact", "output", "value"):
        if key in value:
            candidate = _unwrap_artifact_value(value[key], depth + 1)
            if candidate is not value[key] or isinstance(candidate, ModelArtifact):
                return candidate
            if isinstance(value[key], Mapping):
                return candidate
    return value


def _credential_secret(credential: Any) -> Mapping[str, Any]:
    if not isinstance(credential, Mapping):
        raise ArtifactReferenceError("Artifact storage credential is unavailable.")
    secret = credential.get("secret")
    if not isinstance(secret, Mapping):
        raise ArtifactReferenceError("Artifact storage credential is invalid.")
    return secret


def _minio_artifact_from_mapping(
    value: Mapping[str, Any],
    credential_lookup: Callable[[str], Any] | None,
) -> ModelArtifact:
    if credential_lookup is None:
        raise ArtifactReferenceError(
            "A credential resolver is required for stored artifacts."
        )
    credential_id = str(value.get("credential_id") or "").strip()
    bucket = str(value.get("bucket") or value.get("bucket_name") or "").strip()
    object_key = str(value.get("object_key") or value.get("key") or "").strip()
    if not credential_id or not bucket or not object_key or "\x00" in object_key:
        raise ArtifactReferenceError("Stored artifact reference is incomplete.")

    secret = _credential_secret(credential_lookup(credential_id))
    endpoint = str(secret.get("endpoint") or "").strip()
    access_key = str(
        secret.get("access_key") or secret.get("username") or secret.get("id") or ""
    ).strip()
    secret_key = str(
        secret.get("secret_key") or secret.get("password") or secret.get("secret") or ""
    ).strip()
    if not endpoint or not access_key or not secret_key:
        raise ArtifactReferenceError("Artifact storage credential is incomplete.")
    if endpoint.startswith("http://"):
        endpoint = endpoint[7:]
    elif endpoint.startswith("https://"):
        endpoint = endpoint[8:]
    use_ssl = secret.get("use_ssl") is True or str(
        secret.get("use_ssl", "")
    ).lower() in {"1", "true", "yes"}

    try:
        client = minio_service.get_client(
            endpoint,
            access_key,
            secret_key,
            use_ssl=use_ssl,
        )
        head = client.head_object(Bucket=bucket, Key=object_key)
        size_bytes = int(head.get("ContentLength", 0))
        source_etag = str(head.get("ETag") or "").strip('"')
        source_version_id = str(head.get("VersionId") or "").strip()
    except Exception as exc:
        raise ArtifactReferenceError("Stored artifact could not be opened.") from exc

    def open_stream() -> Any:
        try:
            request = {"Bucket": bucket, "Key": object_key}
            if source_version_id:
                request["VersionId"] = source_version_id
            response = client.get_object(**request)
            response_size = int(response.get("ContentLength", size_bytes))
            response_etag = str(response.get("ETag") or "").strip('"')
            if response_size != size_bytes or (
                source_etag and response_etag and response_etag != source_etag
            ):
                close = getattr(response.get("Body"), "close", None)
                if callable(close):
                    close()
                raise ArtifactReferenceError(
                    "Stored artifact changed while the scan reference was opened."
                )
            return response["Body"]
        except ArtifactReferenceError:
            raise
        except Exception as exc:
            raise ArtifactReferenceError(
                "Stored artifact stream could not be opened."
            ) from exc

    safe_name = sanitize_artifact_name(str(value.get("name") or object_key))
    reference_digest = hashlib.sha256(
        f"{credential_id}\0{bucket}\0{object_key}\0{source_version_id or source_etag}".encode()
    ).hexdigest()[:24]
    return ModelArtifact(
        name=safe_name,
        size_bytes=size_bytes,
        format_hint=str(value.get("format") or "").lower() or None,
        reference_id=f"minio:{reference_digest}",
        storage="minio",
        stream_factory=open_stream,
    )


def _managed_artifact_from_mapping(
    value: Mapping[str, Any], owner_id: Any
) -> ModelArtifact:
    artifact_id = str(value.get("artifact_id") or "").strip()
    try:
        record = managed_model_artifact_store.resolve(artifact_id, owner_id=owner_id)
    except ManagedArtifactError as exc:
        raise ArtifactReferenceError(str(exc)) from exc
    return ModelArtifact(
        name=record.name,
        size_bytes=record.size_bytes,
        format_hint=record.format_hint,
        reference_id=f"managed:{record.artifact_id}",
        storage="managed",
        stream_factory=record.open_stream,
        direct_path=record.payload_path,
        expected_sha256=record.sha256,
    )


def configured_local_model_roots() -> tuple[Path, ...]:
    """Return canonical roots from which direct model references may be read.

    JSON is the portable representation because Windows drive letters contain a
    colon.  ``os.pathsep``-separated values remain supported for conventional
    shell configuration on each host.
    """

    raw = os.getenv("KAI_MODEL_LOCAL_ALLOWED_ROOTS", "").strip()
    if not raw:
        return ()
    values: Any
    if raw.startswith("["):
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ArtifactReferenceError(
                "KAI_MODEL_LOCAL_ALLOWED_ROOTS must be a JSON array of paths."
            ) from exc
    else:
        values = [item for item in raw.split(os.pathsep) if item.strip()]
    if not isinstance(values, list) or not all(
        isinstance(item, str) and item.strip() for item in values
    ):
        raise ArtifactReferenceError(
            "KAI_MODEL_LOCAL_ALLOWED_ROOTS must contain only non-empty paths."
        )

    roots: list[Path] = []
    for value in values:
        root = Path(value).expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise ArtifactReferenceError(
                "A configured local model root could not be opened."
            ) from exc
        if not resolved.is_dir():
            raise ArtifactReferenceError(
                "Every configured local model root must be a directory."
            )
        roots.append(resolved)
    return tuple(dict.fromkeys(roots))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _ensure_local_path_is_allowed(path: Path) -> None:
    roots = configured_local_model_roots()
    if roots:
        if not any(_is_relative_to(path, root) for root in roots):
            raise ArtifactReferenceError(
                "Local artifact path is outside the configured model roots."
            )
        return

    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    if environment in {"production", "staging"}:
        raise ArtifactReferenceError(
            "Direct local model paths are disabled until "
            "KAI_MODEL_LOCAL_ALLOWED_ROOTS is configured."
        )
    logger.warning(
        "Direct local model paths are unrestricted outside production because "
        "KAI_MODEL_LOCAL_ALLOWED_ROOTS is not configured."
    )


def _is_link_or_reparse(path_stat: os.stat_result) -> bool:
    if stat.S_ISLNK(path_stat.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(path_stat, "st_file_attributes", 0) & reparse_flag)


def _local_path_artifact_from_mapping(value: Mapping[str, Any]) -> ModelArtifact:
    source_type = (
        str(value.get("source_type") or value.get("storage") or "").strip().lower()
    )
    if source_type not in {"path", "local_path", "direct"}:
        raise ArtifactReferenceError(
            "A local path source must explicitly use source_type='path'."
        )
    raw_path = str(value.get("path") or value.get("local_path") or "").strip()
    if not raw_path or "\x00" in raw_path:
        raise ArtifactReferenceError("Local artifact path is incomplete.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ArtifactReferenceError("Local artifact path must be absolute.")
    try:
        source_stat = path.lstat()
        if _is_link_or_reparse(source_stat):
            raise ArtifactReferenceError(
                "Local artifact path cannot be a symbolic link or reparse point."
            )
        resolved = path.resolve(strict=True)
        path_stat = resolved.stat()
    except OSError as exc:
        raise ArtifactReferenceError(
            "Local artifact path could not be opened."
        ) from exc
    _ensure_local_path_is_allowed(resolved)
    is_file = stat.S_ISREG(path_stat.st_mode)
    is_directory = stat.S_ISDIR(path_stat.st_mode)
    if not is_file and not is_directory:
        raise ArtifactReferenceError(
            "Local artifact path must point to a regular file or directory."
        )
    if not os.access(resolved, os.R_OK):
        raise ArtifactReferenceError("Local artifact path is not readable.")

    safe_name = sanitize_artifact_name(
        str(value.get("name") or resolved.name or "model-directory")
    )
    path_digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:24]
    return ModelArtifact(
        name=safe_name,
        size_bytes=int(path_stat.st_size) if is_file else None,
        format_hint=(
            "directory"
            if is_directory
            else str(value.get("format") or "").lower() or None
        ),
        reference_id=f"path:{path_digest}",
        storage="local_path",
        stream_factory=(lambda: resolved.open("rb")) if is_file else None,
        direct_path=resolved,
    )


def resolve_model_artifact(
    value: Any,
    credential_lookup: Callable[[str], Any] | None = None,
    owner_id: Any = None,
) -> ModelArtifact:
    """Resolve a managed, MinIO, or explicitly configured local-path artifact."""

    candidate = _unwrap_artifact_value(value)
    if isinstance(candidate, ModelArtifact):
        return candidate
    if isinstance(candidate, (str, bytes, bytearray, memoryview, os.PathLike)):
        raise ArtifactReferenceError(
            "Use an explicit source_type='path' object for local filesystem scans."
        )
    if isinstance(candidate, Mapping):
        if any(
            candidate.get(key) not in (None, "") for key in ("url", "bytes", "content")
        ):
            raise ArtifactReferenceError(
                "URLs and raw artifact bytes are not accepted."
            )
        if candidate.get("path") not in (None, "") or candidate.get(
            "local_path"
        ) not in (None, ""):
            return _local_path_artifact_from_mapping(candidate)
        storage = _artifact_storage(candidate)
        if storage == "minio":
            return _minio_artifact_from_mapping(candidate, credential_lookup)
        if storage == "managed":
            return _managed_artifact_from_mapping(candidate, owner_id)
    raise ArtifactReferenceError(
        "A managed upload, absolute backend path, or MinIO reference is required."
    )


def _coerce_positive_int(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, maximum)


def _stat_signature(
    entry_type: str, relative_path: str, path_stat: os.stat_result
) -> tuple[Any, ...]:
    return (
        entry_type,
        relative_path,
        int(path_stat.st_mode),
        int(path_stat.st_size),
        int(getattr(path_stat, "st_mtime_ns", int(path_stat.st_mtime * 1e9))),
        int(getattr(path_stat, "st_ctime_ns", int(path_stat.st_ctime * 1e9))),
        int(getattr(path_stat, "st_dev", 0)),
        int(getattr(path_stat, "st_ino", 0)),
    )


def _directory_entries(
    root: Path, deadline: float
) -> list[tuple[Path, str, os.stat_result, str]]:
    """Return a stable, bounded, no-link directory manifest."""

    entries: list[tuple[Path, str, os.stat_result, str]] = []
    pending: list[tuple[Path, int]] = [(root, 0)]
    while pending:
        if time.monotonic() >= deadline:
            raise ModelArtifactAnalysisTimeoutError("Artifact discovery timed out.")
        directory, depth = pending.pop()
        if depth > MAX_LOCAL_DIRECTORY_DEPTH:
            raise ArtifactReferenceError(
                "Local model directory exceeds the maximum nesting depth."
            )
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise ArtifactReferenceError(
                "Local model directory could not be read."
            ) from exc

        child_directories: list[tuple[Path, int]] = []
        for child in children:
            if len(entries) >= MAX_LOCAL_DIRECTORY_ENTRIES:
                raise ArtifactReferenceError(
                    "Local model directory exceeds the maximum entry count."
                )
            child_path = Path(child.path)
            try:
                child_stat = child_path.lstat()
            except OSError as exc:
                raise ArtifactReferenceError(
                    "A local model directory entry could not be inspected."
                ) from exc
            if _is_link_or_reparse(child_stat):
                raise ArtifactReferenceError(
                    "Local model directories cannot contain symbolic links or reparse points."
                )
            relative_path = unicodedata.normalize(
                "NFC", child_path.relative_to(root).as_posix()
            )
            if stat.S_ISDIR(child_stat.st_mode):
                entries.append((child_path, relative_path, child_stat, "directory"))
                child_directories.append((child_path, depth + 1))
            elif stat.S_ISREG(child_stat.st_mode):
                entries.append((child_path, relative_path, child_stat, "file"))
            else:
                raise ArtifactReferenceError(
                    "Local model directories may contain only regular files and directories."
                )
        # Reverse because this is a LIFO stack; traversal remains lexical.
        pending.extend(reversed(child_directories))
    entries.sort(key=lambda item: item[1])
    return entries


def _snapshot_direct_path(
    path: str,
    deadline: float,
    maximum_bytes: int,
) -> tuple[int, str, str, tuple[tuple[Any, ...], ...]]:
    """Hash a file/tree and capture metadata used for post-scan immutability checks."""

    source_path = Path(path)
    try:
        root_stat = source_path.lstat()
    except OSError as exc:
        raise ArtifactReferenceError("Local artifact could not be read.") from exc
    if _is_link_or_reparse(root_stat):
        raise ArtifactReferenceError(
            "Local artifact cannot be a symbolic link or reparse point."
        )

    if stat.S_ISREG(root_stat.st_mode):
        digest = hashlib.sha256()
        size_bytes = 0
        before = _stat_signature("file", "", root_stat)
        try:
            with source_path.open("rb") as source:
                while True:
                    if time.monotonic() >= deadline:
                        raise ModelArtifactAnalysisTimeoutError(
                            "Artifact hashing timed out."
                        )
                    chunk = source.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > maximum_bytes:
                        raise ArtifactTooLargeError(
                            "Artifact exceeds the configured maximum size."
                        )
                    digest.update(chunk)
            after = _stat_signature("file", "", source_path.lstat())
        except OSError as exc:
            raise ArtifactReferenceError("Local artifact could not be read.") from exc
        if before != after:
            raise ArtifactReferenceError("Local artifact changed while it was hashed.")
        return size_bytes, digest.hexdigest(), "file", (after,)

    if not stat.S_ISDIR(root_stat.st_mode):
        raise ArtifactReferenceError(
            "Local artifact path must point to a regular file or directory."
        )

    digest = hashlib.sha256(b"KAI-MODEL-DIRECTORY-v1\0")
    size_bytes = 0
    snapshot: list[tuple[Any, ...]] = [_stat_signature("directory", "", root_stat)]
    for entry_path, relative_path, entry_stat, entry_type in _directory_entries(
        source_path, deadline
    ):
        signature = _stat_signature(entry_type, relative_path, entry_stat)
        snapshot.append(signature)
        digest.update(entry_type.encode("ascii"))
        digest.update(b"\0")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        if entry_type == "directory":
            continue
        file_digest = hashlib.sha256()
        try:
            with entry_path.open("rb") as source:
                while True:
                    if time.monotonic() >= deadline:
                        raise ModelArtifactAnalysisTimeoutError(
                            "Artifact hashing timed out."
                        )
                    chunk = source.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > maximum_bytes:
                        raise ArtifactTooLargeError(
                            "Artifact exceeds the configured maximum size."
                        )
                    file_digest.update(chunk)
        except OSError as exc:
            raise ArtifactReferenceError(
                "A local model directory entry could not be read."
            ) from exc
        after = _stat_signature("file", relative_path, entry_path.lstat())
        if signature != after:
            raise ArtifactReferenceError(
                "Local model directory changed while it was hashed."
            )
        digest.update(file_digest.digest())

    # Re-capture the manifest so additions/removals and metadata changes that
    # occurred during hashing cannot produce a trusted digest.
    verified_snapshot = _metadata_snapshot(source_path, deadline)
    if tuple(snapshot) != verified_snapshot:
        raise ArtifactReferenceError(
            "Local model directory changed while it was hashed."
        )
    return size_bytes, digest.hexdigest(), "directory", verified_snapshot


def _metadata_snapshot(path: Path, deadline: float) -> tuple[tuple[Any, ...], ...]:
    try:
        root_stat = path.lstat()
    except OSError as exc:
        raise ArtifactReferenceError("Local artifact could not be inspected.") from exc
    if _is_link_or_reparse(root_stat):
        raise ArtifactReferenceError(
            "Local artifact cannot be a symbolic link or reparse point."
        )
    if stat.S_ISREG(root_stat.st_mode):
        return (_stat_signature("file", "", root_stat),)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ArtifactReferenceError(
            "Local artifact path must point to a regular file or directory."
        )
    snapshot = [_stat_signature("directory", "", root_stat)]
    snapshot.extend(
        _stat_signature(entry_type, relative_path, entry_stat)
        for _, relative_path, entry_stat, entry_type in _directory_entries(
            path, deadline
        )
    )
    return tuple(snapshot)


def staged_source_is_unchanged(staged: StagedModelArtifact) -> bool:
    """Verify that an in-place source still matches its pre-scan metadata snapshot."""

    if staged.source_snapshot is None:
        return True
    try:
        current = _metadata_snapshot(Path(staged.path), staged.deadline_monotonic)
    except (
        ArtifactReferenceError,
        ModelArtifactAnalysisTimeoutError,
        OSError,
    ):
        return False
    return current == staged.source_snapshot


def _is_zip_path(path: str) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def _safe_archive_member_name(value: Any) -> str | None:
    raw = unicodedata.normalize("NFKC", str(value or "")).replace("\\", "/")
    raw = _CONTROL_CHARS.sub("", raw)
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if not parts or raw.startswith("/") or any(part == ".." for part in parts):
        return None
    safe_parts = []
    for part in parts:
        cleaned = _SAFE_FILENAME_CHAR.sub("_", part).strip(" ._") or "entry"
        safe_parts.append(cleaned)
    return "/".join(safe_parts)[:MAX_ARCHIVE_MEMBER_NAME]


def _archive_entry_matches(name: str, capabilities: Mapping[str, Any]) -> bool:
    lowered = name.lower()
    extensions = capabilities.get("extensions")
    if isinstance(extensions, Sequence) and not isinstance(
        extensions, (str, bytes, bytearray)
    ):
        if any(
            lowered.endswith(str(extension).lower())
            for extension in extensions
            if extension
        ):
            return True
    filenames = capabilities.get("filenames")
    if isinstance(filenames, Sequence) and not isinstance(
        filenames, (str, bytes, bytearray)
    ):
        return lowered.rsplit("/", 1)[-1] in {
            str(filename).lower() for filename in filenames if filename
        }
    return False


@contextmanager
def _stage_model_artifact_unleased(
    artifact_value: Any,
    *,
    credential_lookup: Callable[[str], Any] | None = None,
    owner_id: Any = None,
    max_bytes: Any = DEFAULT_MAX_BYTES,
    timeout_seconds: Any = DEFAULT_TIMEOUT_SECONDS,
    prefix: str = "kai-model-security-",
):
    """Resolve an artifact and expose its path without copying local files."""

    artifact = resolve_model_artifact(
        artifact_value,
        credential_lookup=credential_lookup,
        owner_id=owner_id,
    )
    maximum_bytes = _coerce_positive_int(max_bytes, DEFAULT_MAX_BYTES, MAX_MAX_BYTES)
    timeout = _coerce_positive_int(
        timeout_seconds, DEFAULT_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
    )
    if artifact.size_bytes is not None and artifact.size_bytes > maximum_bytes:
        raise ArtifactTooLargeError("Artifact exceeds the configured maximum size.")

    deadline = time.monotonic() + timeout
    artifact_name = sanitize_artifact_name(artifact.name)
    artifact_format = detect_artifact_format(
        artifact_name, format_hint=artifact.format_hint
    )
    if artifact.direct_path:
        size_bytes, sha256, artifact_kind, source_snapshot = _snapshot_direct_path(
            artifact.direct_path,
            deadline,
            maximum_bytes,
        )
        if artifact.expected_sha256 and sha256 != artifact.expected_sha256:
            raise ArtifactReferenceError(
                "Managed artifact integrity validation failed before scanning."
            )
        yield StagedModelArtifact(
            artifact=artifact,
            path=artifact.direct_path,
            name=artifact_name,
            format="directory" if artifact_kind == "directory" else artifact_format,
            size_bytes=size_bytes,
            sha256=sha256,
            deadline_monotonic=deadline,
            max_bytes=maximum_bytes,
            kind=artifact_kind,
            source_snapshot=(
                source_snapshot if artifact.storage == "local_path" else None
            ),
        )
        return

    staging_reservation_id: str | None = None
    temp_dir = ""
    try:
        try:
            staging_reservation_id = (
                managed_model_artifact_store.reserve_staging_capacity(
                    artifact.size_bytes or maximum_bytes
                )
            )
        except ManagedArtifactInsufficientDiskError as exc:
            raise ArtifactDiskSpaceError(str(exc)) from exc
        staging_root = managed_model_artifact_store.staging_root
        staging_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix=prefix, dir=staging_root)
        os.chmod(temp_dir, 0o700)
        temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}-{artifact_name}")
        size_bytes = 0
        digest = hashlib.sha256()
        _ensure_staging_disk_space(temp_dir, artifact.size_bytes or 0)
        logger.info(
            "Model artifact staging started: source=%s name=%s expected_bytes=%s",
            artifact.storage,
            artifact_name,
            artifact.size_bytes,
        )
        stream = artifact.open_stream()
        try:
            file_descriptor = os.open(
                temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(file_descriptor, "wb") as destination:
                last_disk_check = 0
                while True:
                    if time.monotonic() >= deadline:
                        raise ModelArtifactAnalysisTimeoutError(
                            "Artifact staging timed out."
                        )
                    chunk = stream.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    if not isinstance(chunk, (bytes, bytearray, memoryview)):
                        raise ArtifactReferenceError(
                            "Artifact stream must yield bytes."
                        )
                    chunk_bytes = bytes(chunk)
                    size_bytes += len(chunk_bytes)
                    if size_bytes > maximum_bytes:
                        raise ArtifactTooLargeError(
                            "Artifact exceeds the configured maximum size."
                        )
                    if size_bytes - last_disk_check >= DISK_CHECK_INTERVAL_BYTES:
                        _ensure_staging_disk_space(temp_dir)
                        last_disk_check = size_bytes
                        percent = (
                            round((size_bytes / artifact.size_bytes) * 100, 1)
                            if artifact.size_bytes
                            else None
                        )
                        logger.info(
                            "Model artifact staging progress: name=%s bytes=%s expected_bytes=%s percent=%s",
                            artifact_name,
                            size_bytes,
                            artifact.size_bytes,
                            percent,
                        )
                    digest.update(chunk_bytes)
                    destination.write(chunk_bytes)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

        yield StagedModelArtifact(
            artifact=artifact,
            path=temp_path,
            name=artifact_name,
            format=artifact_format,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
            deadline_monotonic=deadline,
            max_bytes=maximum_bytes,
        )
        logger.info(
            "Model artifact staging completed: name=%s size_bytes=%s sha256=%s",
            artifact_name,
            size_bytes,
            digest.hexdigest(),
        )
    finally:
        try:
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    logger.error("Security scanner temporary workspace cleanup failed.")
                    raise
        finally:
            managed_model_artifact_store.release_staging_capacity(
                staging_reservation_id
            )


@contextmanager
def stage_model_artifact(
    artifact_value: Any,
    *,
    credential_lookup: Callable[[str], Any] | None = None,
    owner_id: Any = None,
    max_bytes: Any = DEFAULT_MAX_BYTES,
    timeout_seconds: Any = DEFAULT_TIMEOUT_SECONDS,
    prefix: str = "kai-model-security-",
):
    """Stage an artifact while protecting managed uploads with a DB-backed lease."""

    timeout = _coerce_positive_int(
        timeout_seconds, DEFAULT_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
    )
    candidate = _unwrap_artifact_value(artifact_value)
    managed_artifact_id: str | None = None
    lease_id: str | None = None
    if isinstance(candidate, Mapping) and _artifact_storage(candidate) == "managed":
        managed_artifact_id = str(candidate.get("artifact_id") or "").strip()
        try:
            lease_id = managed_model_artifact_store.acquire_lease(
                managed_artifact_id,
                owner_id=owner_id,
                lease_seconds=timeout + configured_staging_retention_seconds(),
            )
        except ManagedArtifactError as exc:
            raise ArtifactReferenceError(str(exc)) from exc

    try:
        with _stage_model_artifact_unleased(
            artifact_value,
            credential_lookup=credential_lookup,
            owner_id=owner_id,
            max_bytes=max_bytes,
            timeout_seconds=timeout,
            prefix=prefix,
        ) as staged:
            yield staged
    finally:
        if managed_artifact_id and lease_id:
            try:
                managed_model_artifact_store.release_lease(
                    managed_artifact_id,
                    lease_id,
                    scan_attempted=True,
                )
            except ManagedArtifactError:
                logger.error(
                    "Managed model artifact scan lease release failed: artifact_id=%s",
                    managed_artifact_id,
                )


def parse_scanner_allowlist(value: Any) -> list[str] | None:
    if value in (None, "", []):
        return None
    parsed = value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "scanner_allowlist must be a JSON array or comma-separated scanner IDs."
                ) from exc
        else:
            parsed = [item.strip() for item in stripped.split(",") if item.strip()]
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes, bytearray)):
        raise ValueError("scanner_allowlist must be a list of scanner IDs.")
    scanners: list[str] = []
    for item in parsed:
        scanner = str(item).strip().lower()
        if not _SAFE_SCANNER_ID.fullmatch(scanner):
            raise ValueError("scanner_allowlist contains an invalid scanner ID.")
        if scanner not in scanners:
            scanners.append(scanner)
        if len(scanners) > 32:
            raise ValueError("scanner_allowlist may contain at most 32 scanner IDs.")
    return scanners or None


class ModelArtifactAnalysisService:
    """Shared fail-closed Static model analysis service used by both workflow nodes."""

    def __init__(self, runner: ModelArtifactAnalysisRunner | None = None):
        self._runner = runner or ProcessModelArtifactAnalysisRunner()

    @staticmethod
    def _base_result(
        *,
        scan_id: str,
        scanned_at: str,
        artifact_name: str,
        artifact_format: str,
        size_bytes: int,
        sha256: str,
        decision: str,
        analysis_incomplete: bool,
        scan_outcome: str,
        scanner: str = "none",
        duration_ms: int = 0,
        findings: list[dict[str, Any]] | None = None,
        counts: Mapping[str, int] | None = None,
        checks: int = 0,
        tests: list[dict[str, Any]] | None = None,
        tests_total: int | None = None,
        tests_truncated: bool = False,
        engine_version: str = STATIC_ANALYSIS_VERSION,
        coverage_reason_codes: Sequence[Any] | None = None,
    ) -> dict[str, Any]:
        severity_counts = counts or {}
        critical = max(0, int(severity_counts.get("critical", 0)))
        warning = max(0, int(severity_counts.get("warning", 0)))
        info = max(0, int(severity_counts.get("info", 0)))
        result = {
            "schema_version": SCHEMA_VERSION,
            "scan_id": scan_id,
            "scanned_at": scanned_at,
            "artifact": {
                "name": artifact_name,
                "format": artifact_format,
                "size_bytes": max(0, int(size_bytes)),
                "sha256": sha256,
                "kind": (
                    "model_directory"
                    if artifact_format == "directory"
                    else "model_artifact"
                ),
            },
            "decision": decision,
            "should_continue": decision == "allow",
            "analysis_incomplete": bool(analysis_incomplete),
            "scan_outcome": scan_outcome,
            "summary": {
                "critical": critical,
                "warning": warning,
                "info": info,
                "total": critical + warning + info,
                "checks": max(0, int(checks)),
            },
            "findings": deepcopy(findings or []),
            "coverage_reason_codes": [
                str(reason)[:96]
                for reason in list(coverage_reason_codes or [])[:16]
                if str(reason).strip()
            ],
            "engine": {
                "name": "Static model analysis",
                "version": engine_version,
                "scanner": scanner,
                "duration_ms": max(0, int(duration_ms)),
            },
        }
        if tests is not None or tests_total is not None:
            result["tests"] = deepcopy(tests or [])
            result["tests_total"] = max(
                len(result["tests"]),
                int(tests_total or 0),
            )
            result["tests_truncated"] = bool(tests_truncated)
        return result

    def _failure_result(
        self,
        *,
        scan_id: str,
        scanned_at: str,
        artifact_name: str,
        artifact_format: str,
        size_bytes: int = 0,
        sha256: str = "",
        decision: str = "error",
    ) -> dict[str, Any]:
        outcome = "inconclusive" if decision == "inconclusive" else "error"
        return self._base_result(
            scan_id=scan_id,
            scanned_at=scanned_at,
            artifact_name=artifact_name,
            artifact_format=artifact_format,
            size_bytes=size_bytes,
            sha256=sha256,
            decision=decision,
            analysis_incomplete=True,
            scan_outcome=outcome,
        )

    def _normalize_engine_result(
        self,
        raw: Mapping[str, Any],
        *,
        scan_id: str,
        scanned_at: str,
        artifact: ModelArtifact,
        size_bytes: int,
        sha256: str,
    ) -> dict[str, Any]:
        raw_metadata = raw.get("metadata")
        metadata: Mapping[str, Any] = (
            raw_metadata if isinstance(raw_metadata, Mapping) else {}
        )
        raw_counts = raw.get("counts")
        counts: Mapping[str, Any] = (
            raw_counts if isinstance(raw_counts, Mapping) else {}
        )
        critical = int(counts.get("critical", 0) or 0)
        warning = int(counts.get("warning", 0) or 0)
        scanner = str(raw.get("scanner") or "unknown").lower()
        checks = max(0, int(raw.get("checks", 0) or 0))
        metadata_name = Path(artifact.name).name.lower()
        data_only_metadata = (
            raw.get("success") is True
            and scanner in {"", "unknown", "skipped", "none"}
            and checks == 0
            and critical == 0
            and warning == 0
            and metadata_name in _DATA_ONLY_MODEL_FILENAMES
        )
        reported_outcome = str(metadata.get("scan_outcome") or "").lower()
        validated_format = (
            metadata.get("validated_format")
            or metadata.get("format")
            or artifact.format_hint
        )
        artifact_format = detect_artifact_format(
            artifact.name, scanner=scanner, format_hint=validated_format
        )

        coverage_gap = (
            bool(metadata.get("analysis_incomplete"))
            or reported_outcome == "inconclusive"
        )
        coverage_gap = coverage_gap or (
            not data_only_metadata and scanner in {"", "unknown", "skipped", "none"}
        )
        coverage_gap = coverage_gap or (
            not data_only_metadata and (checks == 0 or artifact_format == "unknown")
        )
        operational_error = (
            bool(metadata.get("operational_error")) or raw.get("success") is not True
        )

        if critical > 0:
            decision = "block"
        elif coverage_gap:
            decision = "inconclusive"
        elif warning > 0:
            decision = "review"
        elif operational_error:
            decision = "error"
        else:
            decision = "allow"

        scan_outcome = (
            "complete" if decision in {"allow", "review", "block"} else decision
        )
        findings = raw.get("findings") if isinstance(raw.get("findings"), list) else []
        tests = raw.get("tests") if isinstance(raw.get("tests"), list) else None
        raw_reasons = metadata.get("scan_outcome_reasons")
        coverage_reasons = (
            [str(reason) for reason in raw_reasons]
            if isinstance(raw_reasons, Sequence)
            and not isinstance(raw_reasons, (str, bytes, bytearray))
            else []
        )
        if coverage_gap and not coverage_reasons:
            coverage_reasons.append(
                "unsupported_or_unclassified_format"
                if scanner in {"", "unknown", "skipped", "none"}
                else "analysis_incomplete"
            )
        return self._base_result(
            scan_id=scan_id,
            scanned_at=scanned_at,
            artifact_name=sanitize_artifact_name(artifact.name),
            artifact_format=artifact_format,
            size_bytes=size_bytes,
            sha256=sha256,
            decision=decision,
            analysis_incomplete=coverage_gap or decision == "error",
            scan_outcome=scan_outcome,
            scanner="model_metadata" if data_only_metadata else scanner,
            duration_ms=int(raw.get("duration_ms", 0) or 0),
            findings=findings,
            counts=counts,
            checks=checks,
            tests=tests,
            tests_total=raw.get("tests_total") if tests is not None else None,
            tests_truncated=bool(raw.get("tests_truncated", False)),
            engine_version=str(raw.get("engine_version") or STATIC_ANALYSIS_VERSION),
            coverage_reason_codes=coverage_reasons,
        )

    def _scan_single_staged(
        self,
        staged: StagedModelArtifact,
        *,
        policy_profile: Any = "strict",
        scanner_allowlist: Any = None,
    ) -> dict[str, Any]:
        scan_id = str(uuid.uuid4())
        scanned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            profile_name = str(
                policy_profile.get("name", "strict")
                if isinstance(policy_profile, Mapping)
                else policy_profile or "strict"
            ).lower()
            if profile_name not in {"strict", "default"}:
                raise ValueError("Unsupported Static model analysis policy profile.")
            scanners = parse_scanner_allowlist(scanner_allowlist)
            remaining = staged.remaining_seconds()
            scan_config: dict[str, Any] = {
                "cache_scan_results": False,
                "enable_progress": False,
                "max_file_read_size": max(
                    1,
                    (
                        staged.max_bytes
                        if staged.kind == "directory"
                        else staged.size_bytes
                    ),
                ),
                "max_file_size": max(
                    1,
                    (
                        staged.max_bytes
                        if staged.kind == "directory"
                        else staged.size_bytes
                    ),
                ),
                "timeout": remaining,
            }
            if staged.kind == "directory":
                scan_config["max_total_size"] = max(1, staged.max_bytes)
            if scanners:
                scan_config["scanners"] = scanners
            raw = self._runner.run(staged.path, scan_config, remaining, staged.name)
            result = self._normalize_engine_result(
                raw,
                scan_id=scan_id,
                scanned_at=scanned_at,
                artifact=staged.artifact,
                size_bytes=staged.size_bytes,
                sha256=staged.sha256,
            )
        except Exception as exc:
            logger.error(
                "Static model analysis staged scan failed: "
                "scan_id=%s error_type=%s error=%s",
                scan_id,
                type(exc).__name__,
                _safe_text(
                    exc,
                    replace_path=staged.path,
                    artifact_name=staged.name,
                ),
            )
            result = self._failure_result(
                scan_id=scan_id,
                scanned_at=scanned_at,
                artifact_name=staged.name,
                artifact_format=staged.format,
                size_bytes=staged.size_bytes,
                sha256=staged.sha256,
                decision="error",
            )
        json.dumps(result, ensure_ascii=False)
        return result

    @staticmethod
    def _archive_file_result(
        result: Mapping[str, Any], entry_name: str, scan_order: int
    ) -> dict[str, Any]:
        artifact = (
            result.get("artifact")
            if isinstance(result.get("artifact"), Mapping)
            else {}
        )
        summary = (
            result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
        )
        engine = (
            result.get("engine") if isinstance(result.get("engine"), Mapping) else {}
        )
        findings = deepcopy(
            result.get("findings")[:MAX_ENGINE_FINDINGS]
            if isinstance(result.get("findings"), list)
            else []
        )
        severity_counts = {
            "critical": max(0, int(summary.get("critical", 0) or 0)),
            "warning": max(0, int(summary.get("warning", 0) or 0)),
            "info": max(0, int(summary.get("info", 0) or 0)),
        }
        visible_counts = {"critical": 0, "warning": 0, "info": 0}
        for finding in findings:
            severity = str(finding.get("severity") or "").lower()
            if severity in visible_counts:
                visible_counts[severity] += 1
        for severity in severity_counts:
            severity_counts[severity] = max(
                severity_counts[severity],
                visible_counts[severity],
            )
        tests = deepcopy(
            result.get("tests") if isinstance(result.get("tests"), list) else []
        )
        tests_total = max(
            len(tests),
            int(result.get("tests_total", 0) or 0),
        )
        normalized_summary = {
            "critical": severity_counts["critical"],
            "warning": severity_counts["warning"],
            "info": severity_counts["info"],
            "total": max(
                max(0, int(summary.get("total", 0) or 0)),
                sum(severity_counts.values()),
            ),
            "checks": max(0, int(summary.get("checks", 0) or 0)),
        }
        normalized_summary["checks"] = max(
            normalized_summary["checks"],
            len(tests),
        )
        item = {
            "scan_order": max(1, int(scan_order)),
            "path": entry_name,
            "name": str(artifact.get("name") or entry_name),
            "format": str(artifact.get("format") or "unknown"),
            "size_bytes": max(0, int(artifact.get("size_bytes", 0) or 0)),
            "sha256": str(artifact.get("sha256") or ""),
            "decision": str(result.get("decision") or "error"),
            "scan_outcome": str(result.get("scan_outcome") or "error"),
            "analysis_incomplete": bool(result.get("analysis_incomplete")),
            "coverage_reason_codes": list(result.get("coverage_reason_codes") or [])[
                :16
            ],
            "summary": normalized_summary,
            "tests": tests,
            "tests_total": tests_total,
            "tests_truncated": bool(result.get("tests_truncated"))
            or tests_total > len(tests),
            "findings": findings,
            "engine": {
                "name": str(engine.get("name") or "Static model analysis"),
                "version": str(engine.get("version") or "unknown"),
                "scanner": str(engine.get("scanner") or "unknown"),
                "duration_ms": max(0, int(engine.get("duration_ms", 0) or 0)),
            },
        }
        return item

    def _scan_zip_staged(
        self,
        staged: StagedModelArtifact,
        *,
        policy_profile: Any,
        scanner_allowlist: Any,
        archive_depth: int,
    ) -> dict[str, Any]:
        started = time.monotonic()
        scan_id = str(uuid.uuid4())
        scanned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        capabilities = get_static_analysis_capabilities()
        entry_results: list[dict[str, Any]] = []
        skipped_files: list[str] = []
        archive_findings: list[dict[str, Any]] = []
        temp_dir: str | None = None
        limit_reached = False
        expanded_bytes = 0
        # Compressed source admission and expanded archive capacity are separate
        # controls. This prevents a small ZIP bomb while allowing deployments to
        # size archive extraction independently from object/file size.
        archive_max_bytes = configured_archive_expanded_max_bytes()

        try:
            with zipfile.ZipFile(staged.path) as archive:
                infos = archive.infolist()
                limit_reached = len(infos) > MAX_ARCHIVE_ENTRIES
                seen_member_names: set[str] = set()
                temp_dir = tempfile.mkdtemp(prefix="kai-static_analysis-zip-entry-")
                os.chmod(temp_dir, 0o700)
                for index, info in enumerate(infos[:MAX_ARCHIVE_ENTRIES]):
                    if info.is_dir():
                        continue
                    raw_member_name = str(info.filename or "").replace("\\", "/")
                    if raw_member_name in seen_member_names:
                        archive_findings.append(
                            {
                                "severity": "warning",
                                "title": "Duplicate archive member",
                                "message": "Archive contains duplicate member names with ambiguous content.",
                                "rule_code": "DUPLICATE_ARCHIVE_MEMBER",
                                "location": raw_member_name[:MAX_ARCHIVE_MEMBER_NAME],
                            }
                        )
                    seen_member_names.add(raw_member_name)
                    entry_name = _safe_archive_member_name(info.filename)
                    if not entry_name:
                        skipped_files.append("<unsafe archive entry>")
                        archive_findings.append(
                            {
                                "severity": "critical",
                                "title": "Unsafe archive member path",
                                "message": "Archive member uses an absolute or traversal path.",
                                "rule_code": "UNSAFE_ARCHIVE_MEMBER_PATH",
                                "location": raw_member_name[:MAX_ARCHIVE_MEMBER_NAME],
                            }
                        )
                        continue
                    unix_mode = (int(info.external_attr) >> 16) & 0xFFFF
                    if unix_mode and stat.S_ISLNK(unix_mode):
                        skipped_files.append(entry_name)
                        archive_findings.append(
                            {
                                "severity": "critical",
                                "title": "Archive symbolic link",
                                "message": "Archive contains a symbolic-link member.",
                                "rule_code": "ARCHIVE_SYMBOLIC_LINK",
                                "location": entry_name,
                            }
                        )
                        continue
                    if (
                        int(info.file_size) > 1024 * 1024
                        and int(info.compress_size) > 0
                        and int(info.file_size) / int(info.compress_size) > 1000
                    ):
                        skipped_files.append(entry_name)
                        archive_findings.append(
                            {
                                "severity": "critical",
                                "title": "Suspicious archive expansion ratio",
                                "message": "Archive member exceeds the safe compression-ratio threshold.",
                                "rule_code": "ARCHIVE_EXPANSION_RATIO",
                                "location": entry_name,
                            }
                        )
                        continue
                    if not _archive_entry_matches(entry_name, capabilities):
                        skipped_files.append(entry_name)
                        continue

                    scan_order = len(entry_results) + 1

                    declared_size = int(info.file_size)
                    if declared_size < 0 or declared_size > archive_max_bytes:
                        entry_results.append(
                            self._archive_file_result(
                                self._failure_result(
                                    scan_id=str(uuid.uuid4()),
                                    scanned_at=scanned_at,
                                    artifact_name=entry_name,
                                    artifact_format=detect_artifact_format(entry_name),
                                    size_bytes=max(0, declared_size),
                                    decision="inconclusive",
                                ),
                                entry_name,
                                scan_order,
                            )
                        )
                        continue
                    if expanded_bytes + declared_size > archive_max_bytes:
                        limit_reached = True
                        skipped_files.append(f"<archive expansion limit: {entry_name}>")
                        break
                    if time.monotonic() >= staged.deadline_monotonic:
                        limit_reached = True
                        break

                    _ensure_staging_disk_space(temp_dir, declared_size)
                    # Several model formats (for example Hugging Face
                    # tokenizer.json) are routed by their canonical basename.
                    # Keep that basename intact inside a unique directory; a
                    # numeric filename prefix silently changes scanner routing.
                    entry_directory = Path(temp_dir) / str(index)
                    entry_directory.mkdir(mode=0o700)
                    entry_path = entry_directory / sanitize_artifact_name(
                        Path(entry_name).name
                    )
                    entry_size = 0
                    entry_digest = hashlib.sha256()
                    try:
                        with archive.open(info, "r") as source, entry_path.open(
                            "xb"
                        ) as destination:
                            while True:
                                if time.monotonic() >= staged.deadline_monotonic:
                                    raise ModelArtifactAnalysisTimeoutError(
                                        "Archive entry extraction timed out."
                                    )
                                chunk = source.read(COPY_CHUNK_BYTES)
                                if not chunk:
                                    break
                                entry_size += len(chunk)
                                if entry_size > archive_max_bytes:
                                    raise ArtifactTooLargeError(
                                        "Archive entry exceeds the configured maximum size."
                                    )
                                entry_digest.update(chunk)
                                destination.write(chunk)
                        if entry_size != declared_size:
                            raise ArtifactReferenceError(
                                "Archive entry size validation failed."
                            )
                        expanded_bytes += entry_size
                        entry_artifact = ModelArtifact(
                            name=entry_name,
                            size_bytes=entry_size,
                            format_hint=None,
                            storage="archive_entry",
                            stream_factory=lambda path=entry_path: path.open("rb"),
                            direct_path=entry_path,
                        )
                        entry_staged = StagedModelArtifact(
                            artifact=entry_artifact,
                            path=str(entry_path),
                            name=sanitize_artifact_name(entry_name),
                            format=detect_artifact_format(entry_name),
                            size_bytes=entry_size,
                            sha256=entry_digest.hexdigest(),
                            deadline_monotonic=staged.deadline_monotonic,
                            max_bytes=archive_max_bytes,
                        )
                        entry_result = self.scan_staged(
                            entry_staged,
                            policy_profile=policy_profile,
                            scanner_allowlist=scanner_allowlist,
                            archive_depth=archive_depth + 1,
                        )
                    except Exception as exc:
                        logger.error(
                            "Static model analysis archive entry failed: entry=%s error_type=%s",
                            entry_name,
                            type(exc).__name__,
                        )
                        entry_result = self._failure_result(
                            scan_id=str(uuid.uuid4()),
                            scanned_at=scanned_at,
                            artifact_name=entry_name,
                            artifact_format=detect_artifact_format(entry_name),
                            size_bytes=entry_size,
                            sha256=entry_digest.hexdigest(),
                            decision="error",
                        )
                    entry_results.append(
                        self._archive_file_result(
                            entry_result,
                            entry_name,
                            scan_order,
                        )
                    )

                if len(infos) > MAX_ARCHIVE_ENTRIES:
                    skipped_files.append(
                        f"<archive entry limit: {len(infos) - MAX_ARCHIVE_ENTRIES} more>"
                    )
        except (OSError, zipfile.BadZipFile) as exc:
            logger.error(
                "Static model analysis ZIP scan failed: scan_id=%s error_type=%s",
                scan_id,
                type(exc).__name__,
            )
            result = self._failure_result(
                scan_id=scan_id,
                scanned_at=scanned_at,
                artifact_name=staged.name,
                artifact_format="archive",
                size_bytes=staged.size_bytes,
                sha256=staged.sha256,
                decision="error",
            )
            result["archive"] = {
                "files_scanned": 0,
                "files_skipped": 0,
                "supported_extensions": capabilities.get("extensions", []),
                "error": "Archive could not be read.",
            }
            return result
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

        counts = {
            "critical": sum(
                1 for finding in archive_findings if finding["severity"] == "critical"
            ),
            "warning": sum(
                1 for finding in archive_findings if finding["severity"] == "warning"
            ),
            "info": 0,
        }
        checks = len(archive_findings)
        findings: list[dict[str, Any]] = list(archive_findings)
        decisions = (
            ["block"] if counts["critical"] else ["review"] if counts["warning"] else []
        )
        coverage_reason_codes: list[str] = []
        for file_result in entry_results:
            decisions.append(str(file_result.get("decision") or "error"))
            summary = file_result.get("summary") or {}
            for severity in counts:
                counts[severity] += max(0, int(summary.get(severity, 0) or 0))
            checks += max(0, int(summary.get("checks", 0) or 0))
            for reason in list(file_result.get("coverage_reason_codes") or [])[:16]:
                normalized_reason = str(reason)[:96]
                if normalized_reason and normalized_reason not in coverage_reason_codes:
                    coverage_reason_codes.append(normalized_reason)
            for finding in file_result.get("findings", [])[:MAX_ENGINE_FINDINGS]:
                finding_copy = deepcopy(finding)
                finding_copy.setdefault("file", file_result["path"])
                findings.append(finding_copy)

        if not entry_results:
            decision = "inconclusive"
        elif "block" in decisions:
            decision = "block"
        elif limit_reached:
            decision = "inconclusive"
        elif "error" in decisions:
            decision = "error"
        elif "inconclusive" in decisions:
            decision = "inconclusive"
        elif "review" in decisions:
            decision = "review"
        else:
            decision = "allow"
        findings.sort(
            key=lambda item: {"critical": 0, "warning": 1, "info": 2}.get(
                str(item.get("severity")), 3
            )
        )
        result = self._base_result(
            scan_id=scan_id,
            scanned_at=scanned_at,
            artifact_name=staged.name,
            artifact_format="archive",
            size_bytes=staged.size_bytes,
            sha256=staged.sha256,
            decision=decision,
            analysis_incomplete=limit_reached or decision in {"inconclusive", "error"},
            scan_outcome=(
                "complete" if decision in {"allow", "review", "block"} else decision
            ),
            scanner="zip",
            duration_ms=int((time.monotonic() - started) * 1000),
            findings=findings[:MAX_ENGINE_FINDINGS],
            counts=counts,
            checks=checks,
            engine_version=str(capabilities.get("version") or STATIC_ANALYSIS_VERSION),
            coverage_reason_codes=(
                coverage_reason_codes
                + (["archive_limit_reached"] if limit_reached else [])
            ),
        )
        result["files"] = entry_results
        result["archive"] = {
            "files_scanned": len(entry_results),
            "files_skipped": len(skipped_files),
            "skipped": skipped_files[:128],
            "supported_extensions": capabilities.get("extensions", []),
            "scanner_version": capabilities.get("version") or STATIC_ANALYSIS_VERSION,
            "entry_limit_reached": limit_reached,
        }
        result["total_evaluation"] = {
            "decision": decision,
            "should_continue": decision == "allow",
            "scan_outcome": (
                "complete" if decision in {"allow", "review", "block"} else decision
            ),
            "analysis_incomplete": limit_reached
            or decision in {"inconclusive", "error"},
            "tests_truncated": any(
                bool(file_result.get("tests_truncated"))
                for file_result in entry_results
            ),
            "summary": {
                **counts,
                "total": sum(counts.values()),
                "checks": checks,
                "tests_total": sum(
                    max(0, int(file_result.get("tests_total", 0) or 0))
                    for file_result in entry_results
                ),
            },
            "findings": deepcopy(findings[:MAX_ENGINE_FINDINGS]),
            "files_scanned": len(entry_results),
            "files_skipped": len(skipped_files),
        }
        json.dumps(result, ensure_ascii=False)
        return result

    def scan_staged(
        self,
        staged: StagedModelArtifact,
        *,
        policy_profile: Any = "strict",
        scanner_allowlist: Any = None,
        archive_depth: int = 0,
    ) -> dict[str, Any]:
        """Scan a path directly, expanding ZIP files into one bounded JSON result."""

        is_zip = _is_zip_path(staged.path)
        # Only generic .zip bundles are expanded by this adapter. PyTorch,
        # Keras, and other ZIP-based model formats must reach modelaudit as a
        # whole container so their structure-level checks are not bypassed.
        expand_generic_zip = is_zip and Path(staged.name).suffix.lower() == ".zip"
        if expand_generic_zip and archive_depth >= MAX_ARCHIVE_DEPTH:
            result = self._failure_result(
                scan_id=str(uuid.uuid4()),
                scanned_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                artifact_name=staged.name,
                artifact_format="archive",
                size_bytes=staged.size_bytes,
                sha256=staged.sha256,
                decision="inconclusive",
            )
            result["archive"] = {
                "files_scanned": 0,
                "files_skipped": 0,
                "supported_extensions": get_static_analysis_capabilities().get(
                    "extensions", []
                ),
                "scanner_version": installed_static_analysis_version(),
                "error": "Nested archive depth limit was reached.",
            }
            return result
        if expand_generic_zip:
            return self._scan_zip_staged(
                staged,
                policy_profile=policy_profile,
                scanner_allowlist=scanner_allowlist,
                archive_depth=archive_depth,
            )
        return self._scan_single_staged(
            staged,
            policy_profile=policy_profile,
            scanner_allowlist=scanner_allowlist,
        )

    def scan(
        self,
        artifact_value: Any,
        *,
        credential_lookup: Callable[[str], Any] | None = None,
        owner_id: Any = None,
        policy_profile: Any = "strict",
        scanner_allowlist: Any = None,
        max_bytes: Any = DEFAULT_MAX_BYTES,
        timeout_seconds: Any = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Resolve and scan an artifact directly, staging only stream-only sources."""

        scan_id = str(uuid.uuid4())
        scanned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result: dict[str, Any] | None = None
        artifact_name = "artifact.bin"
        artifact_format = "unknown"
        size_bytes = 0
        sha256 = ""

        try:
            artifact = resolve_model_artifact(
                artifact_value,
                credential_lookup=credential_lookup,
                owner_id=owner_id,
            )
            artifact_name = sanitize_artifact_name(artifact.name)
            artifact_format = detect_artifact_format(
                artifact_name, format_hint=artifact.format_hint
            )
            profile_name = str(
                policy_profile.get("name", "strict")
                if isinstance(policy_profile, Mapping)
                else policy_profile or "strict"
            ).lower()
            if profile_name not in {"strict", "default"}:
                raise ValueError("Unsupported Static model analysis policy profile.")

            maximum_bytes = _coerce_positive_int(
                max_bytes, DEFAULT_MAX_BYTES, MAX_MAX_BYTES
            )
            timeout = _coerce_positive_int(
                timeout_seconds, DEFAULT_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
            )
            if artifact.size_bytes is not None and artifact.size_bytes > maximum_bytes:
                result = self._failure_result(
                    scan_id=scan_id,
                    scanned_at=scanned_at,
                    artifact_name=artifact_name,
                    artifact_format=artifact_format,
                    size_bytes=artifact.size_bytes,
                    decision="inconclusive",
                )
            else:
                with stage_model_artifact(
                    artifact,
                    credential_lookup=credential_lookup,
                    owner_id=owner_id,
                    max_bytes=maximum_bytes,
                    timeout_seconds=timeout,
                    prefix="kai-static_analysis-",
                ) as staged:
                    result = self.scan_staged(
                        staged,
                        policy_profile=profile_name,
                        scanner_allowlist=scanner_allowlist,
                    )
                    size_bytes = staged.size_bytes
                    sha256 = staged.sha256
                    if not staged_source_is_unchanged(staged):
                        logger.error(
                            "Local model source changed during Static model analysis: scan_id=%s",
                            scan_id,
                        )
                        result = self._failure_result(
                            scan_id=scan_id,
                            scanned_at=scanned_at,
                            artifact_name=staged.name,
                            artifact_format=staged.format,
                            size_bytes=staged.size_bytes,
                            sha256=staged.sha256,
                            decision="error",
                        )
        except ArtifactTooLargeError:
            result = self._failure_result(
                scan_id=scan_id,
                scanned_at=scanned_at,
                artifact_name=artifact_name,
                artifact_format=artifact_format,
                size_bytes=size_bytes,
                sha256=sha256,
                decision="inconclusive",
            )
        except ArtifactDiskSpaceError:
            result = self._failure_result(
                scan_id=scan_id,
                scanned_at=scanned_at,
                artifact_name=artifact_name,
                artifact_format=artifact_format,
                size_bytes=size_bytes,
                sha256=sha256,
                decision="error",
            )
        except Exception as exc:
            logger.error(
                "Static model analysis scan failed: scan_id=%s error_type=%s",
                scan_id,
                type(exc).__name__,
            )
            result = self._failure_result(
                scan_id=scan_id,
                scanned_at=scanned_at,
                artifact_name=artifact_name,
                artifact_format=artifact_format,
                size_bytes=size_bytes,
                sha256=sha256,
                decision="error",
            )
        assert result is not None
        json.dumps(result, ensure_ascii=False)
        logger.info(
            "Static model analysis scan completed: scan_id=%s decision=%s size_bytes=%d",
            scan_id,
            result["decision"],
            result["artifact"]["size_bytes"],
        )
        return result


model_artifact_analysis_service = ModelArtifactAnalysisService()


__all__ = [
    "ArtifactDiskSpaceError",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "InProcessModelArtifactAnalysisRunner",
    "STATIC_ANALYSIS_VERSION",
    "ModelArtifact",
    "ModelArtifactAnalysisRunnerError",
    "ModelArtifactAnalysisService",
    "ModelArtifactAnalysisTimeoutError",
    "MAX_MAX_BYTES",
    "StagedModelArtifact",
    "configured_local_model_roots",
    "detect_artifact_format",
    "get_static_analysis_capabilities",
    "installed_static_analysis_version",
    "model_artifact_analysis_service",
    "resolve_model_artifact",
    "sanitize_artifact_name",
    "staged_source_is_unchanged",
    "stage_model_artifact",
]
