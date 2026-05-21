"""Trigger a configured error-handling workflow when a source workflow fails."""

import copy
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _clean_error_message(message: str) -> str:
    if not message:
        return message
    text = str(message).strip()
    returned_match = re.search(r"returned error:\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
    if returned_match:
        text = returned_match.group(1).strip()
    node_prefix_pattern = r"^Node\s+[^\s]+\s+\([^)]+\)\s+execution failed:?\s*"
    text = re.sub(node_prefix_pattern, "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^:\s*", "", text).strip()
    return text


class ErrorHandlerService:
    @staticmethod
    def extract_error_workflow_id(workflow) -> Optional[str]:
        if not workflow:
            return None
        ew = getattr(workflow, "error_workflow", None)
        if ew:
            return str(ew)
        fd = workflow.flow_data
        if not isinstance(fd, dict):
            return None
        settings = fd.get("settings", {})
        if isinstance(settings, dict):
            eid = settings.get("error_workflow_id")
            if eid and str(eid).strip():
                return str(eid).strip()
        return None

    @staticmethod
    def build_error_data(
        error: Exception,
        workflow: Optional[Any] = None,
        execution_id: Optional[str] = None,
        trigger_type: str = "unknown",
        execution_inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw_msg = str(error)
        error_message = _clean_error_message(raw_msg) or f"Execution failed: {type(error).__name__}"
        try:
            stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        except Exception:
            stack_trace = repr(error)

        return {
            "error": error_message,
            "status": "failed",
            "error_type": type(error).__name__,
            "source": {
                "workflow_id": str(workflow.id) if workflow else None,
                "workflow_name": workflow.name if workflow else None,
                "node_id": getattr(error, "node_id", None),
                "node_type": getattr(error, "node_type", None),
                "execution_id": str(execution_id) if execution_id else None,
            },
            "debug": {"stack_trace": stack_trace, "raw_error": raw_msg},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger_type": trigger_type,
            "execution_inputs": execution_inputs,
        }

    @staticmethod
    async def trigger_error_workflow(
        db: AsyncSession,
        error_workflow_id: str,
        error_data: Dict[str, Any],
        source_workflow,
    ) -> bool:
        from app.models.workflow import Workflow
        from app.models.user import User
        from app.services.workflow_executor import WorkflowExecutor

        try:
            try:
                error_wf_uuid = uuid.UUID(error_workflow_id)
            except (ValueError, AttributeError):
                return False

            if source_workflow and str(source_workflow.id) == str(error_wf_uuid):
                logger.warning("[ErrorHandler] Skipping recursive error workflow trigger")
                return False

            result = await db.execute(select(Workflow).where(Workflow.id == error_wf_uuid))
            error_workflow = result.scalar_one_or_none()
            if not error_workflow:
                logger.error("[ErrorHandler] Error workflow not found: %s", error_workflow_id)
                return False

            user_result = await db.execute(select(User).where(User.id == error_workflow.user_id))
            owner = user_result.scalar_one_or_none()
            if not owner:
                logger.error("[ErrorHandler] Owner not found for error workflow")
                return False

            modified_flow = _inject_error_data_into_flow(error_workflow.flow_data, error_data)

            class _TempWorkflow:
                __slots__ = ("id", "user_id", "name", "description", "is_public", "flow_data", "error_workflow")

                def __init__(self, original: Workflow, new_flow: Dict[str, Any]):
                    self.id = original.id
                    self.user_id = original.user_id
                    self.name = original.name
                    self.description = original.description
                    self.is_public = original.is_public
                    self.flow_data = new_flow
                    self.error_workflow = getattr(original, "error_workflow", None)

            temp = _TempWorkflow(error_workflow, modified_flow)
            src = error_data.get("source") if isinstance(error_data.get("source"), dict) else {}
            wf_label = src.get("workflow_name") or "Workflow"

            executor = WorkflowExecutor()
            ctx = await executor.prepare_execution_context(
                db=db,
                workflow=temp,
                execution_inputs={
                    "input": f"Error in: {wf_label}",
                    "error_data": error_data,
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                },
                user=owner,
                is_webhook=False,
            )
            await executor.execute_workflow(ctx=ctx, db=db, stream=False)
            return True
        except Exception as e:
            logger.error("[ErrorHandler] Failed to trigger error workflow: %s", e, exc_info=True)
            return False


def _inject_error_data_into_flow(flow_data: Dict[str, Any], error_data: Dict[str, Any]) -> Dict[str, Any]:
    modified = copy.deepcopy(flow_data) if isinstance(flow_data, dict) else {"nodes": [], "edges": []}
    nodes = modified.get("nodes", [])
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") in ("ErrorTrigger", "ErrorTriggerNode"):
            node.setdefault("data", {})
            node["data"]["error_data"] = error_data
    return modified


_error_handler_service: Optional[ErrorHandlerService] = None


def get_error_handler_service() -> ErrorHandlerService:
    global _error_handler_service
    if _error_handler_service is None:
        _error_handler_service = ErrorHandlerService()
    return _error_handler_service
