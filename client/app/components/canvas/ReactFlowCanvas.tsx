import React, { useRef } from "react";
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  Controls,
  Background,
  useReactFlow,
  ConnectionMode,
  type Node,
  type Edge,
  type Connection,
} from "@xyflow/react";
import CustomEdge from "../common/CustomEdge";
import {
  getEdgeExecutionStatus,
  getEffectiveNodeStatus,
} from "~/lib/nodeStatusUtils";

interface ReactFlowCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: any;
  onEdgesChange: any;
  onConnect: (connection: Connection) => void;
  nodeTypes: any;
  edgeTypes: any;
  activeNodes: string[];
  reactFlowWrapper: React.RefObject<HTMLDivElement | null>;
  onDrop: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  nodeStatus?: Record<string, 'success' | 'failed' | 'pending'>;
  edgeStatus?: Record<string, 'success' | 'failed' | 'pending'>;
  onNodeClick?: (event: React.MouseEvent, node: Node) => void;
  onNodeContextMenu?: (event: React.MouseEvent, node: Node) => void;
  onPaneClick?: (event: React.MouseEvent) => void;
}

export default function ReactFlowCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  nodeTypes,
  edgeTypes,
  activeNodes,
  reactFlowWrapper,
  onDrop,
  onDragOver,
  nodeStatus = {},
  edgeStatus = {},
  onNodeClick,
  onNodeContextMenu,
  onPaneClick,
}: ReactFlowCanvasProps) {
  const activeNodeIds = new Set(activeNodes);

  return (
    <div
      ref={reactFlowWrapper}
      className="w-full h-full"
      onDrop={onDrop}
      onDragOver={onDragOver}
    >
      <ReactFlow
        nodes={nodes.map((node) => {
          const reportedStatus = getEffectiveNodeStatus(node.id, nodeStatus, nodes, edges);
          const status =
            reportedStatus === "pending" && !activeNodeIds.has(node.id)
              ? undefined
              : reportedStatus;
          return {
            ...node,
            data: {
              ...(node.data || {}),
              executionStatus: status,
            },
          };
        })}
        edges={edges.map((edge) => {
          const status = getEdgeExecutionStatus(edge, edgeStatus);

          return {
            ...edge,
            data: { ...(edge.data || {}), status },
            style: { ...(edge.style || {}), __status: status },
          };
        })}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionMode={ConnectionMode.Loose}
        connectionRadius={30}
        snapToGrid={false}
        snapGrid={[10, 10]}
        fitView
        onNodeClick={onNodeClick}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={onPaneClick}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}