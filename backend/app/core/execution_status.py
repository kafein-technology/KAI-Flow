from collections.abc import Callable, Iterable, Mapping
from typing import Literal

ExecutionStatus = Literal["pending", "success", "failed"]


def build_execution_edge_statuses(
    node_statuses: Mapping[str, str],
    transmitted_edge_ids: Iterable[str] = (),
    *,
    is_dependency_node: Callable[[str], bool],
    outgoing_edge_ids_for_node: Callable[[str], Iterable[str]],
) -> dict[str, ExecutionStatus]:
    """Map runtime lifecycle data to canvas edges without naming heuristics."""
    statuses: dict[str, ExecutionStatus] = {
        str(edge_id): "success"
        for edge_id in transmitted_edge_ids
        if edge_id
    }

    for node_id, status in node_statuses.items():
        if status not in {"pending", "success", "failed"}:
            continue
        if not is_dependency_node(node_id):
            continue
        for edge_id in outgoing_edge_ids_for_node(node_id):
            statuses[str(edge_id)] = status

    return statuses
