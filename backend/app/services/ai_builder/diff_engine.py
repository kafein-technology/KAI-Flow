import logging
from typing import Dict, List, Any

from .types import (
    WorkflowSnapshot,
    WorkflowNode,
    WorkflowEdge,
    NodeDiff,
    NodeDiffStatus,
    ConnectionsDiff,
    WorkflowChangeSet,
)

logger = logging.getLogger(__name__)


# ─── Node Comparison ───

def compare_nodes(base: WorkflowNode, target: WorkflowNode) -> bool:
    if base.type != target.type:
        return False
    return base.data == target.data


def _detect_changes(base: WorkflowNode, target: WorkflowNode) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}

    if base.type != target.type:
        changes["__type__"] = {"old": base.type, "new": target.type}

    all_keys = set(list(base.data.keys()) + list(target.data.keys()))
    for key in all_keys:
        old_val = base.data.get(key)
        new_val = target.data.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}

    return changes


# ─── Workflow-level Node Diff ───

def compare_workflow_nodes(
    base_nodes: List[WorkflowNode],
    target_nodes: List[WorkflowNode],
) -> Dict[str, NodeDiff]:
    base_map = {n.id: n for n in base_nodes}
    target_map = {n.id: n for n in target_nodes}
    diff: Dict[str, NodeDiff] = {}

    # Check nodes in base
    for nid, node in base_map.items():
        if nid not in target_map:
            # Not in target -> deleted
            diff[nid] = NodeDiff(status=NodeDiffStatus.DELETED, node=node)
        elif not compare_nodes(node, target_map[nid]):
            # Differs -> modified
            changes = _detect_changes(node, target_map[nid])
            diff[nid] = NodeDiff(
                status=NodeDiffStatus.MODIFIED,
                node=target_map[nid],
                changes=changes,
            )
        else:
            # Equal
            diff[nid] = NodeDiff(status=NodeDiffStatus.EQUAL, node=node)

    # In target but not in base -> added
    for nid, node in target_map.items():
        if nid not in base_map:
            diff[nid] = NodeDiff(status=NodeDiffStatus.ADDED, node=node)

    return diff


# ─── Connection Diff ───

def compare_connections(
    base_edges: List[WorkflowEdge],
    target_edges: List[WorkflowEdge],
) -> ConnectionsDiff:
    base_set = {e.key: e for e in base_edges}
    target_set = {e.key: e for e in target_edges}

    added = [e for k, e in target_set.items() if k not in base_set]
    removed = [e for k, e in base_set.items() if k not in target_set]

    return ConnectionsDiff(added=added, removed=removed)


# ─── Full Changeset ───

def compute_changeset(
    base: WorkflowSnapshot,
    target: WorkflowSnapshot,
) -> WorkflowChangeSet:
    if not base.nodes and not base.edges:
        # Empty base -> all added
        node_diffs = {
            n.id: NodeDiff(status=NodeDiffStatus.ADDED, node=n)
            for n in target.nodes
        }
        return WorkflowChangeSet(
            nodes=node_diffs,
            connections=ConnectionsDiff(added=list(target.edges), removed=[]),
        )

    return WorkflowChangeSet(
        nodes=compare_workflow_nodes(base.nodes, target.nodes),
        connections=compare_connections(base.edges, target.edges),
    )


# ─── Edit Context Builder ───

def build_edit_context(
    existing: WorkflowSnapshot,
    user_request: str,
) -> Dict[str, Any]:
    compact_nodes = []
    for node in existing.nodes:
        compact_nodes.append({
            "id": node.id,
            "type": node.type,
            "data": node.data,
        })

    compact_edges = []
    for edge in existing.edges:
        compact_edges.append({
            "source": edge.source,
            "target": edge.target,
            "sourceHandle": edge.sourceHandle,
            "targetHandle": edge.targetHandle,
        })

    return {
        "nodes": compact_nodes,
        "edges": compact_edges,
    }


# ─── Changeset Application ───

def apply_changeset(
    base: WorkflowSnapshot,
    changeset: WorkflowChangeSet,
) -> WorkflowSnapshot:
    result_nodes: List[WorkflowNode] = []

    for nid, diff in changeset.nodes.items():
        if diff.status == NodeDiffStatus.DELETED:
            continue
        result_nodes.append(diff.node)

    # Update connections
    removed_keys = {e.key for e in changeset.connections.removed}
    result_edges = [e for e in base.edges if e.key not in removed_keys]
    result_edges.extend(changeset.connections.added)

    # Remove edges referencing deleted nodes
    valid_ids = {n.id for n in result_nodes}
    result_edges = [
        e for e in result_edges
        if e.source in valid_ids and e.target in valid_ids
    ]

    return WorkflowSnapshot(nodes=result_nodes, edges=result_edges)


# ─── Utility ───

def has_non_positional_changes(changeset: WorkflowChangeSet) -> bool:
    return changeset.has_any_changes
