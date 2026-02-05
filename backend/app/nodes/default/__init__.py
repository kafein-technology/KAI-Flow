"""
Default nodes for KAI-Flow workflows.
These nodes provide basic workflow structure and control flow.
"""

from .start_node import StartNode
from .end_node import EndNode

__all__ = [
    "StartNode",
    "EndNode"
] 