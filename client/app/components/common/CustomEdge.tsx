import React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  useReactFlow,
  type EdgeProps,
} from "@xyflow/react";
import { X } from "./Icon";

interface CustomAnimatedEdgeProps extends EdgeProps {
  isActive?: boolean;
}

function CustomAnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  isActive = false,
}: CustomAnimatedEdgeProps) {
  const { setEdges } = useReactFlow();
  const [isHovered, setIsHovered] = React.useState(false);
  // read status that ReactFlowCanvas injected into edge.data
  const status: 'success' | 'failed' | 'pending' | undefined = (style as any)?.__status;

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 100,
  });

  const onEdgeClick = () => {
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
  };

  return (
    <>
      {/* Elektrik efekti olan ana edge */}
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke:
            status === 'success'
              ? '#22c55e'
              : status === 'failed'
              ? '#ef4444'
              : isActive
              ? "url(#electric-gradient-" + id + ")"
              : "#6b7280",
          strokeWidth: isActive ? 3 : 2,
          strokeDasharray: isActive ? "12 8" : "none",
          strokeDashoffset: isActive ? 0 : undefined,
          animation: isActive ? "electric-flow 1.2s linear infinite" : "none",
          // carry status for BaseEdge consumption
          // @ts-ignore - internal flag
          __status: status,
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      />

      {/* Daha iyi hover detection için görünmez path */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={30}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      />

      {/* Silme butonu */}
      <EdgeLabelRenderer>
        {isHovered && (
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: 12,
              pointerEvents: "all",
              padding: "8px",
            }}
            className="nodrag nopan"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          >
            <button
              className="flex items-center justify-center w-3 h-3 bg-red-500 hover:bg-red-600 text-white rounded-full shadow-lg transition-all duration-200 hover:scale-110"
              onClick={onEdgeClick}
              title="Delete Edge"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </EdgeLabelRenderer>

      {/* Gradient ve glow tanımları */}
      <svg style={{ height: 0, width: 0 }}>
        <defs>
          <linearGradient
            id={`electric-gradient-${id}`}
            x1={sourceX}
            y1={sourceY}
            x2={targetX}
            y2={targetY}
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#00ffff" />
            <stop offset="100%" stopColor="#facc15" />
          </linearGradient>
        </defs>
      </svg>

      {/* Elektrik animasyonu CSS keyframe */}
      <style>{`
        @keyframes electric-flow {
          0% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -20; }
        }
      `}</style>
    </>
  );
}

export default CustomAnimatedEdge;
