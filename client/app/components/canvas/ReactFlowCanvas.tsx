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

interface ReactFlowCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: any;
  onEdgesChange: any;
  onConnect: (connection: Connection) => void;
  nodeTypes: any;
  edgeTypes: any;
  activeEdges: string[];
  reactFlowWrapper: React.RefObject<HTMLDivElement | null>;
  onDrop: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  nodeStatus?: Record<string, 'success' | 'failed' | 'pending'>;
  edgeStatus?: Record<string, 'success' | 'failed' | 'pending'>;
  onNodeClick?: (event: React.MouseEvent, node: Node) => void;
}

export default function ReactFlowCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  nodeTypes,
  edgeTypes,
  activeEdges,
  reactFlowWrapper,
  onDrop,
  onDragOver,
  nodeStatus = {},
  edgeStatus = {},
  onNodeClick,
}: ReactFlowCanvasProps) {
  return (
    <div
      ref={reactFlowWrapper}
      className="w-full h-full"
      onDrop={onDrop}
      onDragOver={onDragOver}
    >
      <ReactFlow
        nodes={nodes.map((node) => {
          const status = nodeStatus[node.id];
          const statusStyle =
            status === 'success'
              ? { outline: '2px solid #22c55e', outlineOffset: 2, borderRadius: 12 }
              : status === 'failed'
              ? { outline: '2px solid #ef4444', outlineOffset: 2, borderRadius: 12 }
              : {};
          return {
            ...node,
            style: { ...(node.style || {}), ...statusStyle },
            data: { ...node.data },
          };
        })}
        edges={edges.map((edge) => ({
          ...edge,
          data: { ...(edge.data || {}), status: edgeStatus[edge.id] },
          style: { ...(edge.style || {}), __status: edgeStatus[edge.id] },
        }))}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionMode={ConnectionMode.Loose}
        connectionRadius={30}
        snapToGrid={true}
        snapGrid={[10, 10]}
        fitView
        onNodeClick={onNodeClick}
        proOptions={{ hideAttribution: true }}
      >
        <Controls position="top-right" className="bg-background text-black" />
        <Background gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}
