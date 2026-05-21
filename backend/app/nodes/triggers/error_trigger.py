"""Error Trigger — entry node for workflows invoked by ErrorHandlerService."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.nodes.base import (
    BaseNode,
    NodeInput,
    NodeOutput,
    NodeProperty,
    NodePropertyType,
    NodeType,
)
from app.core.state import FlowState

logger = logging.getLogger(__name__)


class ErrorTriggerNode(BaseNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "ErrorTrigger",
            "display_name": "Error Trigger",
            "description": "Runs when a linked workflow fails; receives injected error_data.",
            "node_type": NodeType.PROVIDER,
            "category": "Triggers",
            "colors": ["green-500", "emerald-600"],
            "icon": {"name": "error_trigger", "path": "icons/error_trigger.svg", "alt": "Error Trigger"},
            "inputs": [
                NodeInput(
                    name="error_data",
                    type="object",
                    description="Injected by the system on failure",
                    required=False,
                    is_connection=False,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="error_data",
                    displayName="Error Data",
                    type="object",
                    description="Error context for downstream nodes",
                    is_connection=True,
                ),
            ],
            "properties": [],
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        error_data = self.user_data.get("error_data", {})
        if not error_data:
            logger.info("[ErrorTrigger] No error_data — manual/test run")
            error_data = {
                "error": "No error - manual or test execution",
                "status": "failed",
                "error_type": "test",
                "source": {
                    "workflow_id": None,
                    "workflow_name": None,
                    "node_id": None,
                    "node_type": None,
                    "execution_id": None,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger_type": "manual",
            }
        return error_data

    def to_graph_node(self):
        def graph_node_function(state: FlowState) -> Dict[str, Any]:
            try:
                for key, value in self.user_data.items():
                    state.set_variable(key, value)

                node_id = getattr(self, "node_id", f"ErrorTrigger_{id(self)}")
                result = self.execute()

                updated_executed_nodes = state.executed_nodes.copy()
                if node_id not in updated_executed_nodes:
                    updated_executed_nodes.append(node_id)

                clean = dict(result)
                output_payload = {"error_data": clean}

                if not hasattr(state, "node_outputs"):
                    state.node_outputs = {}
                state.node_outputs[node_id] = output_payload

                ui_summary = {"error": clean.get("error"), "status": clean.get("status", "failed")}
                result_str = json.dumps(ui_summary, ensure_ascii=False)

                return {
                    f"output_{node_id}": output_payload,
                    "executed_nodes": updated_executed_nodes,
                    "last_output": result_str,
                    "node_outputs": state.node_outputs,
                }
            except Exception as e:
                nid = getattr(self, "node_id", "ErrorTrigger")
                msg = f"Error in ErrorTrigger ({nid}): {e}"
                logger.error(msg)
                state.add_error(msg)
                return {"errors": state.errors, "last_output": f"ERROR: {msg}"}

        return graph_node_function
