"""Conditional, process-isolated Pickle security analysis for Pickle/PyTorch artifacts."""

from __future__ import annotations

import logging
import os
import time
import zipfile
from collections.abc import Callable, Mapping
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Protocol

from app.services.model_artifact_analysis_service import (
    DEFAULT_TIMEOUT_SECONDS,
    StagedModelArtifact,
    staged_source_is_unchanged,
    stage_model_artifact,
)
from app.services.model_scan_process import (
    IsolatedProcessError,
    IsolatedProcessTimeoutError,
    run_in_isolated_process,
)
from app.services.model_security_error_catalog import (
    enrich_security_finding,
    infer_serialization_source_code,
)
from app.services.model_scan_limits import (
    DEFAULT_PICKLE_MAX_BYTES,
    HARD_PICKLE_MAX_BYTES,
)
from app.services.security_audit_service import make_layer_result


logger = logging.getLogger(__name__)

PICKLE_ENGINE_VERSION = "0.1.12"
MAX_PICKLE_MEMORY_BYTES = HARD_PICKLE_MAX_BYTES
MAX_PICKLE_FINDINGS = 32_768
MAX_PICKLE_TESTS = 512
MAX_PICKLE_ARCHIVE_ENTRIES = 512
MAX_PICKLE_CONTAINER_ENTRIES = 32_768
MAX_PICKLE_ARCHIVE_DEPTH = 4
MAX_PICKLE_ANALYSIS_GROUPS = 32
MAX_PICKLE_ANALYSES_PER_GROUP = MAX_PICKLE_FINDINGS
_APPLICABLE_FORMATS = {"pickle", "pytorch", "checkpoint"}
_APPLICABLE_SUFFIXES = {".pkl", ".pickle", ".pt", ".pth", ".ckpt", ".bin"}
_DIRECTORY_APPLICABLE_SUFFIXES = _APPLICABLE_SUFFIXES | {".zip"}


class PickleSecurityRunnerError(RuntimeError):
    """Raised when the isolated Pickle security analysis worker cannot return a result."""


class PickleSecurityTimeoutError(PickleSecurityRunnerError):
    """Raised when the Pickle security analysis worker exceeds its deadline."""


class PickleSecurityRunner(Protocol):
    def run(
        self,
        path: str,
        *,
        timeout_seconds: int,
        artifact_name: str,
        max_memory_bytes: int,
        max_scan_bytes: int,
    ) -> dict[str, Any]:
        """Analyze one service-owned artifact path."""


def _bounded_text(
    value: Any, *, path: str, artifact_name: str, limit: int = 320
) -> str:
    # Some scanner result objects deliberately evaluate to False even though
    # their string representation carries the actual finding evidence.
    raw = "" if value is None else value
    text = str(raw).replace(path, artifact_name).replace("\x00", "")
    return " ".join(text.split())[:limit]


def _severity_number(value: Any) -> int:
    try:
        return max(0, min(5, int(getattr(value, "severity", value))))
    except (TypeError, ValueError):
        return 0


def _scan_result_payload(
    scan_results: Mapping[str, Any], *, path: str, artifact_name: str
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    errors: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    checks = 0
    max_severity = 0

    scan_items = list(scan_results.items())
    if len(scan_items) > MAX_PICKLE_ARCHIVE_ENTRIES:
        errors.append("Pickle security analysis archive-entry limit was reached.")
    engine_version = importlib_metadata.version("fickling")
    for scan_order, (location, scan_result) in enumerate(
        scan_items[:MAX_PICKLE_ARCHIVE_ENTRIES], start=1
    ):
        file_findings: list[dict[str, Any]] = []
        file_tests: list[dict[str, Any]] = []
        file_errors: list[str] = []
        file_checks = 0
        file_max_severity = _severity_number(getattr(scan_result, "severity", 0))
        max_severity = max(max_severity, file_max_severity)
        for error in list(getattr(scan_result, "errors", []) or [])[:8]:
            bounded_error = _bounded_text(
                error, path=path, artifact_name=artifact_name, limit=192
            )
            errors.append(bounded_error)
            file_errors.append(bounded_error)
            scanner_rule_code = (
                infer_serialization_source_code(bounded_error) or "AnalysisError"
            )
            diagnostics.append(
                {
                    "code": str(scanner_rule_code),
                    "severity": "error",
                    "location": _bounded_text(
                        location,
                        path=path,
                        artifact_name=artifact_name,
                        limit=192,
                    ),
                    "message": bounded_error,
                }
            )
        analysis_groups = list(getattr(scan_result, "results", []) or [])
        if len(analysis_groups) > MAX_PICKLE_ANALYSIS_GROUPS:
            errors.append("Pickle analysis-group limit was reached.")
            file_errors.append("Pickle analysis-group limit was reached.")
        for analysis_results in analysis_groups[:MAX_PICKLE_ANALYSIS_GROUPS]:
            analyses = list(getattr(analysis_results, "results", []) or [])
            remaining_analyses = max(0, MAX_PICKLE_FINDINGS - checks)
            analysis_limit = min(
                MAX_PICKLE_ANALYSES_PER_GROUP,
                remaining_analyses,
            )
            if len(analyses) > analysis_limit:
                errors.append("Pickle security analysis finding limit was reached.")
                file_errors.append(
                    "Pickle security analysis finding limit was reached."
                )
            for analysis in analyses[:analysis_limit]:
                severity_number = _severity_number(getattr(analysis, "severity", 0))
                checks += 1
                file_checks += 1
                max_severity = max(max_severity, severity_number)
                analysis_name = _bounded_text(
                    getattr(analysis, "analysis_name", None),
                    path=path,
                    artifact_name=artifact_name,
                    limit=96,
                )
                message = _bounded_text(
                    analysis,
                    path=path,
                    artifact_name=artifact_name,
                )
                scanner_rule_code = analysis_name or infer_serialization_source_code(
                    message
                )
                title = _bounded_text(
                    getattr(analysis, "analysis_name", None)
                    or scanner_rule_code
                    or "Pickle security analysis pickle check",
                    path=path,
                    artifact_name=artifact_name,
                    limit=160,
                )
                finding_metadata = enrich_security_finding(
                    "serialization_analysis",
                    scanner_rule_code,
                    severity=severity_number,
                    message=message,
                )
                rule_code = str(
                    finding_metadata.get("rule_code")
                    or scanner_rule_code
                    or "pickle_security-analysis"
                )
                if len(file_tests) < MAX_PICKLE_TESTS:
                    test = {
                        "name": title,
                        "status": "failed" if severity_number > 0 else "passed",
                        "message": message,
                    }
                    if severity_number > 0:
                        test["severity"] = (
                            "critical" if severity_number >= 3 else "warning"
                        )
                    if rule_code:
                        test["rule_code"] = rule_code
                    test.update(finding_metadata)
                    file_tests.append(test)
                if severity_number <= 0:
                    continue
                finding = {
                    "severity": "critical" if severity_number >= 3 else "warning",
                    "title": title,
                    "message": message,
                    "rule_code": rule_code,
                    "location": _bounded_text(
                        location,
                        path=path,
                        artifact_name=artifact_name,
                        limit=192,
                    ),
                }
                finding.update(finding_metadata)
                findings.append(finding)
                file_findings.append(finding)

        file_findings.sort(
            key=lambda finding: 0 if finding["severity"] == "critical" else 1
        )
        file_critical = sum(
            1 for finding in file_findings if finding["severity"] == "critical"
        )
        file_warning = sum(
            1 for finding in file_findings if finding["severity"] == "warning"
        )
        file_decision = (
            "block"
            if file_max_severity >= 3
            else (
                "inconclusive"
                if file_errors
                else "review" if file_max_severity > 0 else "allow"
            )
        )
        location_text = _bounded_text(
            location, path=path, artifact_name=artifact_name, limit=240
        )
        files.append(
            {
                "scan_order": scan_order,
                "path": location_text,
                "name": Path(str(location)).name or location_text,
                "format": (
                    "pickle"
                    if Path(str(location)).suffix.lower() in {".pkl", ".pickle"}
                    else "pytorch"
                ),
                "decision": file_decision,
                "scan_outcome": (
                    "complete"
                    if file_decision in {"allow", "review", "block"}
                    else file_decision
                ),
                "analysis_incomplete": bool(file_errors),
                "summary": {
                    "critical": file_critical,
                    "warning": file_warning,
                    "info": 0,
                    "total": file_critical + file_warning,
                    "checks": file_checks,
                },
                "tests": file_tests,
                "tests_total": file_checks,
                "tests_truncated": file_checks > len(file_tests),
                "findings": file_findings[:MAX_PICKLE_FINDINGS],
                "engine": {
                    "name": "Pickle security analysis",
                    "version": engine_version,
                    "scanner": "pickle_security",
                },
            }
        )

    findings.sort(key=lambda finding: 0 if finding["severity"] == "critical" else 1)
    finding_counts = {
        "critical": sum(
            1 for finding in findings if finding.get("severity") == "critical"
        ),
        "warning": sum(
            1 for finding in findings if finding.get("severity") == "warning"
        ),
        "info": 0,
    }
    return {
        "success": not errors,
        "max_severity": max_severity,
        "checks": checks,
        "findings": findings[:MAX_PICKLE_FINDINGS],
        "findings_total": len(findings),
        "finding_counts": finding_counts,
        "files": files,
        "errors": errors,
        "diagnostics": diagnostics,
        "engine_version": engine_version,
    }


def _execute_pickle_scan(
    path: str, artifact_name: str, max_scan_bytes: int
) -> dict[str, Any]:
    import shutil  # noqa: PLC0415 - isolated worker import
    import tempfile  # noqa: PLC0415 - isolated worker import
    import zipfile  # noqa: PLC0415 - isolated worker import

    from fickling.loader import scan_file  # noqa: PLC0415

    started = time.monotonic()
    byte_limit = max(1, int(max_scan_bytes))
    raw_results: dict[str, Any] = {}
    traversal_diagnostics: list[dict[str, Any]] = []
    expanded_bytes = 0
    candidates_seen = 0

    def add_diagnostic(code: str, message: str, location: str) -> None:
        traversal_diagnostics.append(
            {
                "code": code,
                "severity": "error",
                "message": message,
                "location": location[:240],
            }
        )

    def safe_member_name(name: str) -> str | None:
        normalized = str(name or "").replace("\\", "/")
        parts = [part for part in normalized.split("/") if part not in {"", "."}]
        if (
            not parts
            or normalized.startswith("/")
            or any(part == ".." for part in parts)
            or ":" in parts[0]
        ):
            return None
        return "/".join(parts)

    with tempfile.TemporaryDirectory(prefix="kai-pickle-security-") as temp_root:

        def scan_candidate(candidate: Path, logical_name: str, depth: int) -> None:
            nonlocal expanded_bytes, candidates_seen
            if candidates_seen >= MAX_PICKLE_ARCHIVE_ENTRIES:
                add_diagnostic(
                    "pickle_candidate_limit_reached",
                    "Pickle/PyTorch candidate limit was reached.",
                    logical_name,
                )
                return
            candidates_seen += 1

            try:
                is_archive = zipfile.is_zipfile(candidate)
            except OSError:
                is_archive = False
            if not is_archive:
                raw_results[logical_name] = scan_file(candidate, graceful=True)
                return

            if depth >= MAX_PICKLE_ARCHIVE_DEPTH:
                add_diagnostic(
                    "pickle_archive_depth_limit_reached",
                    "Nested Pickle/PyTorch archive depth limit was reached.",
                    logical_name,
                )
                return

            try:
                with zipfile.ZipFile(candidate) as archive:
                    infos = archive.infolist()
                    if len(infos) > MAX_PICKLE_CONTAINER_ENTRIES:
                        add_diagnostic(
                            "pickle_archive_entry_limit_reached",
                            "Archive contains more entries than the bounded Pickle/PyTorch inspection limit.",
                            logical_name,
                        )
                        infos = infos[:MAX_PICKLE_CONTAINER_ENTRIES]

                    relevant_infos = [
                        info
                        for info in infos
                        if not info.is_dir()
                        and Path(str(info.filename).replace("\\", "/")).suffix.lower()
                        in _DIRECTORY_APPLICABLE_SUFFIXES
                    ]
                    for info in relevant_infos:
                        if candidates_seen >= MAX_PICKLE_ARCHIVE_ENTRIES:
                            add_diagnostic(
                                "pickle_candidate_limit_reached",
                                "Pickle/PyTorch candidate limit was reached.",
                                logical_name,
                            )
                            break
                        member_name = safe_member_name(info.filename)
                        member_location = (
                            f"{logical_name}!/{member_name}"
                            if member_name
                            else f"{logical_name}!/<unsafe-entry>"
                        )
                        if member_name is None:
                            add_diagnostic(
                                "unsafe_archive_member",
                                "Unsafe archive member name was rejected.",
                                member_location,
                            )
                            continue
                        if info.flag_bits & 0x1:
                            add_diagnostic(
                                "encrypted_archive_member",
                                "Encrypted archive members cannot be inspected.",
                                member_location,
                            )
                            continue
                        declared_size = int(info.file_size)
                        if (
                            declared_size < 0
                            or declared_size > byte_limit
                            or expanded_bytes + declared_size > byte_limit
                        ):
                            add_diagnostic(
                                "pickle_expansion_limit_reached",
                                "Pickle/PyTorch archive expansion limit was reached.",
                                member_location,
                            )
                            continue

                        free_bytes = shutil.disk_usage(temp_root).free
                        if declared_size > max(0, free_bytes - 64 * 1024 * 1024):
                            add_diagnostic(
                                "insufficient_temporary_disk_space",
                                "Insufficient temporary disk space for bounded Pickle/PyTorch inspection.",
                                member_location,
                            )
                            continue

                        member_directory = (
                            Path(temp_root) / str(depth) / str(candidates_seen)
                        )
                        member_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                        member_path = member_directory / (
                            Path(member_name).name or "artifact.bin"
                        )
                        actual_size = 0
                        try:
                            with archive.open(info, "r") as source, member_path.open(
                                "xb"
                            ) as destination:
                                while True:
                                    chunk = source.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    actual_size += len(chunk)
                                    if (
                                        actual_size > declared_size
                                        or expanded_bytes + actual_size > byte_limit
                                    ):
                                        raise ValueError(
                                            "archive expansion limit reached"
                                        )
                                    destination.write(chunk)
                            if actual_size != declared_size:
                                raise ValueError("archive member size mismatch")
                        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile):
                            add_diagnostic(
                                "pickle_archive_member_read_error",
                                "Archive member could not be read safely.",
                                member_location,
                            )
                            continue
                        expanded_bytes += actual_size
                        scan_candidate(member_path, member_location, depth + 1)
            except (OSError, zipfile.BadZipFile):
                add_diagnostic(
                    "pickle_archive_read_error",
                    "Pickle/PyTorch archive could not be read.",
                    logical_name,
                )

        if os.path.isdir(path):
            root = Path(path)
            candidates = sorted(
                (
                    candidate
                    for candidate in root.rglob("*")
                    if candidate.is_file()
                    and not candidate.is_symlink()
                    and candidate.suffix.lower() in _DIRECTORY_APPLICABLE_SUFFIXES
                ),
                key=lambda candidate: candidate.relative_to(root).as_posix(),
            )
            if len(candidates) > MAX_PICKLE_ARCHIVE_ENTRIES:
                add_diagnostic(
                    "pickle_candidate_limit_reached",
                    "Directory contains more Pickle/PyTorch candidates than the inspection limit.",
                    artifact_name,
                )
            for candidate in candidates[:MAX_PICKLE_ARCHIVE_ENTRIES]:
                scan_candidate(
                    candidate,
                    candidate.relative_to(root).as_posix(),
                    0,
                )
        else:
            scan_candidate(Path(path), artifact_name, 0)

    if not raw_results and not traversal_diagnostics:
        return {
            "success": True,
            "max_severity": 0,
            "checks": 0,
            "findings": [],
            "findings_total": 0,
            "errors": [],
            "diagnostics": [],
            "no_applicable_files": True,
            "engine_version": importlib_metadata.version("fickling"),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    payload = _scan_result_payload(raw_results, path=path, artifact_name=artifact_name)
    if traversal_diagnostics:
        payload.setdefault("diagnostics", []).extend(traversal_diagnostics)
        payload.setdefault("errors", []).extend(
            diagnostic["message"] for diagnostic in traversal_diagnostics
        )
        payload["success"] = False
    payload["duration_ms"] = int((time.monotonic() - started) * 1000)
    return payload


def _pickle_worker_memory_limit(max_memory_bytes: int) -> int:
    return max(128 * 1024 * 1024, min(max_memory_bytes, MAX_PICKLE_MEMORY_BYTES))


def _set_worker_limits(max_memory_bytes: int, timeout_seconds: int) -> None:
    try:
        import resource  # noqa: PLC0415 - unavailable on some platforms

        memory_limit = _pickle_worker_memory_limit(max_memory_bytes)
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        cpu_limit = max(1, int(timeout_seconds) + 1)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    except (ImportError, OSError, ValueError):
        # The parent process still enforces a killable wall-clock timeout.
        return


def _pickle_process_entry(
    send_connection: Any,
    path: str,
    timeout_seconds: int,
    artifact_name: str,
    max_memory_bytes: int,
    max_scan_bytes: int,
) -> None:
    try:
        _set_worker_limits(max_memory_bytes, timeout_seconds)
        send_connection.send(
            {
                "ok": True,
                "result": _execute_pickle_scan(path, artifact_name, max_scan_bytes),
            }
        )
    except BaseException as exc:
        try:
            send_connection.send(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error_message": _bounded_text(
                        exc,
                        path=path,
                        artifact_name=artifact_name,
                    ),
                }
            )
        except BaseException:
            pass
    finally:
        send_connection.close()


class ProcessPickleSecurityRunner:
    """Run Pickle security analysis in a killable child process with resource limits."""

    def __init__(self, start_method: str | None = None):
        self._start_method = start_method

    def run(
        self,
        path: str,
        *,
        timeout_seconds: int,
        artifact_name: str,
        max_memory_bytes: int,
        max_scan_bytes: int,
    ) -> dict[str, Any]:
        memory_limit_bytes = _pickle_worker_memory_limit(max_memory_bytes)
        try:
            return run_in_isolated_process(
                target=_pickle_process_entry,
                worker_args=(
                    path,
                    timeout_seconds,
                    artifact_name,
                    max_memory_bytes,
                    max_scan_bytes,
                ),
                timeout_seconds=timeout_seconds,
                worker_name="Pickle security analysis",
                memory_limit_bytes=memory_limit_bytes,
                artifact_path=path,
                artifact_name=artifact_name,
                start_method=self._start_method,
            )
        except IsolatedProcessTimeoutError as exc:
            raise PickleSecurityTimeoutError(str(exc)) from exc
        except IsolatedProcessError as exc:
            raise PickleSecurityRunnerError(str(exc)) from exc


class InProcessPickleSecurityRunner:
    """Test runner that uses the same bounded payload conversion in-process."""

    def run(
        self,
        path: str,
        *,
        timeout_seconds: int,
        artifact_name: str,
        max_memory_bytes: int,
        max_scan_bytes: int,
    ) -> dict[str, Any]:
        return _execute_pickle_scan(path, artifact_name, max_scan_bytes)


class PickleSecurityService:
    def __init__(self, runner: PickleSecurityRunner | None = None):
        self._runner = runner or ProcessPickleSecurityRunner()

    @staticmethod
    def is_applicable(staged: StagedModelArtifact) -> bool:
        return (
            staged.kind == "directory"
            or staged.format in _APPLICABLE_FORMATS
            or Path(staged.name.lower()).suffix in _APPLICABLE_SUFFIXES
            or (
                staged.format == "archive"
                and Path(staged.name.lower()).suffix == ".zip"
            )
        )

    def scan_staged(
        self,
        staged: StagedModelArtifact,
        *,
        max_bytes: Any = DEFAULT_PICKLE_MAX_BYTES,
        max_memory_bytes: int = MAX_PICKLE_MEMORY_BYTES,
    ) -> dict[str, Any]:
        target = {
            "name": staged.name,
            "format": staged.format,
            "size_bytes": staged.size_bytes,
            "sha256": staged.sha256,
            "kind": (
                "model_directory" if staged.kind == "directory" else "model_artifact"
            ),
        }
        if not self.is_applicable(staged):
            return make_layer_result(
                layer_id="pickle_security",
                engine_name="Pickle security analysis",
                engine_version=PICKLE_ENGINE_VERSION,
                decision="allow",
                status="not_applicable",
                applicable=False,
                target=target,
                coverage_complete=True,
                reason_codes=["format_not_applicable"],
            )

        try:
            maximum_bytes = max(1, min(int(max_bytes), MAX_PICKLE_MEMORY_BYTES))
        except (TypeError, ValueError):
            maximum_bytes = DEFAULT_PICKLE_MAX_BYTES
        try:
            staged_is_zip_container = staged.kind != "directory" and zipfile.is_zipfile(
                staged.path
            )
        except OSError:
            staged_is_zip_container = False
        applicable_size = 0 if staged_is_zip_container else staged.size_bytes
        if staged.kind == "directory":
            applicable_size = 0
            applicable_count = 0
            for root, directory_names, filenames in os.walk(
                staged.path, followlinks=False
            ):
                directory_names[:] = sorted(directory_names)
                for filename in sorted(filenames):
                    candidate = Path(root) / filename
                    if (
                        candidate.suffix.lower() not in _DIRECTORY_APPLICABLE_SUFFIXES
                        or candidate.is_symlink()
                    ):
                        continue
                    applicable_count += 1
                    try:
                        # Container size is not a useful proxy for the amount of
                        # Pickle data inside it. Expanded relevant members are
                        # bounded in the isolated worker instead.
                        if not zipfile.is_zipfile(candidate):
                            applicable_size += candidate.stat().st_size
                    except OSError:
                        applicable_count = MAX_PICKLE_ARCHIVE_ENTRIES + 1
                        break
                if applicable_count > MAX_PICKLE_ARCHIVE_ENTRIES:
                    break
            if applicable_count == 0:
                return make_layer_result(
                    layer_id="pickle_security",
                    engine_name="Pickle security analysis",
                    engine_version=PICKLE_ENGINE_VERSION,
                    decision="allow",
                    status="not_applicable",
                    applicable=False,
                    target=target,
                    coverage_complete=True,
                    reason_codes=["format_not_applicable"],
                )
            if applicable_count > MAX_PICKLE_ARCHIVE_ENTRIES:
                return make_layer_result(
                    layer_id="pickle_security",
                    engine_name="Pickle security analysis",
                    engine_version=PICKLE_ENGINE_VERSION,
                    decision="inconclusive",
                    status="unsupported",
                    applicable=True,
                    target=target,
                    coverage_complete=False,
                    reason_codes=["directory_entry_limit_reached"],
                )
        if applicable_size > maximum_bytes:
            return make_layer_result(
                layer_id="pickle_security",
                engine_name="Pickle security analysis",
                engine_version=PICKLE_ENGINE_VERSION,
                decision="inconclusive",
                status="unsupported",
                applicable=True,
                target=target,
                coverage_complete=False,
                reason_codes=["artifact_exceeds_pickle_limit"],
            )

        started = time.monotonic()
        try:
            raw = self._runner.run(
                staged.path,
                timeout_seconds=staged.remaining_seconds(),
                artifact_name=staged.name,
                max_memory_bytes=max_memory_bytes,
                max_scan_bytes=maximum_bytes,
            )
            severity_number = int(raw.get("max_severity", 0) or 0)
            errors = raw.get("errors") if isinstance(raw.get("errors"), list) else []
            diagnostics = (
                raw.get("diagnostics")
                if isinstance(raw.get("diagnostics"), list)
                else []
            )
            scan_succeeded = raw.get("success") is True
            if severity_number >= 3:
                decision = "block"
            elif errors or not scan_succeeded:
                decision = "inconclusive"
            elif severity_number > 0:
                decision = "review"
            else:
                decision = "allow"
            status = "complete" if scan_succeeded and not errors else "inconclusive"
            findings = (
                raw.get("findings") if isinstance(raw.get("findings"), list) else []
            )
            raw_counts = (
                raw.get("finding_counts")
                if isinstance(raw.get("finding_counts"), Mapping)
                else {}
            )
            critical = max(
                int(raw_counts.get("critical", 0) or 0),
                sum(1 for item in findings if item.get("severity") == "critical"),
            )
            warning = max(
                int(raw_counts.get("warning", 0) or 0),
                sum(1 for item in findings if item.get("severity") == "warning"),
            )
            files = raw.get("files") if isinstance(raw.get("files"), list) else []
            if raw.get("no_applicable_files") and not files:
                return make_layer_result(
                    layer_id="pickle_security",
                    engine_name="Pickle security analysis",
                    engine_version=str(
                        raw.get("engine_version") or PICKLE_ENGINE_VERSION
                    ),
                    decision="allow",
                    status="not_applicable",
                    applicable=False,
                    target=target,
                    coverage_complete=True,
                    reason_codes=["no_supported_archive_entries"],
                )
            result = make_layer_result(
                layer_id="pickle_security",
                engine_name="Pickle security analysis",
                engine_version=str(raw.get("engine_version") or PICKLE_ENGINE_VERSION),
                decision=decision,
                status=status,
                target=target,
                counts={"critical": critical, "warning": warning, "info": 0},
                checks=raw.get("checks", 0),
                findings=findings,
                duration_ms=raw.get("duration_ms", 0),
                coverage_complete=scan_succeeded and not errors,
                reason_codes=(
                    [
                        str(item.get("code") or "analysis_error")
                        for item in diagnostics
                        if isinstance(item, Mapping)
                    ][:16]
                    or (["analysis_error"] if errors or not scan_succeeded else [])
                ),
                diagnostics=diagnostics,
            )
            if files:
                result["files"] = files
                if Path(staged.name.lower()).suffix == ".zip":
                    result["archive"] = {
                        "files_scanned": len(files),
                        "files_skipped": 0,
                        "scanner_version": str(
                            raw.get("engine_version") or PICKLE_ENGINE_VERSION
                        ),
                    }
            return result
        except PickleSecurityTimeoutError as exc:
            logger.warning(
                "Pickle security analysis scan timed out: error=%s",
                _bounded_text(exc, path=staged.path, artifact_name=staged.name),
            )
            status = "timeout"
            reasons = ["timeout"]
        except Exception as exc:
            logger.error(
                "Pickle security analysis scan failed: error_type=%s error=%s",
                type(exc).__name__,
                _bounded_text(exc, path=staged.path, artifact_name=staged.name),
            )
            status = "error"
            reasons = ["engine_error"]
        return make_layer_result(
            layer_id="pickle_security",
            engine_name="Pickle security analysis",
            engine_version=PICKLE_ENGINE_VERSION,
            decision="error",
            status=status,
            target=target,
            duration_ms=int((time.monotonic() - started) * 1000),
            coverage_complete=False,
            reason_codes=reasons,
        )

    def scan(
        self,
        artifact_value: Any,
        *,
        credential_lookup: Callable[[str], Any] | None = None,
        owner_id: Any = None,
        max_bytes: Any = DEFAULT_PICKLE_MAX_BYTES,
        timeout_seconds: Any = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        try:
            with stage_model_artifact(
                artifact_value,
                credential_lookup=credential_lookup,
                owner_id=owner_id,
                max_bytes=max_bytes,
                timeout_seconds=timeout_seconds,
                prefix="kai-pickle_security-",
            ) as staged:
                result = self.scan_staged(
                    staged,
                    max_bytes=max_bytes,
                )
                if not staged_source_is_unchanged(staged):
                    return make_layer_result(
                        layer_id="pickle_security",
                        engine_name="Pickle security analysis",
                        engine_version=PICKLE_ENGINE_VERSION,
                        decision="error",
                        status="error",
                        applicable=True,
                        target={
                            "name": staged.name,
                            "format": staged.format,
                            "size_bytes": staged.size_bytes,
                            "sha256": staged.sha256,
                            "kind": (
                                "model_directory"
                                if staged.kind == "directory"
                                else "model_artifact"
                            ),
                        },
                        coverage_complete=False,
                        reason_codes=["artifact_changed_during_scan"],
                    )
                return result
        except Exception as exc:
            logger.error(
                "Pickle security analysis artifact staging failed: error_type=%s",
                type(exc).__name__,
            )
            return make_layer_result(
                layer_id="pickle_security",
                engine_name="Pickle security analysis",
                engine_version=PICKLE_ENGINE_VERSION,
                decision="error",
                status="error",
                applicable=True,
                coverage_complete=False,
                reason_codes=["artifact_staging_error"],
            )


pickle_security_service = PickleSecurityService()


__all__ = [
    "DEFAULT_PICKLE_MAX_BYTES",
    "PICKLE_ENGINE_VERSION",
    "PickleSecurityRunnerError",
    "PickleSecurityService",
    "PickleSecurityTimeoutError",
    "InProcessPickleSecurityRunner",
    "ProcessPickleSecurityRunner",
    "pickle_security_service",
]
