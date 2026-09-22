"""Lifecycle-managed storage for browser-uploaded model artifacts.

This store owns only uploads made through the application. It never records or
deletes service-visible local/shared paths or customer-owned MinIO objects.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import stat
import threading
import time
import uuid
import zipfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from filelock import FileLock, Timeout as FileLockTimeout
from sqlalchemy import func, text

from app.services.model_artifact_settings import (
    configured_model_artifact_directory,
    configured_model_staging_directory,
)
from app.services.model_scan_limits import (
    DEFAULT_MANAGED_UPLOAD_MAX_BYTES,
    HARD_MANAGED_UPLOAD_MAX_BYTES,
    configured_incomplete_retention_seconds,
    configured_managed_post_scan_retention_seconds,
    configured_managed_retention_seconds,
    configured_managed_upload_max_bytes,
    configured_staging_retention_seconds,
    configured_storage_aggressive_percent,
    configured_storage_hard_percent,
    configured_storage_min_free_bytes,
    configured_storage_min_free_percent,
    configured_storage_soft_percent,
    configured_upload_reservation_seconds,
)


logger = logging.getLogger(__name__)
# Capacity and maintenance locks are operational detail; DEBUG-level polling
# from the dependency would otherwise flood customer logs every cleanup cycle.
logging.getLogger("filelock").setLevel(logging.WARNING)

COPY_CHUNK_BYTES = 1024 * 1024
LOCAL_UPLOAD_MAX_BYTES = DEFAULT_MANAGED_UPLOAD_MAX_BYTES
DEFAULT_UPLOAD_MAX_BYTES = DEFAULT_MANAGED_UPLOAD_MAX_BYTES
MAX_UPLOAD_MAX_BYTES = HARD_MANAGED_UPLOAD_MAX_BYTES
DISK_CHECK_INTERVAL_BYTES = 16 * 1024 * 1024
MAX_DIRECTORY_FILES = 512
MAX_DIRECTORY_PATH_LENGTH = 512
_OWNER_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_MAINTENANCE_ADVISORY_LOCK_ID = 4_934_176_821


class ManagedArtifactError(ValueError):
    """Raised when a managed artifact operation cannot be completed safely."""


class ManagedArtifactTooLargeError(ManagedArtifactError):
    """Raised when an upload exceeds the configured hard size limit."""


class ManagedArtifactInsufficientDiskError(ManagedArtifactError):
    """Raised when the managed artifact volume cannot safely hold an upload."""


class ManagedArtifactMetadataError(ManagedArtifactError):
    """Raised when durable lifecycle metadata is unavailable."""


class ManagedArtifactInUseError(ManagedArtifactError):
    """Raised when deletion is requested while a scan lease is active."""


@dataclass(frozen=True)
class ManagedArtifactRecord:
    artifact_id: str
    name: str
    size_bytes: int
    format_hint: str | None
    sha256: str | None
    payload_path: Path
    expires_at: datetime

    def open_stream(self):
        return self.payload_path.open("rb")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _positive_limit(value: Any, default: int = DEFAULT_UPLOAD_MAX_BYTES) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, MAX_UPLOAD_MAX_BYTES)


def configured_upload_max_bytes() -> int:
    return configured_managed_upload_max_bytes()


def _safe_display_name(value: str | None) -> str:
    raw = (value or "artifact.bin").replace("\\", "/").split("/")[-1]
    cleaned = "".join(
        character
        if character.isascii() and (character.isalnum() or character in "._-")
        else "_"
        for character in raw
    ).strip("._")
    return (cleaned or "artifact.bin")[:255]


def _format_hint(name: str) -> str | None:
    lowered = name.lower()
    if lowered.endswith(".tar.gz"):
        return "archive"
    suffix = Path(lowered).suffix
    return {
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
        ".tflite": "tflite",
        ".onnx": "onnx",
        ".safetensors": "safetensors",
        ".zip": "archive",
        ".tar": "archive",
        ".tgz": "archive",
        ".gz": "archive",
        ".7z": "archive",
    }.get(suffix)


def _safe_archive_path(value: Any) -> str:
    """Normalize one browser directory path without allowing ZIP traversal."""

    raw = str(value or "").replace("\\", "/").strip()
    if not raw or len(raw) > MAX_DIRECTORY_PATH_LENGTH or raw.startswith("/"):
        raise ManagedArtifactError("A selected folder contains an invalid file path.")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} or "\x00" in part for part in parts):
        raise ManagedArtifactError("A selected folder contains an unsafe file path.")
    return "/".join(_safe_display_name(part) for part in parts)


def _safe_context_id(value: Any, maximum: int) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) > maximum or any(ord(character) < 32 for character in normalized):
        raise ManagedArtifactError("Managed artifact workflow context is invalid.")
    return normalized


def _is_link_or_reparse(path_stat: os.stat_result) -> bool:
    """Identify links and Windows junctions without following their targets."""

    if stat.S_ISLNK(path_stat.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(path_stat, "st_file_attributes", 0) & reparse_flag)


def _remove_owned_entry(path: Path, *, root: Path) -> None:
    """Remove one entry under an application-owned root without following links."""

    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ManagedArtifactError("Cleanup target is outside managed storage.") from exc
    path_stat = path.lstat()
    if _is_link_or_reparse(path_stat):
        if stat.S_ISDIR(path_stat.st_mode):
            path.rmdir()
        else:
            path.unlink()
        return
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ManagedArtifactError("Cleanup target is outside managed storage.") from exc
    if stat.S_ISDIR(path_stat.st_mode):
        shutil.rmtree(path)
    else:
        path.unlink()


class ManagedModelArtifactStore:
    """Persist, lease, expire, and garbage-collect application-owned uploads."""

    def __init__(
        self,
        root: str | os.PathLike[str] | None = None,
        staging_root: str | os.PathLike[str] | None = None,
    ):
        self.root = (
            Path(root).resolve() if root else configured_model_artifact_directory()
        )
        self.staging_root = Path(
            staging_root or configured_model_staging_directory()
        ).resolve()
        self._schema_ready = False
        self._schema_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._upload_metrics = {
            "succeeded": 0,
            "rejected_too_large": 0,
            "rejected_capacity": 0,
            "failed": 0,
        }
        self._last_cleanup: dict[str, Any] = {
            "completed_at": None,
            "artifacts_deleted": 0,
            "bytes_reclaimed": 0,
            "staging_entries_deleted": 0,
            "orphan_entries_deleted": 0,
            "legacy_entries_registered": 0,
            "missing_payload_records_deleted": 0,
        }

    @staticmethod
    def _owner_key(owner_id: Any) -> str:
        value = str(owner_id or "").strip()
        if not value:
            raise ManagedArtifactError("Artifact owner context is required.")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _normalize_artifact_id(artifact_id: Any) -> str:
        try:
            return str(uuid.UUID(str(artifact_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ManagedArtifactError("Managed artifact ID is invalid.") from exc

    def _artifact_directory_from_keys(self, owner_key: str, artifact_id: Any) -> Path:
        normalized_id = self._normalize_artifact_id(artifact_id)
        if not _OWNER_KEY_PATTERN.fullmatch(owner_key):
            raise ManagedArtifactError("Managed artifact owner key is invalid.")
        candidate = (self.root / owner_key / normalized_id).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ManagedArtifactError("Managed artifact path is invalid.") from exc
        return candidate

    def _artifact_directory(self, owner_id: Any, artifact_id: Any) -> Path:
        return self._artifact_directory_from_keys(
            self._owner_key(owner_id), artifact_id
        )

    def _storage_key(self, owner_key: str, artifact_id: Any) -> str:
        normalized_id = self._normalize_artifact_id(artifact_id)
        return f"{owner_key}/{normalized_id}/payload"

    def _path_from_storage_key(self, storage_key: str) -> Path:
        relative = Path(str(storage_key or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ManagedArtifactError("Managed artifact storage key is invalid.")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ManagedArtifactError("Managed artifact storage key is invalid.") from exc
        return candidate

    def _ensure_roots(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.staging_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    @staticmethod
    def _database_components():
        # Deliberately lazy: isolated scanner workers import this module and must
        # not initialize the database or the rest of the application graph.
        import app.core.database as database  # noqa: PLC0415
        from app.models.model_artifact import (  # noqa: PLC0415
            ManagedModelArtifact,
            ManagedModelArtifactLease,
        )

        if database.SessionLocal is None or database.engine is None:
            raise ManagedArtifactMetadataError(
                "Managed artifact metadata storage is unavailable."
            )
        return database, ManagedModelArtifact, ManagedModelArtifactLease

    def ensure_metadata_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            database, artifact_model, lease_model = self._database_components()
            try:
                artifact_model.__table__.create(bind=database.engine, checkfirst=True)
                lease_model.__table__.create(bind=database.engine, checkfirst=True)
            except Exception as exc:
                raise ManagedArtifactMetadataError(
                    "Managed artifact metadata schema is unavailable."
                ) from exc
            self._schema_ready = True

    @contextmanager
    def _session(self) -> Iterator[Any]:
        database, _, _ = self._database_components()
        session = database.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _minimum_free_bytes(self, total_bytes: int) -> int:
        percentage_reserve = int(
            total_bytes * configured_storage_min_free_percent() / 100
        )
        return max(configured_storage_min_free_bytes(), percentage_reserve)

    def _reservation_files(self, storage_root: Path | None = None) -> list[Path]:
        reservation_root = (storage_root or self.root) / ".reservations"
        reservation_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        return list(reservation_root.glob("*.json"))

    def _active_reserved_bytes(
        self,
        *,
        exclude_id: str | None = None,
        storage_root: Path | None = None,
    ) -> int:
        cutoff = time.time() - configured_upload_reservation_seconds()
        total = 0
        reservation_root = (storage_root or self.root) / ".reservations"
        reservation_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for partial_path in reservation_root.glob("*.partial"):
            try:
                if partial_path.stat().st_mtime < cutoff:
                    partial_path.unlink(missing_ok=True)
            except OSError:
                pass
        for path in self._reservation_files(storage_root):
            if exclude_id and path.stem == exclude_id:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                created_at = float(data["created_at"])
                reserved_bytes = max(0, int(data["reserved_bytes"]))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                created_at = 0
                reserved_bytes = 0
            if created_at < cutoff:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                continue
            total += reserved_bytes
        return total

    def _check_capacity(
        self,
        required_bytes: int,
        *,
        exclude_reservation_id: str | None = None,
        storage_root: Path | None = None,
    ) -> None:
        self._ensure_roots()
        capacity_root = storage_root or self.root
        try:
            usage = shutil.disk_usage(capacity_root)
        except OSError as exc:
            raise ManagedArtifactInsufficientDiskError(
                "The model artifact storage volume could not be checked."
            ) from exc
        used_percent = (usage.used / usage.total * 100) if usage.total else 100
        if used_percent >= configured_storage_hard_percent():
            raise ManagedArtifactInsufficientDiskError(
                "Model artifact storage reached its hard utilization limit."
            )
        other_reservations = self._active_reserved_bytes(
            exclude_id=exclude_reservation_id,
            storage_root=capacity_root,
        )
        safe_free = self._minimum_free_bytes(usage.total)
        if usage.free - other_reservations - max(0, int(required_bytes)) < safe_free:
            raise ManagedArtifactInsufficientDiskError(
                "Not enough unreserved disk space to store this model artifact safely."
            )

    def _reserve_capacity(
        self, required_bytes: int, *, storage_root: Path | None = None
    ) -> str:
        self._ensure_roots()
        capacity_root = storage_root or self.root
        reservation_id = uuid.uuid4().hex
        lock = FileLock(str(capacity_root / ".capacity.lock"), timeout=10)
        try:
            with lock:
                self._check_capacity(required_bytes, storage_root=capacity_root)
                path = capacity_root / ".reservations" / f"{reservation_id}.json"
                partial_path = path.with_suffix(".partial")
                descriptor = os.open(
                    partial_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as reservation:
                    json.dump(
                        {
                            "created_at": time.time(),
                            "reserved_bytes": max(0, int(required_bytes)),
                        },
                        reservation,
                        separators=(",", ":"),
                    )
                    reservation.flush()
                    os.fsync(reservation.fileno())
                os.replace(partial_path, path)
        except FileLockTimeout as exc:
            raise ManagedArtifactInsufficientDiskError(
                "Model artifact storage capacity is currently being allocated."
            ) from exc
        except Exception:
            try:
                (
                    capacity_root
                    / ".reservations"
                    / f"{reservation_id}.partial"
                ).unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return reservation_id

    def _release_capacity(
        self,
        reservation_id: str | None,
        *,
        storage_root: Path | None = None,
    ) -> None:
        if not reservation_id:
            return
        try:
            ((storage_root or self.root) / ".reservations" / f"{reservation_id}.json").unlink(
                missing_ok=True
            )
        except OSError:
            logger.warning("Managed artifact disk reservation cleanup failed.")

    def reserve_staging_capacity(self, required_bytes: int) -> str:
        """Reserve capacity for one streamed MinIO/connected artifact stage."""

        return self._reserve_capacity(required_bytes, storage_root=self.staging_root)

    def release_staging_capacity(self, reservation_id: str | None) -> None:
        self._release_capacity(reservation_id, storage_root=self.staging_root)

    def _create_upload_record(
        self,
        *,
        artifact_id: str,
        owner_key: str,
        name: str,
        source_kind: str,
        source_file_count: int | None,
        workflow_id: Any = None,
        node_id: Any = None,
    ) -> None:
        self.ensure_metadata_schema()
        _, artifact_model, _ = self._database_components()
        now = _utcnow()
        with self._session() as session:
            session.add(
                artifact_model(
                    id=uuid.UUID(artifact_id),
                    owner_key=owner_key,
                    storage_backend="filesystem",
                    storage_key=self._storage_key(owner_key, artifact_id),
                    name=name,
                    size_bytes=0,
                    format_hint=_format_hint(name),
                    source_kind=source_kind,
                    source_file_count=source_file_count,
                    workflow_id=_safe_context_id(workflow_id, 64),
                    node_id=_safe_context_id(node_id, 128),
                    state="uploading",
                    scan_count=0,
                    created_at=now,
                    updated_at=now,
                    expires_at=now
                    + timedelta(seconds=configured_incomplete_retention_seconds()),
                )
            )

    def _finalize_upload_record(
        self,
        *,
        artifact_id: str,
        size_bytes: int,
        sha256: str,
        format_hint: str | None,
        expires_at: datetime,
    ) -> datetime:
        _, artifact_model, _ = self._database_components()
        now = _utcnow()
        with self._session() as session:
            record = session.get(artifact_model, uuid.UUID(artifact_id))
            if record is None:
                raise ManagedArtifactMetadataError(
                    "Managed artifact metadata disappeared during upload."
                )
            record.size_bytes = size_bytes
            record.sha256 = sha256
            record.format_hint = format_hint
            record.state = "ready"
            record.updated_at = now
            record.last_accessed_at = now
            record.expires_at = expires_at
            record.last_error = None
        return expires_at

    def _remove_metadata(self, artifact_id: str) -> None:
        try:
            _, artifact_model, _ = self._database_components()
            with self._session() as session:
                record = session.get(artifact_model, uuid.UUID(artifact_id))
                if record is not None:
                    session.delete(record)
        except Exception:
            logger.error(
                "Managed artifact metadata rollback failed: artifact_id=%s",
                artifact_id,
            )

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(COPY_CHUNK_BYTES):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _response(
        *,
        artifact_id: str,
        name: str,
        size_bytes: int,
        format_hint: str | None,
        sha256: str,
        expires_at: datetime,
        source_kind: str,
        source_file_count: int | None = None,
    ) -> dict[str, Any]:
        response: dict[str, Any] = {
            "storage": "managed",
            "artifact_id": artifact_id,
            "name": name,
            "size_bytes": size_bytes,
            "format": format_hint,
            "sha256": sha256,
            "source_kind": source_kind,
            "retention_mode": "temporary",
            "retention_seconds": configured_managed_retention_seconds(),
            "expires_at": expires_at.isoformat(),
        }
        if source_file_count is not None:
            response["source_file_count"] = source_file_count
        return response

    def _record_upload_result(self, outcome: str) -> None:
        with self._metrics_lock:
            self._upload_metrics[outcome] += 1

    def _record_upload_error(self, exc: Exception) -> None:
        if isinstance(exc, ManagedArtifactTooLargeError):
            outcome = "rejected_too_large"
        elif isinstance(exc, ManagedArtifactInsufficientDiskError):
            outcome = "rejected_capacity"
        else:
            outcome = "failed"
        self._record_upload_result(outcome)

    async def save_upload(
        self,
        upload: UploadFile,
        *,
        owner_id: Any,
        max_bytes: Any = None,
        workflow_id: Any = None,
        node_id: Any = None,
    ) -> dict[str, Any]:
        limit = _positive_limit(max_bytes or configured_upload_max_bytes())
        artifact_id = str(uuid.uuid4())
        owner_key = self._owner_key(owner_id)
        name = _safe_display_name(upload.filename)
        artifact_directory = self._artifact_directory_from_keys(owner_key, artifact_id)
        partial_path = artifact_directory / "payload.partial"
        payload_path = artifact_directory / "payload"
        manifest_path = artifact_directory / "metadata.json"
        size_bytes = 0
        reservation_id: str | None = None
        metadata_created = False
        digest = hashlib.sha256()

        self._ensure_roots()
        try:
            known_size = getattr(upload, "size", None)
            try:
                known_size = int(known_size) if known_size is not None else None
            except (TypeError, ValueError):
                known_size = None
            if known_size is not None and known_size < 0:
                known_size = None
            if known_size is not None and known_size > limit:
                raise ManagedArtifactTooLargeError(
                    "Model artifact exceeds the configured upload size limit."
                )
            reservation_id = self._reserve_capacity(
                known_size if known_size is not None else limit
            )
            self._create_upload_record(
                artifact_id=artifact_id,
                owner_key=owner_key,
                name=name,
                source_kind="file",
                source_file_count=1,
                workflow_id=workflow_id,
                node_id=node_id,
            )
            metadata_created = True
            artifact_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            descriptor = os.open(
                partial_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "wb") as destination:
                last_disk_check = 0
                while True:
                    chunk = await upload.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > limit:
                        raise ManagedArtifactTooLargeError(
                            "Model artifact exceeds the configured upload size limit."
                        )
                    if size_bytes - last_disk_check >= DISK_CHECK_INTERVAL_BYTES:
                        remaining = max(0, (known_size or limit) - size_bytes)
                        self._check_capacity(
                            remaining, exclude_reservation_id=reservation_id
                        )
                        last_disk_check = size_bytes
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())

            if size_bytes == 0:
                raise ManagedArtifactError("Empty model artifacts cannot be uploaded.")
            os.replace(partial_path, payload_path)
            sha256 = digest.hexdigest()
            expires_at = _utcnow() + timedelta(
                seconds=configured_managed_retention_seconds()
            )
            self._write_manifest(
                manifest_path,
                {
                    "schema_version": "2.0",
                    "artifact_id": artifact_id,
                    "name": name,
                    "size_bytes": size_bytes,
                    "format": _format_hint(name),
                    "sha256": sha256,
                    "source_kind": "file",
                    "source_file_count": 1,
                    "created_at": _utcnow().isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
            )
            self._finalize_upload_record(
                artifact_id=artifact_id,
                size_bytes=size_bytes,
                sha256=sha256,
                format_hint=_format_hint(name),
                expires_at=expires_at,
            )
            response = self._response(
                artifact_id=artifact_id,
                name=name,
                size_bytes=size_bytes,
                format_hint=_format_hint(name),
                sha256=sha256,
                expires_at=expires_at,
                source_kind="file",
                source_file_count=1,
            )
            self._record_upload_result("succeeded")
            return response
        except Exception as exc:
            self._record_upload_error(exc)
            shutil.rmtree(artifact_directory, ignore_errors=True)
            if metadata_created:
                self._remove_metadata(artifact_id)
            raise
        finally:
            self._release_capacity(reservation_id)
            await upload.close()

    async def save_directory_upload(
        self,
        uploads: Sequence[UploadFile],
        relative_paths: Sequence[str],
        *,
        archive_name: str,
        owner_id: Any,
        max_bytes: Any = None,
        workflow_id: Any = None,
        node_id: Any = None,
    ) -> dict[str, Any]:
        """Stream browser folder files into one uncompressed, Zip64 archive."""

        files = list(uploads)
        paths = list(relative_paths)

        async def close_uploads() -> None:
            for upload in files:
                await upload.close()

        if not files or len(files) != len(paths):
            await close_uploads()
            raise ManagedArtifactError("Folder upload metadata is incomplete.")
        if len(files) > MAX_DIRECTORY_FILES:
            await close_uploads()
            raise ManagedArtifactError(
                f"A folder may contain at most {MAX_DIRECTORY_FILES} files."
            )
        try:
            safe_paths = [_safe_archive_path(path) for path in paths]
        except Exception:
            await close_uploads()
            raise
        if len({path.casefold() for path in safe_paths}) != len(safe_paths):
            await close_uploads()
            raise ManagedArtifactError("A selected folder contains duplicate file paths.")

        limit = _positive_limit(max_bytes or configured_upload_max_bytes())
        artifact_id = str(uuid.uuid4())
        owner_key = self._owner_key(owner_id)
        name = _safe_display_name(archive_name)
        if not name.lower().endswith(".zip"):
            name = f"{name}.zip"
        artifact_directory = self._artifact_directory_from_keys(owner_key, artifact_id)
        partial_path = artifact_directory / "payload.partial"
        payload_path = artifact_directory / "payload"
        manifest_path = artifact_directory / "metadata.json"
        total_source_bytes = 0
        reservation_id: str | None = None
        metadata_created = False

        self._ensure_roots()
        try:
            known_sizes: list[int] = []
            all_sizes_known = True
            for upload in files:
                known_size = getattr(upload, "size", None)
                try:
                    parsed_size = int(known_size)
                    if parsed_size < 0:
                        raise ValueError
                    known_sizes.append(parsed_size)
                except (TypeError, ValueError):
                    all_sizes_known = False
                    break
            known_total = (
                sum(max(0, size) for size in known_sizes)
                if all_sizes_known
                else None
            )
            if known_total is not None and known_total > limit:
                raise ManagedArtifactTooLargeError(
                    "Selected folder exceeds the configured upload size limit."
                )
            reservation_bytes = (
                known_total + max(1024 * 1024, len(files) * 1024)
                if known_total is not None
                else limit
            )
            reservation_id = self._reserve_capacity(reservation_bytes)
            self._create_upload_record(
                artifact_id=artifact_id,
                owner_key=owner_key,
                name=name,
                source_kind="directory",
                source_file_count=len(files),
                workflow_id=workflow_id,
                node_id=node_id,
            )
            metadata_created = True
            artifact_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            descriptor = os.open(
                partial_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "w+b") as archive_file:
                with zipfile.ZipFile(
                    archive_file,
                    mode="w",
                    compression=zipfile.ZIP_STORED,
                    allowZip64=True,
                ) as archive:
                    last_disk_check = 0
                    for upload, relative_path in zip(files, safe_paths, strict=True):
                        info = zipfile.ZipInfo(relative_path)
                        info.compress_type = zipfile.ZIP_STORED
                        info.external_attr = 0o600 << 16
                        with archive.open(info, mode="w", force_zip64=True) as destination:
                            while True:
                                chunk = await upload.read(COPY_CHUNK_BYTES)
                                if not chunk:
                                    break
                                total_source_bytes += len(chunk)
                                if total_source_bytes > limit:
                                    raise ManagedArtifactTooLargeError(
                                        "Selected folder exceeds the configured upload size limit."
                                    )
                                if (
                                    total_source_bytes - last_disk_check
                                    >= DISK_CHECK_INTERVAL_BYTES
                                ):
                                    remaining = max(
                                        0,
                                        reservation_bytes - total_source_bytes,
                                    )
                                    self._check_capacity(
                                        remaining,
                                        exclude_reservation_id=reservation_id,
                                    )
                                    last_disk_check = total_source_bytes
                                destination.write(chunk)
                archive_file.flush()
                os.fsync(archive_file.fileno())

            if total_source_bytes == 0:
                raise ManagedArtifactError("An empty folder cannot be uploaded.")
            archive_size = partial_path.stat().st_size
            if archive_size > limit:
                raise ManagedArtifactTooLargeError(
                    "Generated ZIP exceeds the configured upload size limit."
                )
            os.replace(partial_path, payload_path)
            sha256 = self._hash_file(payload_path)
            expires_at = _utcnow() + timedelta(
                seconds=configured_managed_retention_seconds()
            )
            self._write_manifest(
                manifest_path,
                {
                    "schema_version": "2.0",
                    "artifact_id": artifact_id,
                    "name": name,
                    "size_bytes": archive_size,
                    "format": "archive",
                    "sha256": sha256,
                    "source_kind": "directory",
                    "source_file_count": len(files),
                    "source_size_bytes": total_source_bytes,
                    "created_at": _utcnow().isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
            )
            self._finalize_upload_record(
                artifact_id=artifact_id,
                size_bytes=archive_size,
                sha256=sha256,
                format_hint="archive",
                expires_at=expires_at,
            )
            response = self._response(
                artifact_id=artifact_id,
                name=name,
                size_bytes=archive_size,
                format_hint="archive",
                sha256=sha256,
                expires_at=expires_at,
                source_kind="directory",
                source_file_count=len(files),
            )
            self._record_upload_result("succeeded")
            return response
        except Exception as exc:
            self._record_upload_error(exc)
            shutil.rmtree(artifact_directory, ignore_errors=True)
            if metadata_created:
                self._remove_metadata(artifact_id)
            raise
        finally:
            self._release_capacity(reservation_id)
            await close_uploads()

    @staticmethod
    def _write_manifest(path: Path, metadata: dict[str, Any]) -> None:
        partial_path = path.with_suffix(".partial")
        descriptor = os.open(
            partial_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as manifest:
            json.dump(metadata, manifest, ensure_ascii=True, separators=(",", ":"))
            manifest.flush()
            os.fsync(manifest.fileno())
        os.replace(partial_path, path)

    def _read_payload(
        self, artifact_directory: Path, artifact_id: str
    ) -> tuple[dict[str, Any], Path]:
        payload_path = artifact_directory / "payload"
        manifest_path = artifact_directory / "metadata.json"
        try:
            metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload_stat = payload_path.stat()
        except (OSError, json.JSONDecodeError) as exc:
            raise ManagedArtifactError("Managed artifact is unavailable.") from exc
        if not stat.S_ISREG(payload_stat.st_mode) or payload_path.is_symlink():
            raise ManagedArtifactError("Managed artifact payload is invalid.")
        if str(metadata.get("artifact_id")) != artifact_id:
            raise ManagedArtifactError("Managed artifact metadata is invalid.")
        try:
            declared_size = int(metadata.get("size_bytes", -1))
        except (TypeError, ValueError) as exc:
            raise ManagedArtifactError("Managed artifact metadata is invalid.") from exc
        if declared_size < 0 or declared_size != payload_stat.st_size:
            raise ManagedArtifactError("Managed artifact size validation failed.")
        return metadata, payload_path

    def resolve(self, artifact_id: str, *, owner_id: Any) -> ManagedArtifactRecord:
        normalized_id = self._normalize_artifact_id(artifact_id)
        owner_key = self._owner_key(owner_id)
        artifact_directory = self._artifact_directory_from_keys(owner_key, normalized_id)
        self.ensure_metadata_schema()
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        with self._session() as session:
            metadata_exists = (
                session.get(artifact_model, uuid.UUID(normalized_id)) is not None
            )
        if not metadata_exists:
            self._reconcile_legacy_uploads()
        with self._session() as session:
            record = session.get(
                artifact_model, uuid.UUID(normalized_id), with_for_update=True
            )
            if record is None or record.owner_key != owner_key:
                raise ManagedArtifactError("Managed artifact is unavailable or expired.")
            active_lease = (
                session.query(lease_model.id)
                .filter(
                    lease_model.artifact_id == record.id,
                    lease_model.expires_at > now,
                )
                .first()
                is not None
            )
            if record.state not in {"ready", "in_use"}:
                raise ManagedArtifactError("Managed artifact is unavailable or expired.")
            if record.expires_at <= now and not active_lease:
                raise ManagedArtifactError("Managed artifact is unavailable or expired.")
            record.last_accessed_at = now
            record.updated_at = now
            expires_at = record.expires_at
            sha256 = record.sha256
            name = record.name
            format_hint = record.format_hint
            declared_size = int(record.size_bytes)

        metadata, payload_path = self._read_payload(artifact_directory, normalized_id)
        if int(metadata["size_bytes"]) != declared_size:
            raise ManagedArtifactError("Managed artifact metadata does not match its payload.")
        return ManagedArtifactRecord(
            artifact_id=normalized_id,
            name=_safe_display_name(name),
            size_bytes=declared_size,
            format_hint=str(format_hint or "").lower() or None,
            sha256=sha256,
            payload_path=payload_path,
            expires_at=expires_at,
        )

    def acquire_lease(
        self,
        artifact_id: str,
        *,
        owner_id: Any,
        lease_seconds: int,
    ) -> str:
        normalized_id = self._normalize_artifact_id(artifact_id)
        owner_key = self._owner_key(owner_id)
        self.ensure_metadata_schema()
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        lease_id = uuid.uuid4()
        lease_until = now + timedelta(seconds=max(60, int(lease_seconds)))
        with self._session() as session:
            metadata_exists = (
                session.get(artifact_model, uuid.UUID(normalized_id)) is not None
            )
        if not metadata_exists:
            self._reconcile_legacy_uploads()
        with self._session() as session:
            record = session.get(
                artifact_model, uuid.UUID(normalized_id), with_for_update=True
            )
            if (
                record is None
                or record.owner_key != owner_key
                or record.state not in {"ready", "in_use"}
            ):
                raise ManagedArtifactError("Managed artifact is unavailable or expired.")
            active_lease = (
                session.query(lease_model.id)
                .filter(
                    lease_model.artifact_id == record.id,
                    lease_model.expires_at > now,
                )
                .first()
                is not None
            )
            if record.expires_at <= now and not active_lease:
                raise ManagedArtifactError("Managed artifact is unavailable or expired.")
            session.add(
                lease_model(
                    id=lease_id,
                    artifact_id=record.id,
                    acquired_at=now,
                    expires_at=lease_until,
                )
            )
            record.state = "in_use"
            record.last_accessed_at = now
            record.updated_at = now
        return str(lease_id)

    def describe(self, artifact_id: str, *, owner_id: Any) -> dict[str, Any] | None:
        """Return owner-scoped lifecycle metadata without opening the payload."""

        normalized_id = self._normalize_artifact_id(artifact_id)
        owner_key = self._owner_key(owner_id)
        self.ensure_metadata_schema()
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        with self._session() as session:
            record = session.get(artifact_model, uuid.UUID(normalized_id))
            if record is None or record.owner_key != owner_key:
                return None
            active_leases = int(
                session.query(func.count(lease_model.id))
                .filter(
                    lease_model.artifact_id == record.id,
                    lease_model.expires_at > now,
                )
                .scalar()
                or 0
            )
            available = record.state in {"ready", "in_use"} and (
                record.expires_at > now or active_leases > 0
            )
            state = record.state if available else "expired"
            return {
                "storage": "managed",
                "artifact_id": normalized_id,
                "name": record.name,
                "size_bytes": int(record.size_bytes or 0),
                "format": record.format_hint,
                "sha256": record.sha256,
                "source_kind": record.source_kind,
                "source_file_count": record.source_file_count,
                "retention_mode": "temporary",
                "state": state,
                "available": available,
                "active_scan_leases": active_leases,
                "scan_count": int(record.scan_count or 0),
                "expires_at": record.expires_at.isoformat(),
                "last_scanned_at": (
                    record.last_scanned_at.isoformat()
                    if record.last_scanned_at
                    else None
                ),
            }

    def release_lease(
        self,
        artifact_id: str,
        lease_id: str,
        *,
        scan_attempted: bool = True,
    ) -> None:
        normalized_id = self._normalize_artifact_id(artifact_id)
        try:
            normalized_lease_id = uuid.UUID(str(lease_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ManagedArtifactError("Managed artifact lease ID is invalid.") from exc
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        with self._session() as session:
            lease = session.get(lease_model, normalized_lease_id)
            if lease is not None and lease.artifact_id == uuid.UUID(normalized_id):
                session.delete(lease)
                session.flush()
            record = session.get(
                artifact_model, uuid.UUID(normalized_id), with_for_update=True
            )
            if record is None:
                return
            if scan_attempted:
                record.scan_count = int(record.scan_count or 0) + 1
                record.last_scanned_at = now
                record.expires_at = now + timedelta(
                    seconds=configured_managed_post_scan_retention_seconds()
                )
            active_count = (
                session.query(lease_model.id)
                .filter(
                    lease_model.artifact_id == record.id,
                    lease_model.expires_at > now,
                )
                .count()
            )
            record.state = "in_use" if active_count else "ready"
            record.updated_at = now

    def delete(self, artifact_id: str, *, owner_id: Any) -> bool:
        normalized_id = self._normalize_artifact_id(artifact_id)
        owner_key = self._owner_key(owner_id)
        self.ensure_metadata_schema()
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        with self._session() as session:
            record = session.get(
                artifact_model, uuid.UUID(normalized_id), with_for_update=True
            )
            if record is None or record.owner_key != owner_key:
                return False
            active_count = (
                session.query(lease_model.id)
                .filter(
                    lease_model.artifact_id == record.id,
                    lease_model.expires_at > now,
                )
                .count()
            )
            if active_count:
                raise ManagedArtifactInUseError(
                    "Managed artifact is currently protected by an active scan."
                )
            record.state = "deleting"
            record.updated_at = now
            storage_key = record.storage_key

        payload_path = self._path_from_storage_key(storage_key)
        shutil.rmtree(payload_path.parent, ignore_errors=True)
        with self._session() as session:
            record = session.get(artifact_model, uuid.UUID(normalized_id))
            if record is not None and record.owner_key == owner_key:
                session.delete(record)
        return True

    def _delete_record(self, artifact_id: uuid.UUID) -> tuple[int, bool]:
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        with self._session() as session:
            record = session.get(artifact_model, artifact_id, with_for_update=True)
            if record is None:
                return 0, False
            active = (
                session.query(lease_model.id)
                .filter(
                    lease_model.artifact_id == artifact_id,
                    lease_model.expires_at > now,
                )
                .count()
            )
            if active:
                return 0, False
            record.state = "deleting"
            storage_key = record.storage_key
            size_bytes = int(record.size_bytes or 0)
        payload_path = self._path_from_storage_key(storage_key)
        shutil.rmtree(payload_path.parent, ignore_errors=True)
        with self._session() as session:
            record = session.get(artifact_model, artifact_id)
            if record is not None:
                session.delete(record)
        return size_bytes, True

    def _cleanup_staging(self, now_epoch: float) -> int:
        self.staging_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        cutoff = now_epoch - configured_staging_retention_seconds()
        deleted = 0
        for entry in self.staging_root.iterdir():
            try:
                if entry.name.startswith("."):
                    continue
                if entry.lstat().st_mtime >= cutoff:
                    continue
                _remove_owned_entry(entry, root=self.staging_root)
                deleted += 1
            except (ManagedArtifactError, OSError):
                logger.warning("Stale model scan staging entry could not be removed.")
        return deleted

    def _cleanup_filesystem_orphans(self, now_epoch: float) -> int:
        cutoff = now_epoch - configured_incomplete_retention_seconds()
        deleted = 0
        _, artifact_model, _ = self._database_components()
        for owner_directory in self.root.iterdir():
            try:
                owner_stat = owner_directory.lstat()
            except OSError:
                continue
            if not _OWNER_KEY_PATTERN.fullmatch(owner_directory.name):
                continue
            if _is_link_or_reparse(owner_stat):
                try:
                    _remove_owned_entry(owner_directory, root=self.root)
                    deleted += 1
                except (ManagedArtifactError, OSError):
                    logger.warning("Unsafe managed artifact link could not be removed.")
                continue
            if not stat.S_ISDIR(owner_stat.st_mode):
                continue
            for artifact_directory in owner_directory.iterdir():
                try:
                    normalized_id = self._normalize_artifact_id(artifact_directory.name)
                    artifact_stat = artifact_directory.lstat()
                    entry_mtime = artifact_stat.st_mtime
                except (ManagedArtifactError, OSError):
                    continue
                if entry_mtime >= cutoff:
                    continue
                with self._session() as session:
                    exists = session.get(artifact_model, uuid.UUID(normalized_id)) is not None
                if exists:
                    continue
                try:
                    _remove_owned_entry(artifact_directory, root=self.root)
                    deleted += 1
                except (ManagedArtifactError, OSError):
                    logger.warning("Orphaned managed artifact could not be removed.")
            try:
                owner_directory.rmdir()
            except OSError:
                pass
        return deleted

    def _reconcile_legacy_uploads(self) -> int:
        """Register complete pre-lifecycle uploads before orphan cleanup runs."""

        _, artifact_model, _ = self._database_components()
        registered = 0
        for owner_directory in self.root.iterdir():
            try:
                owner_stat = owner_directory.lstat()
            except OSError:
                continue
            if (
                not _OWNER_KEY_PATTERN.fullmatch(owner_directory.name)
                or _is_link_or_reparse(owner_stat)
                or not stat.S_ISDIR(owner_stat.st_mode)
            ):
                continue
            for artifact_directory in owner_directory.iterdir():
                try:
                    artifact_stat = artifact_directory.lstat()
                    normalized_id = self._normalize_artifact_id(artifact_directory.name)
                except (ManagedArtifactError, OSError):
                    continue
                if (
                    _is_link_or_reparse(artifact_stat)
                    or not stat.S_ISDIR(artifact_stat.st_mode)
                ):
                    continue
                with self._session() as session:
                    if session.get(artifact_model, uuid.UUID(normalized_id)) is not None:
                        continue
                try:
                    metadata, payload_path = self._read_payload(
                        artifact_directory, normalized_id
                    )
                    size_bytes = int(metadata["size_bytes"])
                    sha256 = str(metadata.get("sha256") or "").strip() or self._hash_file(
                        payload_path
                    )
                    if len(sha256) != 64:
                        sha256 = self._hash_file(payload_path)
                except (ManagedArtifactError, OSError, ValueError, TypeError):
                    continue

                now = _utcnow()
                try:
                    source_file_count = int(metadata["source_file_count"])
                except (KeyError, TypeError, ValueError):
                    source_file_count = None
                try:
                    with self._session() as session:
                        session.add(
                            artifact_model(
                                id=uuid.UUID(normalized_id),
                                owner_key=owner_directory.name,
                                storage_backend="filesystem",
                                storage_key=self._storage_key(
                                    owner_directory.name, normalized_id
                                ),
                                name=_safe_display_name(metadata.get("name")),
                                size_bytes=size_bytes,
                                sha256=sha256,
                                format_hint=str(metadata.get("format") or "").lower()
                                or None,
                                source_kind=str(
                                    metadata.get("source_kind") or "file"
                                )[:32],
                                source_file_count=source_file_count,
                                state="ready",
                                scan_count=0,
                                created_at=now,
                                updated_at=now,
                                last_accessed_at=now,
                                expires_at=now
                                + timedelta(
                                    seconds=configured_managed_retention_seconds()
                                ),
                            )
                        )
                    registered += 1
                except Exception as exc:
                    # Another replica may have registered the same directory.
                    logger.debug(
                        "Legacy managed artifact registration skipped: error_type=%s",
                        type(exc).__name__,
                    )
        return registered

    def _remove_missing_payload_records(self) -> int:
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        removed = 0
        with self._session() as session:
            records = session.query(artifact_model).all()
            for record in records:
                active = (
                    session.query(lease_model.id)
                    .filter(
                        lease_model.artifact_id == record.id,
                        lease_model.expires_at > now,
                    )
                    .count()
                )
                if active:
                    continue
                try:
                    payload_path = self._path_from_storage_key(record.storage_key)
                except ManagedArtifactError:
                    payload_path = None
                if payload_path is not None and payload_path.is_file():
                    continue
                session.delete(record)
                removed += 1
        return removed

    def run_maintenance(self) -> dict[str, Any]:
        """Run one cross-process-safe cleanup and return operational counters."""

        self._ensure_roots()
        self.ensure_metadata_schema()
        database, _, _ = self._database_components()
        with database.engine.connect() as connection:
            database_lock_acquired = True
            if connection.dialect.name == "postgresql":
                database_lock_acquired = bool(
                    connection.execute(
                        text("SELECT pg_try_advisory_lock(:lock_id)"),
                        {"lock_id": _MAINTENANCE_ADVISORY_LOCK_ID},
                    ).scalar()
                )
            if not database_lock_acquired:
                return {
                    **self._last_cleanup,
                    "skipped": "another_instance_is_running",
                }
            try:
                maintenance_lock = FileLock(
                    str(self.root / ".maintenance.lock"), timeout=0
                )
                try:
                    with maintenance_lock:
                        return self._run_maintenance_locked()
                except FileLockTimeout:
                    return {
                        **self._last_cleanup,
                        "skipped": "another_process_is_running",
                    }
            finally:
                if connection.dialect.name == "postgresql":
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": _MAINTENANCE_ADVISORY_LOCK_ID},
                    )

    def _run_maintenance_locked(self) -> dict[str, Any]:
        _, artifact_model, lease_model = self._database_components()
        now = _utcnow()
        now_epoch = now.timestamp()
        deleted_count = 0
        reclaimed_bytes = 0
        legacy_registered = self._reconcile_legacy_uploads()
        missing_records_deleted = self._remove_missing_payload_records()

        with self._session() as session:
            session.query(lease_model).filter(lease_model.expires_at <= now).delete(
                synchronize_session=False
            )
            session.flush()
            for record in session.query(artifact_model).filter(
                artifact_model.state == "in_use"
            ):
                active = (
                    session.query(lease_model.id)
                    .filter(
                        lease_model.artifact_id == record.id,
                        lease_model.expires_at > now,
                    )
                    .count()
                )
                if not active:
                    record.state = "ready"
            expired_ids = [
                row[0]
                for row in session.query(artifact_model.id)
                .filter(
                    artifact_model.expires_at <= now,
                    artifact_model.state.in_(("uploading", "ready", "failed", "deleting")),
                )
                .order_by(artifact_model.expires_at.asc())
                .all()
            ]

        for artifact_id in expired_ids:
            reclaimed, deleted = self._delete_record(artifact_id)
            if deleted:
                deleted_count += 1
                reclaimed_bytes += reclaimed

        usage = shutil.disk_usage(self.root)
        used_percent = usage.used / usage.total * 100 if usage.total else 100
        minimum_free = self._minimum_free_bytes(usage.total)
        under_pressure = (
            used_percent >= configured_storage_aggressive_percent()
            or usage.free < minimum_free
        )
        if under_pressure:
            with self._session() as session:
                pressure_ids = [
                    row[0]
                    for row in session.query(artifact_model.id)
                    .filter(artifact_model.state.in_(("ready", "failed")))
                    .order_by(
                        func.coalesce(
                            artifact_model.last_accessed_at,
                            artifact_model.created_at,
                        ).asc()
                    )
                    .all()
                ]
            for artifact_id in pressure_ids:
                usage = shutil.disk_usage(self.root)
                used_percent = usage.used / usage.total * 100 if usage.total else 100
                if (
                    used_percent < configured_storage_soft_percent()
                    and usage.free >= minimum_free
                ):
                    break
                reclaimed, deleted = self._delete_record(artifact_id)
                if deleted:
                    deleted_count += 1
                    reclaimed_bytes += reclaimed

        staging_deleted = self._cleanup_staging(now_epoch)
        orphan_deleted = self._cleanup_filesystem_orphans(now_epoch)
        self._active_reserved_bytes()
        self._active_reserved_bytes(storage_root=self.staging_root)
        self._last_cleanup = {
            "completed_at": now.isoformat(),
            "artifacts_deleted": deleted_count,
            "bytes_reclaimed": reclaimed_bytes,
            "staging_entries_deleted": staging_deleted,
            "orphan_entries_deleted": orphan_deleted,
            "legacy_entries_registered": legacy_registered,
            "missing_payload_records_deleted": missing_records_deleted,
        }
        if deleted_count or staging_deleted or orphan_deleted:
            logger.info("Managed model artifact cleanup completed: %s", self._last_cleanup)
        return dict(self._last_cleanup)

    def storage_status(self) -> dict[str, Any]:
        """Return coarse health and lifecycle metrics without exposing paths."""

        self._ensure_roots()
        usage = shutil.disk_usage(self.root)
        staging_usage = shutil.disk_usage(self.staging_root)
        used_percent = round(usage.used / usage.total * 100, 2) if usage.total else 100
        staging_used_percent = (
            round(staging_usage.used / staging_usage.total * 100, 2)
            if staging_usage.total
            else 100
        )
        status = "healthy"
        if max(used_percent, staging_used_percent) >= configured_storage_hard_percent():
            status = "critical"
        elif (
            max(used_percent, staging_used_percent)
            >= configured_storage_soft_percent()
            or usage.free < self._minimum_free_bytes(usage.total)
            or staging_usage.free < self._minimum_free_bytes(staging_usage.total)
        ):
            status = "warning"
        counts: dict[str, int] = {}
        stored_bytes = 0
        active_leases = 0
        try:
            self.ensure_metadata_schema()
            _, artifact_model, lease_model = self._database_components()
            now = _utcnow()
            with self._session() as session:
                counts = {
                    str(state): int(count)
                    for state, count in session.query(
                        artifact_model.state, func.count(artifact_model.id)
                    )
                    .group_by(artifact_model.state)
                    .all()
                }
                stored_bytes = int(
                    session.query(func.coalesce(func.sum(artifact_model.size_bytes), 0))
                    .filter(artifact_model.state != "deleting")
                    .scalar()
                    or 0
                )
                active_leases = int(
                    session.query(func.count(lease_model.id))
                    .filter(lease_model.expires_at > now)
                    .scalar()
                    or 0
                )
        except Exception as exc:
            status = "error"
            logger.warning(
                "Managed model artifact metrics are unavailable: error_type=%s",
                type(exc).__name__,
            )
        return {
            "status": status,
            "managed_artifacts": sum(counts.values()),
            "artifacts_by_state": counts,
            "stored_bytes": stored_bytes,
            "active_scan_leases": active_leases,
            "disk_total_bytes": usage.total,
            "disk_free_bytes": usage.free,
            "disk_used_percent": used_percent,
            "reserved_upload_bytes": self._active_reserved_bytes(),
            "staging_disk_total_bytes": staging_usage.total,
            "staging_disk_free_bytes": staging_usage.free,
            "staging_disk_used_percent": staging_used_percent,
            "reserved_staging_bytes": self._active_reserved_bytes(
                storage_root=self.staging_root
            ),
            "upload_metrics": dict(self._upload_metrics),
            "last_cleanup": dict(self._last_cleanup),
        }


managed_model_artifact_store = ManagedModelArtifactStore()


__all__ = [
    "DISK_CHECK_INTERVAL_BYTES",
    "ManagedArtifactError",
    "ManagedArtifactInUseError",
    "ManagedArtifactInsufficientDiskError",
    "ManagedArtifactMetadataError",
    "ManagedArtifactRecord",
    "ManagedArtifactTooLargeError",
    "ManagedModelArtifactStore",
    "LOCAL_UPLOAD_MAX_BYTES",
    "configured_model_staging_directory",
    "configured_upload_max_bytes",
    "managed_model_artifact_store",
]
