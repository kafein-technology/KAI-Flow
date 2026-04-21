import React, { useEffect, useRef } from "react";
import { Copy } from "lucide-react";

interface NodeContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  onDuplicate: (nodeId: string) => void;
  onClose: () => void;
}

const NodeContextMenu: React.FC<NodeContextMenuProps> = ({
  x,
  y,
  nodeId,
  onDuplicate,
  onClose,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  // Dışarıya tıklandığında menüyü kapat
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      style={{
        top: y,
        left: x,
      }}
      className="fixed z-[1000] min-w-[150px] bg-black/80 backdrop-blur-md border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
    >
      <div className="py-1">
        <button
          onClick={() => {
            onDuplicate(nodeId);
            onClose();
          }}
          className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-cyan-50 hover:bg-white/10 transition-colors bg-transparent border-none cursor-pointer text-left focus:outline-none"
        >
          <Copy size={16} className="text-cyan-400" />
          <span className="font-medium">Clone Node</span>
        </button>
      </div>
    </div>
  );
};

export default NodeContextMenu;
