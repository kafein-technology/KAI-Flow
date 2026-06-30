import pytest
from app.services.ai_builder.types import WorkflowSnapshot, WorkflowNode, WorkflowEdge
from app.services.ai_builder.diff_engine import compute_changeset

def test_compute_changeset():
    # Setup base workflow snapshot
    base = WorkflowSnapshot(
        nodes=[
            WorkflowNode(id="node_1", type="StartNode", data={"name": "Start"}),
            WorkflowNode(id="node_2", type="Agent", data={"name": "ai_agent", "system_prompt": "hello"}),
        ],
        edges=[
            WorkflowEdge(source="node_1", target="node_2", sourceHandle="output", targetHandle="input")
        ]
    )

    # Target snapshot representing a change:
    # 1. node_2 is modified (system_prompt changed)
    # 2. node_3 is added
    # 3. connection node_2 -> node_3 is added
    target = WorkflowSnapshot(
        nodes=[
            WorkflowNode(id="node_1", type="StartNode", data={"name": "Start"}),
            WorkflowNode(id="node_2", type="Agent", data={"name": "ai_agent", "system_prompt": "hello turkish"}),
            WorkflowNode(id="node_3", type="EndNode", data={"name": "End"}),
        ],
        edges=[
            WorkflowEdge(source="node_1", target="node_2", sourceHandle="output", targetHandle="input"),
            WorkflowEdge(source="node_2", target="node_3", sourceHandle="output", targetHandle="input"),
        ]
    )

    changeset = compute_changeset(base, target)

    assert changeset.has_any_changes is True
    assert changeset.has_structural_changes is True  # added node_3
    
    assert "node_3" in changeset.added_node_ids
    assert "node_2" in changeset.modified_node_ids
    assert len(changeset.deleted_node_ids) == 0

    assert len(changeset.connections.added) == 1
    assert changeset.connections.added[0].source == "node_2"
    assert changeset.connections.added[0].target == "node_3"
    assert len(changeset.connections.removed) == 0
