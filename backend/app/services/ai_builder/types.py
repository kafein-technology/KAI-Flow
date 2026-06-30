from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class NodeDiffStatus(str, Enum):
    EQUAL = "equal"
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"


class WorkflowNode(BaseModel):
    id: str
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    position: Optional[Dict[str, float]] = None

    model_config = {"extra": "allow"}


class WorkflowEdge(BaseModel):
    source: str
    target: str
    sourceHandle: str = "output"
    targetHandle: str = "input"

    model_config = {"extra": "allow"}

    @property
    def key(self) -> str:
        return f"{self.source}:{self.sourceHandle}->{self.target}:{self.targetHandle}"


class WorkflowSnapshot(BaseModel):
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowSnapshot":
        nodes = [WorkflowNode(**n) for n in data.get("nodes", [])]
        edges = [WorkflowEdge(**e) for e in data.get("edges", [])]
        return cls(nodes=nodes, edges=edges)


class NodeDiff(BaseModel):
    status: NodeDiffStatus
    node: WorkflowNode
    changes: Optional[Dict[str, Any]] = None


class ConnectionsDiff(BaseModel):
    added: List[WorkflowEdge] = Field(default_factory=list)
    removed: List[WorkflowEdge] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed)


class WorkflowChangeSet(BaseModel):
    nodes: Dict[str, NodeDiff] = Field(default_factory=dict)
    connections: ConnectionsDiff = Field(default_factory=ConnectionsDiff)

    @property
    def has_structural_changes(self) -> bool:
        return any(
            d.status in (NodeDiffStatus.ADDED, NodeDiffStatus.DELETED)
            for d in self.nodes.values()
        )

    @property
    def has_any_changes(self) -> bool:
        return any(
            d.status != NodeDiffStatus.EQUAL
            for d in self.nodes.values()
        ) or self.connections.has_changes

    @property
    def modified_node_ids(self) -> List[str]:
        return [nid for nid, d in self.nodes.items() if d.status == NodeDiffStatus.MODIFIED]

    @property
    def added_node_ids(self) -> List[str]:
        return [nid for nid, d in self.nodes.items() if d.status == NodeDiffStatus.ADDED]

    @property
    def deleted_node_ids(self) -> List[str]:
        return [nid for nid, d in self.nodes.items() if d.status == NodeDiffStatus.DELETED]

    def summary(self) -> str:
        added = len(self.added_node_ids)
        modified = len(self.modified_node_ids)
        deleted = len(self.deleted_node_ids)
        conn_added = len(self.connections.added)
        conn_removed = len(self.connections.removed)
        return (
            f"Nodes: +{added} ~{modified} -{deleted} | "
            f"Edges: +{conn_added} -{conn_removed}"
        )
