export type CanvasExecutionStatus = "success" | "failed" | "pending";

type CanvasNodeLike = {
  id: string;
  type?: string;
};

type CanvasEdgeLike = {
  id: string;
};

/**
 * A node only reflects its own execution. A provider/sub-node must never inherit
 * the status of a downstream agent: an agent may catch a provider error, and a
 * provider may succeed even when the agent later fails.
 */
export function getEffectiveNodeStatus(
  nodeId: string,
  nodeStatus: Record<string, CanvasExecutionStatus>,
  _nodes: CanvasNodeLike[],
  _edges: CanvasEdgeLike[]
): CanvasExecutionStatus | undefined {
  return nodeStatus[nodeId];
}

/**
 * Edge lifecycle is reported explicitly by the execution stream. Handle names
 * and node types are deliberately not used as execution semantics.
 */
export function getEdgeExecutionStatus(
  edge: CanvasEdgeLike,
  edgeStatus: Record<string, CanvasExecutionStatus> = {}
): CanvasExecutionStatus | undefined {
  return edgeStatus[edge.id];
}
