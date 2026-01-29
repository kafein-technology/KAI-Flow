from typing import Any, Dict
import logging
from langchain_core.runnables import Runnable
from ..base import TerminatorNode, NodeMetadata, NodeInput, NodeOutput, NodeType

logger = logging.getLogger(__name__)

class EndNode(TerminatorNode):
    """
    Marks the end of a workflow path.
    This node acts as a sink, terminating a branch of the graph. Any data
    passed to it will be available in the final output of the graph execution.
    """
    
    def __init__(self):
        super().__init__()
        # Correctly assign metadata as a dictionary
        self._metadata = NodeMetadata(
            name="EndNode",
            display_name="End",
            description="Marks the end of a workflow path",
            category="Special",
            node_type=NodeType.TERMINATOR,
            icon={"name": "flag", "path": None, "alt": None},
            colors=["gray-500", "slate-600"],
            inputs=[
                NodeInput(
                    name="target",
                    displayName="Target",
                    type="any",
                    description="The final data from the preceding node",
                    is_connection=True,
                    required=True,
                )
            ],
            outputs=[], # End node has no outputs
        ).dict()

    def execute(self, previous_node: Any, inputs: Dict[str, Any]) -> str:
        """
        Processes the final output from the preceding node and returns it for the chat interface.
        The actual termination is handled by the GraphBuilder connecting this node to END.
        """
        # EndNode receives the actual output data (text) from the connected node
        if previous_node is not None:
            # Convert to string if needed and return for chat interface
            result = str(previous_node) if not isinstance(previous_node, str) else previous_node
            logger.debug(f"EndNode returning output: '{result[:100]}...'")
            return result
        else:
            logger.debug("EndNode received None as input")
            return "No output received"