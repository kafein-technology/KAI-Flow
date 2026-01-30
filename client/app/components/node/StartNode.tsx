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
} from "../common/Icon";

import NeonHandle from "../common/NeonHandle";

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
    if (isActive) {
      return "shadow-green-400/70";
    }
    if (localExecuting || isExecuting) {
      return "shadow-yellow-500/50";
    }
    switch (validationStatus || data?.validationStatus) {
      case "success":
        return "shadow-emerald-500/30";
      case "error":
        return "shadow-red-500/30";
      default:
        return "shadow-green-500/30";
    }
  };

  return (
    <>
      {/* Ana node kutusu */}
      <div
        className={`relative group w-24 h-24 rounded-2xl flex flex-col items-center justify-center 
          cursor-pointer transition-all duration-300 transform
          ${isHovered ? "scale-105" : "scale-100"}
          bg-gradient-to-br ${getStatusColor()}
          ${
            isHovered
              ? `shadow-2xl ${getGlowColor()}`
              : "shadow-lg shadow-black/50"
          }
          border border-white/20 backdrop-blur-sm
          hover:border-white/40
          ${localExecuting || isExecuting ? "animate-pulse" : ""}
          ${isActive ? "animate-pulse ring-4 ring-green-400/50" : ""}`}
        onDoubleClick={handleDoubleClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        title={
          localExecuting || isExecuting
            ? "Executing..."
            : "Double click to execute"
        }
      >
        {/* Background pattern */}
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-transparent opacity-50"></div>

        {/* Main icon */}
        <div className="relative z-10 mb-2">
          <div className="relative">
            {localExecuting || isExecuting ? (
              <Loader className="w-10 h-10 text-white drop-shadow-lg animate-spin" />
            ) : (
              <Rocket className="w-10 h-10 text-white drop-shadow-lg" />
            )}
            {/* Activity indicator */}
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full flex items-center justify-center">
              <Play className="w-2 h-2 text-white" />
            </div>
          </div>
        </div>

        {/* Node title */}
        <div className="text-white text-xs font-semibold text-center drop-shadow-lg z-10">
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

        {/* Connection Status Indicator */}
        {isHandleConnected && (
          <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 z-10">
            <div className="w-3 h-3 bg-green-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Execution Status Indicator */}
        {(localExecuting || isExecuting) && (
          <div className="absolute top-1 left-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full flex items-center justify-center shadow-lg animate-pulse">
              <Activity className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Ready Status Indicator */}
        {data?.is_ready && (
          <div className="absolute top-1 right-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full flex items-center justify-center shadow-lg">
              <Power className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Execution Time Indicator */}
        {data?.execution_time && (
          <div className="absolute bottom-1 left-1 z-10">
            <div className="w-3 h-3 bg-blue-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Performance Indicator */}
        {data?.performance_metrics && (
          <div className="absolute bottom-1 right-1 z-10">
            <div className="w-3 h-3 bg-green-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Start Type Badge */}
        {data?.start_type && (
          <div className="absolute -right-2 top-1/2 transform -translate-y-1/2 z-10">
            <div className="px-2 py-1 rounded bg-emerald-600 text-white text-xs font-bold shadow-lg transform rotate-90">
              {data.start_type === "manual"
                ? "Manual"
                : data.start_type === "trigger"
                ? "Trigger"
                : "Start"}
            </div>
          </div>
        )}

        {/* Execution Count Indicator */}
        {data?.execution_count && (
          <div className="absolute -left-2 top-1/2 transform -translate-y-1/2 z-10">
            <div className="px-2 py-1 rounded bg-green-600 text-white text-xs font-bold shadow-lg transform -rotate-90">
              {data.execution_count > 1000
                ? `${Math.round(data.execution_count / 1000)}K`
                : data.execution_count}
            </div>
          </div>
        )}

        {/* Start Status Badge */}
        {data?.start_status && (
          <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 z-10">
            <div className="px-2 py-1 rounded bg-gradient-to-r from-green-500 to-emerald-600 text-white text-xs font-bold shadow-lg">
              {data.start_status === "ready"
                ? "Ready"
                : data.start_status === "executing"
                ? "Executing"
                : data.start_status === "completed"
                ? "Completed"
                : data.start_status === "error"
                ? "Error"
                : "Active"}
            </div>
          </div>
        )}

        {/* Last Execution Indicator */}
        {data?.last_execution && (
          <div className="absolute top-1 right-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full flex items-center justify-center shadow-lg">
              <Clock className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Execution Speed Indicator */}
        {data?.execution_speed && (
          <div className="absolute bottom-1 left-1 z-10">
            <div className="w-3 h-3 bg-purple-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Workflow Status Indicator */}
        {data?.workflow_status && (
          <div className="absolute bottom-1 right-1 z-10">
            <div className="w-3 h-3 bg-orange-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Auto Start Indicator */}
        {data?.auto_start && (
          <div className="absolute top-1 left-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-purple-400 to-pink-500 rounded-full flex items-center justify-center shadow-lg">
              <Zap className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Timer Indicator */}
        {data?.has_timer && (
          <div className="absolute top-1 right-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full flex items-center justify-center shadow-lg">
              <Timer className="w-2 h-2 text-white" />
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default StartNode;
