import React, { useState, useEffect, useRef } from "react";
import { NodeResizer, useReactFlow } from "@xyflow/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Trash, Palette } from "lucide-react";

const COLORS = [
  { bg: "#fff5d6", border: "#f6c036", borderUnselected: "#eede8e" }, // Varsayılan renk
  { bg: "#F4E34A", border: "#D4C32A", borderUnselected: "#E4D33A" },
  { bg: "#4DA7D1", border: "#2D87B1", borderUnselected: "#3D97C1" },
  { bg: "#E98AA3", border: "#C96A83", borderUnselected: "#D97A93" },
  { bg: "#9B63A5", border: "#7B4385", borderUnselected: "#8B5395" },
  { bg: "#F39A2E", border: "#D37A0E", borderUnselected: "#E38A1E" },
  { bg: "#7BCF1A", border: "#5BAF0A", borderUnselected: "#6BBF0A" },
  { bg: "#E84AA3", border: "#C82A83", borderUnselected: "#D83A93" },
  { bg: "#8CC7D8", border: "#6CA7B8", borderUnselected: "#7CB7C8" },
];

interface StickyNoteNodeProps {
  id: string;
  data: any;
  selected?: boolean;
}

function StickyNoteNode({ id, data, selected }: StickyNoteNodeProps) {
  const FONT_SIZE = "10px";

  const { setNodes } = useReactFlow();
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [text, setText] = useState(data.text || "# Sticky Note\n\nDouble click to edit.");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const colorIndex = data.colorIndex || 0;
  const currentColor = COLORS[colorIndex] || COLORS[0];

  // Focus textarea when editing starts
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isEditing]);

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(true);
  };

  const handleDeleteNode = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setNodes((nodes) => nodes.filter((n) => n.id !== id));
  };

  const handleColorChange = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const nextIndex = (colorIndex + 1) % COLORS.length;
    setNodes((nodes) =>
      nodes.map((n) => {
        if (n.id === id) {
          return {
            ...n,
            selected: true, // Mantains visibility of CSS button
            data: {
              ...n.data,
              colorIndex: nextIndex,
            },
          };
        }
        return { ...n, selected: false };
      })
    );
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
  };

  const handleBlur = () => {
    setIsEditing(false);
    // Auto-save the text to the node's data so it persists
    setNodes((nodes) =>
      nodes.map((n) => {
        if (n.id === id) {
          return {
            ...n,
            data: {
              ...n.data,
              text: text,
            },
          };
        }
        return n;
      })
    );
  };

  return (
    <>
      <NodeResizer
        color={currentColor.border}
        isVisible={selected}
        minWidth={100}
        minHeight={100}
        keepAspectRatio={false}
      />
      {/* Wrapper div to hold the absolute delete button outside the hidden overflow */}
      <div
        className="relative w-full h-full group"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className={`absolute -top-3 left-0 w-full z-20 flex justify-between px-3 transition-opacity duration-200 pointer-events-none ${(!isEditing && (isHovered || selected)) ? 'opacity-100' : 'opacity-0'}`}>
          <button
            className="nodrag w-8 h-8 pointer-events-auto
              bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500
              text-white rounded-full border border-white/30 shadow-xl 
              transition-all duration-200 hover:scale-110 flex items-center justify-center
              backdrop-blur-sm -translate-x-6"
            onMouseDown={handleColorChange}
            title="Change Color"
          >
            <Palette size={14} />
          </button>
          <button
            className="nodrag w-8 h-8 pointer-events-auto
            bg-gradient-to-r from-red-500 to-red-600 hover:from-red-400 hover:to-red-500
            text-white rounded-full border border-white/30 shadow-xl 
            transition-all duration-200 hover:scale-110 flex items-center justify-center
            backdrop-blur-sm translate-x-6"
            onMouseDown={handleDeleteNode}
            title="Delete Note"
          >
            <Trash size={14} />
          </button>
        </div>

        <div
          className="w-full h-full p-4 rounded-sm shadow-md overflow-hidden flex flex-col transition-colors duration-300"
          style={{
            backgroundColor: currentColor.bg,
            border: selected ? `2px solid ${currentColor.border}` : `1px solid ${currentColor.borderUnselected}`,
          }}
          onDoubleClick={handleDoubleClick}
        >
          {/* Main content area - overflow-hidden to hide scroll in view mode */}
          <div className="flex-1 w-full h-full overflow-hidden">
            {isEditing ? (
              <textarea
                ref={textareaRef}
                value={text}
                onChange={handleChange}
                onBlur={handleBlur}
                /* Textarea has its own scrollbar, avoiding double scrollbars */
                className="w-full h-full resize-none bg-transparent border-none focus:outline-none focus:ring-0 text-gray-800 leading-relaxed overflow-y-auto custom-scrollbar"
                style={{ fontSize: FONT_SIZE }}
                placeholder="Type your markdown here..."
              />
            ) : (
              /* 
                Markdown için prose kullanıldı. Boyut `FONT_SIZE` değişkeninden alınır.
                Etkileşimi kapatmak ve scroll'u gizlemek için overflow-hidden kullanıldı.
              */
              <div
                className="prose prose-yellow max-w-none text-gray-800 break-words leading-relaxed select-none overflow-hidden"
                style={{ fontSize: FONT_SIZE }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {text}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default StickyNoteNode;
