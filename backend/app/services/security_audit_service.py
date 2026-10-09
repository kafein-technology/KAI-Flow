"""Shared, bounded contracts for layered model-security controls.

The individual scanners intentionally keep their native reports behind their
service boundary.  Workflow state receives only the normalized layer envelope
defined here, and the policy gate combines those envelopes deterministically.
"""

from __future__ import annotations

import json
import hashlib
import re
import time
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from itertools import islice
from typing import Any

from app.services.model_security_error_catalog import enrich_security_finding


LAYER_SCHEMA_VERSION = "kai.security.layer.v1"
AUDIT_SCHEMA_VERSION = "kai.security.audit.v1"
PUBLIC_RESULT_SCHEMA_VERSION = "kai.model_security.result.v2"
POLICY_VERSION = "1"
# Presentation never applies a "top N" cut. This high ceiling is a defensive
# contract limit; scanner-side resource limits determine the normally retained set.
MAX_FINDING_CANDIDATES = 32_768
MAX_ARCHIVE_TESTS = 512
MAX_DIAGNOSTICS = 128
MAX_TEXT = 320

_SAFE_LAYER_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_VALID_DECISIONS = {"allow", "review", "block", "inconclusive", "error"}
_VALID_STATUSES = {
    "complete",
    "not_applicable",
    "unsupported",
    "timeout",
    "inconclusive",
    "error",
}
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_LAYER_LABELS = {
    "static_analysis": "Artifact security analysis",
    "pickle_security": "Pickle/PyTorch security analysis",
}


def _safe_text(value: Any, limit: int = MAX_TEXT) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
        return default
    if isinstance(value, (int, float)):
        return value != 0
    return default


def _severity(value: Any) -> str:
    normalized = str(getattr(value, "name", value) or "info").lower()
    if normalized in {
        "critical",
        "high",
        "overtly_malicious",
        "likely_overtly_malicious",
    }:
        return "critical"
    if normalized in {
        "warning",
        "medium",
        "suspicious",
        "likely_unsafe",
        "possibly_unsafe",
    }:
        return "warning"
    return "info"


def _bounded_findings(
    findings: Any,
    limit: int | None = None,
    *,
    layer_id: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(findings, Sequence) or isinstance(
        findings, (str, bytes, bytearray)
    ):
        return []
    bounded: list[dict[str, Any]] = []
    for raw in islice(findings, MAX_FINDING_CANDIDATES):
        item = raw if isinstance(raw, Mapping) else {"message": raw}
        finding: dict[str, Any] = {
            "severity": _severity(item.get("severity")),
            "title": _safe_text(
                item.get("title") or item.get("type") or "Security finding", 160
            ),
            "message": _safe_text(item.get("message") or item.get("description") or ""),
        }
        for source_key, target_key, field_limit in (
            ("rule_code", "rule_code", 96),
            ("rule_description", "rule_description", MAX_TEXT),
            ("rule_solution", "rule_solution", MAX_TEXT),
            ("risk_level", "risk_level", 32),
            ("rule_id", "rule_code", 96),
            ("category", "category", 96),
            ("location", "location", 192),
            ("remediation", "remediation", MAX_TEXT),
            ("fixed_version", "fixed_version", 96),
        ):
            if item.get(source_key) not in (None, ""):
                finding[target_key] = _safe_text(item[source_key], field_limit)
        finding_layer_id = str(layer_id or item.get("layer_id") or "").strip().lower()
        scanner_rule_code = item.get("rule_code")
        if (
            finding_layer_id in {"static_analysis", "pickle_security"}
            and scanner_rule_code
        ):
            finding.update(
                enrich_security_finding(
                    finding_layer_id,
                    scanner_rule_code,
                    severity=item.get("severity"),
                    message=finding.get("message"),
                )
            )
        bounded.append(finding)
    bounded.sort(key=lambda item: _SEVERITY_ORDER.get(str(item.get("severity")), 3))
    return bounded if limit is None else bounded[: max(0, limit)]


def _bounded_tests(tests: Any) -> list[dict[str, Any]]:
    if not isinstance(tests, Sequence) or isinstance(tests, (str, bytes, bytearray)):
        return []
    bounded: list[dict[str, Any]] = []
    for raw in list(tests)[:MAX_ARCHIVE_TESTS]:
        if not isinstance(raw, Mapping):
            continue
        item: dict[str, Any] = {}
        for key, limit in (
            ("name", 160),
            ("status", 32),
            ("message", MAX_TEXT),
            ("severity", 32),
            ("rule_code", 96),
            ("rule_description", MAX_TEXT),
            ("rule_solution", MAX_TEXT),
            ("risk_level", 32),
            ("why", MAX_TEXT),
            ("location", 192),
        ):
            if raw.get(key) not in (None, ""):
                item[key] = _safe_text(raw[key], limit)
        bounded.append(item)
    return bounded


def _bounded_target(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    target: dict[str, Any] = {}
    for key, limit in (
        ("name", 160),
        ("format", 64),
        ("sha256", 64),
        ("kind", 32),
        ("reference", 256),
    ):
        if value.get(key) not in (None, ""):
            target[key] = _safe_text(value[key], limit)
    if value.get("size_bytes") is not None:
        target["size_bytes"] = _positive_int(value.get("size_bytes"))
    return target


def _bounded_diagnostics(value: Any) -> list[dict[str, Any]]:
    """Normalize operational diagnostics without mixing them with vulnerabilities."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[dict[str, Any]] = []
    for raw in list(value)[:MAX_DIAGNOSTICS]:
        item = raw if isinstance(raw, Mapping) else {"message": raw}
        diagnostic: dict[str, Any] = {
            "code": _safe_text(item.get("code") or "scanner_diagnostic", 96)
            .lower()
            .replace(" ", "_"),
            "message": _safe_text(item.get("message"), MAX_TEXT),
        }
        for key, limit in (("location", 240), ("severity", 32)):
            if item.get(key) not in (None, ""):
                diagnostic[key] = (
                    _safe_text(item[key], limit).lower()
                    if key == "severity"
                    else _safe_text(item[key], limit)
                )
        result.append(diagnostic)
    return result


def _bounded_archive_files(value: Any) -> list[dict[str, Any]]:
    """Keep the per-entry results of a bounded Static model analysis ZIP scan visible."""

    raw_files = value.get("files") if isinstance(value, Mapping) else None
    if not isinstance(raw_files, Sequence) or isinstance(
        raw_files, (str, bytes, bytearray)
    ):
        return []
    bounded: list[dict[str, Any]] = []
    for index, raw in enumerate(list(raw_files)[:512], start=1):
        if not isinstance(raw, Mapping):
            continue
        summary = raw.get("summary") if isinstance(raw.get("summary"), Mapping) else {}
        engine = raw.get("engine") if isinstance(raw.get("engine"), Mapping) else {}
        tests = _bounded_tests(raw.get("tests"))
        tests_total = max(
            _positive_int(raw.get("tests_total")),
            len(tests),
        )
        item: dict[str, Any] = {
            "scan_order": max(1, _positive_int(raw.get("scan_order")) or index),
            "path": _safe_text(raw.get("path") or raw.get("name"), 240),
            "name": _safe_text(raw.get("name") or raw.get("path"), 160),
            "format": _safe_text(raw.get("format"), 64),
            "decision": _safe_text(raw.get("decision") or "error", 32),
            "scan_outcome": _safe_text(raw.get("scan_outcome") or "error", 32),
            "analysis_incomplete": _safe_bool(raw.get("analysis_incomplete")),
            "summary": {
                "critical": _positive_int(summary.get("critical")),
                "warning": _positive_int(summary.get("warning")),
                "info": _positive_int(summary.get("info")),
                "total": _positive_int(summary.get("total")),
                "checks": _positive_int(summary.get("checks")),
            },
            "tests": tests,
            "tests_total": tests_total,
            "tests_truncated": _safe_bool(raw.get("tests_truncated"))
            or tests_total > len(tests),
            "findings": _bounded_findings(raw.get("findings")),
            "engine": {
                "name": _safe_text(engine.get("name") or "Static model analysis", 96),
                "version": _safe_text(engine.get("version") or "unknown", 64),
                "scanner": _safe_text(engine.get("scanner") or "unknown", 64),
                "duration_ms": _positive_int(engine.get("duration_ms")),
            },
        }
        for key in ("size_bytes",):
            if raw.get(key) is not None:
                item[key] = _positive_int(raw.get(key))
        sha256 = _safe_text(raw.get("sha256"), 64)
        if sha256:
            item["sha256"] = sha256
        bounded.append(item)
    return bounded


def _bounded_archive_info(value: Any) -> dict[str, Any]:
    raw = value.get("archive") if isinstance(value, Mapping) else None
    if not isinstance(raw, Mapping):
        return {}
    info: dict[str, Any] = {}
    for key in ("files_scanned", "files_skipped"):
        if raw.get(key) is not None:
            info[key] = _positive_int(raw.get(key))
    if raw.get("entry_limit_reached") is not None:
        info["entry_limit_reached"] = _safe_bool(raw.get("entry_limit_reached"))
    extensions = raw.get("supported_extensions")
    if isinstance(extensions, Sequence) and not isinstance(
        extensions, (str, bytes, bytearray)
    ):
        info["supported_extensions"] = [
            _safe_text(extension, 64)
            for extension in list(extensions)[:256]
            if _safe_text(extension, 64)
        ]
    version = _safe_text(raw.get("scanner_version"), 64)
    if version:
        info["scanner_version"] = version
    return info


def _compact_archive_info(value: Any) -> dict[str, Any]:
    """Keep archive counters in the default output without repeating capabilities."""

    archive = _bounded_archive_info(value)
    return {
        key: archive[key]
        for key in ("files_scanned", "files_skipped", "entry_limit_reached")
        if key in archive
    }


def _compact_archive_files(files: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep file names and outcomes while leaving individual checks opt-in."""

    compact: list[dict[str, Any]] = []
    for index, raw in enumerate(files, start=1):
        summary = raw.get("summary") if isinstance(raw.get("summary"), Mapping) else {}
        item: dict[str, Any] = {
            "scan_order": _positive_int(raw.get("scan_order")) or index,
            "name": _safe_text(raw.get("name") or raw.get("path"), 160),
            "path": _safe_text(raw.get("path") or raw.get("name"), 240),
            "format": _safe_text(raw.get("format"), 64),
            "decision": _safe_text(raw.get("decision") or "error", 32),
            "scan_outcome": _safe_text(
                raw.get("scan_outcome") or raw.get("decision") or "error", 32
            ),
            "summary": {
                "critical": _positive_int(summary.get("critical")),
                "warning": _positive_int(summary.get("warning")),
                "info": _positive_int(summary.get("info")),
                "total": _positive_int(summary.get("total")),
                "checks": _positive_int(summary.get("checks")),
                "tests_total": max(
                    _positive_int(raw.get("tests_total")),
                    (
                        len(raw.get("tests") or [])
                        if isinstance(raw.get("tests"), Sequence)
                        and not isinstance(raw.get("tests"), (str, bytes, bytearray))
                        else 0
                    ),
                ),
            },
        }
        if raw.get("analysis_incomplete"):
            item["analysis_incomplete"] = _safe_bool(raw.get("analysis_incomplete"))
        findings = _bounded_findings(raw.get("findings"))
        if findings:
            item["findings"] = findings
        compact.append(item)
    return compact


def make_layer_result(
    *,
    layer_id: str,
    engine_name: str,
    engine_version: str,
    decision: str,
    status: str,
    applicable: bool = True,
    target: Mapping[str, Any] | None = None,
    counts: Mapping[str, Any] | None = None,
    checks: Any = 0,
    findings: Any = None,
    duration_ms: Any = 0,
    coverage_complete: bool | None = None,
    reason_codes: Sequence[Any] | None = None,
    diagnostics: Any = None,
    audit_id: str | None = None,
) -> dict[str, Any]:
    """Create one JSON-safe scanner result with bounded details."""

    normalized_layer = str(layer_id or "").lower()
    if not _SAFE_LAYER_ID.fullmatch(normalized_layer):
        raise ValueError("Invalid security layer identifier.")
    normalized_decision = str(decision or "error").lower()
    normalized_status = str(status or "error").lower()
    if normalized_decision not in _VALID_DECISIONS:
        normalized_decision = "error"
    if normalized_status not in _VALID_STATUSES:
        normalized_status = "error"

    raw_counts = counts if isinstance(counts, Mapping) else {}
    severity_counts = {
        "critical": _positive_int(raw_counts.get("critical")),
        "warning": _positive_int(raw_counts.get("warning")),
        "info": _positive_int(raw_counts.get("info")),
    }
    bounded_findings = _bounded_findings(findings, layer_id=normalized_layer)
    if not any(severity_counts.values()) and bounded_findings:
        for finding in bounded_findings:
            severity_counts[_severity(finding.get("severity"))] += 1

    coverage = (
        _safe_bool(coverage_complete)
        if coverage_complete is not None
        else normalized_status in {"complete", "not_applicable"}
    )
    reasons = []
    for reason in list(reason_codes or [])[:16]:
        safe_reason = _safe_text(reason, 96).lower().replace(" ", "_")
        if safe_reason and safe_reason not in reasons:
            reasons.append(safe_reason)

    normalized_audit_id = _safe_text(audit_id, 64)
    result = {
        "schema_version": LAYER_SCHEMA_VERSION,
        "audit_id": normalized_audit_id or str(uuid.uuid4()),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "layer_id": normalized_layer,
        "status": normalized_status,
        "applicable": _safe_bool(applicable, True),
        "decision": normalized_decision,
        "should_continue": normalized_decision == "allow",
        "target": _bounded_target(target or {}),
        "summary": {
            **severity_counts,
            "total": sum(severity_counts.values()),
            "checks": _positive_int(checks),
        },
        "coverage": {
            "complete": coverage,
            "reason_codes": reasons,
        },
        "findings": bounded_findings,
        "diagnostics": _bounded_diagnostics(diagnostics),
        "engine": {
            "name": _safe_text(engine_name, 96),
            "version": _safe_text(engine_version, 64),
            "duration_ms": _positive_int(duration_ms),
        },
    }
    json.dumps(result, ensure_ascii=False)
    return result


def _layer_as_normalized(value: Mapping[str, Any]) -> dict[str, Any]:
    layer_id = str(value.get("layer_id") or "").lower()
    engine = value.get("engine") if isinstance(value.get("engine"), Mapping) else {}
    summary = value.get("summary") if isinstance(value.get("summary"), Mapping) else {}
    coverage = (
        value.get("coverage") if isinstance(value.get("coverage"), Mapping) else {}
    )
    result = make_layer_result(
        layer_id=layer_id,
        engine_name=str(engine.get("name") or layer_id.title()),
        engine_version=str(engine.get("version") or "unknown"),
        decision=str(value.get("decision") or "error"),
        status=str(value.get("status") or "error"),
        applicable=_safe_bool(value.get("applicable", True), True),
        target=value.get("target") if isinstance(value.get("target"), Mapping) else {},
        counts=summary,
        checks=summary.get("checks", 0),
        findings=value.get("findings"),
        duration_ms=engine.get("duration_ms", 0),
        coverage_complete=_safe_bool(coverage.get("complete", False)),
        reason_codes=(
            coverage.get("reason_codes")
            if isinstance(coverage.get("reason_codes"), Sequence)
            and not isinstance(coverage.get("reason_codes"), (str, bytes, bytearray))
            else []
        ),
        diagnostics=value.get("diagnostics"),
        audit_id=str(value.get("audit_id") or "") or None,
    )
    files = _bounded_archive_files(value)
    if files:
        result["files"] = files
    archive = _bounded_archive_info(value)
    if archive:
        result["archive"] = archive
    if files:
        result["total_evaluation"] = _archive_total_evaluation(
            result["decision"],
            result["summary"],
            result["coverage"],
            files,
            archive,
            result["findings"],
        )
    return result


def _static_analysis_as_layer(value: Mapping[str, Any]) -> dict[str, Any]:
    decision = str(value.get("decision") or "error").lower()
    engine = value.get("engine") if isinstance(value.get("engine"), Mapping) else {}
    summary = value.get("summary") if isinstance(value.get("summary"), Mapping) else {}
    artifact = (
        value.get("artifact") if isinstance(value.get("artifact"), Mapping) else {}
    )
    status = str(value.get("scan_outcome") or "").lower()
    if status not in _VALID_STATUSES:
        status = "complete" if decision in {"allow", "review", "block"} else decision
    reasons: list[str] = []
    native_reasons = value.get("coverage_reason_codes")
    if isinstance(native_reasons, Sequence) and not isinstance(
        native_reasons, (str, bytes, bytearray)
    ):
        reasons.extend(str(reason) for reason in list(native_reasons)[:16])
    if value.get("analysis_incomplete") and not reasons:
        reasons.append("analysis_incomplete")
    result = make_layer_result(
        layer_id="static_analysis",
        engine_name=str(engine.get("name") or "Static model analysis"),
        engine_version=str(engine.get("version") or "unknown"),
        decision=decision,
        status=status,
        applicable=True,
        target=artifact,
        counts=summary,
        checks=summary.get("checks", 0),
        findings=value.get("findings"),
        duration_ms=engine.get("duration_ms", 0),
        coverage_complete=not bool(value.get("analysis_incomplete")),
        reason_codes=reasons,
        audit_id=str(value.get("scan_id") or "") or None,
    )
    files = _bounded_archive_files(value)
    if files:
        result["files"] = files
    archive = _bounded_archive_info(value)
    if archive:
        result["archive"] = archive
    if files:
        result["total_evaluation"] = _archive_total_evaluation(
            result["decision"],
            result["summary"],
            result["coverage"],
            files,
            archive,
            result["findings"],
        )
    return result


def collect_layer_results(value: Any) -> list[dict[str, Any]]:
    """Unwrap workflow output wrappers and return normalized layer envelopes."""

    collected: list[dict[str, Any]] = []

    def visit(candidate: Any, depth: int = 0) -> None:
        if depth > 8 or candidate is None:
            return
        if isinstance(candidate, Sequence) and not isinstance(
            candidate, (str, bytes, bytearray)
        ):
            for item in candidate:
                visit(item, depth + 1)
            return
        if not isinstance(candidate, Mapping):
            return

        schema = str(candidate.get("schema_version") or "")
        if schema == LAYER_SCHEMA_VERSION:
            try:
                collected.append(_layer_as_normalized(candidate))
            except ValueError:
                return
            return
        if (
            candidate.get("layer_id")
            and candidate.get("decision")
            and isinstance(candidate.get("summary"), Mapping)
        ):
            try:
                collected.append(_layer_as_normalized(candidate))
            except ValueError:
                return
            return
        if schema == AUDIT_SCHEMA_VERSION and isinstance(candidate.get("layers"), list):
            visit(candidate["layers"], depth + 1)
            return
        engine = candidate.get("engine")
        if (
            "decision" in candidate
            and isinstance(engine, Mapping)
            and str(engine.get("name") or "").lower() == "static model analysis"
            and isinstance(candidate.get("artifact"), Mapping)
        ):
            collected.append(_static_analysis_as_layer(candidate))
            return

        for key in (
            "audit_result",
            "scan_result",
            "audit",
            "output",
            "result",
            "value",
        ):
            if key in candidate:
                visit(candidate[key], depth + 1)
                return

    visit(value)
    return collected


def parse_layer_ids(
    value: Any, default: Sequence[str] = ("static_analysis",)
) -> list[str]:
    parsed = value
    if value is None or value == "":
        parsed = list(default)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "required_layers must be a JSON array or comma-separated list."
                ) from exc
        else:
            parsed = [item.strip() for item in stripped.split(",") if item.strip()]
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes, bytearray)):
        raise ValueError("required_layers must be a list.")
    result: list[str] = []
    for item in parsed:
        layer_id = str(item).strip().lower()
        if not _SAFE_LAYER_ID.fullmatch(layer_id):
            raise ValueError("required_layers contains an invalid layer identifier.")
        if layer_id not in result:
            result.append(layer_id)
    return result


def _compact_target(value: Any) -> dict[str, Any]:
    bounded = _bounded_target(value)
    return {
        key: bounded[key]
        for key in ("name", "format", "kind", "reference", "size_bytes", "sha256")
        if key in bounded
    }


def _compact_findings(
    findings: Any,
    *,
    limit: int | None = None,
    retain_layer_id: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(findings, Sequence) or isinstance(
        findings, (str, bytes, bytearray)
    ):
        return []

    result: list[dict[str, Any]] = []
    for raw in islice(findings, MAX_FINDING_CANDIDATES):
        item = raw if isinstance(raw, Mapping) else {"message": raw}
        normalized = _bounded_findings([item], 1)
        if not normalized:
            continue
        finding = normalized[0]
        layer_id = _safe_text(item.get("layer_id"), 64).lower()

        compact: dict[str, Any] = {
            "severity": finding["severity"],
            "title": finding["title"],
        }
        if retain_layer_id and layer_id:
            compact["layer_id"] = layer_id
        for field in (
            "message",
            "rule_code",
            "rule_description",
            "rule_solution",
            "risk_level",
            "category",
            "location",
            "remediation",
            "fixed_version",
        ):
            if finding.get(field) not in (None, ""):
                compact[field] = finding[field]
        result.append(compact)
        if limit is not None and len(result) >= max(0, limit):
            break
    return result


def _public_status(decision: Any) -> str:
    """Translate the policy decision into one stable, user-facing status."""

    return {
        "allow": "completed",
        "review": "completed",
        "block": "completed",
        "inconclusive": "inconclusive",
        "error": "error",
    }.get(str(decision or "").lower(), "error")


def _public_risk_level(summary: Mapping[str, Any], decision: Any) -> str:
    if _positive_int(summary.get("critical")):
        return "critical"
    if _positive_int(summary.get("warning")) or str(decision) == "review":
        return "warning"
    if _positive_int(summary.get("info")):
        return "info"
    if str(decision) in {"error", "inconclusive"}:
        return "unknown"
    return "none"


def _public_findings(
    findings: Any,
    *,
    limit: int | None = None,
    default_scanner: str = "security",
) -> list[dict[str, Any]]:
    """Expose every retained finding through one product-owned vocabulary."""

    if not isinstance(findings, Sequence) or isinstance(
        findings, (str, bytes, bytearray)
    ):
        return []

    prepared: list[dict[str, Any]] = []
    for raw in islice(findings, MAX_FINDING_CANDIDATES):
        item = dict(raw) if isinstance(raw, Mapping) else {"message": raw}
        if not item.get("layer_id"):
            item["layer_id"] = default_scanner
        prepared.append(item)

    normalized = _compact_findings(
        prepared,
        limit=limit,
        retain_layer_id=True,
    )
    result: list[dict[str, Any]] = []
    for index, finding in enumerate(normalized, start=1):
        description = _safe_text(
            finding.get("rule_description") or finding.get("message"), MAX_TEXT
        )
        evidence = _safe_text(finding.get("message"), MAX_TEXT)
        recommendation = _safe_text(
            finding.get("rule_solution") or finding.get("remediation"), MAX_TEXT
        )
        fingerprint_source = "\x1f".join(
            str(finding.get(key) or "")
            for key in ("layer_id", "rule_code", "location", "title", "message")
        )
        public_finding: dict[str, Any] = {
            "id": f"finding-{index:03d}",
            "fingerprint": hashlib.sha256(
                fingerprint_source.encode("utf-8", errors="replace")
            ).hexdigest()[:24],
            "scanner": _safe_text(
                finding.get("layer_id") or default_scanner, 64
            ).lower(),
            "severity": _severity(finding.get("severity")),
            "code": _safe_text(
                finding.get("rule_code") or finding.get("category") or "unclassified",
                96,
            ),
            "title": _safe_text(finding.get("title") or "Security finding", 160),
        }
        if description:
            public_finding["description"] = description
        if evidence:
            public_finding["evidence"] = evidence
        if recommendation:
            public_finding["recommendation"] = recommendation
        for field in ("location", "fixed_version", "risk_level"):
            if finding.get(field) not in (None, ""):
                public_finding[field] = _safe_text(finding[field], 192)
        result.append(public_finding)
    return result


def _public_scanner_result(layer: Mapping[str, Any]) -> dict[str, Any]:
    layer_id = _safe_text(layer.get("layer_id") or "security", 64).lower()
    summary = layer.get("summary") if isinstance(layer.get("summary"), Mapping) else {}
    coverage = (
        layer.get("coverage") if isinstance(layer.get("coverage"), Mapping) else {}
    )
    counts = {
        "critical": _positive_int(summary.get("critical")),
        "warning": _positive_int(summary.get("warning")),
        "info": _positive_int(summary.get("info")),
    }
    result: dict[str, Any] = {
        "name": _LAYER_LABELS.get(layer_id, layer_id.replace("_", " ").title()),
        "status": _safe_text(layer.get("status") or "inconclusive", 32),
        "decision": _safe_text(layer.get("decision") or "inconclusive", 32),
        "applicable": _safe_bool(layer.get("applicable", True), True),
        "coverage_complete": _safe_bool(coverage.get("complete", False)),
        "finding_counts": {**counts, "total": sum(counts.values())},
    }
    result["message"] = _decision_message(
        result["decision"],
        summary,
        layer_id=layer_id,
        applicable=result["applicable"],
    )
    reasons = [
        _safe_text(reason, 96)
        for reason in list(coverage.get("reason_codes") or [])[:16]
        if _safe_text(reason, 96)
    ]
    if reasons:
        result["coverage_reasons"] = reasons
    engine = layer.get("engine") if isinstance(layer.get("engine"), Mapping) else {}
    result["engine"] = {
        "name": _safe_text(engine.get("name") or result["name"], 96),
        "version": _safe_text(engine.get("version") or "unknown", 64),
        "duration_ms": _positive_int(engine.get("duration_ms")),
    }
    diagnostics = _bounded_diagnostics(layer.get("diagnostics"))
    if diagnostics:
        result["diagnostics"] = diagnostics
    archive = _compact_archive_info(layer)
    for field in ("files_scanned", "files_skipped", "entry_limit_reached"):
        if field in archive:
            result[field] = archive[field]
    return result


def _public_summary(
    summary: Mapping[str, Any],
    *,
    decision: Any,
    scanners_passed: int,
    scanners_total: int,
    findings_returned: int,
    scanner_states: Mapping[str, Any] | None = None,
    archive: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    counts = {
        "critical": _positive_int(summary.get("critical")),
        "warning": _positive_int(summary.get("warning")),
        "info": _positive_int(summary.get("info")),
    }
    result: dict[str, Any] = {
        "risk_level": _public_risk_level(counts, decision),
        "findings_total": sum(counts.values()),
        "findings_returned": findings_returned,
        **counts,
        "scanners_passed": scanners_passed,
        "scanners_total": scanners_total,
    }
    states = scanner_states if isinstance(scanner_states, Mapping) else {}
    for key in ("scanners_completed", "scanners_inconclusive", "scanners_failed"):
        if key in states:
            result[key] = _positive_int(states.get(key))
    result["findings_truncated"] = result["findings_total"] > findings_returned
    archive = archive if isinstance(archive, Mapping) else {}
    for field in ("files_scanned", "files_skipped"):
        if field in archive:
            result[field] = _positive_int(archive.get(field))
    return result


def _decision_message(
    decision: Any,
    summary: Mapping[str, Any],
    *,
    layer_id: str | None = None,
    applicable: bool = True,
) -> str:
    normalized = str(decision or "inconclusive").lower()
    critical = _positive_int(summary.get("critical"))
    warning = _positive_int(summary.get("warning"))
    label = _LAYER_LABELS.get(str(layer_id or ""), str(layer_id or "Security scan"))

    if not applicable:
        return f"Not applicable: {label} does not inspect this target format."
    if normalized == "allow":
        return (
            f"Passed: {label} completed without retained findings."
            if layer_id
            else "Allowed: all required security layers passed."
        )
    if normalized == "block":
        return (
            f"Blocked: {critical} critical finding(s) detected."
            if critical
            else "Blocked by security policy."
        )
    if normalized == "review":
        return (
            f"Review required: {warning} warning(s) require review."
            if warning
            else "Review required: manual review is required."
        )
    if normalized == "error":
        return "Scan error: the security decision is fail-closed."
    return "Inconclusive: one or more required security checks did not complete."


def _archive_total_evaluation(
    decision: Any,
    summary: Mapping[str, Any],
    coverage: Mapping[str, Any],
    files: Sequence[Mapping[str, Any]],
    archive: Mapping[str, Any],
    findings: Any,
) -> dict[str, Any]:
    normalized_decision = str(decision or "inconclusive").lower()
    counts = {
        "critical": _positive_int(summary.get("critical")),
        "warning": _positive_int(summary.get("warning")),
        "info": _positive_int(summary.get("info")),
    }
    checks = 0
    tests_total = 0
    analysis_incomplete = False
    tests_truncated = False
    for file_result in files:
        file_summary = (
            file_result.get("summary")
            if isinstance(file_result.get("summary"), Mapping)
            else {}
        )
        file_checks = _positive_int(file_summary.get("checks"))
        file_tests = max(
            file_checks,
            _positive_int(file_result.get("tests_total")),
        )
        checks += file_checks
        tests_total += file_tests
        analysis_incomplete = analysis_incomplete or _safe_bool(
            file_result.get("analysis_incomplete")
        )
        tests_truncated = tests_truncated or _safe_bool(
            file_result.get("tests_truncated")
        )

    total_summary = {
        **counts,
        "total": sum(counts.values()),
        "checks": checks,
        "tests_total": tests_total,
    }
    return {
        "decision": normalized_decision,
        "should_continue": normalized_decision == "allow",
        "scan_outcome": (
            "complete"
            if normalized_decision in {"allow", "review", "block"}
            else normalized_decision
        ),
        "analysis_incomplete": analysis_incomplete,
        "tests_truncated": tests_truncated,
        "message": _decision_message(normalized_decision, total_summary),
        "summary": total_summary,
        "coverage": {
            "complete": _safe_bool(coverage.get("complete", False)),
        },
        "files_scanned": (
            _positive_int(archive["files_scanned"])
            if "files_scanned" in archive
            else len(files)
        ),
        "files_skipped": _positive_int(archive.get("files_skipped")),
        "findings": _bounded_findings(findings),
    }


def compact_layer_result(
    value: Mapping[str, Any],
    *,
    include_findings: bool = True,
    include_target: bool = True,
    embedded: bool = False,
    finding_limit: int | None = None,
) -> dict[str, Any]:
    """Return the stable public result contract for one scanner."""

    schema = str(value.get("schema_version") or "")
    if schema == LAYER_SCHEMA_VERSION or value.get("layer_id"):
        normalized = _layer_as_normalized(value)
    else:
        layers = collect_layer_results(value)
        if not layers:
            raise ValueError(
                "Value does not contain a supported security-layer result."
            )
        normalized = layers[0]

    layer_id = str(normalized.get("layer_id") or "security")
    summary = (
        normalized.get("summary")
        if isinstance(normalized.get("summary"), Mapping)
        else {}
    )
    coverage = (
        normalized.get("coverage")
        if isinstance(normalized.get("coverage"), Mapping)
        else {}
    )
    applicable = _safe_bool(normalized.get("applicable", True), True)
    decision = str(normalized.get("decision") or "inconclusive")
    reasons = [
        _safe_text(reason, 96)
        for reason in list(coverage.get("reason_codes") or [])[:8]
        if _safe_text(reason, 96)
    ]
    findings = (
        _public_findings(
            normalized.get("findings"),
            limit=finding_limit,
            default_scanner=layer_id,
        )
        if include_findings
        else []
    )
    scanner_result = _public_scanner_result(normalized)
    scanner_passed = int(
        applicable
        and decision == "allow"
        and str(normalized.get("status")) == "complete"
        and _safe_bool(coverage.get("complete", False))
    )
    scanner_status = str(normalized.get("status") or "inconclusive")
    archive = _compact_archive_info(normalized)
    compact: dict[str, Any] = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": _public_status(decision),
        "decision": decision,
        "should_continue": decision == "allow",
        "message": _decision_message(
            decision,
            summary,
            layer_id=layer_id,
            applicable=applicable,
        ),
        "artifact": _compact_target(normalized.get("target")) if include_target else {},
        "policy": {
            "profile": "single_scanner",
            "coverage_complete": _safe_bool(coverage.get("complete", False)),
            "required_scanners": [layer_id],
        },
        "summary": _public_summary(
            summary,
            decision=decision,
            scanners_passed=scanner_passed,
            scanners_total=int(applicable),
            findings_returned=len(findings),
            scanner_states={
                "scanners_completed": int(scanner_status == "complete"),
                "scanners_inconclusive": int(
                    scanner_status in {"inconclusive", "unsupported", "timeout"}
                ),
                "scanners_failed": int(scanner_status == "error"),
            },
            archive=archive,
        ),
        "scanner_results": {layer_id: scanner_result},
        "findings": findings,
    }
    if reasons:
        compact["policy"]["coverage_reasons"] = reasons
    if embedded:
        compact.pop("schema_version", None)
        compact.pop("should_continue", None)
    json.dumps(compact, ensure_ascii=False)
    return compact


def compact_audit_result(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return one concise public contract; diagnostics remain opt-in."""

    if str(value.get("schema_version") or "") != AUDIT_SCHEMA_VERSION:
        raise ValueError("Value is not a layered security audit.")
    summary = value.get("summary") if isinstance(value.get("summary"), Mapping) else {}
    policy = value.get("policy") if isinstance(value.get("policy"), Mapping) else {}
    coverage = (
        value.get("coverage") if isinstance(value.get("coverage"), Mapping) else {}
    )
    layers = value.get("layers") if isinstance(value.get("layers"), list) else []

    normalized_decision = str(value.get("decision") or "inconclusive")
    coverage_complete = _safe_bool(
        coverage.get("complete", summary.get("coverage_complete", False))
    )
    findings = _public_findings(
        value.get("findings"),
    )
    scanner_results: dict[str, dict[str, Any]] = {}
    for layer in layers:
        if not isinstance(layer, Mapping):
            continue
        layer_id = _safe_text(layer.get("layer_id") or "security", 64).lower()
        scanner_results[layer_id] = _public_scanner_result(layer)

    scanner_states = {
        "scanners_completed": sum(
            1
            for result in scanner_results.values()
            if result.get("status") == "complete"
        ),
        "scanners_inconclusive": sum(
            1
            for result in scanner_results.values()
            if result.get("status") in {"inconclusive", "unsupported", "timeout"}
        ),
        "scanners_failed": sum(
            1 for result in scanner_results.values() if result.get("status") == "error"
        ),
    }

    public_policy: dict[str, Any] = {
        "profile": _safe_text(policy.get("profile") or "balanced", 32),
        "coverage_complete": coverage_complete,
        "required_scanners": parse_layer_ids(policy.get("required_layers"), default=()),
    }
    issue_names = {
        "missing_required_layers": "missing_scanners",
        "incomplete_required_layers": "incomplete_scanners",
        "duplicate_layer_ids": "duplicate_scanners",
    }
    coverage_issues: dict[str, list[str]] = {}
    for source_name, public_name in issue_names.items():
        items = coverage.get(source_name)
        if isinstance(items, Sequence) and not isinstance(
            items, (str, bytes, bytearray)
        ):
            bounded_items = [
                _safe_text(item, 64)
                for item in list(items)[:16]
                if _safe_text(item, 64)
            ]
            if bounded_items:
                coverage_issues[public_name] = bounded_items
    if coverage_issues:
        public_policy["coverage_issues"] = coverage_issues

    compact: dict[str, Any] = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": _public_status(normalized_decision),
        "decision": normalized_decision,
        "should_continue": normalized_decision == "allow",
        "message": _decision_message(normalized_decision, summary),
        "artifact": _compact_target(value.get("target")),
        "policy": public_policy,
        "summary": _public_summary(
            summary,
            decision=normalized_decision,
            scanners_passed=_positive_int(summary.get("layers_passed")),
            scanners_total=_positive_int(summary.get("layers_total")),
            findings_returned=len(findings),
            scanner_states=scanner_states,
            archive=_compact_archive_info(value),
        ),
        "scanner_results": scanner_results,
        "findings": findings,
        "limitations": [
            "Static analysis reduces risk but cannot guarantee that a model artifact is safe at runtime."
        ],
    }
    json.dumps(compact, ensure_ascii=False)
    return compact


def compact_security_result(value: Mapping[str, Any]) -> dict[str, Any]:
    """Compact either an aggregate audit, a shared layer, or native Static model analysis output."""

    if str(value.get("schema_version") or "") == AUDIT_SCHEMA_VERSION:
        return compact_audit_result(value)
    return compact_layer_result(value)


def present_security_result(
    value: Mapping[str, Any], *, include_details: Any = False
) -> dict[str, Any]:
    """Select the stable public output or the bounded diagnostic contract."""

    if _safe_bool(include_details):
        detailed = deepcopy(dict(value))
        json.dumps(detailed, ensure_ascii=False)
        return detailed
    return compact_security_result(value)


class SecurityPolicyService:
    """Aggregate scanner envelopes without majority voting."""

    def evaluate(
        self,
        values: Any,
        *,
        profile: Any = "balanced",
        required_layers: Any = None,
    ) -> dict[str, Any]:
        layers = collect_layer_results(values)
        profile_name = str(profile or "balanced").lower()
        if profile_name not in {"balanced", "strict"}:
            raise ValueError("Unsupported security policy profile.")

        # A duplicate layer is a contract violation. Never let a later clean
        # result overwrite an earlier block from the same scanner identity.
        by_id: dict[str, dict[str, Any]] = {}
        duplicate_layer_ids: set[str] = set()
        for layer in layers:
            layer_id = str(layer.get("layer_id") or "")
            if not _SAFE_LAYER_ID.fullmatch(layer_id):
                continue
            if layer_id not in by_id:
                by_id[layer_id] = layer
                continue

            duplicate_layer_ids.add(layer_id)
            existing = by_id[layer_id]
            existing_summary = (
                existing.get("summary")
                if isinstance(existing.get("summary"), Mapping)
                else {}
            )
            incoming_summary = (
                layer.get("summary")
                if isinstance(layer.get("summary"), Mapping)
                else {}
            )
            existing_blocks = (
                str(existing.get("decision")) == "block"
                or _positive_int(existing_summary.get("critical")) > 0
            )
            incoming_blocks = (
                str(layer.get("decision")) == "block"
                or _positive_int(incoming_summary.get("critical")) > 0
            )
            if existing_blocks:
                continue
            if incoming_blocks:
                by_id[layer_id] = layer
                continue
            target = existing.get("target") or layer.get("target")
            by_id[layer_id] = make_layer_result(
                layer_id=layer_id,
                engine_name="Security Policy Gate",
                engine_version=POLICY_VERSION,
                decision="error",
                status="error",
                target=target if isinstance(target, Mapping) else {},
                findings=[
                    {
                        "severity": "warning",
                        "title": "Duplicate security layer result",
                        "message": "Multiple results used the same security layer identifier.",
                        "rule_code": "duplicate-layer-result",
                    }
                ],
                coverage_complete=False,
                reason_codes=["duplicate_layer_result"],
            )
        normalized_layers = list(by_id.values())

        required = set(parse_layer_ids(required_layers))
        if profile_name == "strict":
            required.update(
                str(layer.get("layer_id"))
                for layer in normalized_layers
                if bool(layer.get("applicable", True))
            )

        present = {str(layer.get("layer_id")) for layer in normalized_layers}
        missing_required = sorted(required - present)
        required_incomplete = sorted(
            str(layer.get("layer_id"))
            for layer in normalized_layers
            if str(layer.get("layer_id")) in required
            and bool(layer.get("applicable", True))
            and (
                str(layer.get("decision")) in {"inconclusive", "error"}
                or str(layer.get("status"))
                in {"unsupported", "timeout", "inconclusive", "error"}
                or not bool(
                    (layer.get("coverage") or {}).get("complete")
                    if isinstance(layer.get("coverage"), Mapping)
                    else False
                )
            )
        )

        total_counts = {"critical": 0, "warning": 0, "info": 0}
        all_findings: list[dict[str, Any]] = []
        for layer in normalized_layers:
            summary = (
                layer.get("summary")
                if isinstance(layer.get("summary"), Mapping)
                else {}
            )
            for severity in total_counts:
                total_counts[severity] += _positive_int(summary.get(severity))
            for finding in _bounded_findings(layer.get("findings")):
                all_findings.append({"layer_id": layer.get("layer_id"), **finding})
        all_findings.sort(
            key=lambda item: _SEVERITY_ORDER.get(str(item.get("severity")), 3)
        )

        has_block = any(
            str(layer.get("decision")) == "block" for layer in normalized_layers
        )
        has_review = any(
            str(layer.get("decision")) == "review" for layer in normalized_layers
        )
        advisory_failure = any(
            str(layer.get("layer_id")) not in required
            and bool(layer.get("applicable", True))
            and str(layer.get("decision")) in {"inconclusive", "error"}
            for layer in normalized_layers
        )

        if has_block or total_counts["critical"] > 0:
            decision = "block"
        elif not normalized_layers or missing_required or required_incomplete:
            decision = "inconclusive"
        elif has_review or total_counts["warning"] > 0 or advisory_failure:
            decision = "review"
        else:
            decision = "allow"

        applicable_layers = [
            layer for layer in normalized_layers if bool(layer.get("applicable", True))
        ]
        passed_layers = [
            layer
            for layer in applicable_layers
            if str(layer.get("status")) == "complete"
            and str(layer.get("decision")) == "allow"
            and bool((layer.get("coverage") or {}).get("complete", False))
        ]
        target = next(
            (
                layer.get("target")
                for layer in normalized_layers
                if isinstance(layer.get("target"), Mapping)
                and bool(layer.get("target"))
            ),
            {},
        )
        compact_layers = deepcopy(normalized_layers)
        for compact_layer in compact_layers:
            compact_layer["findings"] = _bounded_findings(compact_layer.get("findings"))

        audit = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "audit_id": str(uuid.uuid4()),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "decision": decision,
            "should_continue": decision == "allow",
            "policy": {
                "profile": profile_name,
                "version": POLICY_VERSION,
                "required_layers": sorted(required),
            },
            "target": _bounded_target(target),
            "summary": {
                **total_counts,
                "total": sum(total_counts.values()),
                "layers_passed": len(passed_layers),
                "layers_total": len(applicable_layers),
                "coverage_complete": not missing_required
                and not required_incomplete
                and not duplicate_layer_ids,
            },
            "coverage": {
                "missing_required_layers": missing_required,
                "incomplete_required_layers": required_incomplete,
                "duplicate_layer_ids": sorted(duplicate_layer_ids),
            },
            "layers": compact_layers,
            "findings": deepcopy(all_findings),
        }
        archive_files = [
            file_result
            for layer in compact_layers
            if isinstance(layer, Mapping)
            for file_result in _bounded_archive_files(layer)
        ]
        archive_info = next(
            (
                layer.get("archive")
                for layer in compact_layers
                if isinstance(layer, Mapping)
                and isinstance(layer.get("archive"), Mapping)
            ),
            {},
        )
        if archive_files:
            audit["files"] = archive_files
            if archive_info:
                audit["archive"] = dict(archive_info)
            audit["total_evaluation"] = _archive_total_evaluation(
                decision,
                audit["summary"],
                {"complete": audit["summary"]["coverage_complete"]},
                archive_files,
                archive_info,
                audit["findings"],
            )
        json.dumps(audit, ensure_ascii=False)
        return audit


security_policy_service = SecurityPolicyService()


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "LAYER_SCHEMA_VERSION",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "SecurityPolicyService",
    "collect_layer_results",
    "compact_audit_result",
    "compact_layer_result",
    "compact_security_result",
    "make_layer_result",
    "parse_layer_ids",
    "present_security_result",
    "security_policy_service",
]
