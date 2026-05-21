"""Sticky Note Node - For decorative purposes."""

from typing import Dict, Any
from app.nodes.base import TerminatorNode, NodeMetadata, NodeType

class StickyNoteNode(TerminatorNode):
    """
    Sticky Note node provides a decorative element for the canvas.
    It doesn't participate in workflow execution.
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "StickyNoteNode",
            "display_name": "Sticky Note",
            "description": "A resizable text note for adding documentation or comments to your workflow canvas.",
            "node_type": NodeType.TERMINATOR,
            "category": "Decorative",
            "inputs": [],
            "outputs": [],
            "colors": ["yellow-300", "amber-300"],
            "icon": {"name": "sticky-note", "path": None, "alt": None},
        }
    
    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute is a no-op for decorative nodes.
        """
        return {"status": "success", "message": "Decorative node passed"}
