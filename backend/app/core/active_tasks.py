import asyncio
import logging
from typing import Dict
import uuid

logger = logging.getLogger(__name__)

class ActiveTaskManager:
    """
    Thread-safe registry to track running asyncio Tasks for workflow executions.
    This enables manual cancellation of workflow execution tasks.
    """
    def __init__(self):
        self._tasks: Dict[uuid.UUID, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, execution_id: uuid.UUID, task: asyncio.Task):
        async with self._lock:
            self._tasks[execution_id] = task
            logger.info(f"Registered active task for execution ID: {execution_id}")

    async def unregister(self, execution_id: uuid.UUID):
        async with self._lock:
            if execution_id in self._tasks:
                del self._tasks[execution_id]
                logger.info(f"Unregistered active task for execution ID: {execution_id}")

    async def cancel(self, execution_id: uuid.UUID) -> bool:
        async with self._lock:
            task = self._tasks.get(execution_id)
            if task and not task.done():
                task.cancel()
                logger.warning(f"Sent cancellation request to task for execution ID: {execution_id}")
                return True
            logger.info(f"No active running task found to cancel for execution ID: {execution_id}")
            return False

# Global active task manager instance
active_tasks_manager = ActiveTaskManager()
