import pytest
from app.services.ai_builder.validator import validate_structure

def test_validate_structure_valid():
    workflow = {
        "nodes": [
            {"id": "node_1", "type": "StartNode", "data": {"name": "Start"}},
            {"id": "node_2", "type": "EndNode", "data": {"name": "End"}},
        ],
        "edges": [
            {"source": "node_1", "target": "node_2", "sourceHandle": "output", "targetHandle": "input"}
        ]
    }
    issues = validate_structure(workflow)
    assert len(issues) == 0

def test_validate_structure_missing_fields():
    workflow = {
        "nodes": [
            {"type": "StartNode", "data": {"name": "Start"}}, # missing id
            {"id": "node_2", "data": {"name": "End"}}, # missing type
        ],
        "edges": []
    }
    issues = validate_structure(workflow)
    assert len(issues) == 2
    codes = [issue.code for issue in issues]
    assert "missing_id" in codes
    assert "missing_type" in codes

def test_validate_structure_duplicate_id():
    workflow = {
        "nodes": [
            {"id": "node_1", "type": "StartNode", "data": {"name": "Start"}},
            {"id": "node_1", "type": "EndNode", "data": {"name": "End"}},
        ],
        "edges": []
    }
    issues = validate_structure(workflow)
    assert len(issues) == 1
    assert issues[0].code == "duplicate_id"

def test_validate_structure_unknown_edges():
    workflow = {
        "nodes": [
            {"id": "node_1", "type": "StartNode", "data": {"name": "Start"}},
        ],
        "edges": [
            {"source": "node_1", "target": "node_999", "sourceHandle": "output", "targetHandle": "input"}
        ]
    }
    issues = validate_structure(workflow)
    assert len(issues) == 1
    assert issues[0].code == "unknown_target"
