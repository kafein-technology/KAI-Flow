"""Start Node - Entry point for workflows."""

from typing import Dict, Any
import logging
from app.nodes.base import TerminatorNode, NodeMetadata, NodeInput, NodeOutput, NodeType
from app.core.state import FlowState

logger = logging.getLogger(__name__)


class StartNode(TerminatorNode):
    """
    Start node serves as the entry point for workflows.
    It receives initial input and forwards it to connected nodes.
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "StartNode",
            "display_name": "Start",
            "description": "Entry point for workflow execution. Receives initial input and starts the workflow.",
            "node_type": NodeType.TERMINATOR,
            "category": "Special",
            "inputs": [
                NodeInput(
                    name="initial_input",
                    displayName="Initial Input",
                    type="string",
                    description="Initial input text to start the workflow",
                    default="",
                    required=False
                ),
                NodeInput(
                    name="trigger_data",
                    displayName="Trigger Data",
                    type="any",
                    description="Data received from trigger nodes",
                    required=False,
                    is_connection=True
                )
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Execute",
                    type="string",
                    description="Forwarded input to start the workflow chain",
                    is_connection=True,
                )
            ],
            "colors": ["green-500", "emerald-600"],
            "icon": {"name": "rocket", "path": None, "alt": None},
        }
    
    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the start node.
        
        Args:
            inputs: User inputs from the frontend
            connected_nodes: Connected node outputs
            
        Returns:
            Dict containing the initial input to pass to next nodes
        """
        # Get initial input from user data or connected nodes
        initial_input = inputs.get("initial_input", "")
        
        # If no input provided, check connected nodes for trigger data
        if not initial_input and connected_nodes:
            trigger_data = connected_nodes.get("trigger_data")
            if trigger_data:
                # Handle different types of trigger data
                if isinstance(trigger_data, dict):
                    initial_input = trigger_data.get("data", trigger_data.get("message", str(trigger_data)))
                else:
                    initial_input = str(trigger_data)
        
        # If still no input, use a default message
        if not initial_input:
            initial_input = "Workflow started"
        
        logger.info(f"Starting workflow with input: {initial_input}")
        
        return {
            "output": initial_input,
            "message": f"Workflow started with: {initial_input}",
            "status": "started"
        }