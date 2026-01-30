import React, { useRef, useState } from "react";
import { useReactFlow, Handle, Position } from "@xyflow/react";
import NeonHandle from "../common/NeonHandle";
import {
  Play,
  Square,
  Trash,
  Activity,
  CheckCircle,
  StopCircle,
  Flag,
  Target,
  Zap,
  Clock,
  Power,
} from "../common/Icon";

interface EndNodeProps {
  data: any;
  id: string;
  onExecute?: (id: string) => void;
  validationStatus?: "success" | "error" | null;
}

function EndNode({ data, id, onExecute, validationStatus }: EndNodeProps) {
  const { setNodes } = useReactFlow();
  const [isHovered, setIsHovered] = useState(false);

  // Get onExecute from data if not provided as prop
  const executeHandler = onExecute || data?.onExecute;
  const validationState = validationStatus || data?.validationStatus;

  const handleDeleteNode = (e: React.MouseEvent) => {
    e.stopPropagation();
    setNodes((nodes) => nodes.filter((node) => node.id !== id));
  };

  const getStatusColor = () => {
    switch (validationState) {
      case "success":
        return "from-emerald-500 to-green-600";
      case "error":
        return "from-red-500 to-rose-600";
      default:
        return "from-gray-500 to-slate-600";
    }
  };

  const getGlowColor = () => {
    switch (validationState) {
      case "success":
        return "shadow-emerald-500/30";
      case "error":
        return "shadow-red-500/30";
      default:
        return "shadow-gray-500/30";
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
          hover:border-white/40`}
        onDoubleClick={() => executeHandler?.(id)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        title="Double click to execute"
      >
        {/* Background pattern */}
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-transparent opacity-50"></div>

        {/* Main icon */}
        <div className="relative z-10 mb-2">
          <div className="relative">
            <Flag className="w-10 h-10 text-white drop-shadow-lg" />
            {/* Activity indicator */}
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-r from-gray-400 to-slate-500 rounded-full flex items-center justify-center">
              <CheckCircle className="w-2 h-2 text-white" />
            </div>
          </div>
        </div>

        {/* Node title */}
        <div className="text-white text-xs font-semibold text-center drop-shadow-lg z-10">
          {data?.displayName || data?.name || "End"}
        </div>

        {/* Hover effects */}
        {isHovered && (
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



        {/* Input Handle */}
        <NeonHandle
          type="target"
          position={Position.Left}
          id="target"
          size={8}
          color1="#3b82f6"
          className="hover:scale-110 transition-transform duration-200"
        />

        {/* Left side label for input (sadece hover'da görünür) */}
        <div
          className="absolute text-[9px] font-medium text-cyan-100 opacity-0 group-hover:opacity-100 
            transition-opacity pointer-events-none whitespace-nowrap bg-black/60 px-1 rounded 
            backdrop-blur-[1px] z-100 -left-14 top-1/2 transform -translate-y-1/2"
        >
          Complete
        </div>

        {/* End Node Type Badge */}
        {data?.end_type && (
          <div className="absolute -bottom-6 left-1/2 transform -translate-x-1/2 z-10">
            <div className="px-2 py-1 rounded bg-gray-600 text-white text-xs font-bold shadow-lg">
              {data.end_type === "success"
                ? "Success"
                : data.end_type === "error"
                ? "Error"
                : data.end_type === "complete"
                ? "Complete"
                : data.end_type?.toUpperCase() || "END"}
            </div>
          </div>
        )}




        {/* Connection Status Indicator */}
        {data?.has_input && (
          <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 z-10">
            <div className="w-3 h-3 bg-gray-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Completion Status Indicator */}
        {data?.is_completed && (
          <div className="absolute top-1 left-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full flex items-center justify-center shadow-lg">
              <CheckCircle className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Execution Status Indicator */}
        {data?.is_executing && (
          <div className="absolute top-1 right-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full flex items-center justify-center shadow-lg">
              <Activity className="w-2 h-2 text-white" />
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

        {/* End Type Badge */}
        {data?.end_type && (
          <div className="absolute -right-2 top-1/2 transform -translate-y-1/2 z-10">
            <div className="px-2 py-1 rounded bg-slate-600 text-white text-xs font-bold shadow-lg transform rotate-90">
              {data.end_type === "success"
                ? "Success"
                : data.end_type === "error"
                ? "Error"
                : "End"}
            </div>
          </div>
        )}

        {/* Completion Count Indicator */}
        {data?.completion_count && (
          <div className="absolute -left-2 top-1/2 transform -translate-y-1/2 z-10">
            <div className="px-2 py-1 rounded bg-gray-600 text-white text-xs font-bold shadow-lg transform -rotate-90">
              {data.completion_count > 1000
                ? `${Math.round(data.completion_count / 1000)}K`
                : data.completion_count}
            </div>
          </div>
        )}

        {/* End Status Badge */}
        {data?.end_status && (
          <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 z-10">
            <div className="px-2 py-1 rounded bg-gradient-to-r from-gray-500 to-slate-600 text-white text-xs font-bold shadow-lg">
              {data.end_status === "ready"
                ? "Ready"
                : data.end_status === "executing"
                ? "Executing"
                : data.end_status === "completed"
                ? "Completed"
                : data.end_status === "error"
                ? "Error"
                : "Active"}
            </div>
          </div>
        )}

        {/* Last Completion Indicator */}
        {data?.last_completion && (
          <div className="absolute top-1 right-1 z-10">
            <div className="w-4 h-4 bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full flex items-center justify-center shadow-lg">
              <Clock className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Completion Speed Indicator */}
        {data?.completion_speed && (
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

        {/* Auto Complete Indicator */}
        {data?.auto_complete && (
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
              <Clock className="w-2 h-2 text-white" />
            </div>
          </div>
        )}

        {/* Success Rate Indicator */}
        {data?.success_rate && (
          <div className="absolute bottom-1 left-1 z-10">
            <div className="w-3 h-3 bg-green-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}

        {/* Error Rate Indicator */}
        {data?.error_rate && (
          <div className="absolute bottom-1 right-1 z-10">
            <div className="w-3 h-3 bg-red-400 rounded-full shadow-lg animate-pulse"></div>
          </div>
        )}
      </div>
    </>
  );
}

export default EndNode;
