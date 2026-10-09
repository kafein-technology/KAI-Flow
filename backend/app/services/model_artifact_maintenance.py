"""Background lifecycle maintenance for application-managed model uploads."""

from __future__ import annotations

import asyncio
import logging

from app.services.model_artifact_store import managed_model_artifact_store
from app.services.model_scan_limits import configured_artifact_gc_interval_seconds


logger = logging.getLogger(__name__)


async def run_model_artifact_maintenance_once() -> dict:
    """Run blocking filesystem/database maintenance outside the event loop."""

    return await asyncio.to_thread(managed_model_artifact_store.run_maintenance)


async def model_artifact_maintenance_loop() -> None:
    """Run at startup and periodically; one replica wins the shared file lock."""

    while True:
        try:
            await run_model_artifact_maintenance_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Managed model artifact maintenance failed: error_type=%s",
                type(exc).__name__,
            )
        await asyncio.sleep(configured_artifact_gc_interval_seconds())


__all__ = [
    "model_artifact_maintenance_loop",
    "run_model_artifact_maintenance_once",
]
