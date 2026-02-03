import React from "react";
import { PlusIcon as Plus, MinusIcon as Minus } from "../../icons/index";

interface SidebarToggleButtonProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

export default function SidebarToggleButton({
  isSidebarOpen,
  setIsSidebarOpen,
}: SidebarToggleButtonProps) {
  return (
    <button
      className={`fixed top-20 left-2 z-30 rounded-full p-3 transition-all duration-300 backdrop-blur-md border-2 shadow-2xl ${
        isSidebarOpen
          ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white border-blue-400/50 shadow-blue-500/40 shadow-[0_8px_32px_rgba(59,130,246,0.4)]"
          : "bg-gray-800/95 text-white border-gray-600/60 hover:bg-gray-700/95 hover:border-gray-500/60 shadow-gray-900/40 shadow-[0_8px_32px_rgba(0,0,0,0.3)]"
      }`}
      onClick={() => setIsSidebarOpen(!isSidebarOpen)}
      title={isSidebarOpen ? "Close Sidebar" : "Open Sidebar"}
    >
              <div className="relative">
          {isSidebarOpen ? (
            <Minus
              className={`w-5 h-5 transition-transform duration-300 drop-shadow-lg ${
                isSidebarOpen ? "rotate-180" : ""
              }`}
            />
          ) : (
            <Plus
              className={`w-5 h-5 transition-transform duration-300 drop-shadow-lg ${
                !isSidebarOpen ? "rotate-0" : ""
              }`}
            />
          )}
          {isSidebarOpen && (
            <div className="absolute -top-1 -right-1 w-2 h-2 bg-green-400 rounded-full animate-pulse shadow-lg"></div>
          )}
        </div>
    </button>
  );
}
