"""Import-safe filesystem settings for isolated model scanner workers.

This module deliberately has no dependency on the application-wide constants,
database, tracing, or secret-decryption modules.  Spawned scanner processes can
therefore resolve their working directories without bootstrapping the web app.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


DEFAULT_UPLOAD_DIRECTORY = Path("uploads")


def configured_model_artifact_directory() -> Path:
    configured = os.getenv("KAI_MODEL_ARTIFACT_DIR", "").strip()
    return Path(
        configured or DEFAULT_UPLOAD_DIRECTORY / "model-artifacts"
    ).resolve()


def configured_model_staging_directory() -> Path:
    configured = os.getenv("KAI_MODEL_STAGING_DIR", "").strip()
    return Path(
        configured or Path(tempfile.gettempdir()) / "kai-model-scan-staging"
    ).resolve()


__all__ = [
    "DEFAULT_UPLOAD_DIRECTORY",
    "configured_model_artifact_directory",
    "configured_model_staging_directory",
]
