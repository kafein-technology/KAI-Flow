"""Authenticated model artifact API for LLM model scanner nodes."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.model_artifact_store import (
    ManagedArtifactError,
    ManagedArtifactInUseError,
    ManagedArtifactInsufficientDiskError,
    ManagedArtifactMetadataError,
    ManagedArtifactTooLargeError,
    configured_upload_max_bytes,
    managed_model_artifact_store,
)
from app.services.model_artifact_analysis_service import get_static_analysis_capabilities
from app.services.model_scan_limits import public_managed_artifact_policy, public_scan_limits


logger = logging.getLogger(__name__)
router = APIRouter()


def _known_upload_error(exc: ManagedArtifactError) -> HTTPException:
    if isinstance(exc, ManagedArtifactTooLargeError):
        return HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        )
    if isinstance(exc, ManagedArtifactInsufficientDiskError):
        return HTTPException(status_code=507, detail=str(exc))
    if isinstance(exc, ManagedArtifactMetadataError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if isinstance(exc, ManagedArtifactInUseError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get("/capabilities")
async def get_model_artifact_capabilities():
    """Return only the upload-picker capabilities needed by the frontend."""

    capabilities = get_static_analysis_capabilities()
    return {
        "extensions": capabilities.get("extensions", []),
        "version": capabilities.get("version", "unknown"),
        "limits": public_scan_limits(),
        "managed_artifact_policy": public_managed_artifact_policy(),
    }


@router.get("/status")
def get_managed_artifact_storage_status(
    current_user: User = Depends(get_current_user),
):
    """Return operational lifecycle counters without exposing storage paths."""

    del current_user
    try:
        return managed_model_artifact_store.storage_status()
    except ManagedArtifactError as exc:
        raise _known_upload_error(exc) from exc


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_model_artifact(
    file: UploadFile = File(...),
    workflow_id: str | None = Form(None),
    node_id: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Stream a local browser upload into user-scoped managed artifact storage."""

    try:
        return await managed_model_artifact_store.save_upload(
            file,
            owner_id=current_user.id,
            max_bytes=configured_upload_max_bytes(),
            workflow_id=workflow_id,
            node_id=node_id,
        )
    except ManagedArtifactError as exc:
        raise _known_upload_error(exc) from exc
    except Exception as exc:
        logger.error(
            "Managed model artifact upload failed: user_id=%s error_type=%s",
            current_user.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model artifact could not be stored.",
        ) from exc


@router.post("/upload-directory", status_code=status.HTTP_201_CREATED)
async def upload_model_directory(
    files: list[UploadFile] = File(...),
    paths: str = Form(...),
    archive_name: str = Form("model-folder.zip"),
    workflow_id: str | None = Form(None),
    node_id: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Build one managed ZIP from a browser folder without buffering it in RAM."""

    try:
        relative_paths = json.loads(paths)
        if not isinstance(relative_paths, list) or not all(
            isinstance(path, str) for path in relative_paths
        ):
            raise ManagedArtifactError("Folder upload paths must be a JSON string array.")
        return await managed_model_artifact_store.save_directory_upload(
            files,
            relative_paths,
            archive_name=archive_name,
            owner_id=current_user.id,
            max_bytes=configured_upload_max_bytes(),
            workflow_id=workflow_id,
            node_id=node_id,
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder upload paths are invalid.",
        ) from exc
    except ManagedArtifactError as exc:
        raise _known_upload_error(exc) from exc
    except Exception as exc:
        logger.error(
            "Managed model directory upload failed: user_id=%s error_type=%s",
            current_user.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model folder could not be stored.",
        ) from exc


@router.get("/{artifact_id}")
def get_model_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the current owner-scoped expiry and lease state."""

    try:
        artifact = managed_model_artifact_store.describe(
            artifact_id, owner_id=current_user.id
        )
    except ManagedArtifactError as exc:
        raise _known_upload_error(exc) from exc
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Managed model artifact was not found.",
        )
    return artifact


@router.delete("/{artifact_id}")
def delete_model_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete one managed artifact owned by the authenticated user."""

    try:
        deleted = managed_model_artifact_store.delete(
            artifact_id, owner_id=current_user.id
        )
    except ManagedArtifactError as exc:
        raise _known_upload_error(exc) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Managed model artifact was not found.",
        )
    return {"deleted": True, "artifact_id": artifact_id}
