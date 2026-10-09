"""Central deployment limits for model scanning and managed uploads."""

from __future__ import annotations

import os
from typing import Any


MIB = 1024 * 1024
GIB = 1024 * MIB
TIB = 1024 * GIB

DEFAULT_ARTIFACT_MAX_BYTES = 256 * GIB
HARD_ARTIFACT_MAX_BYTES = 1 * TIB

DEFAULT_ARCHIVE_EXPANDED_MAX_BYTES = 256 * GIB
HARD_ARCHIVE_EXPANDED_MAX_BYTES = 1 * TIB

# Browser uploads still traverse the application API. Larger interactive
# transfers should use a service-visible path or object storage until resumable
# direct-to-object-storage upload is available.
DEFAULT_MANAGED_UPLOAD_MAX_BYTES = 8 * GIB
HARD_MANAGED_UPLOAD_MAX_BYTES = 8 * GIB

DEFAULT_PICKLE_MAX_BYTES = 256 * MIB
HARD_PICKLE_MAX_BYTES = 2 * GIB

DEFAULT_WORKER_MEMORY_BYTES = 4 * GIB
MIN_WORKER_MEMORY_BYTES = 512 * MIB
HARD_WORKER_MEMORY_BYTES = 16 * GIB

# Managed browser uploads are temporary execution inputs. Reusable model assets
# belong on a service-visible shared path or in customer-owned object storage.
DEFAULT_MANAGED_RETENTION_SECONDS = 24 * 60 * 60
DEFAULT_MANAGED_POST_SCAN_RETENTION_SECONDS = 60 * 60
DEFAULT_INCOMPLETE_RETENTION_SECONDS = 60 * 60
DEFAULT_STAGING_RETENTION_SECONDS = 2 * 60 * 60
DEFAULT_ARTIFACT_GC_INTERVAL_SECONDS = 15 * 60
DEFAULT_UPLOAD_RESERVATION_SECONDS = 2 * 60 * 60

DEFAULT_STORAGE_SOFT_PERCENT = 75
DEFAULT_STORAGE_AGGRESSIVE_PERCENT = 85
DEFAULT_STORAGE_HARD_PERCENT = 90
DEFAULT_STORAGE_MIN_FREE_BYTES = 20 * GIB
DEFAULT_STORAGE_MIN_FREE_PERCENT = 15


def _configured_bytes(name: str, default: int, hard_maximum: int) -> int:
    value: Any = os.getenv(name)
    try:
        parsed = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, hard_maximum)


def _configured_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value: Any = os.getenv(name)
    try:
        parsed = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def configured_artifact_max_bytes() -> int:
    return _configured_bytes(
        "KAI_MODEL_MAX_ARTIFACT_BYTES",
        DEFAULT_ARTIFACT_MAX_BYTES,
        HARD_ARTIFACT_MAX_BYTES,
    )


def configured_archive_expanded_max_bytes() -> int:
    return _configured_bytes(
        "KAI_MODEL_ARCHIVE_MAX_EXPANDED_BYTES",
        DEFAULT_ARCHIVE_EXPANDED_MAX_BYTES,
        HARD_ARCHIVE_EXPANDED_MAX_BYTES,
    )


def configured_managed_upload_max_bytes() -> int:
    return _configured_bytes(
        "KAI_MODEL_UPLOAD_MAX_BYTES",
        DEFAULT_MANAGED_UPLOAD_MAX_BYTES,
        HARD_MANAGED_UPLOAD_MAX_BYTES,
    )


def configured_worker_memory_bytes() -> int:
    configured = _configured_bytes(
        "KAI_MODEL_SCAN_MEMORY_LIMIT_BYTES",
        DEFAULT_WORKER_MEMORY_BYTES,
        HARD_WORKER_MEMORY_BYTES,
    )
    return max(MIN_WORKER_MEMORY_BYTES, configured)


def configured_managed_retention_seconds() -> int:
    return _configured_int(
        "KAI_MODEL_MANAGED_RETENTION_SECONDS",
        DEFAULT_MANAGED_RETENTION_SECONDS,
        60 * 60,
        30 * 24 * 60 * 60,
    )


def configured_managed_post_scan_retention_seconds() -> int:
    return _configured_int(
        "KAI_MODEL_MANAGED_POST_SCAN_RETENTION_SECONDS",
        DEFAULT_MANAGED_POST_SCAN_RETENTION_SECONDS,
        5 * 60,
        7 * 24 * 60 * 60,
    )


def configured_incomplete_retention_seconds() -> int:
    return _configured_int(
        "KAI_MODEL_INCOMPLETE_RETENTION_SECONDS",
        DEFAULT_INCOMPLETE_RETENTION_SECONDS,
        5 * 60,
        24 * 60 * 60,
    )


def configured_staging_retention_seconds() -> int:
    return _configured_int(
        "KAI_MODEL_STAGING_RETENTION_SECONDS",
        DEFAULT_STAGING_RETENTION_SECONDS,
        60 * 60,
        7 * 24 * 60 * 60,
    )


def configured_artifact_gc_interval_seconds() -> int:
    return _configured_int(
        "KAI_MODEL_ARTIFACT_GC_INTERVAL_SECONDS",
        DEFAULT_ARTIFACT_GC_INTERVAL_SECONDS,
        60,
        24 * 60 * 60,
    )


def configured_upload_reservation_seconds() -> int:
    return _configured_int(
        "KAI_MODEL_UPLOAD_RESERVATION_SECONDS",
        DEFAULT_UPLOAD_RESERVATION_SECONDS,
        10 * 60,
        24 * 60 * 60,
    )


def configured_storage_soft_percent() -> int:
    return _configured_int(
        "KAI_MODEL_STORAGE_SOFT_PERCENT", DEFAULT_STORAGE_SOFT_PERCENT, 1, 97
    )


def configured_storage_aggressive_percent() -> int:
    soft = configured_storage_soft_percent()
    return _configured_int(
        "KAI_MODEL_STORAGE_AGGRESSIVE_PERCENT",
        DEFAULT_STORAGE_AGGRESSIVE_PERCENT,
        soft + 1,
        98,
    )


def configured_storage_hard_percent() -> int:
    aggressive = configured_storage_aggressive_percent()
    return _configured_int(
        "KAI_MODEL_STORAGE_HARD_PERCENT",
        DEFAULT_STORAGE_HARD_PERCENT,
        aggressive + 1,
        99,
    )


def configured_storage_min_free_bytes() -> int:
    return _configured_bytes(
        "KAI_MODEL_STORAGE_MIN_FREE_BYTES",
        DEFAULT_STORAGE_MIN_FREE_BYTES,
        1 * TIB,
    )


def configured_storage_min_free_percent() -> int:
    return _configured_int(
        "KAI_MODEL_STORAGE_MIN_FREE_PERCENT",
        DEFAULT_STORAGE_MIN_FREE_PERCENT,
        1,
        50,
    )


def public_managed_artifact_policy() -> dict[str, int | str]:
    return {
        "mode": "temporary",
        "unscanned_retention_seconds": configured_managed_retention_seconds(),
        "post_scan_retention_seconds": configured_managed_post_scan_retention_seconds(),
        "incomplete_retention_seconds": configured_incomplete_retention_seconds(),
        "cleanup_interval_seconds": configured_artifact_gc_interval_seconds(),
        "storage_soft_percent": configured_storage_soft_percent(),
        "storage_aggressive_percent": configured_storage_aggressive_percent(),
        "storage_hard_percent": configured_storage_hard_percent(),
    }


def public_scan_limits() -> dict[str, int]:
    """Return non-secret limits used to keep clients aligned with deployment policy."""

    return {
        "artifact_max_bytes": configured_artifact_max_bytes(),
        "artifact_hard_max_bytes": HARD_ARTIFACT_MAX_BYTES,
        "archive_expanded_max_bytes": configured_archive_expanded_max_bytes(),
        "archive_expanded_hard_max_bytes": HARD_ARCHIVE_EXPANDED_MAX_BYTES,
        "managed_upload_max_bytes": configured_managed_upload_max_bytes(),
        "managed_upload_hard_max_bytes": HARD_MANAGED_UPLOAD_MAX_BYTES,
        "pickle_default_max_bytes": DEFAULT_PICKLE_MAX_BYTES,
        "pickle_hard_max_bytes": HARD_PICKLE_MAX_BYTES,
        "worker_memory_bytes": configured_worker_memory_bytes(),
    }


__all__ = [
    "DEFAULT_ARTIFACT_MAX_BYTES",
    "DEFAULT_ARCHIVE_EXPANDED_MAX_BYTES",
    "DEFAULT_MANAGED_UPLOAD_MAX_BYTES",
    "DEFAULT_PICKLE_MAX_BYTES",
    "DEFAULT_WORKER_MEMORY_BYTES",
    "DEFAULT_MANAGED_RETENTION_SECONDS",
    "DEFAULT_MANAGED_POST_SCAN_RETENTION_SECONDS",
    "DEFAULT_INCOMPLETE_RETENTION_SECONDS",
    "DEFAULT_STAGING_RETENTION_SECONDS",
    "DEFAULT_ARTIFACT_GC_INTERVAL_SECONDS",
    "DEFAULT_STORAGE_MIN_FREE_BYTES",
    "GIB",
    "HARD_ARTIFACT_MAX_BYTES",
    "HARD_ARCHIVE_EXPANDED_MAX_BYTES",
    "HARD_MANAGED_UPLOAD_MAX_BYTES",
    "HARD_PICKLE_MAX_BYTES",
    "HARD_WORKER_MEMORY_BYTES",
    "MIB",
    "MIN_WORKER_MEMORY_BYTES",
    "TIB",
    "configured_archive_expanded_max_bytes",
    "configured_artifact_max_bytes",
    "configured_managed_upload_max_bytes",
    "configured_managed_retention_seconds",
    "configured_managed_post_scan_retention_seconds",
    "configured_incomplete_retention_seconds",
    "configured_staging_retention_seconds",
    "configured_artifact_gc_interval_seconds",
    "configured_upload_reservation_seconds",
    "configured_storage_soft_percent",
    "configured_storage_aggressive_percent",
    "configured_storage_hard_percent",
    "configured_storage_min_free_bytes",
    "configured_storage_min_free_percent",
    "configured_worker_memory_bytes",
    "public_managed_artifact_policy",
    "public_scan_limits",
]
