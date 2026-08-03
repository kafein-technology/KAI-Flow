import React, { useRef, useState } from "react";
import { useReactFlow, Handle, Position } from "@xyflow/react";
import {
  Play,
  Trash,
  Activity,
  Zap,
  Rocket,
  Timer,
  Clock,
  Power,
  ArrowRight,
  Loader,
} from "lucide-react";

import NeonHandle from "../common/NeonHandle";
import { getExecutionStatusStyle, PendingWormRing } from "~/lib/nodeStatusUtils";

interface StartNodeProps {
  data: any;
  id: string;
  onExecute?: (id: string) => void;
  validationStatus?: "success" | "error" | null;
  isExecuting?: boolean;
  isActive?: boolean;
}

function StartNode({
  data,
  id,
  onExecute,
  validationStatus,
  isExecuting,
  isActive,
}: StartNodeProps) {
  const { setNodes, getEdges } = useReactFlow();
  const [isHovered, setIsHovered] = useState(false);
  const [localExecuting, setLocalExecuting] = useState(false);

  const handleDeleteNode = (e: React.MouseEvent) => {
    e.stopPropagation();
    setNodes((nodes) => nodes.filter((node) => node.id !== id));
  };

  const handleDoubleClick = async () => {
    if (onExecute && !localExecuting && !isExecuting) {
      setLocalExecuting(true);
      try {
        await onExecute(id);
      } finally {
        setLocalExecuting(false);
      }
    }
  };

  const edges = getEdges ? getEdges() : [];
  const isHandleConnected = edges.some(
    (edge) => edge.source === id && edge.sourceHandle === "output"
  );

  const getStatusColor = () => {
    if (isActive) {
      return "from-green-400 to-emerald-500";
    }
    if (localExecuting || isExecuting) {
      return "from-yellow-500 to-orange-600";
    }
    switch (validationStatus || data?.validationStatus) {
      case "success":
        return "from-emerald-500 to-green-600";
      case "error":
        return "from-red-500 to-rose-600";
      default:
        return "from-green-500 to-emerald-600";
    }
  };

  const getGlowColor = () => {
    return "";
  };

  const executionStatusStyle = getExecutionStatusStyle(data?.executionStatus);

  return (
    <>
      {/* Ana node kutusu */}
      <div
        className={`relative group w-24 h-24 rounded-2xl flex flex-col items-center justify-center 
          cursor-pointer transition-all duration-300 transform
          ${isHovered ? "scale-105" : "scale-100"}
          bg-gradient-to-br ${getStatusColor()}
          border border-white/20 backdrop-blur-sm
          hover:border-white/40`}
        style={executionStatusStyle}
        onDoubleClick={handleDoubleClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        title={
          localExecuting || isExecuting
            ? "Executing..."
            : "Double click to execute"
        }
      >
        {/* Pending status clockwise revolving amber worm light */}
        {data?.executionStatus === "pending" && (
          <PendingWormRing borderRadius="1rem" rx={16} />
        )}

        {/* Background pattern */}
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-transparent opacity-50"></div>

        {/* Main icon */}
        <div className="relative z-10 mb-2">
          {localExecuting || isExecuting ? (
            <Loader className="w-10 h-10 text-white animate-spin" />
          ) : (
            <Rocket className="w-10 h-10 text-white" />
          )}
        </div>

        {/* Node title */}
        <div className="text-white text-xs font-semibold text-center z-10">
          {localExecuting || isExecuting
            ? "Executing..."
            : data?.displayName || data?.name || "Start"}
        </div>

        {/* Hover effects */}
        {isHovered && !localExecuting && !isExecuting && (
          <>
            {/* Delete button */}
            <button
              className="absolute -top-3 -right-3 w-8 h-8 
                bg-gradient-to-r from-red-500 to-red-600 hover:from-red-400 hover:to-red-500
                text-white rounded-full border border-white/30 shadow-xl 
                transition-all duration-200 hover:scale-110 flex items-center justify-center z-20
                backdrop-blur-sm"
              onClick={handleDeleteNode}
              title="Delete Node"
            >
              <Trash size={14} />
            </button>
          </>
        )}
        
        {/* Output Handle */}
        <NeonHandle
          type="source"
          position={Position.Right}
          id="output"
          isConnectable={true}
          size={8}
          color1="#00FFFF"
          glow={isHandleConnected}
        />

        {/* Right side label for output (sadece hover'da görünür) */}
        <div
          className="absolute text-[9px] font-medium text-cyan-100 opacity-0 group-hover:opacity-100 
            transition-opacity pointer-events-none whitespace-nowrap bg-black/60 px-1 rounded 
            backdrop-blur-[1px] z-100 -right-12 top-1/2 transform -translate-y-1/2"
        >
          Execute
        </div>

        {/* Start Node Type Badge */}
        {data?.start_type && (
          <div className="absolute -bottom-6 left-1/2 transform -translate-x-1/2 z-10">
            <div className="px-2 py-1 rounded bg-green-600 text-white text-xs font-bold shadow-lg">
              {data.start_type === "manual"
                ? "Manual"
                : data.start_type === "trigger"
                ? "Trigger"
                : data.start_type === "scheduled"
                ? "Scheduled"
                : data.start_type?.toUpperCase() || "START"}
            </div>
          </div>
        )}

      </div>
    </>
  );
}

export default StartNode;
