import React, { useRef, useState } from "react";
import { useReactFlow, Handle, Position } from "@xyflow/react";
import NeonHandle from "../common/NeonHandle";
import { getExecutionStatusStyle, PendingWormRing } from "~/lib/nodeStatusUtils";
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
} from "lucide-react";

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
        onDoubleClick={() => executeHandler?.(id)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        title="Double click to execute"
      >
        {/* Pending status clockwise revolving amber worm light */}
        {data?.executionStatus === "pending" && (
          <PendingWormRing borderRadius="1rem" rx={16} />
        )}

        {/* Background pattern */}
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-transparent opacity-50"></div>

        {/* Main icon */}
        <div className="relative z-10 mb-2">
          <Flag className="w-10 h-10 text-white" />
        </div>

        {/* Node title */}
        <div className="text-white text-xs font-semibold text-center z-10">
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




      </div>
    </>
  );
}

export default EndNode;
